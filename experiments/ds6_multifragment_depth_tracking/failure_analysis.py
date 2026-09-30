"""Postseal causal evidence availability and real state-action decomposition."""
from collections import Counter
from common import HERE,RUN,SEGMENTS,ARMS,read,rows,write_new,artifact
import numpy as np

def main():
    result=[];counts=Counter();actions={arm:Counter() for arm in ARMS[1:]}
    differences=[]
    for name,(start,stop) in SEGMENTS.items():
        public=RUN/name/'public'
        events=read(public/'EVENTS.json')
        facts={row['frame']:row for row in rows(public/'DEPTH_OBSERVATIONS.jsonl.gz')}
        for arm,items in events.items():
            for event in items:
                restore=event['restore']
                if restore:
                    actions[arm][restore['status']]+=1
                    actions[arm]['changed_sources']+=len(restore['changes'])
        core_by_q={e['q']:e for e in events['D2_CORE_FROZEN'] if e['q'] is not None}
        multi_by_q={e['q']:e for e in events['D5_MULTIFRAGMENT'] if e['q'] is not None}
        for shadow in read(public/'COMMON_STATE_SHADOW.json'):
            q=shadow['frame'];event=multi_by_q[q];detail=shadow['multi']
            row=dict(segment=name,event=event['id'],q=q,global_q=start+q-1,
                multi_choice=shadow['multi_choice'],same_state_scalar_choice=shadow['scalar_choice'],
                joint_available=detail.get('joint_available',False),
                reason=detail.get('reason'),history={},post={},multiple_qualified_current=False,
                bank_mapping=event['restore']['mapping'],restore=event['restore'])
            for role,frozen in event['depth_frozen'].items():
                prediction=next((edge['predict'] for key,edge in detail.get('edges',{}).items()
                                 if key.startswith(role+':')),None)
                row['history'][role]=dict(samples=len(frozen['samples']),key=frozen['key'],
                    latest_frame=frozen['samples'][-1]['frame'] if frozen['samples'] else None,
                    status=prediction['status'] if prediction else 'NO_NUMERIC_PAIR',
                    scale_mm=prediction['scale_mm'] if prediction else None,
                    mu_mm=prediction['mu_mm'] if prediction else None,
                    slope_mm_s=prediction['slope_mm_s'] if prediction else None)
            for native in event['post_first_observations']:
                m=facts[q]['f6'][native]
                row['post'][native]=dict(status=m['filter']['status'],reason=m['filter']['reason'],
                    n=m['filter']['selected']['n'],qualified_pieces=m['qualified_piece_count'],
                    piece_medians=[p['median'] for p in m['pieces'] if p['qualified']],
                    raw_core_available=facts[q]['objects'][native]['core_usable'],
                    f6_q_available=m['core_usable'])
                row['multiple_qualified_current'] |= m['qualified_piece_count']>1
            missing=[]
            if row['reason']=='NO_NUMERIC_PAIR':
                missing.append('NO_NUMERIC_PAIR')
            else:
                for role,v in row['history'].items():
                    if v['mu_mm'] is None:missing.append('NO_PRE_HISTORY_'+role)
                for native,v in row['post'].items():
                    if not v['f6_q_available']:missing.append('POST_'+v['reason'])
            row['missing_reasons']=missing
            counts['q']+=1
            counts['joint_available']+=row['joint_available']
            counts['multi_surface_q']+=row['multiple_qualified_current']
            counts['multi_surface_joint_available']+=row['multiple_qualified_current'] and row['joint_available']
            counts['representation_choice_change']+=shadow['multi_choice']!=shadow['scalar_choice']
            for reason in missing:counts[reason]+=1
            old=core_by_q.get(q)
            if old:
                row['old_core_choice']=old['numeric']['choice']
                row['old_core_used_edges']=old['numeric']['detail'].get('used_edges',0)
                if old['numeric']['choice']!=row['multi_choice']:
                    differences.append(dict(row,old_core_mapping=old['restore']['mapping'],
                        old_core_restore=old['restore'],old_core_frozen=old['depth_frozen']))
            result.append(row)
    write_new(HERE/'CAUSAL_EVIDENCE_ANALYSIS.json',dict(
        status='POSTSEAL_FROZEN_TRIAL_ANALYSIS',counts=dict(counts),events=result,
        depth_choice_differences_from_core=differences,
        real_state_actions={arm:dict(v) for arm,v in actions.items()},
        interpretation='availability is a source/measurement condition, not a model competency verdict; no certified physical surfaces; no thresholds or state output altered',
        dependencies=[artifact(RUN/'SCORING_SEALED.json'),artifact(HERE/'failure_analysis.py')],
        model_http=0,cost_usd=0))
    print(dict(counts));print({arm:dict(v) for arm,v in actions.items()})
    print('core differences',[(x['global_q'],x['old_core_choice'],x['multi_choice'],x['missing_reasons']) for x in differences])
if __name__=='__main__':main()

