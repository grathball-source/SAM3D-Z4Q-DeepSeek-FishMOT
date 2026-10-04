"""Original same-source TrackEval and physical action audit after all eight seals."""
from common import *
from collections import Counter
import time
reference = module('ds25_old_independent_scoring',ROOT/'experiments/ds20_pending_confirmation_isolation/score.py')
metrics,rle,polygon_reference,unique_matches,clear_step,same=reference.metrics,reference.rle,reference.polygon_reference,reference.unique_matches,reference.clear_step,reference.same
np,coco,FIELDS=reference.np,reference.coco,reference.FIELDS

def verify_all():
    manifest=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert manifest['frames']==20098 and tuple(manifest['arms'])==ARMS
    for name in SEGMENTS:
        verify_item(manifest['seals'][name]);verify_item(manifest['access_seals'][name]);verify_seal(name)
        assert read(RUN/name/'public/ACCESS.json')['status']=='NO_GT_RGB_RESTORED_NETWORK'
    return manifest

def physical(name,matches,transactions):
    first={}
    for f,m in matches.items():
        for n in m:first.setdefault(n,f)
    def match(f,n):return matches.get(f,{}).get(n,dict(status='MISSING_ENDPOINT'))
    def verdict(relations):return 'WRONG' if 'DIFFERENT' in relations.values() else 'UNSCORABLE' if 'UNKNOWN' in relations.values() else 'CORRECT'
    actions=[];vetos=[]
    for tx in transactions:
        arm=tx['arm'];f=tx['frame']
        for item in tx['actual_actions']:
            a=item['action'];n,k=a['native_id'],a['canonical_id'];anchor=a.get('old_anchor')
            current=match(f,n);past=match(anchor['frame'],anchor['native_id']) if anchor else dict(status='MISSING_ANCHOR')
            origin=match(first.get(k),k)
            relations=dict(query_vs_bank=same(current,past),bank_vs_public_origin=same(past,origin),query_vs_public_origin=same(current,origin))
            committed=item['actual_published'] and item['durable_alias']
            actions.append(dict(arm=arm,frame=f,global_frame=tx['global_frame'],source=n,target=k,
                origin_rule='BIRTH_REFINE' if a.get('phase')=='birth' else 'D1_DELAYED',
                physical=verdict(relations) if committed else 'NOT_DURABLE',
                actual_reference_physical='CORRECT' if relations['query_vs_bank']=='SAME' else 'WRONG' if relations['query_vs_bank']=='DIFFERENT' else 'UNSCORABLE',
                preexisting_public_origin='MISMATCH' if relations['bank_vs_public_origin']=='DIFFERENT' else relations['bank_vs_public_origin'],
                relations=relations,anchor=anchor,actual_published=item['actual_published'],durable_alias=item['durable_alias']))
        if arm!='Z4Q_LOCAL_LAYERS':continue
        original=next(x for x in transactions if x['frame']==f and x['arm']=='Z4Q_FROZEN')
        for x in tx['controller_trace'].get('relative_order_checks',[]):
            if not x['veto']:continue
            n,k=x['native_id'],x['public_id'];anchor=x['anchor']
            relation=same(match(f,n),match(anchor['frame'],anchor['native_id']))
            targets=[a for a in original['actual_actions'] if a['actual_published'] and a['durable_alias'] and a['action']['native_id']==n and a['action']['canonical_id']==k]
            vetos.append(dict(frame=f,global_frame=tx['global_frame'],source=n,target=k,origin_rule=x['origin_rule'],
                physical_rejected_edge='CORRECT' if relation=='SAME' else 'WRONG' if relation=='DIFFERENT' else 'UNSCORABLE',
                original_actually_committed_this_edge=bool(targets),
                new_actual_published_id=tx['actual_published_mapping'][str(n)],evidence=x))
    return dict(actions=actions,actual_vetos=vetos,counts={a:dict(Counter(x['physical'] for x in actions if x['arm']==a)) for a in ARMS[1:]})

def score_segment(name):
    start,stop=SEGMENTS[name];public=RUN/name/'public';pin=reference.authoritative_development_pin()
    gt=[];sims=[];pred={a:[] for a in ARMS};matches={};changed=[]
    previous={a:{} for a in ARMS};step={a:{} for a in ARMS};switches={a:[] for a in ARMS}
    tx=iter(rows(public/'TRANSACTIONS.jsonl.gz'));transactions=[]
    for i,(p,assignment,refs,ledger,checks) in enumerate(zip(rows(public/'predictions.jsonl.gz'),
        rows(input_dir(name)/'assignments.jsonl.gz'),reference.reference_rows(name,pin),rows(public/'PUBLISH_LEDGER.jsonl'),
        rows(public/'ORDER_CHECKS.jsonl.gz'),strict=True),1):
        g,ids,encoded_gt=refs;assert p['frame']==i and p['global_frame']==g==start+i-1
        assert row_sha(p)==ledger['prediction_row_sha256'] and row_sha(checks)==ledger['checks_row_sha256']
        keys=[x['mask'] for x in assignment['variants']['N0']];sources=[int(k[2:]) for k in keys]
        encoded=[rle(assignment['masks'][k]) for k in keys]
        if name in ('L3','LW'):
            label=read(WORK/'data/AnnotationNewBags_20260919'/name/'labels_raw'/f'{g:06d}.json')
            native_ids,encoded=polygon_reference(label['shapes'],1080,1920);assert native_ids==sources
        matrix=(np.asarray(coco.iou(encoded_gt,encoded,[0]*len(encoded)),float).reshape(len(ids),len(encoded))
                if ids and encoded else np.zeros((len(ids),len(encoded))))
        gt.append(ids);sims.append(matrix);matches[i]=unique_matches(ids,sources,matrix)
        for arm in ARMS:
            objects=p['variants'][arm];assert [x['mask'] for x in objects]==keys
            public_ids=[x['id'] for x in objects];assert len(set(public_ids))==len(sources)
            pred[arm].append(public_ids)
            step[arm],sw=clear_step(ids,keys,public_ids,matrix,previous[arm],step[arm],g)
            switches[arm].extend(dict(x,segment=name) for x in sw)
            if arm=='SAM3_NATIVE':assert objects==assignment['variants']['N0'];continue
            transaction=next(tx);assert (transaction['frame'],transaction['arm'])==(i,arm)
            assert row_sha(transaction)==ledger['transaction_row_sha256'][arm]
            assert {int(n):k for n,k in transaction['actual_published_mapping'].items()}==dict(zip(sources,public_ids,strict=True))
            transactions.append(transaction)
        if p['variants']['Z4Q_LOCAL_LAYERS']!=p['variants']['Z4Q_FROZEN']:changed.append(g)
        if i%1000==0:print('SCORE',name,i,flush=True)
    assert next(tx,None) is None and len(gt)==stop-start+1
    summary={a:metrics(gt,pred[a],sims)[0] for a in ARMS}
    for arm in ARMS:assert len(switches[arm])==summary[arm]['IDSW']
    archived=read(ROOT/'experiments/ds20_pending_confirmation_isolation/run/METRICS.json')['segments'][name]['metrics']
    for arm in ARMS[:2]:assert summary[arm]==archived[arm],(name,arm,'Original score reproduction')
    result=dict(segment=name,frames=len(gt),metrics=summary,changed_frames=changed,
        deltas={base:{k:summary[ARMS[2]][k]-summary[base][k] for k in FIELDS} for base in ARMS[:2]},
        reference_status='WEAK_UNREVIEWED_PREDICTION_DERIVED_PREANNOTATION' if name in ('L3','LW') else 'EXPOSED_EXISTING_ANNOTATION')
    write_new(public/'METRICS.json',result);write_new(public/'SWITCHES.json',switches)
    audit=physical(name,matches,transactions);write_new(public/'ACTION_AUDIT.json',audit)
    with gzip.open(public/'REFERENCE_MATCHES.jsonl.gz','xt',encoding='utf-8') as h:
        for f,m in matches.items():h.write(json.dumps(dict(frame=f,matches=m),separators=(',',':'))+'\n')
    print(name,json.dumps(summary),flush=True)
    return result,(gt,pred,sims)

def main():
    seal=verify_all();results={};gt=[];sims=[];pred={a:[] for a in ARMS};began=time.perf_counter()
    for name in SEGMENTS:
        results[name],parts=score_segment(name)
        if name.startswith('feeding_'):
            g,p,s=parts;gt.extend([[(name,x) for x in ids] for ids in g]);sims.extend(s)
            for arm in ARMS:pred[arm].extend([[(name,x) for x in ids] for ids in p[arm]])
    pooled={a:metrics(gt,pred[a],sims)[0] for a in ARMS}
    write_new(RUN/'METRICS.json',dict(status='SCORED_AFTER_ALL_EIGHT_PREDICTION_AND_ACCESS_SEALS',frames=20098,
        segments=results,feeding_pooled=dict(frames=1471,metrics=pooled),all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),
        score_seconds=time.perf_counter()-began,new_model_http=0,cost_usd=0))
    write_new(RUN/'SCORE_PROVENANCE.json',dict(scorer=artifact(__file__),old_math=artifact(reference._math.__file__),
        development_reference=artifact(reference.GT_DEV),validation_reference=artifact(reference.ARCHIVE),
        prediction_seals_verified_before_reference_read=True,ignored_public_ids=0,new_model_http=0,cost_usd=0))

if __name__=='__main__':main()
