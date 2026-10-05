"""Official same-source metrics and actual-reference judgments only after all seals."""
from common import *
from collections import Counter
import time
ref=module('ds31_official_readonly',ROOT/'experiments/ds20_pending_confirmation_isolation/score.py')
metrics,rle,polygon_reference,unique_matches,clear_step,same=ref.metrics,ref.rle,ref.polygon_reference,ref.unique_matches,ref.clear_step,ref.same
np,coco,FIELDS=ref.np,ref.coco,ref.FIELDS
def verify_all():
    m=read(RUN/'ALL_PREDICTIONS_SEALED.json');assert m['frames']==20098 and tuple(m['arms'])==ARMS
    for name in SEGMENTS:
        verify_item(m['seals'][name]);verify_item(m['access_seals'][name]);verify_seal(name)
        assert read(RUN/name/'public/ACCESS.json')['status']=='NO_GT_RGB_RESTORED_NETWORK'
    return m

def score_segment(name):
    p=RUN/name/'public';start,stop=SEGMENTS[name];pin=ref.authoritative_development_pin()
    gt=[];sims=[];pred={a:[] for a in ARMS};previous={a:{} for a in ARMS};step={a:{} for a in ARMS};switches={a:[] for a in ARMS}
    matches={};actions=[];changed={a:[] for a in ARMS[2:]};depth_changed=[];events=read(p/'EVENTS.json');tx=iter(rows(p/'TRANSACTIONS.jsonl.gz'))
    for f,(pr,assignment,refs,ledger,extracts) in enumerate(zip(rows(p/'predictions.jsonl.gz'),rows(input_dir(name)/'assignments.jsonl.gz'),ref.reference_rows(name,pin),
        rows(p/'PUBLISH_LEDGER.jsonl'),rows(p/'DEPTH_EXTRACTS.jsonl.gz'),strict=True),1):
        g,ids,encoded_gt=refs;assert pr['frame']==f and pr['global_frame']==g==start+f-1
        assert row_sha(pr)==ledger['prediction_row_sha256'] and row_sha(extracts)==ledger['depth_extract_row_sha256']
        keys=[x['mask'] for x in assignment['variants']['N0']];sources=[int(k[2:]) for k in keys];encoded=[rle(assignment['masks'][k]) for k in keys]
        if name in ('L3','LW'):
            label=read(WORK/'data/AnnotationNewBags_20260919'/name/'labels_raw'/f'{g:06d}.json')
            native_ids,encoded=polygon_reference(label['shapes'],1080,1920);assert native_ids==sources
        sim=np.asarray(coco.iou(encoded_gt,encoded,[0]*len(encoded)),float).reshape(len(ids),len(encoded)) if ids and encoded else np.zeros((len(ids),len(encoded)))
        gt.append(ids);sims.append(sim);matches[f]=unique_matches(ids,sources,sim)
        for arm in ARMS:
            objects=pr['variants'][arm];assert [x['mask'] for x in objects]==keys
            public=[x['id'] for x in objects];assert len(set(public))==len(sources)
            pred[arm].append(public);step[arm],sw=clear_step(ids,keys,public,sim,previous[arm],step[arm],g);switches[arm].extend(dict(x,segment=name) for x in sw)
            if arm=='SAM3_NATIVE':assert objects==assignment['variants']['N0'];continue
            t=next(tx);assert (t['arm'],t['frame'],t['version'])==(arm,f,f) and t['decided_before_first_publish']
            assert row_sha(t)==ledger['transaction_row_sha256'][arm] and {int(n):k for n,k in t['mapping'].items()}==dict(zip(sources,public))
            if arm in ARMS[2:]:
                trace=t['controller_trace'];assert trace['future_frames_used']==0 and trace['all_masks_retained']
                for a in trace['actions']:
                    anchor=a['reference'];assert anchor['frame']<f and t['mapping'][str(a['source'])]==a['target']
                    relation=same(matches[f].get(a['source'],{}),matches[anchor['frame']].get(anchor['native_id'],{}))
                    actions.append(dict(segment=name,arm=arm,frame=f,global_frame=g,source=a['source'],target=a['target'],previous_pid=a['previous_pid'],reference=anchor,
                        relation=relation,physical='CORRECT' if relation=='SAME' else 'WRONG' if relation=='DIFFERENT' else 'UNSCORABLE',
                        mapping_changed=a['previous_pid']!=a['target'],depth_used=bool(a['depth_row'].get('active')),
                        depth_changed_same_state_selection=bool(a['depth_row'].get('active')) and a['geometry_selected_target']!=a['target']))
        for arm in ARMS[2:]:
            if pr['variants'][arm]!=pr['variants']['Z4Q_FROZEN']:changed[arm].append(g)
        if pr['variants']['PID_DEPTH']!=pr['variants']['PID_MOTION']:depth_changed.append(g)
        if f%1000==0:print('SCORE',name,f,flush=True)
    assert next(tx,None) is None and f==stop-start+1
    summary={a:metrics(gt,pred[a],sims)[0] for a in ARMS}
    original=read(ROOT/'experiments/ds30_original_z4q_depth_increment/run/METRICS.json')['segments'][name]['metrics']
    for arm in ARMS[:2]:assert summary[arm]==original[arm],(name,arm)
    for arm in ARMS:assert len(switches[arm])==summary[arm]['IDSW']
    result=dict(segment=name,frames=f,metrics=summary,changed_frames_vs_z4q=changed,depth_vs_motion_changed_frames=depth_changed,
        deltas={arm:{base:{k:summary[arm][k]-summary[base][k] for k in FIELDS} for base in ARMS[:2]} for arm in ARMS[2:]},
        depth_minus_motion={k:summary['PID_DEPTH'][k]-summary['PID_MOTION'][k] for k in FIELDS},
        reference_status='WEAK_UNREVIEWED_PREDICTION_DERIVED_PREANNOTATION' if name in ('L3','LW') else 'EXPOSED_EXISTING_ANNOTATION')
    write_new(p/'METRICS.json',result);write_new(p/'SWITCHES.json',switches)
    write_new(p/'ACTION_AUDIT.json',dict(actions=actions,counts={a:dict(Counter(x['physical'] for x in actions if x['arm']==a)) for a in ARMS[2:]},
        boundary='Repeated associations to the same PID are listed; true PID changes are mapping_changed. Reference correctness is distinct from initial public-ID correctness.'))
    with gzip.open(p/'REFERENCE_MATCHES.jsonl.gz','xt',encoding='utf-8') as h:
        for f,m in matches.items():h.write(json.dumps(dict(frame=f,matches=m),separators=(',',':'))+'\n')
    changes={}
    for arm in ARMS[2:]:
        orig={digest(x):x for x in switches['Z4Q_FROZEN']};cur={digest(x):x for x in switches[arm]}
        changes[arm]=dict(added=[cur[k] for k in cur.keys()-orig.keys()],eliminated=[orig[k] for k in orig.keys()-cur.keys()],common=len(cur.keys()&orig.keys()))
    write_new(p/'SWITCH_CHANGES.json',changes)
    print(name,json.dumps(summary),flush=True);return result,(gt,pred,sims)

def main():
    seal=verify_all();results={};gt=[];sims=[];pred={a:[] for a in ARMS};began=time.perf_counter()
    for name in SEGMENTS:
        results[name],parts=score_segment(name)
        if name.startswith('feeding_'):
            g,p,s=parts;gt.extend([[(name,x) for x in ids] for ids in g]);sims.extend(s)
            for arm in ARMS:pred[arm].extend([[(name,x) for x in ids] for ids in p[arm]])
    pooled={a:metrics(gt,pred[a],sims)[0] for a in ARMS}
    write_new(RUN/'METRICS.json',dict(status='SCORED_AFTER_ALL_EIGHT_PREDICTION_AND_ACCESS_SEALS',frames=20098,segments=results,
        feeding_pooled=dict(frames=1471,metrics=pooled),all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),score_seconds=time.perf_counter()-began,new_model_http=0,cost_usd=0))
    write_new(RUN/'SCORE_PROVENANCE.json',dict(scorer=artifact(__file__),old_math=artifact(ref._math.__file__),
        development_reference=artifact(ref.GT_DEV),validation_reference=artifact(ref.ARCHIVE),prediction_seals_verified_before_reference_read=True,
        ignored_public_ids=0,L3_LW_weak_reference=True,new_model_http=0,cost_usd=0))
if __name__=='__main__':main()
