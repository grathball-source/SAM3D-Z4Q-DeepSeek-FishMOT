"""Post-seal report-only state review: no engine calls, image reads, or GT access."""
from __future__ import annotations

from collections import Counter
import argparse
from common import HERE, RUN, ARMS, artifact, read, rows, sha, write_new

CASES = {
    'fishsa_development_8400': dict(frame=3902, native=7, extras=[6], near=[3900,3901,3902,3903,3904,3905,3906,3907]),
    'fishsa_validation_2888': dict(frame=2188, native=8, extras=[], near=list(range(2186,2195))),
    'LW': dict(frame=3064, native=133, extras=[106], near=list(range(3062,3070))),
    'feeding_001201_001906': dict(frame=264, native=176, extras=[], near=list(range(243,249))+list(range(261,269))),
}

def slim_action(value):
    keys = ('kind','origin_rule','native_id','canonical_id','accepted','birth_frame',
        'original_birth_frame','evaluation_frame','public_at_frame','phase','rejection',
        'failures','confirmations','pending_retry','old_anchor','source_previously_published',
        'actual_first_source_publication','association_evidence_sha256')
    return {k:value[k] for k in keys if k in value}

def slim_check(value):
    keys = ('native_id','canonical_id','old','public_id','accepted','failures','edge_veto',
        'required_whole_evidence','current_depths','depth_anchors','old_eligibility',
        'motion','cost','legal','core','whole')
    out={k:value[k] for k in keys if k in value}
    # These are measured scalar tables, not pixels. Large per-partner bundles are
    # bound in the original transaction and intentionally referenced by file SHA.
    if not out:out={k:v for k,v in value.items() if not isinstance(v,(dict,list))}
    return out

def snapshot(row, natives):
    trace=row['controller_trace']; separate=trace.get('activity_reference_separation',{})
    pending=trace.get('pending_birth',{})
    out={k:row.get(k) for k in ('frame','global_frame','arm','signal','active_event',
        'actual_published_mapping','previous_mapping','epochs','actual_alias_targets','bank_anchors')}
    restore=row.get('restore')
    if restore:out['restore']={k:v for k,v in restore.items() if k!='engine'}
    out['actions']=[slim_action(x) for x in trace.get('events',[]) if
        x.get('kind')=='reconnect' and x.get('native_id') in natives]
    out['birth_checks']=[slim_check(x) for x in trace.get('birth_checks',[]) if x.get('native_id') in natives]
    out['edge_checks']=[x for x in trace.get('ds16_original_automatic_edge_checks',[])
        if x.get('native_id') in natives]
    out['pending']={str(n):pending[str(n)] for n in natives if str(n) in pending}
    keys=('public_reference_keys','anonymous_native_keys','public_activity',
        'missing_sources_not_updated','certified_recent_core_frozen',
        'anonymous_current_measurement_preserved','reference_status')
    out['separation']={k:separate[k] for k in keys if k in separate}
    registry=separate.get('immutable_reference_registry',{})
    out['frozen_reference_registry']=registry
    out['source_activity']={str(n):separate.get('source_activity',{}).get(str(n)) for n in natives
        if str(n) in separate.get('source_activity',{})}
    pub=trace.get('publication_effects',{})
    out['publication_effects']=pub
    binding=trace.get('ds18_reference_binding_state',{})
    out['committed_clean_whole_updates']=[x for x in binding.get('clean_whole_updates',[])
        if x.get('input_native') in natives]
    group=trace.get('merge_split_group',{})
    out['visible_source_state']={str(n):group.get('visible_source_state',{}).get(str(n))
        for n in natives if str(n) in group.get('visible_source_state',{})}
    return out

def source_review():
    allseal=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert allseal['status']=='ALL_PREDICTIONS_AND_ACCESS_SEALED'
    result={}
    sources=[artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),artifact(HERE/'controller.py')]
    for segment,case in CASES.items():
        public=RUN/segment/'public';seal=read(public/'PREDICTIONS_SEALED.json')
        for name in ('predictions.jsonl.gz','TRANSACTIONS.jsonl.gz'):
            assert sha(public/name)==seal['artifacts_sha256'][name]
            sources.append(artifact(public/name))
        sources.append(artifact(public/'PREDICTIONS_SEALED.json'))
        wanted=[case['native'],*case['extras']]
        mapping_runs={arm:{str(n):[] for n in wanted} for arm in ARMS}
        first_differences={};predictions={};time_by_frame={}
        comparisons=[('ACTIVITY_ORDER','DS16_ORDER'),('ACTIVITY_ORDER','Z4Q_FROZEN'),
            ('MIXED_ORDER','ACTIVITY_ORDER'),('MIXED_ORDER','MIXED_OFF')]
        previous={}
        for row in rows(public/'predictions.jsonl.gz'):
            frame=row['frame'];time_by_frame[frame]=row['time']
            maps={arm:{int(x['mask'].split(':')[1]):x['id'] for x in row['variants'][arm]} for arm in ARMS}
            for arm in ARMS:
                for native in wanted:
                    value=maps[arm].get(native)
                    key=(arm,native)
                    if previous.get(key,'UNSEEN')!=value:
                        mapping_runs[arm][str(native)].append(dict(frame=frame,global_frame=row['global_frame'],public=value))
                    previous[key]=value
            for arm,base in comparisons:
                key=arm+'__minus__'+base
                if key not in first_differences and maps[arm]!=maps[base]:
                    tokens=sorted(n for n in set(maps[arm])|set(maps[base]) if maps[arm].get(n)!=maps[base].get(n))
                    first_differences[key]=dict(frame=frame,global_frame=row['global_frame'],
                        changed={str(n):dict(arm=maps[arm].get(n),base=maps[base].get(n)) for n in tokens})
            if frame in case['near']:predictions[str(frame)]={k:maps[k] for k in ARMS}
        accepted={arm:[] for arm in ARMS[1:]};snapshots={arm:[] for arm in ARMS[1:]}
        final={};pending_evaluations={arm:{str(n):[] for n in wanted} for arm in ARMS[1:]}
        pending_previous={};retirement_changes={arm:[] for arm in ARMS[1:]}
        for row in rows(public/'TRANSACTIONS.jsonl.gz'):
            arm=row['arm'];frame=row['frame'];tr=row['controller_trace']
            relevant_accepted=False
            for x in row.get('automatic_candidate_events',[]):
                ev=x['event'];entry=dict(frame=frame,global_frame=row['global_frame'],event=slim_action(ev),
                    applied_at_first_publication=x['applied_at_first_publication'],
                    durable_alias_after_commit=x['durable_alias_after_commit'],
                    overridden_by_explicit_transaction=x['overridden_by_explicit_transaction'])
                accepted[arm].append(entry)
                relevant_accepted |= ev.get('native_id') in wanted
            pending=tr.get('pending_birth',{})
            for native in wanted:
                p=pending.get(str(native))
                if not p:continue
                key=(arm,native)
                sig=(p.get('last_evaluation_frame'),p.get('retired_reason'),p.get('status'))
                if pending_previous.get(key)!=sig:
                    entry=dict(frame=frame,global_frame=row['global_frame'],last_evaluation_frame=p.get('last_evaluation_frame'),
                        original_birth_frame=p.get('original_birth_frame'),actual_first_eligible=p.get('actual_first_eligible'),
                        targets=p.get('targets'),status=p.get('status'),retired_reason=p.get('retired_reason'),
                        last_reason=p.get('last_reason'),evidence_status=p.get('evidence_status'))
                    pending_evaluations[arm][str(native)].append(entry)
                    if p.get('retired_reason'):retirement_changes[arm].append(entry)
                pending_previous[key]=sig
            if frame in case['near'] or relevant_accepted:
                snapshots[arm].append(snapshot(row,wanted))
            final[arm]=row
        final_summary={}
        for arm,row in final.items():
            pending=row['controller_trace'].get('pending_birth',{})
            now=time_by_frame[row['frame']];counts=Counter();dormant=[]
            for n,p in pending.items():
                counts[p['status']]+=1
                deadline=min(p['original_birth_time']+6,
                    (p['actual_first_eligible'] if p.get('actual_first_eligible') is not None else p['original_birth_time']+3)+3)
                if not p.get('retired_reason') and now>deadline:
                    counts['UNRETIRED_SNAPSHOT_PAST_ORIGINAL_WINDOW']+=1
                    alias=row['actual_alias_targets'].get(n)
                    counts['DORMANT_ALIASED' if alias is not None else 'DORMANT_NOT_CURRENTLY_ALIASED']+=1
                    dormant.append(dict(native=int(n),original_birth_frame=p['original_birth_frame'],
                        last_evaluation_frame=p.get('last_evaluation_frame'),alias=alias,
                        currently_observed=n in row['actual_published_mapping'],
                        last_reason=p.get('last_reason',{}).get('reason'),status=p['status']))
            final_summary[arm]=dict(frame=row['frame'],actual_alias_targets=row['actual_alias_targets'],
                actual_published_mapping=row['actual_published_mapping'],bank_anchors=row.get('bank_anchors'),
                pending_counts=dict(counts),dormant_past_window_records=dormant,
                focus_pending={str(n):pending[str(n)] for n in wanted if str(n) in pending})
        result[segment]=dict(case=case,first_full_publication_differences=first_differences,
            focus_native_mapping_runs=mapping_runs,near_predictions=predictions,
            accepted_automatic_actions=accepted,selected_actual_transactions=snapshots,
            pending_evaluation_transitions=pending_evaluations,retirement_changes=retirement_changes,
            final_actual_state=final_summary)
        print(segment,'source review complete',flush=True)
    return dict(status='SEALED_SOURCE_STATE_REVIEW_NO_GT',scope=list(CASES),
        sources=sources,helper=artifact(__file__),segments=result,
        limitations=['No GT pixels/raster/labels read; physical verdicts require complete independent score gate.',
            'evaluation_frame on pending log is snapshot frame; last_evaluation_frame is actual most recent proposal evaluation.',
            'Unretired past-window cached records are not evidence of eligibility: birth_candidates checks original windows whenever evaluated.'])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',action='store_true');args=parser.parse_args()
    if args.source:
        write_new(HERE/'POSTSEAL_STATE_SOURCE_CASES.json',source_review())
