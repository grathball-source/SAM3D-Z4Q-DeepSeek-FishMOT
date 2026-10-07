"""Independently recompute all edge decisions and explain sealed state effects."""
from common import *
from collections import Counter
import math, statistics
from predictor import predict, DEPTH

def stats(values):
    xs=[x for x in values if isinstance(x,(float,int)) and math.isfinite(x)]
    return dict(n=len(xs),minimum=min(xs) if xs else None,median=statistics.median(xs) if xs else None,
                maximum=max(xs) if xs else None,missing=len(values)-len(xs))

def physical(matches, frame, native, anchor):
    current=matches.get(str(frame),{}).get(str(native),{})
    old=matches.get(str(anchor['frame']),{}).get(str(anchor['native_id']),{}) if anchor else {}
    if current.get('status')!='UNIQUE_IOU_MATCH' or old.get('status')!='UNIQUE_IOU_MATCH':return 'UNSCORABLE'
    return 'SAME' if current['gt_id']==old['gt_id'] else 'DIFFERENT'

def main():
    from score import verify_all
    verify_all();assert read(RUN/'METRICS.json')['status']=='SCORED_AFTER_ALL_SEALS'
    totals={arm:Counter() for arm in VETO_ARMS};all_reasons={arm:Counter() for arm in VETO_ARMS}
    segments={};queries=[];changes=[];original_actions=[];wanted=[]
    for name in SEGMENTS:
        p=RUN/name/'public';matches=read(p/'REFERENCE_MATCHES.json');graded=read(p/'ACTION_AUDIT.json')['actions']
        original_by_frame={}
        for action in graded:
            if action['arm']=='Z4Q_FROZEN':original_by_frame.setdefault(action['frame'],[]).append(action)
        counters={a:Counter() for a in VETO_ARMS};reasons={a:Counter() for a in VETO_ARMS}
        tx=iter(rows(p/'TRANSACTIONS.jsonl.gz'));seen=Counter();first_control=False
        for pr,ledger,extract in zip(rows(p/'predictions.jsonl.gz'),rows(p/'PUBLISH_LEDGER.jsonl'),rows(p/'DEPTH_EXTRACTS.jsonl.gz'),strict=True):
            f=pr['frame'];assert row_sha(pr)==ledger['prediction_row_sha256'] and row_sha(extract)==ledger['depth_extract_row_sha256']
            records={}
            for arm in ARMS[1:]:
                t=next(tx);assert (t['arm'],t['frame'],t['version'])==(arm,f,f)
                assert row_sha(t)==ledger['transaction_row_sha256'][arm] and t['decided_before_first_publish']
                assert {int(n):v for n,v in t['mapping'].items()}=={int(o['mask'][2:]):o['id'] for o in pr['variants'][arm]}
                records[arm]=t
            checks_by_arm={}
            for arm in VETO_ARMS:
                t=records[arm];checks=t['controller_trace']['depth_checks'];checks_by_arm[arm]=checks
                current=t['mapping'];own=t['original_own_state_mapping'];deleted=[c for c in checks if c['veto']]
                counters[arm]['frames']+=1;counters[arm]['changed_frames']+=pr['variants'][arm]!=pr['variants']['Z4Q_FROZEN']
                counters[arm]['same_prior_changed_frames']+=current!=own
                if not deleted:
                    assert current==own and t['engine_state_sha256']==t['original_own_state_sha256'] and t['full_state_null_checked']
                if current!=own:
                    changes.append(dict(segment=name,arm=arm,frame=f,global_frame=pr['global_frame'],
                        before_mapping=own,after_mapping=current,actual_bank_anchors=t['bank_anchors'],
                        original_own_state_sha256=t['original_own_state_sha256'],after_state_sha256=t['engine_state_sha256'],
                        rejected_edges=[dict(phase=c['phase'],native=c['native_id'],public=c['canonical_id']) for c in deleted]))
                for check in checks:
                    counters[arm]['hook_edges']+=1;reasons[arm][check['reason']]+=1
                    phase=check['phase'];eligible=not check['terms']['failures'] and check['terms']['cost'] is not None if phase=='BIRTH_REFINE' else check['terms']['rejection'] is None
                    assert check['original_eligible']==eligible
                    assert check['veto']==(eligible and check['conflict']) and not check['counterfactual_allowed']
                    counters[arm]['original_eligible_edges']+=eligible
                    counters[arm]['raw_conflicts']+=check['conflict'];counters[arm]['legal_edges_deleted']+=check['veto']
                    xs=check['samples'];forecast=check.get('forecast');measurement=check.get('current') or {}
                    if xs:
                        assert xs[-1]['anchor']==check['anchor'] and all(x['frame']<f and x['time']<t['time'] for x in xs)
                        assert all(x['version']==xs[-1]['version'] for x in xs)
                    if forecast:
                        fresh=DEPTH.forecast(xs,t['time']) if arm=='Z4Q_WLS_VETO' else predict(xs,t['time'])
                        assert digest(forecast)==digest(fresh),'Forecast drift from frozen formula'
                        counters[arm]['bound_forecasts']+=1
                    usable=bool(forecast and forecast['usable'] and forecast['scale_mm']<=CFG['max_forecast_scale_mm'] and measurement.get('usable'))
                    if usable:
                        counters[arm]['both_depth_usable_edges']+=1
                        residual=abs(measurement['z_mm']-forecast['mu_mm'])
                        threshold=max(CFG['absolute_conflict_floor_mm'],CFG['conflict_scale_multiplier']*math.hypot(forecast['scale_mm'],measurement['scale_mm']))
                        assert math.isclose(check['residual_mm'],residual) and math.isclose(check['threshold'],threshold)
                        assert check['conflict']==(residual>threshold)
                    grade=physical(matches,f,check['native_id'],check['anchor'])
                    counters[arm]['eligible_'+grade]+=eligible
                    if check['veto']:
                        counters[arm]['deleted_'+grade]+=1
                        if arm=='Z4Q_LEVEL_VETO':wanted.append(dict(segment=name,frame=f,native=check['native_id'],
                            anchor=check['anchor'],grade=grade,selection='ALL_ACTUAL_LEVEL_MATRIX_DELETIONS_POSTSEAL'))
                    if not first_control and arm=='Z4Q_LEVEL_VETO' and eligible and usable:
                        wanted.append(dict(segment=name,frame=f,native=check['native_id'],anchor=check['anchor'],
                            grade=grade,selection='FIRST_SOURCE_ELIGIBLE_RELIABLE_QUERY_CONTROL_POSTSEAL'));first_control=True
                    queries.append(dict(segment=name,arm=arm,frame=f,global_frame=pr['global_frame'],phase=phase,
                        native=check['native_id'],public=check['canonical_id'],anchor=check['anchor'],reason=check['reason'],
                        eligible=eligible,conflict=check['conflict'],actual_deletion=check['veto'],physical_bank_relation=grade,
                        reference_points=len(xs),source_fact_ids=[x['fact_id'] for x in xs],current_fact_id=measurement.get('fact_id'),
                        current_usable=measurement.get('usable',False),mu_mm=forecast.get('mu_mm') if forecast else None,
                        scale_mm=forecast.get('scale_mm') if forecast else None,
                        old_wls_slope_mm_s=(forecast.get('original_wls_diagnostic',forecast).get('slope_mm_s') if forecast else None),
                        innovation_rate_mm2_s=forecast.get('innovation_rate_mm2_s') if forecast else None,
                        residual_mm=check.get('residual_mm'),threshold_mm=check.get('threshold')))
                seen[arm]+=1
            for action in original_by_frame.get(f,[]):
                event=action['event'];phase='BIRTH_REFINE' if event.get('phase')=='birth' else 'D1_DELAYED'
                support={a:[q for q in checks_by_arm[a] if (q['phase'],q['native_id'],q['canonical_id'])==(phase,event['native_id'],event['canonical_id'])] for a in VETO_ARMS}
                original_actions.append(dict(action,segment=name,depth_edges=support,
                    matching_final_public={a:records[a]['mapping'].get(str(event['native_id']))==event['canonical_id'] for a in VETO_ARMS},
                    event_reference_and_depth_bank_reference_may_differ=True))
                if action['physical']=='WRONG':wanted.append(dict(segment=name,frame=f,native=event['native_id'],
                    anchor=action['actual_reference'],grade='WRONG_ORIGINAL_ACTION',selection='ALL_ORIGINAL_WRONG_ACTIONS_POSTSEAL'))
        assert next(tx,None) is None and all(v==SEGMENTS[name][1]-SEGMENTS[name][0]+1 for v in seen.values())
        for arm in VETO_ARMS:totals[arm].update(counters[arm]);all_reasons[arm].update(reasons[arm])
        segments[name]=dict(counters={a:dict(counters[a]) for a in VETO_ARMS},reasons={a:dict(reasons[a]) for a in VETO_ARMS})
    with gzip.open(RUN/'EDGE_AUDIT.jsonl.gz','xt',encoding='utf-8') as handle:
        for value in queries:handle.write(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n')
    write_new(RUN/'ORIGINAL_ACTION_FOLLOWUP.json',dict(actions=original_actions,counts=dict(Counter(a['physical'] for a in original_actions))))
    write_new(RUN/'STATE_CHANGES.json',changes)
    unique={digest({k:c[k] for k in ('segment','frame','native','anchor')}):c for c in wanted}
    write_new(HERE/'VISUAL_CASES.json',dict(cases=list(unique.values()),GT_raster_used=False,pixels_private=True))
    result=dict(status='ALL_EDGE_FORMULAS_SOURCE_CAUSALITY_LEGALITY_AND_STATE_EFFECTS_RECOMPUTED',
        totals={a:dict(totals[a]) for a in VETO_ARMS},reasons={a:dict(all_reasons[a]) for a in VETO_ARMS},segments=segments,
        original_actions=len(original_actions),actual_same_prior_publication_changes=len(changes),
        edge_audit=artifact(RUN/'EDGE_AUDIT.jsonl.gz'),model_http=0,cost_usd=0)
    write_new(RUN/'MECHANISM_AUDIT.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
