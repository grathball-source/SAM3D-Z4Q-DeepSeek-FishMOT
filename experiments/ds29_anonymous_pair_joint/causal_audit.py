"""Locate original accepted actions retained/lost and durable wrong joint edits."""
from common import *
from collections import Counter
assert read(RUN/'METRICS.json')['frames']==20098
results={};total=Counter()
for name in SEGMENTS:
    public=RUN/name/'public';audit=read(public/'ACTION_AUDIT.json');joint=read(public/'JOINT_ACTION_AUDIT.json')
    original=[x for x in audit['actions'] if x['arm']=='Z4Q_FROZEN'];new=[x for x in audit['actions'] if x['arm']=='JOINT_DEPTH']
    sought={x['frame'] for x in original}|{x['frame'] for x in joint['events'] if x['arm']=='JOINT_DEPTH' and x['changes']}
    traces={t['frame']:t for t in rows(public/'TRANSACTIONS.jsonl.gz') if t['arm']=='JOINT_DEPTH' and t['frame'] in sought}
    controls={t['frame']:t for t in rows(public/'TRANSACTIONS.jsonl.gz') if t['arm']=='Z4Q_FROZEN' and t['frame'] in sought}
    comparisons=[];counts=Counter()
    for old in original:
        t=traces[old['frame']];n,k=old['source'],old['target']
        equivalent=[x for x in new if x['source']==n and x['target']==k and x['origin_rule']==old['origin_rule']]
        own=t['actual_published_mapping'].get(str(n));joint_restore=next((x for x in joint['events'] if x['arm']=='JOINT_DEPTH'
            and x['staged'] and x['actual_published_mapping'].get(str(n))==k and x['frame']<=old['frame']),None)
        status=('SAME_FRAME_ORIGINAL_COMMIT' if any(x['frame']==old['frame'] for x in equivalent) else
            'ORIGINAL_RULE_AT_OTHER_FRAME' if equivalent else 'PRIOR_EXPLICIT_JOINT_RESTORE' if joint_restore else
            'MAPPED_TO_TARGET_WITHOUT_SAME_ORIGINAL_ACTION' if own==k else 'ORIGINAL_ACTION_NOT_RETAINED_AT_THIS_FRAME')
        counts[status]+=1;counts[old['actual_reference_physical']+'/'+status]+=1
        edge_key='birth_checks' if old['origin_rule']=='BIRTH_REFINE' else 'edges'
        edges=[x for x in t['controller_trace'].get(edge_key,[]) if x.get('native_id')==n and x.get('canonical_id')==k]
        comparisons.append(dict(original=old,status=status,current_public=own,other_original_rule_commits=equivalent,
            prior_joint_restore=joint_restore,actual_current_protection=t['controller_trace'].get('joint_protection'),
            actual_edges_at_original_frame=edges,signal=t['signal'],branch_target_anchor=t['bank_anchors'].get(str(k)),
            limitation='Different later states can change eligibility; a lost action is not automatically a causal wrong intervention. No counterfactual metrics claimed.'))
    wrong=[]
    for x in joint['events']:
        if x['arm']!='JOINT_DEPTH' or x['committed_actual_reference_physical']!='WRONG' or not x['changes']:continue
        q=x['frame'];sources=[int(n) for n in x['changes']];run_lengths={n:0 for n in sources};active=set(sources)
        for p in rows(public/'predictions.jsonl.gz'):
            if p['frame']<q:continue
            mapping={int(a['mask'][2:]):a['id'] for a in p['variants']['JOINT_DEPTH']}
            for n in list(active):
                if mapping.get(n)==x['changes'][str(n)]:run_lengths[n]+=1
                else:active.remove(n)
            if not active:break
        wrong.append(dict(action=x,depth_signal_used=traces[q]['joint_decision']['detail']['depth_used'],
            complete_joint_candidates=traces[q]['joint_decision']['detail']['candidates'],
            original_at_same_frame=controls[q]['actual_published_mapping'],
            consecutive_published_wrong_transaction_target_frames={str(n):v for n,v in run_lengths.items()},
            frame_counts_are_public_mapping_persistence_not_per_frame_GT_error_certificates=True))
    total.update(counts);results[name]=dict(original_commit_comparison_counts=counts,all_original_commits=comparisons,
        wrong_joint_edits=wrong,joint_audit_pin=artifact(public/'JOINT_ACTION_AUDIT.json'))
write_new(HERE/'CAUSE_AUDIT.json',dict(status='POSTSEAL_ACTUAL_STATE_ACTION_PATH_COMPARISON_NO_COUNTERFACTUAL_CLAIM',
    segments=results,counts=total,no_prediction_or_scoring_changes=True,new_model_http=0,cost_usd=0))
print(json.dumps(total),flush=True)
