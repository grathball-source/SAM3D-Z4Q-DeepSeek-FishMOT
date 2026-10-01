"""All segment seals first; independent official same-source mask scoring."""
from common import *
from collections import Counter
import ast,math
import numpy as np,cv2
from pycocotools import mask as coco
from scipy.optimize import linear_sum_assignment
for alias,builtin in (('int',int),('float',float),('bool',bool)):
    if alias not in np.__dict__:setattr(np,alias,builtin)
import trackeval
cv2.setNumThreads(1)
GT_DEV=WORK/'Depth-Anchored Association/sam3_training_free_association/v03/results/error_audit/gt_grid_and_native_alignment.jsonl.gz'
GT_DEV_SHA='ab6bc733911cc07dc4be70ef3a893c1475aca6908fc376923597eed5d1'
CAMERA_REFS={'L3':'labels_recovered_after2888_20260919_200202','LW':'labels_recovered_after1459_20260919_201837'}
FIELDS=('IDF1','HOTA','AssA','DetA','IDSW','FP','FN')

def rle(x):return dict(size=x['size'],counts=x['counts'].encode('ascii') if isinstance(x['counts'],str) else x['counts'])
def data_for(gt,pred,sims):
    gm={n:i for i,n in enumerate(sorted({x for ids in gt for x in ids}))}
    pm={n:i for i,n in enumerate(sorted({x for ids in pred for x in ids}))}
    return dict(num_timesteps=len(gt),num_gt_ids=len(gm),num_tracker_ids=len(pm),
        num_gt_dets=sum(map(len,gt)),num_tracker_dets=sum(map(len,pred)),
        gt_ids=[np.asarray([gm[n] for n in ids],int) for ids in gt],
        tracker_ids=[np.asarray([pm[n] for n in ids],int) for ids in pred],similarity_scores=sims)
def metrics(gt,pred,sims):
    d=data_for(gt,pred,sims)
    c=trackeval.metrics.CLEAR({'THRESHOLD':.5,'PRINT_CONFIG':False}).eval_sequence(d)
    i=trackeval.metrics.Identity({'THRESHOLD':.5,'PRINT_CONFIG':False}).eval_sequence(d)
    h=trackeval.metrics.HOTA({'PRINT_CONFIG':False}).eval_sequence(d)
    return dict(IDF1=100*float(i['IDF1']),HOTA=100*float(np.mean(h['HOTA'])),AssA=100*float(np.mean(h['AssA'])),
        DetA=100*float(np.mean(h['DetA'])),IDSW=int(c['IDSW']),FP=int(c['CLR_FP']),FN=int(c['CLR_FN']),
        GT=d['num_gt_dets'],predictions=d['num_tracker_dets']),dict(CLEAR=c,Identity=i,HOTA=h)
def delta(m):return {k:m['R12_RAW'][k]-m['SAM3_NATIVE'][k] for k in FIELDS}

def verify_all():
    manifest=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert manifest['status']=='ALL_TWO_BRANCHES_EIGHT_SEGMENTS_SEALED' and manifest['frames']==20098
    assert set(manifest['seals'])==set(SEGMENTS) and tuple(manifest['arms'])==ARMS
    checked={}
    def verify_once(item):
        if item['path'] not in checked:verify_item(item);checked[item['path']]=item
        else:assert checked[item['path']]==item
    for name,(start,stop) in SEGMENTS.items():
        p=RUN/name/'public'
        verify_once(manifest['seals'][name]);verify_once(manifest['access_seals'][name])
        seal=read(p/'PREDICTIONS_SEALED.json')
        assert seal['frames']==seal['published_frames']==stop-start+1 and tuple(seal['arms'])==ARMS
        assert seal['original_frames']==[start,stop]
        for filename,h in seal['artifacts_sha256'].items():assert sha(p/filename)==h,filename
        frozen=read(p/'FREEZE.json');verify_once(frozen['source_manifest'])
        assert frozen['no_gt_before_seal'] and frozen['new_model_http']==frozen['model_cost_usd']==0
        for path,h in frozen['code_sha256'].items():assert sha(path)==h,path
        chain=frozen['source_chain']
        for item in chain['derived_inputs'].values():verify_once(item)
        for k in ('scan','raw_sources','field_access'):verify_once(chain[k])
        access=read(p/'ACCESS.json');assert access['status']=='NO_GT_RGB_RESTORED_NETWORK'
        assert access['new_model_http']==access['cost_usd']==0
        allowed={'frame_id','aligned/raw_depth_mm','aligned/raw_source_index','native/original_depth_mm','depth_mm','source_index'}
        assert all(set(x['fields'])<=allowed for x in access['h5_or_array_field_reads'])
        assert all(x['key'] in ('depth_mm','source_index') for x in access['npz_field_reads'])
    return manifest

def polygon_reference(shapes,height,width,transform=False):
    masks={}
    for s in shapes:
        assert s['shape_type']=='polygon' and type(s['group_id']) is int
        n=s['group_id'];region=masks.setdefault(n,np.zeros((height,width),'u1'))
        points=np.asarray(s['points'],float);assert np.isfinite(points).all()
        cv2.fillPoly(region,[np.rint(points).astype('i4')],1)
    ids=sorted(masks)
    if transform:
        masks={n:cv2.resize(m,(640,360),interpolation=cv2.INTER_NEAREST) for n,m in masks.items()}
    return ids,[coco.encode(np.asfortranarray(masks[n])) for n in ids]

def reference_rows(name):
    start,stop=SEGMENTS[name]
    if name=='fishsa_development_8400':
        assert sha(GT_DEV)==GT_DEV_SHA
        for row in rows(GT_DEV):yield row['global_frame_id'],[x['id'] for x in row['gt_grid']],[rle(x['rle']) for x in row['gt_grid']]
    elif name=='fishsa_validation_2888':
        base=WORK/'data/AlignedDataset_v1';metadata={r['source_color_index']+1:r for r in rows(base/'manifest.jsonl')}
        for g in range(start,stop+1):
            row=metadata[g];path=base/row['label_original']
            assert sha(path)==row['annotation_sha256'],path
            label=read(path);assert (label['imageHeight'],label['imageWidth'])==(1080,1920)
            ids,encoded=polygon_reference(label['shapes'],1080,1920,transform=True)
            yield g,ids,encoded
    else:
        base=DATA if name.startswith('feeding_') else WORK/'data/AnnotationNewBags_20260919'/name
        folder='labels_640x360' if name.startswith('feeding_') else CAMERA_REFS[name]
        size=(360,640) if name.startswith('feeding_') else (1080,1920)
        for g in range(start,stop+1):
            ids,encoded=polygon_reference(read(base/folder/f'{g:06d}.json')['shapes'],*size)
            yield g,ids,encoded

def unique_matches(ids,sources,matrix):
    out={}
    for j,n in enumerate(sources):
        ranked=sorted(((float(matrix[i,j]),gid) for i,gid in enumerate(ids)),reverse=True)
        best=ranked[0] if ranked else (0.,None);second=ranked[1][0] if len(ranked)>1 else 0.
        out[n]=(dict(status='UNIQUE_IOU_MATCH',gt_id=best[1],iou=best[0],second_iou=second)
            if best[0]>=.5 and best[0]-second>=.1 else dict(status='UNSCORABLE_LOW_OR_AMBIGUOUS_IOU',best_iou=best[0],second_iou=second))
    counts=Counter(x['gt_id'] for x in out.values() if x['status']=='UNIQUE_IOU_MATCH')
    for x in out.values():
        if x['status']=='UNIQUE_IOU_MATCH' and counts[x['gt_id']]>1:x['status']='UNSCORABLE_SHARED_GT_MATCH'
    return out

tree=ast.parse((DS1/'postseal.py').read_text(encoding='utf-8'))
tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='clear_step']
scope=dict(np=np,linear_sum_assignment=linear_sum_assignment);exec(compile(tree,str(DS1/'postseal.py'),'exec'),scope)
clear_step=scope['clear_step']

def same(a,b):
    if a.get('status')!='UNIQUE_IOU_MATCH' or b.get('status')!='UNIQUE_IOU_MATCH':return 'UNKNOWN'
    return 'SAME' if a['gt_id']==b['gt_id'] else 'DIFFERENT'

def event_audit(name,matches,predictions):
    public=RUN/name/'public';events=read(public/'EVENTS.json')['R12_RAW']
    out=[];births=[];first_seen={}
    def match(frame,n):return matches.get(frame,{}).get(int(n),dict(status='SOURCE_OR_REFERENCE_MISSING'))
    for frame,p in predictions.items():
        for x in p['variants']['SAM3_NATIVE']:first_seen.setdefault(int(x['mask'][2:]),frame)
    for event in events:
        q=event['q'];r=event['restore'];detail=dict(segment=name,event=event['id'],suspect=event['suspect_frame'],confirm=event['confirm_frame'],q=q,status=event['status'])
        if q is None:out.append(dict(detail,physical='NO_SPLIT'));continue
        assert event['evidence_cutoff_frame']==q and event['numeric']['detail']['evidence_max_frame']==q
        assert all(p['frame']==q for p in event['post_first_observations'].values())
        anchors={int(k):match(a['frame'],a['native_id']) if a else dict(status='MISSING_ANCHOR') for k,a in event['reference_anchors'].items()}
        posts={int(n):match(q,n) for n in event['post_first_observations']}
        target={x['gt_id']:k for k,x in anchors.items() if x['status']=='UNIQUE_IOU_MATCH'}
        expected=({n:target[x['gt_id']] for n,x in posts.items()} if len(target)==2 and len(anchors)==len(posts)==2
            and all(x['status']=='UNIQUE_IOU_MATCH' and x['gt_id'] in target for x in posts.values()) and len({x['gt_id'] for x in posts.values()})==2 else {})
        actual={int(x['mask'][2:]):x['id'] for x in predictions[q]['variants']['R12_RAW'] if int(x['mask'][2:]) in posts}
        selected={int(n):k for n,k in (r['mapping'] or {}).items()}
        committed=r['status']=='COMMIT'
        physical='NOT_COMMITTED' if not committed else 'UNSCORABLE' if not expected else 'CORRECT' if actual==expected else 'WRONG'
        out.append(dict(detail,physical=physical,choice=r['selected_choice'],restore_status=r['status'],expected_mapping=expected,
            actual_first_public_mapping=actual,selected_mapping=selected,anchors=anchors,posts=posts,changes=r['changes'],
            first_public_physical='UNSCORABLE' if not expected else 'CORRECT' if actual==expected else 'WRONG'))
    for row in rows(public/'BIRTHS.jsonl.gz'):
        for query in row['queries']:
            if query['status']!='COMMIT':continue
            q=row['frame'];clean=query['selected_reference_anchor'];bank=query['selected_anchor'];candidate=query['selected_candidate']
            current=match(q,query['source']);past=match(clean['frame'],clean['native_id']);actualbank=match(bank['frame'],bank['native_id'])
            origin=match(first_seen.get(candidate['source']),candidate['source'])
            relations=dict(query_vs_clean=same(current,past),bank_vs_clean=same(actualbank,past),origin_vs_clean=same(origin,past))
            physical='WRONG' if 'DIFFERENT' in relations.values() else 'UNSCORABLE' if 'UNKNOWN' in relations.values() else 'CORRECT'
            births.append(dict(segment=name,frame=q,global_frame=row['global_frame'],source=query['source'],target=query['selected_target'],
                actual_first_public_id=query['actual_first_public_id'],physical=physical,relations=relations,
                query_match=current,clean_match=past,bank_match=actualbank,origin_match=origin,
                selection=query['selection'],surface_identity='UNKNOWN',physical_depth_accuracy='UNKNOWN'))
    result=dict(segment=name,group_events=out,birth_commits=births,
        group_physical_counts=dict(Counter(e['physical'] for e in out)),birth_physical_counts=dict(Counter(e['physical'] for e in births)))
    write_new(public/'EVENT_AUDIT.json',result)
    return result

def score_segment(name):
    start,stop=SEGMENTS[name];public=RUN/name/'public';gt=[];pred={a:[] for a in ARMS};sims=[];matches={};prediction_rows={}
    prev={a:{} for a in ARMS};step={a:{} for a in ARMS};switches={a:[] for a in ARMS};changed=[]
    publication={r['frame']:r for r in rows(public/'PUBLISH_LEDGER.jsonl')}
    transactions=rows(public/'TRANSACTIONS.jsonl.gz')
    tx=next(transactions,None)
    for index,(a,p,t) in enumerate(zip(rows(input_dir(name)/'assignments.jsonl.gz'),rows(public/'predictions.jsonl.gz'),reference_rows(name),strict=True),1):
        g,ids,reference=t;assert p['frame']==a['frame']==index and p['global_frame']==g==start+index-1
        assert p['time']==a['time'] and set(p['variants'])==set(ARMS)
        assert p['variants']['SAM3_NATIVE']==a['variants']['N0']
        keys=[x['mask'] for x in a['variants']['N0']];natives=[int(k[2:]) for k in keys]
        encoded=[rle(a['masks'][k]) for k in keys]
        if name in ('L3','LW'):
            label=read(WORK/'data/AnnotationNewBags_20260919'/name/'labels_raw'/f'{g:06d}.json')
            native_ids,encoded=polygon_reference(label['shapes'],1080,1920);assert native_ids==natives
        matrix=np.asarray(coco.iou(reference,encoded,[0]*len(encoded)),float).reshape(len(ids),len(encoded)) if ids and encoded else np.zeros((len(ids),len(encoded)))
        gt.append(ids);sims.append(matrix);matches[index]=unique_matches(ids,natives,matrix);prediction_rows[index]=p
        line=json.dumps(p,separators=(',',':'),allow_nan=False)+'\n'
        assert hashlib.sha256(line.encode()).hexdigest()==publication[index]['prediction_row_sha256']
        for arm in ARMS:
            objects=p['variants'][arm];assert [x['mask'] for x in objects]==keys
            public_ids=[x['id'] for x in objects];assert len(public_ids)==len(set(public_ids))==len(encoded)
            pred[arm].append(public_ids)
            step[arm],new=clear_step(ids,keys,public_ids,matrix,prev[arm],step[arm],g)
            switches[arm].extend(dict(x,segment=name) for x in new)
        assert tx and tx['frame']==index and tx['arm']=='R12_RAW'
        assert {int(n):v for n,v in tx['actual_published_mapping'].items()}==dict(zip(natives,pred['R12_RAW'][-1],strict=True))
        if publication[index]['event_publish']:
            pair=publication[index]['event_publish']['R12_RAW']
            assert pair['q']==index and pair['post_sample_count']==1
            assert all(dict(zip(natives,pred['R12_RAW'][-1]))[int(n)]==v for n,v in pair['first_public_pair'].items())
        tx=next(transactions,None)
        if p['variants']['R12_RAW']!=p['variants']['SAM3_NATIVE']:changed.append(g)
        if index%500==0:print(name,'SCORE',index,flush=True)
    assert tx is None and len(gt)==stop-start+1
    summary={};raw={}
    for arm in ARMS:
        summary[arm],raw[arm]=metrics(gt,pred[arm],sims)
        assert len(switches[arm])==summary[arm]['IDSW']
    assert summary['SAM3_NATIVE']['predictions']==summary['R12_RAW']['predictions']
    result=dict(segment=name,frames=len(gt),metrics=summary,delta=delta(summary),changed_frames=changed,
        reference_status='WEAK_UNREVIEWED_PREDICTION_DERIVED_PREANNOTATION' if name in ('L3','LW') else 'EXPOSED_EXISTING_ANNOTATION',
        score_protocol='Original full-raster/nearest resize FishSA; original scaled polygon Feeding; original1080 L3/LW; official mask CLEAR.5 Identity.5 HOTA19alphas')
    write_new(public/'METRICS.json',result)
    write_new(public/'SWITCHES.json',switches)
    with gzip.open(public/'REFERENCE_MATCHES.jsonl.gz','xt',encoding='utf-8') as h:
        for f,m in matches.items():h.write(json.dumps(dict(frame=f,matches=m),separators=(',',':'))+'\n')
    audit=event_audit(name,matches,prediction_rows)
    print(name,json.dumps(dict(metrics=summary,delta=result['delta'],changed=len(changed))),flush=True)
    return result,(gt,pred,sims),audit

def main():
    seal=verify_all();results={};pool_gt=[];pool_pred={a:[] for a in ARMS};pool_sims=[];audits={}
    for name in SEGMENTS:
        result,(gt,pred,sims),audit=score_segment(name);results[name]=result;audits[name]=audit
        if name.startswith('feeding_'):
            pool_gt.extend([[(name,x) for x in ids] for ids in gt]);pool_sims.extend(sims)
            for arm in ARMS:pool_pred[arm].extend([[(name,x) for x in ids] for ids in pred[arm]])
    pooled={a:metrics(pool_gt,pool_pred[a],pool_sims)[0] for a in ARMS}
    final=dict(status='SCORED_AFTER_ALL_EIGHT_PREDICTION_AND_ACCESS_SEALS',frames=20098,segments=results,
        feeding_pooled=dict(frames=1471,metrics=pooled,delta=delta(pooled)),new_model_http=0,cost_usd=0,
        depth_necessary='NOT_IDENTIFIED_WITH_TWO_ARMS',physical_depth_accuracy='UNKNOWN',all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'))
    write_new(RUN/'METRICS.json',final)
    write_new(RUN/'SCORE_PROVENANCE.json',dict(scorer=artifact(__file__),source_and_runtime_verified=True,
        development_reference=artifact(GT_DEV),reference_opened_after_all_seals=True,
        trackeval_package=artifact(Path(trackeval.__file__)),masked_or_ignored_ids=0))
    print(json.dumps(dict(feeding=final['feeding_pooled'],segments={n:r['delta'] for n,r in results.items()})),flush=True)

if __name__=='__main__':main()
