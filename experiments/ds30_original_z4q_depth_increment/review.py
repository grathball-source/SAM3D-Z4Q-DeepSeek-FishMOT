"""Postseal source/response-free mechanism audit; reference verdicts are separate."""
from common import *
from collections import Counter
import score
score.verify_all();segments={};overall=Counter();cases=[]
for name in SEGMENTS:
    p=RUN/name/'public';counts=Counter();previous={a:0 for a in ARMS[1:]};depth_vs_original=[]
    facts={}
    for row in rows(p/'MEASUREMENTS.jsonl.gz'):
        f=row['measurement'];key=(row['arm'],f['fact_id'],digest(f));facts[key]=f
        counts['measurement_facts']+=1
        counts['qualified_supports_'+str(len(f['qualified_support_ids']))]+=1
        counts['measurement_reason_'+f['reason']]+=1
    ledger=iter(rows(p/'PUBLISH_LEDGER.jsonl'));tx=iter(rows(p/'TRANSACTIONS.jsonl.gz'));orders=iter(rows(p/'ORDER_CHECKS.jsonl.gz'))
    for prediction in rows(p/'predictions.jsonl.gz'):
        f=prediction['frame'];l=next(ledger);o=next(orders)
        assert row_sha(prediction)==l['prediction_row_sha256'] and row_sha(o)==l['checks_row_sha256']
        if prediction['variants']['DEPTH_INCREMENT']!=prediction['variants']['Z4Q_FROZEN']:depth_vs_original.append(prediction['global_frame'])
        for arm in ARMS[1:]:
            t=next(tx);assert (t['frame'],t['arm'])==(f,arm) and row_sha(t)==l['transaction_row_sha256'][arm]
            assert t['branch_version']==previous[arm]+1;previous[arm]=t['branch_version']
            mapping={int(n):k for n,k in t['actual_published_mapping'].items()}
            assert [mapping[int(x['mask'][2:])] for x in prediction['variants'][arm]]==[x['id'] for x in prediction['variants'][arm]]
            assert len(mapping)==len(set(mapping.values()))
            if arm in ARMS[2:] and t['state_selection']=='ORIGINAL_OWN_BRANCH_PREVIEW':
                assert t['branch_state_sha256']==t['original_own_branch_preview_state_sha256']
                counts['no_transaction_full_state_bound']+=1
            d=t['joint_decision']
            if not d:continue
            detail=d['detail'];prefix=arm+'/'
            counts[prefix+'q']+=1;counts[prefix+'raw_'+d['choice']]+=1;counts[prefix+d['status']]+=1
            counts[prefix+'stage_reason_'+str(d['stage_error'])]+=1
            if detail['depth_used']:counts[prefix+'informative_depth']+=1
            if detail['current_pair']:
                counts[prefix+'pre_q_measured_comparison']+=1
                counts[prefix+'multiple_current_qualified_supports']+=any(sum(s['used'] for s in detail['current_pair'][r]['supports'])>1 for r in ('A','B'))
            else:counts[prefix+'depth_unavailable_'+detail.get('depth_reason',detail['reason'])]+=1
            if d['choice'] in ('H1','H2') and detail['geometry_choice']!=d['choice']:counts[prefix+'depth_changed_raw_choice']+=1
            if d['staged']:
                selected={int(n):k for n,k in d['mapping'].items()};assert all(mapping[n]==k for n,k in selected.items())
                for n,k in selected.items():
                    if n!=k:assert t['actual_alias_targets'][str(n)]==k
            # Keep every episode/q; visual selection later is chronological, never a truth gate.
            cases.append(dict(segment=name,arm=arm,decision=d,transaction_sha256=row_sha(t),engine_state_sha256=t['engine_state_sha256']))
    assert next(tx,None) is None and next(ledger,None) is None and next(orders,None) is None
    events=read(p/'EVENTS.json')
    event_counts={a:dict(Counter(e['status'] for e in es)) for a,es in events.items()}
    for e in events['DEPTH_INCREMENT']:
        if e['q'] is None:counts['DEPTH_INCREMENT/no_q']+=1
        if e['confirm_frame'] is not None:counts['DEPTH_INCREMENT/confirmed_merge']+=1
        for s in e['group']+e['group_anonymous']:
            assert s['public_id'] is None and s['public_epoch'] is None
    access=read(p/'SOURCE_ACCESS.json')
    assert all(r['frame']<=r['query_cutoff_frame'] for r in access['actual_reads'])
    overall.update(counts)
    segments[name]=dict(counts=counts,event_statuses=event_counts,depth_vs_original_changed_frames=depth_vs_original,
        actual_raw_source_reads=len(access['actual_reads']),all_masks_and_ids_scored=True,
        postseal_physical_audit=artifact(p/'JOINT_ACTION_AUDIT.json'),switch_audit=artifact(p/'SWITCH_CHANGES.json'))
write_new(HERE/'MECHANISM_ANALYSIS.json',dict(status='PASS_FULL_SEAL_BINDING_PUBLICATION_AND_CAUSAL_READ_AUDIT',
    segments=segments,counts=overall,source_frames=20098,new_model_http=0,cost_usd=0))
with gzip.open(HERE/'FORMAL_JOINT_DECISIONS.jsonl.gz','xt',encoding='utf-8') as h:
    for c in cases:h.write(json.dumps(c,separators=(',',':'))+'\n')
print(json.dumps(dict(status='PASS',counts=overall)),flush=True)
