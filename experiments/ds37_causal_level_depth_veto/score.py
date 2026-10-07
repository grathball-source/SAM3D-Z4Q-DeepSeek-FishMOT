"""Exact official same-source scoring after all prediction/access seals."""
from common import *
from collections import Counter
import time

saved=sys.modules['common']
try:
    sys.modules['common']=old
    ref=module('ds37_frozen_ds20_official_score',old.HERE/'score.py')
finally:sys.modules['common']=saved
metrics,rle,polygon_reference,unique_matches,clear_step,same=(getattr(ref,k) for k in
    ('metrics','rle','polygon_reference','unique_matches','clear_step','same'))
np,coco,FIELDS=ref.np,ref.coco,ref.FIELDS

def verify_all():
    seal=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert seal['frames']==20098 and tuple(seal['arms'])==ARMS
    for name in SEGMENTS:
        verify_item(seal['seals'][name]);verify_item(seal['access_seals'][name]);verify_seal(name)
        assert read(RUN/name/'public/ACCESS.json')['status']=='NO_GT_RGB_RESTORED_NETWORK'
    for path,h in read(HERE/'RUNTIME_FREEZE.json')['code'].items():assert sha(path)==h,path
    return seal

def switch_delta(before,after):
    key=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'))
    a={key(v):v for v in before};b={key(v):v for v in after}
    return dict(added=[b[k] for k in sorted(b.keys()-a.keys())],
        eliminated=[a[k] for k in sorted(a.keys()-b.keys())],common=len(a.keys()&b.keys()))

def score_segment(name):
    p=RUN/name/'public';start,stop=SEGMENTS[name];pin=ref.authoritative_development_pin()
    gt=[];sims=[];pred={a:[] for a in ARMS};previous={a:{} for a in ARMS};step={a:{} for a in ARMS}
    switches={a:[] for a in ARMS};matches={};actions=[];vetoes=[]
    tx=iter(rows(p/'TRANSACTIONS.jsonl.gz'));ledger=iter(rows(p/'PUBLISH_LEDGER.jsonl'));extracts=iter(rows(p/'DEPTH_EXTRACTS.jsonl.gz'))
    for f,(pr,assignment,refs) in enumerate(zip(rows(p/'predictions.jsonl.gz'),
        rows(input_dir(name)/'assignments.jsonl.gz'),ref.reference_rows(name,pin),strict=True),1):
        g,ids,encoded_gt=refs;assert pr['frame']==f and pr['global_frame']==g==start+f-1
        l=next(ledger);d=next(extracts);assert l['prediction_row_sha256']==row_sha(pr) and l['depth_extract_row_sha256']==row_sha(d)
        keys=[x['mask'] for x in assignment['variants']['N0']];sources=[int(k[2:]) for k in keys]
        encoded=[rle(assignment['masks'][k]) for k in keys]
        if name in ('L3','LW'):
            label=read(WORK/'data/AnnotationNewBags_20260919'/name/'labels_raw'/f'{g:06d}.json')
            native_ids,encoded=polygon_reference(label['shapes'],1080,1920);assert native_ids==sources
        sim=np.asarray(coco.iou(encoded_gt,encoded,[0]*len(encoded)),float).reshape(len(ids),len(encoded)) if ids and encoded else np.zeros((len(ids),len(encoded)))
        gt.append(ids);sims.append(sim);matches[f]=unique_matches(ids,sources,sim)
        for arm in ARMS:
            objects=pr['variants'][arm];assert [o['mask'] for o in objects]==keys
            public=[o['id'] for o in objects];assert len(set(public))==len(sources);pred[arm].append(public)
            step[arm],sw=clear_step(ids,keys,public,sim,previous[arm],step[arm],g)
            switches[arm].extend(dict(s,segment=name) for s in sw)
            if arm=='SAM3_NATIVE':assert objects==assignment['variants']['N0'];continue
            t=next(tx);assert (t['arm'],t['frame'],t['version'])==(arm,f,f) and t['decided_before_first_publish']
            assert row_sha(t)==l['transaction_row_sha256'][arm]
            assert {int(n):k for n,k in t['mapping'].items()}==dict(zip(sources,public))
            for event in t['controller_trace'].get('events',[]):
                if event.get('kind')!='reconnect' or not event.get('accepted'):continue
                anchor=event['old_anchor'];assert anchor['frame']<f and t['mapping'][str(event['native_id'])]==event['canonical_id']
                relation=same(matches[f].get(event['native_id'],{}),matches[anchor['frame']].get(anchor['native_id'],{}))
                actions.append(dict(arm=arm,frame=f,global_frame=g,event=event,actual_reference=anchor,
                    relation=relation,physical='CORRECT' if relation=='SAME' else 'WRONG' if relation=='DIFFERENT' else 'UNSCORABLE'))
            if arm in VETO_ARMS:
                for check in t['controller_trace']['depth_checks']:
                    if not check.get('conflict'):continue
                    anchor=check['anchor'];assert anchor['frame']<f
                    relation=same(matches[f].get(check['native_id'],{}),matches[anchor['frame']].get(anchor['native_id'],{}))
                    vetoes.append(dict(arm=arm,frame=f,global_frame=g,phase=check['phase'],native_id=check['native_id'],canonical_id=check['canonical_id'],
                        actual_bank_reference=anchor,original_scoring_reference=check['terms'].get('old_anchor'),
                        original_eligible=check['original_eligible'],actual_matrix_deletion=check['veto'],
                        relation=relation,physical='DIFFERENT_CORRECT_CONFLICT' if relation=='DIFFERENT' else 'SAME_HARMFUL_CONFLICT' if relation=='SAME' else 'UNSCORABLE'))
        if f%1000==0:print('SCORE',name,f,flush=True)
    assert next(tx,None) is None and next(ledger,None) is None and next(extracts,None) is None and f==stop-start+1
    summary={a:metrics(gt,pred[a],sims)[0] for a in ARMS}
    archived=read(OLD32.RUN/'METRICS.json')['segments'][name]['metrics']
    for a in ARMS[:2]:assert summary[a]==archived[a]
    assert summary['Z4Q_WLS_VETO']==archived['Z4Q_DEPTH_VETO']
    for a in ARMS:assert len(switches[a])==summary[a]['IDSW']
    changes={a:switch_delta(switches['Z4Q_FROZEN'],switches[a]) for a in VETO_ARMS}
    result=dict(segment=name,frames=f,metrics=summary,
        deltas={base:{k:summary['Z4Q_LEVEL_VETO'][k]-summary[base][k] for k in FIELDS} for base in ARMS[:-1]},
        reference_status='WEAK_UNREVIEWED_PREDICTION_DERIVED_PREANNOTATION' if name in ('L3','LW') else 'EXPOSED_EXISTING_ANNOTATION')
    write_new(p/'METRICS.json',result);write_new(p/'SWITCHES.json',switches);write_new(p/'SWITCH_CHANGES.json',changes)
    write_new(p/'ACTION_AUDIT.json',dict(actions=actions,counts={a:dict(Counter(v['physical'] for v in actions if v['arm']==a)) for a in ARMS[1:]}))
    write_new(p/'VETO_AUDIT.json',dict(conflicts=vetoes,
        counts={a:dict(Counter(v['physical'] for v in vetoes if v['arm']==a)) for a in VETO_ARMS},
        active_deletions={a:dict(Counter(v['physical'] for v in vetoes if v['arm']==a and v['actual_matrix_deletion'])) for a in VETO_ARMS},
        scoring_reference='Actual exact bank anchor; original BirthRefine core reference separately recorded.'))
    write_new(p/'REFERENCE_MATCHES.json',{str(f):v for f,v in matches.items()})
    print(name,json.dumps(summary),flush=True);return result,(gt,pred,sims)

def main():
    verify_all();results={};gt=[];sims=[];pred={a:[] for a in ARMS};began=time.perf_counter()
    for name in SEGMENTS:
        results[name],parts=score_segment(name)
        if name.startswith('feeding_'):
            g,p,s=parts;gt.extend([[(name,x) for x in ids] for ids in g]);sims.extend(s)
            for a in ARMS:pred[a].extend([[(name,x) for x in ids] for ids in p[a]])
    write_new(RUN/'METRICS.json',dict(status='SCORED_AFTER_ALL_SEALS',frames=20098,segments=results,
        feeding_pooled=dict(frames=1471,metrics={a:metrics(gt,pred[a],sims)[0] for a in ARMS}),
        all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),score_seconds=time.perf_counter()-began,model_http=0,cost_usd=0))
    write_new(RUN/'SCORE_PROVENANCE.json',dict(scorer=artifact(__file__),adapter=artifact(ref.__file__),old_math=artifact(ref._math.__file__),
        dynamic_clear_math=artifact(DS1/'postseal.py'),development_reference=artifact(ref.GT_DEV),validation_reference=artifact(ref.ARCHIVE),
        prediction_seals_verified_before_reference_read=True,ignored_public_ids=0,L3_LW_weak_reference=True,model_http=0,cost_usd=0))

if __name__=='__main__':main()
