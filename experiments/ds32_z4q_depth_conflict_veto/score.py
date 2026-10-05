"""Official same-source score only after formal and counterfactual seals."""
from common import *
from collections import Counter
import time
# Load the archived scoring adapter against its own unchanged common/config.
# Restore our module even if an archived dependency fails during import.
_saved_common=sys.modules['common']
try:
    sys.modules['common']=old
    ref=module('ds32_official_math',ROOT/'experiments/ds20_pending_confirmation_isolation/score.py')
finally:
    sys.modules['common']=_saved_common
metrics,rle,polygon_reference,unique_matches,clear_step,same=ref.metrics,ref.rle,ref.polygon_reference,ref.unique_matches,ref.clear_step,ref.same
np,coco,FIELDS=ref.np,ref.coco,ref.FIELDS

def verify_all():
    seal=read(RUN/'ALL_PREDICTIONS_SEALED.json');assert seal['frames']==20098 and tuple(seal['arms'])==ARMS
    verify_item(seal['selection']);selection=read(seal['selection']['path'])
    for n in SEGMENTS:
        verify_item(seal['seals'][n]);verify_item(seal['access_seals'][n]);verify_seal(n)
        assert read(RUN/n/'public/ACCESS.json')['status']=='NO_GT_RGB_RESTORED_NETWORK'
    for mode,pins in seal['counterfactual'].items():
        verify_item(pins['seal']);verify_item(pins['access'])
        p=Path(pins['seal']['path']).parent
        for file,h in read(pins['seal']['path'])['artifacts_sha256'].items():assert sha(p/file)==h
        cf=read(p/'CF_FREEZE.json')
        verify_item(cf['formal_freeze']);verify_item(cf['selection']);verify_item(cf['formal_prediction_seal'])
        frozen=read(cf['formal_freeze']['path']);verify_frozen_inputs(frozen)
        for path,h in frozen['code'].items():assert sha(path)==h,path
        assert cf['selection']==seal['selection'] and cf['mode']==mode and cf['segment']==selection['segment']
        assert cf['allow_edge']==(selection['allow_edge'] if mode=='counter_allow' else None)
        assert read(p/'RUN_SUMMARY.json')['allow_edge']==cf['allow_edge']
        assert read(pins['access']['path'])['status']=='NO_GT_RGB_RESTORED_NETWORK'
    return seal

def score_segment(name,output=RUN):
    p=output/name/'public';start,stop=SEGMENTS[name];pin=ref.authoritative_development_pin()
    gt=[];sims=[];pred={a:[] for a in ARMS};previous={a:{} for a in ARMS};step={a:{} for a in ARMS};switches={a:[] for a in ARMS}
    matches={};actions=[];vetoes=[];tx=iter(rows(p/'TRANSACTIONS.jsonl.gz'));ledger=iter(rows(p/'PUBLISH_LEDGER.jsonl'))
    extracts=iter(rows(p/'DEPTH_EXTRACTS.jsonl.gz'))
    for f,(pr,assignment,refs) in enumerate(zip(rows(p/'predictions.jsonl.gz'),rows(input_dir(name)/'assignments.jsonl.gz'),ref.reference_rows(name,pin),strict=True),1):
        g,ids,encoded_gt=refs;assert pr['frame']==f and pr['global_frame']==g==start+f-1
        l=next(ledger);d=next(extracts);assert l['prediction_row_sha256']==row_sha(pr) and l['depth_extract_row_sha256']==row_sha(d)
        keys=[x['mask'] for x in assignment['variants']['N0']];sources=[int(k[2:]) for k in keys];encoded=[rle(assignment['masks'][k]) for k in keys]
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
            if arm=='Z4Q_DEPTH_VETO':
                for check in t['controller_trace']['depth_checks']:
                    if not check.get('conflict'):continue
                    anchor=check['anchor'];assert anchor['frame']<f
                    relation=same(matches[f].get(check['native_id'],{}),matches[anchor['frame']].get(anchor['native_id'],{}))
                    vetoes.append(dict(frame=f,global_frame=g,phase=check['phase'],native_id=check['native_id'],canonical_id=check['canonical_id'],
                        actual_bank_reference=anchor,original_scoring_reference=check['terms'].get('old_anchor'),
                        original_eligible=check['original_eligible'],actual_matrix_deletion=check['veto'],counterfactual_allowed=check['counterfactual_allowed'],
                        relation=relation,physical='DIFFERENT_CORRECT_CONFLICT' if relation=='DIFFERENT' else 'SAME_HARMFUL_CONFLICT' if relation=='SAME' else 'UNSCORABLE'))
        if f%1000==0:print('SCORE',name,f,flush=True)
    assert next(tx,None) is None and next(ledger,None) is None and next(extracts,None) is None and f==stop-start+1
    summary={a:metrics(gt,pred[a],sims)[0] for a in ARMS}
    original=read(ROOT/'experiments/ds31_persistent_identity_depth/run/METRICS.json')['segments'][name]['metrics']
    for a in ARMS[:2]:assert summary[a]==original[a]
    for a in ARMS:assert len(switches[a])==summary[a]['IDSW']
    changed={'added':[],'eliminated':[],'common':0}
    key=lambda s:json.dumps(s,sort_keys=True,separators=(',',':'))
    orig={key(s):s for s in switches['Z4Q_FROZEN']};cur={key(s):s for s in switches['Z4Q_DEPTH_VETO']}
    changed.update(added=[cur[k] for k in sorted(cur.keys()-orig.keys())],eliminated=[orig[k] for k in sorted(orig.keys()-cur.keys())],common=len(cur.keys()&orig.keys()))
    result=dict(segment=name,frames=f,metrics=summary,deltas={base:{k:summary['Z4Q_DEPTH_VETO'][k]-summary[base][k] for k in FIELDS} for base in ARMS[:2]},
        reference_status='WEAK_UNREVIEWED_PREDICTION_DERIVED_PREANNOTATION' if name in ('L3','LW') else 'EXPOSED_EXISTING_ANNOTATION')
    write_new(p/'METRICS.json',result);write_new(p/'SWITCHES.json',switches);write_new(p/'SWITCH_CHANGES.json',changed)
    write_new(p/'ACTION_AUDIT.json',dict(actions=actions,counts={a:dict(Counter(v['physical'] for v in actions if v['arm']==a)) for a in ARMS[1:]}))
    write_new(p/'VETO_AUDIT.json',dict(conflicts=vetoes,counts=dict(Counter(v['physical'] for v in vetoes)),
        active_deletions=dict(Counter(v['physical'] for v in vetoes if v['actual_matrix_deletion'])),
        scoring_reference='Actual extra-evidence bank anchor; original BirthRefine core reference separately recorded.'))
    write_new(p/'REFERENCE_MATCHES.json',{str(f):v for f,v in matches.items()})
    print(name,json.dumps(summary),flush=True);return result,(gt,pred,sims)

def main():
    seal=verify_all();results={};gt=[];sims=[];pred={a:[] for a in ARMS};began=time.perf_counter()
    for n in SEGMENTS:
        results[n],parts=score_segment(n)
        if n.startswith('feeding_'):
            g,p,s=parts;gt.extend([[(n,x) for x in ids] for ids in g]);sims.extend(s)
            for a in ARMS:pred[a].extend([[(n,x) for x in ids] for ids in p[a]])
    counter={}
    for mode,pins in seal['counterfactual'].items():
        n=read(HERE/'COUNTERFACTUAL_SELECTION.json')['segment'];counter[mode]=score_segment(n,HERE/mode)[0]
    write_new(RUN/'METRICS.json',dict(status='SCORED_AFTER_ALL_FORMAL_AND_COUNTERFACTUAL_SEALS',frames=20098,segments=results,
        feeding_pooled=dict(frames=1471,metrics={a:metrics(gt,pred[a],sims)[0] for a in ARMS}),counterfactual=counter,
        all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),score_seconds=time.perf_counter()-began,model_http=0,cost_usd=0))
    write_new(RUN/'SCORE_PROVENANCE.json',dict(scorer=artifact(__file__),old_math=artifact(ref._math.__file__),
        development_reference=artifact(ref.GT_DEV),validation_reference=artifact(ref.ARCHIVE),prediction_seals_verified_before_reference_read=True,
        ignored_public_ids=0,L3_LW_weak_reference=True,model_http=0,cost_usd=0))
if __name__=='__main__':main()
