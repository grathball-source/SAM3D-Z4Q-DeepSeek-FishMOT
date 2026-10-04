"""Coverage of the archived original matrices, never GT-selected new inputs."""
from common import *
from collections import Counter

segments={};overall=Counter();verdicts={}
for name in SEGMENTS:
    public=DS27/'run'/name/'public'
    seal=read(public/'PREDICTIONS_SEALED.json')
    for path,pin in seal['artifacts_sha256'].items():assert sha(public/path)==pin
    physical={(a['frame'],a['origin_rule'],a['source'],a['target']):a['actual_reference_physical']
        for a in read(public/'ACTION_AUDIT.json')['actions'] if a['arm']=='Z4Q_FROZEN'}
    counts=Counter();actions=[];edges=[]
    for tx in rows(public/'TRANSACTIONS.jsonl.gz'):
        if tx['arm']!='SOFT_C1_S5':continue
        trace=tx['controller_trace'];formal={(c['origin_rule'],c['native_id'],c['public_id'])
            for c in trace['depth_soft_checks']}
        legal=set()
        for phase,key in (('D1_DELAYED','edges'),('BIRTH_REFINE','birth_checks')):
            for e in trace.get(key,[]):
                if 'cost_original' not in e:continue
                k=(phase,e['native_id'],e['canonical_id']);assert k not in legal
                legal.add(k);entered=k in formal
                counts[phase+'_legal_edges']+=1;counts[phase+'_near_edges']+=entered
                edges.append(dict(frame=tx['frame'],global_frame=tx['global_frame'],phase=phase,
                    source=e['native_id'],target=e['canonical_id'],original_cost=e['cost_original'],
                    near_entered=entered,risk_all_original_legal_entered=True))
        assert formal<=legal
        for item in tx['actual_actions']:
            a=item['action'];phase='BIRTH_REFINE' if a.get('phase')=='birth' else 'D1_DELAYED'
            k=(phase,a['native_id'],a['canonical_id']);assert k in legal
            verdict=physical[tx['frame'],*k];entered=k in formal
            counts['original_durable_actions']+=1;counts['original_actions_near_entered']+=entered
            counts[phase+'_original_actions']+=1
            actions.append(dict(frame=tx['frame'],global_frame=tx['global_frame'],phase=phase,
                source=k[1],target=k[2],near_entered=entered,risk_legal_edge_entered=True,
                archived_postseal_actual_reference_physical=verdict,
                used_to_select_new_case_or_threshold=False))
    dist={v:dict(total=sum(a['archived_postseal_actual_reference_physical']==v for a in actions),
        near_entered=sum(a['near_entered'] and a['archived_postseal_actual_reference_physical']==v for a in actions))
        for v in ('CORRECT','WRONG','UNSCORABLE')}
    overall.update(counts);segments[name]=dict(counts=counts,archived_actions=actions,legal_edges=edges,
        archived_action_verdict_coverage=dist,old_seal=artifact(public/'PREDICTIONS_SEALED.json'),
        old_postseal_audit=artifact(public/'ACTION_AUDIT.json'))
write_new(HERE/'ENTRY_COVERAGE_PREAUDIT.json',dict(status='ARCHIVED_SEALED_MATRIX_COVERAGE_DIAGNOSTIC',
    segments=segments,counts=overall,all_eight_sources_fixed=True,
    no_new_GT_RGB_or_pixel_reads=True,archived_postseal_verdicts_diagnostic_only=True,
    no_GT_case_anchor_q_or_threshold_selection=True,new_model_http=0,cost_usd=0))
print(json.dumps(overall))
