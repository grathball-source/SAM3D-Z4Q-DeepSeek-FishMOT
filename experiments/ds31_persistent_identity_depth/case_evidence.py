"""Explain actual accepted edges using their recorded costs and later publications."""
from common import *
import score

score.verify_all();assert (RUN/'METRICS.json').is_file()
cases=[]
for name in SEGMENTS:
    p=RUN/name/'public';actions=read(p/'ACTION_AUDIT.json')['actions'];chosen=[]
    for role,predicate in [
        ('FIRST_CHANGED_WRONG',lambda a:a['mapping_changed'] and a['physical']=='WRONG'),
        ('FIRST_LOCAL_DEPTH_CHANGED_WRONG',lambda a:a['mapping_changed'] and a['depth_changed_same_state_selection'] and a['physical']=='WRONG'),
        ('FIRST_LOCAL_DEPTH_CHANGED_CORRECT',lambda a:a['mapping_changed'] and a['depth_changed_same_state_selection'] and a['physical']=='CORRECT')]:
        a=next((a for a in actions if a['arm']=='PID_DEPTH' and predicate(a)),None)
        if a:chosen.append((role,a))
    wanted={a['frame'] for _,a in chosen}
    txs={t['frame']:t for t in rows(p/'TRANSACTIONS.jsonl.gz') if t['arm']=='PID_DEPTH' and t['frame'] in wanted}
    references={r['frame']:r['matches'] for r in rows(p/'REFERENCE_MATCHES.jsonl.gz')}
    origins={(a['frame'],a['source'],a['target']):a for a in read(p/'ORIGIN_ACTION_AUDIT.json')['records']}
    later={};q_publications={}
    for r in rows(p/'predictions.jsonl.gz'):
        mappings={arm:{int(x['mask'][2:]):x['id'] for x in r['variants'][arm]} for arm in ARMS}
        if r['frame'] in wanted:q_publications[r['frame']]=mappings
        for role,a in chosen:
            key=(role,a['frame'],a['source'])
            if r['frame']<a['frame']:continue
            state=later.setdefault(key,dict(last_same_native_and_PID_frame=a['frame']-1,stop_reason=None))
            if state['stop_reason'] is not None:continue
            if a['source'] not in mappings['PID_DEPTH']:state['stop_reason']='NATIVE_OBSERVATION_DISAPPEARED'
            elif mappings['PID_DEPTH'][a['source']]!=a['target']:state['stop_reason']='PUBLISHED_PID_CHANGED'
            else:state['last_same_native_and_PID_frame']=r['frame']
    for role,a in chosen:
        t=txs[a['frame']];trace=t['controller_trace'];actual=next(x for x in trace['actions'] if x['source']==a['source'] and x['target']==a['target'])
        i=trace['unlocked_sources'].index(a['source']);candidates=trace['candidate_pids'];d=actual['depth_row'];edges=[]
        for j,pid in enumerate(candidates):
            if trace['feasible'][i][j]:edges.append(dict(pid=pid,geometry_cost=trace['geometry_cost'][i][j],
                joint_cost=trace['cost'][i][j],depth_edge=d.get('edges',{}).get(str(pid)),forecast=d.get('forecasts',{}).get(str(pid))))
        cases.append(dict(role=role,segment=name,action=a,actual_action=actual,feasible_edges=edges,
            current_query_match=references[a['frame']].get(str(a['source']),{}),
            selected_pre_reference_match=references[a['reference']['frame']].get(str(a['reference']['native_id']),{}),
            public_origin=origins[(a['frame'],a['source'],a['target'])],actual_four_arm_publication=q_publications[a['frame']],
            downstream_continuous_publication=later[(role,a['frame'],a['source'])],
            group_records=trace['group_records'],first_split_events=trace['first_split_events'],occupied_member_targets=trace['occupied_member_targets'],
            evidence=dict(transaction=artifact(p/'TRANSACTIONS.jsonl.gz'),action=artifact(p/'ACTION_AUDIT.json'),prediction=artifact(p/'predictions.jsonl.gz'))))
write_new(HERE/'CASE_EVIDENCE.json',dict(status='POSTSEAL_ACTUAL_EDGE_COST_AND_PUBLICATION_EVIDENCE',cases=cases,
    chronological_per_source_selection=True,new_reference_raster_read=False,tracker_replay=False,parameters_changed=False,
    caveats=['Later frames explain actual continued publications only and were not used at q.',
        'A source handle is not certified physical fish continuity. No future IoU correctness is inferred from an unchanged native handle.',
        'Only the executed target has a decision-time bank anchor; nonselected forecasts are not alternate-action physical truth.',
        'CORRECT is relative to actual selected pre reference; public origin and same-source baseline may still differ.',
        'FIRST cases document concrete mechanisms and are not selected representative rates; full action counts stay in ANALYSIS.']))
print('Actual cost and publication cases',len(cases),flush=True)
