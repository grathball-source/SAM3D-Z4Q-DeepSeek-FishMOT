"""GT-free source upper bound for the explicit risk-before-disappearance contract."""
from collections import Counter, deque
import copy, json, math, sys
from pathlib import Path
from input_contract import (HERE,SEGMENTS,cached_rows,input_clean,artifact,read,write_new)

MIN_POINTS=3
MAX_GAP=12.0
HISTORY=30


def point(row,observation):
    native=observation['id'];raw=row['raw'][str(native)];v2=row['v2'][str(native)]
    return dict(frame=row['frame'],global_frame=row['global_frame'],time=row['time'],source_native=native,
        area=observation['area'],neighbors=list(observation.get('neighbors',[])),
        input_clean=bool(input_clean(observation)),raw_usable=raw['core_usable'],
        raw_fact_id=raw['fact_id'],raw_median_mm=raw['core']['median'],raw_actual_mad_mm=raw['core']['mad'],
        raw_n=raw['core']['n'],v2_fact_id=v2['fact_id'],v2_usable=v2['core_usable'],v2_cohort=v2['cohort'],
        v2_actual_mad_mm=v2['actual_selected_mad_mm'],v2_effective_mad_mm=v2['core']['mad'])


def query_reasons(row,observation):
    raw=row['raw'][str(observation['id'])];presence=observation.get('presence');reasons=[]
    confidence=(math.isfinite(presence) and presence>=.5 if presence is not None
                else observation.get('score_birth',0)>=.5)
    if observation['area']<64:reasons.append('AREA_LT64')
    if observation.get('neighbors'):reasons.append('CONTACT_NEIGHBORS')
    if not confidence:reasons.append('CONFIDENCE')
    if not raw['core_usable']:reasons.append('RAW_CORE_UNUSABLE')
    return reasons


def segment_census(segment):
    seen=set();previous=set();generation={};last={};live={};latest={};history={};absent={}
    births=[];initial=[];disappearances=[];frame_evidence=[];totals=Counter()
    for row in cached_rows(segment):
        frame=row['frame'];present={o['id'] for o in row['observations']}
        frame_evidence.append(dict(frame=frame,global_frame=row['global_frame'],time=row['time'],
            observation_count=len(present),native_sources=sorted(present),
            anonymous_raw_usable_count=sum(v['core_usable'] for v in row['raw'].values()),
            anonymous_v2_cohorts=dict(Counter(v['cohort'] for v in row['v2'].values())),
            source_cache_line_1based=frame))
        for native in previous-present:
            end=copy.deepcopy(latest.get(native,[]));source_last=last[native]
            endpoint=end[-1] if end else None
            risky=[copy.deepcopy(p) for p in history[native]
                   if endpoint and p['frame']>endpoint['frame']]
            item=dict(disappearance_evidence_index=len(disappearances),source_native=native,source_generation=generation[native],
                disappearance_frame=frame,disappearance_global_frame=row['global_frame'],
                last_appearance=source_last,joint_fragment=end,
                joint_fragment_points=len(end),joint_fragment_at_least_three=len(end)>=MIN_POINTS,
                reference_anchor=(dict(frame=endpoint['frame'],global_frame=endpoint['global_frame'],
                    time=endpoint['time'],native_id=native,mask=f'n:{native}',raw_fact_id=endpoint['raw_fact_id'])
                    if endpoint else None),
                risk_anonymous_source_observations=risky,risk_observation_count=len(risky),
                branch_public_id=None,branch_public_epoch=None,branch_version_status='UNKNOWN_SOURCE_UPPER_BOUND',
                bank_anchor_status='NOT_READ_OR_FABRICATED_REQUIRES_CURRENT_BRANCH_RUNTIME_BINDING')
            absent[native]=item;disappearances.append(copy.deepcopy(item));live.pop(native,None)
        for observation in sorted(row['observations'],key=lambda item:item['id']):
            native=observation['id']
            if native in previous:continue
            generation[native]=generation.get(native,0)+1
            live[native]=deque(maxlen=HISTORY);latest.pop(native,None);history[native]=[]
            absent.pop(native,None)
            if native in seen:
                totals['returns_not_retried']+=1;continue
            seen.add(native);p=point(row,observation);reasons=query_reasons(row,observation)
            restored=row['v2'][str(native)]
            v2_reasons=list(reasons)
            if not restored['core_usable']:v2_reasons.append('V2_CORE_UNUSABLE')
            if restored['cohort']!='retained':v2_reasons.append('V2_NOT_RETAINED')
            candidates=[]
            for source,candidate in sorted(absent.items()):
                ss=candidate['joint_fragment'];why=[]
                c={key:copy.deepcopy(candidate[key]) for key in ('disappearance_evidence_index','source_native',
                    'source_generation','disappearance_frame','disappearance_global_frame','reference_anchor',
                    'joint_fragment_points','risk_observation_count','branch_public_id','branch_public_epoch',
                    'branch_version_status','bank_anchor_status')}
                if len(ss)<MIN_POINTS:why.append('LATEST_JOINT_FRAGMENT_LT3')
                if any(b['frame']!=a['frame']+1 or b['time']<=a['time'] for a,b in zip(ss,ss[1:])):
                    why.append('NONCONTIGUOUS_OR_NONINCREASING_JOINT_FRAGMENT')
                if any(not s['input_clean'] or not s['raw_usable'] or s['source_native']!=source or
                       s['source_generation']!=c['source_generation'] for s in ss):
                    why.append('SOURCE_GENERATION_OR_CLEAN_RAW_MISMATCH')
                gap=row['time']-ss[-1]['time'] if ss else None
                if gap is None or not 0<gap<=MAX_GAP:why.append('GAP_FROM_LAST_JOINT_CLEAN_OUTSIDE_12S')
                end=ss[-1]['frame'] if ss else None
                c.update(query_gap_seconds_from_last_joint_clean=gap,source_condition_reasons=why,
                    source_condition_pass=not why,query_global_frame=row['global_frame'],
                    complete_intervening_frame_evidence_indices=([end,frame-2] if end is not None and end<frame-1 else []),
                    complete_intervening_frame_count=(frame-end-1 if end is not None else None),
                    raw_branch_source_opportunity=not reasons and not why and frame>1,
                    retained_v2_branch_source_opportunity=not v2_reasons and not why and frame>1)
                candidates.append(c)
            q=dict(native=native,source_generation=generation[native],frame=frame,global_frame=row['global_frame'],
                time=row['time'],kind='INITIAL_FRAME' if frame==1 else 'FIRST_EVER_NATIVE_BIRTH',
                query=p,raw_query_reasons=reasons,raw_query_qualified=not reasons,
                retained_v2_query_reasons=v2_reasons,retained_v2_query_qualified=not v2_reasons,
                source_candidates=candidates,source_candidates_passing=sum(c['source_condition_pass'] for c in candidates),
                raw_source_opportunity_count=sum(c['raw_branch_source_opportunity'] for c in candidates),
                retained_v2_source_opportunity_count=sum(c['retained_v2_branch_source_opportunity'] for c in candidates))
            (initial if frame==1 else births).append(q)
        for observation in row['observations']:
            native=observation['id'];p=point(row,observation);p['source_generation']=generation[native]
            if p['input_clean'] and p['raw_usable']:
                window=live.setdefault(native,deque(maxlen=HISTORY))
                assert not window or (window[-1]['frame']==frame-1 and window[-1]['time']<row['time'])
                window.append(p);latest[native]=list(window)
            else:
                live[native]=deque(maxlen=HISTORY)
            history[native].append(p);last[native]=p
        previous=present
    summary=dict(frames=len(frame_evidence),initial=len(initial),first_ever_births=len(births),
        returns_not_retried=totals['returns_not_retried'],disappearances=len(disappearances),
        disappearances_with_latest_joint_fragment3=sum(i['joint_fragment_at_least_three'] for i in disappearances),
        raw_qualified_birth_queries=sum(q['raw_query_qualified'] for q in births),
        retained_v2_qualified_birth_queries=sum(q['retained_v2_query_qualified'] for q in births),
        births_with_source_history_candidate_before_query_gate=sum(q['source_candidates_passing']>0 for q in births),
        raw_opportunity_birth_queries=sum(q['raw_source_opportunity_count']>0 for q in births),
        raw_opportunity_edges=sum(q['raw_source_opportunity_count'] for q in births),
        retained_v2_opportunity_birth_queries=sum(q['retained_v2_source_opportunity_count']>0 for q in births),
        retained_v2_opportunity_edges=sum(q['retained_v2_source_opportunity_count'] for q in births),
        raw_query_failure_reasons=dict(Counter(reason for q in births for reason in q['raw_query_reasons'])),
        candidate_failure_reasons=dict(Counter(reason for q in births for c in q['source_candidates'] for reason in c['source_condition_reasons'])))
    assert len(frame_evidence)==SEGMENTS[segment][1]-SEGMENTS[segment][0]+1
    return dict(segment=segment,summary=summary,initial=initial,births=births,disappearances=disappearances,
                anonymous_intervening_frame_evidence=frame_evidence)


def check_fragment_reset():
    """A newer one-point clean window must replace an older qualified window."""
    live=deque(maxlen=HISTORY);latest=[]
    for frame,clean in enumerate((True,True,True,False,True,False),1):
        if clean:live.append(frame);latest=list(live)
        else:live=deque(maxlen=HISTORY)
    assert latest==[5] and len(latest)<MIN_POINTS


def main():
    assert sys.argv[1:] in ([],['--compact-evidence'])
    check_fragment_reset()
    source=read(HERE/'SOURCE_INVENTORY.json')
    # Recheck the already accepted numerical cache producer and every used stream.
    for segment in source['segments'].values():
        for entry in list(segment['cache'].values())+list(segment['derived_inputs'].values())+list(segment['measurement_producer'].values()):
            assert artifact(Path(entry['path']))==entry,entry['path']
    pieces=[segment_census(name) for name in SEGMENTS]
    numeric_keys=[key for key,value in pieces[0]['summary'].items() if isinstance(value,int)]
    aggregate={key:sum(p['summary'][key] for p in pieces) for key in numeric_keys}
    assert aggregate['frames']==1471 and aggregate['first_ever_births']==105 and aggregate['disappearances']==124
    code=artifact(Path(__file__))
    contract=dict(status='EXPLICIT_PRE_FREEZE_REPLACEMENT_ENDPOINT_CONTRACT',code=code,
        supersedes_endpoint_only_in=artifact(HERE/'INPUT_REVIEW.json'),strict_zero_census_preserved=artifact(HERE/'BIRTH_INPUT_CENSUS.json'),
        source_inventory=artifact(HERE/'SOURCE_INVENTORY.json'),
        query=dict(trigger='SEGMENT_FIRST_EVER_NATIVE_FRAME_GT_1; INITIAL_FRAME_RECORDED_NOT_TRIED; RETURNING_NATIVE_NOT_RETRIED',
            quality='ORIGINAL_CONFIDENCE_GATE_AND_AREA_GE64_AND_NO_NEIGHBORS_AND_RAW_CORE_USABLE',
            v2='QUERY_MUST_ALSO_HAVE_USABLE_RETAINED_COHORT; INFERRED_NOT_CERTIFICATION'),
        history=dict(min_points=MIN_POINTS,max_points=HISTORY,
            fragment='MOST_RECENT_CONTIGUOUS_JOINT_GEOMETRY_AND_USABLE_RAW_CLEAN_WINDOW',
            latest_short_fragment='REJECT_IF_LENGTH_1_OR_2; NEVER_FALL_BACK_TO_EARLIER_QUALIFIED_FRAGMENT',
            actual_runtime_support='EVERY_POINT_PRESENT_IN_ACTUAL_RAW_DEPTHSTATE_AND_MANAGER_CLASS_SOURCE_OBSERVATION',
            version='SAME_SEGMENT_SOURCE_NATIVE_GENERATION_AND_ACTUAL_BRANCH_PUBLIC_EPOCH_AND_PUBLIC_ID',
            breaks=['SOURCE_GAP','VERSION_CHANGE','QUALITY_OR_CONTACT_RISK','UNUSABLE_RAW','NON_SOURCE_OBSERVATION_CLASS'],
            fit='NEVER_INCLUDE_RISK_OR_GAP_OBSERVATIONS; NO_STITCHING; RAW_AND_GEOMETRY_ENDPOINT_ALIGNED'),
        anchors=dict(reference='ACTUAL_LAST_JOINT_CLEAN_POINT',bank='SEPARATE_ACTUAL_PREFRAME_BRANCH_BANK_ANCHOR_AND_CURRENT_VERSION; NO_FABRICATED_OR_CROSS_VERSION_INHERITANCE'),
        timing=dict(max_query_gap_seconds=MAX_GAP,gap='QUERY_TIME_MINUS_LAST_JOINT_CLEAN_TIME_INCLUDES_ALL_RISK_AND_ABSENCE'),
        risk=dict(retain='COMPLETE_INTERVENING_INPUT_FRAME_CHAIN_AND_REAL_SOURCE_OBSERVATIONS',
            ownership='ANONYMOUS_FACTS_NO_INDIVIDUAL_FISH_OWNERSHIP_CLAIM',not_history=True),
        source_census_scope='UPPER_BOUND_ONLY; SOURCE_GENERATION_PROVEN; BRANCH_PUBLIC_EPOCH_BANK_ALIAS_OCCUPANCY_GROUP_CLASS_UNKNOWN',
        runtime_required=['CURRENT_PUBLIC_UNOCCUPIED','NO_ALIAS_CLAIM','NO_PROTECTED_GROUP_CLAIM','NO_ACTIVE_GROUP_AT_QUERY',
            'EXACT_PREFRAME_BANK_ANCHOR_AND_CURRENT_VERSION_BINDING','UNIQUE_TARGET_AND_ATOMIC_FIRST_PUBLICATION'],
        no_GT_scoring_reference_reads=True,no_RGB_pixels=True,no_new_model=True,no_v3=True)
    write_new(HERE/'ENDPOINT_CONTRACT.json',contract)
    write_new(HERE/'RISK_PRE_FRAGMENT_CENSUS.json',dict(status='GT_FREE_SOURCE_UPPER_BOUND_NOT_BRANCH_ELIGIBILITY',
        code=code,contract=artifact(HERE/'ENDPOINT_CONTRACT.json'),source_inventory=artifact(HERE/'SOURCE_INVENTORY.json'),
        aggregate=aggregate,segments=pieces,
        frame_evidence_index_note='Zero-based inclusive indices into anonymous_intervening_frame_evidence; old source measurements remain hash-bound in DS10 cache.',
        current_frame_only_queries=True,no_GT_scoring_reference_reads=True,public_version_or_alias_not_fabricated=True))
    print(json.dumps(aggregate,ensure_ascii=False))
    for p in pieces:
        print(p['segment'],json.dumps(p['summary'],ensure_ascii=False))
        for q in p['births']:
            if q['raw_source_opportunity_count']:
                print('SOURCE_UPPER_BOUND',q['global_frame'],q['native'],
                    [(c['source_native'],c['reference_anchor']['global_frame'],c['query_gap_seconds_from_last_joint_clean'])
                     for c in q['source_candidates'] if c['raw_branch_source_opportunity']])


if __name__=='__main__':main()
