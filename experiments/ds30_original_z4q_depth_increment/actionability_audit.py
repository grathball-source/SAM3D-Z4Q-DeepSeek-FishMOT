"""Postseal diagnose the two non-null suggestions; no counterfactual score/run."""
from common import *
import score
score.verify_all();records=[]
for name in SEGMENTS:
    p=RUN/name/'public';events={e['id']:e for e in read(p/'EVENTS.json')['DEPTH_INCREMENT']}
    matches={x['frame']:x['matches'] for x in rows(p/'REFERENCE_MATCHES.jsonl.gz')};previous_bank={}
    for tx in rows(p/'TRANSACTIONS.jsonl.gz'):
        if tx['arm']!='DEPTH_INCREMENT':continue
        d=tx['joint_decision']
        if d and d['detail']['depth_used']:
            detail=d['detail'];preferred=detail['depth_preference'];selected=detail['candidates'][preferred]['mapping']
            actual={int(n):k for n,k in tx['actual_published_mapping'].items()};selected={int(n):k for n,k in selected.items()}
            wanted=dict(actual);wanted.update(selected);targets={}
            for n,k in wanted.items():targets.setdefault(k,[]).append(n)
            collisions={k:ns for k,ns in targets.items() if len(ns)>1}
            changed={n:k for n,k in selected.items() if actual[n]!=k}
            edges=[]
            for n,k in selected.items():
                a=d['references'][str(k)]
                current=matches.get(tx['frame'],{}).get(str(n),dict(status='MISSING_ENDPOINT'))
                past=matches.get(a['frame'],{}).get(str(a['native_id']),dict(status='MISSING_ENDPOINT'))
                edges.append(dict(source=n,public=k,reference=a,relation=score.same(current,past),
                    actual_previous_bank_anchor=previous_bank.get(str(k)),
                    previous_bank_anchor_still_frozen=previous_bank.get(str(k))==a))
            relations=[x['relation'] for x in edges]
            verdict='WRONG' if 'DIFFERENT' in relations else 'UNSCORABLE' if 'UNKNOWN' in relations else 'CORRECT'
            records.append(dict(segment=name,event=d['event'],q=tx['frame'],global_frame=tx['global_frame'],
                depth_preference=preferred,geometry_preference=detail['geometry_choice'],
                depth_only_margin=detail['depth_only_margin'],total_margin=detail['margin'],
                suggestion_only_not_committed=True,not_a_counterfactual_tracking_run_or_metric=True,
                preferred_mapping=selected,actual_published_mapping=actual,changes_needed=changed,
                occupied_public_targets=collisions,visible_member_residual=sorted((set(events[d['event']]['member_sources'])&set(actual))-set(selected)),
                edges=edges,depth_preference_actual_reference_physical=verdict,
                weak_unreviewed_reference=name in ('L3','LW'),original_decision=d['choice'],stage_error=d['stage_error']))
        previous_bank=tx['bank_anchors']
assert len(records)==read(HERE/'INPUT_DIAGNOSIS.json')['counts']['non_null_depth']
write_new(HERE/'ACTIONABILITY_AUDIT.json',dict(status='POSTSEAL_SUGGESTION_AND_ACTUAL_OCCUPATION_REFERENCE_AUDIT',
    records=records,no_new_stage_or_counterfactual_metrics=True,new_model_http=0,cost_usd=0))
print(json.dumps([dict(segment=r['segment'],q=r['q'],needed=r['changes_needed'],collisions=r['occupied_public_targets'],physical=r['depth_preference_actual_reference_physical']) for r in records]),flush=True)
