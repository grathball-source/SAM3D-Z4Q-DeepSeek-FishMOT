"""GT-free DS11 input acceptance and exhaustive native-birth census.

Reuse only DS10's source-bound measurements, never its aliases or depth state.
"""
from pathlib import Path
from itertools import zip_longest
from functools import lru_cache
from collections import Counter
import sys, json, gzip, hashlib, math, datetime
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DS10=ROOT/'experiments/ds10_depth_failure_repair'
DATA=Path('E:/CAU/D-MOT/data/AlignedFeeding_v1')
SEGMENTS={'feeding_000000_000199':(0,199),'feeding_000351_000555':(351,555),
          'feeding_000701_001060':(701,1060),'feeding_001201_001906':(1201,1906)}
AGE_BINS=(.2,.5,1.,2.,3.,12.)  # Descriptive bins only; no rule selection from outcomes.


def input_dir(segment):
    owner='feeding_first_two_s0p' if SEGMENTS[segment][0]<701 else 'ds2_depth_transfer_validation'
    return ROOT/'experiments'/owner/'private'/segment


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        yield from (json.loads(line) for line in stream)


@lru_cache(maxsize=None)
def artifact(path):
    path=Path(path).resolve()
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return dict(path=str(path),bytes=path.stat().st_size,sha256=digest)


def verify(entry):
    assert artifact(Path(entry['path']))=={key:entry[key] for key in ('path','bytes','sha256')},entry['path']


def verify_cached_segment(segment):
    """Check current bytes against pre-prediction source bindings, without scoring."""
    assert segment in SEGMENTS
    run=DS10/'run';public=run/segment/'public';base=input_dir(segment)
    all_seal=read(run/'ALL_PREDICTIONS_SEALED.json')
    seal=read(public/'PREDICTIONS_SEALED.json')
    assert all_seal['frames']==1471 and all_seal['seals'][segment]==artifact(public/'PREDICTIONS_SEALED.json')['sha256']
    assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
    selected={}
    for name in ('FREEZE.json','predictions.jsonl.gz','DEPTH_OBSERVATIONS.jsonl.gz'):
        entry=artifact(public/name);assert entry['sha256']==seal['artifacts_sha256'][name];selected[name]=entry
    frozen=read(public/'FREEZE.json')
    assert artifact(base/'SOURCE_MANIFEST.json')['sha256']==frozen['source_manifest_sha256']
    assert artifact(base/'sources.json')['sha256']==frozen['source_list_sha256']
    derived=frozen['derived_inputs']
    assert set(derived)=={'observations','profiles','assignments'}
    for entry in derived.values():verify(entry)
    producer={}
    for name in ('common.py','CONFIG.json','measurement.py','measurement_tests.py','MEASUREMENT_CHECKS.json',
                 'adaptive_core.py','adaptive_tests.py','ADAPTIVE_CHECKS.json','restored_source.py','REAL_INPUT_CHECKS.json'):
        path=DS10/name;entry=artifact(path)
        assert frozen['code_sha256'][str(path.resolve())]==entry['sha256'];producer[name]=entry
    legacy=ROOT/'experiments/ds1_depth_only/depth_measurement.py'
    assert artifact(legacy)['sha256']==frozen['code_sha256'][str(legacy.resolve())]
    producer['legacy_depth_measurement.py']=artifact(legacy)
    sources=read(base/'sources.json');start,stop=SEGMENTS[segment]
    assert len(sources)==seal['frames']==stop-start+1
    actual=[]
    for source in sources:
        record={}
        for prefix in ('prediction','depth'):
            entry=artifact(Path(source[prefix+'_path']))
            assert entry['bytes']==source[prefix+'_bytes'] and entry['sha256']==source[prefix+'_sha256']
            record[prefix]=entry
        actual.append(record)
    for entry in frozen['native_depth_sources']:verify(entry)
    for entry in frozen['restored_sources'].values():verify(entry)
    for entry in frozen['current_metadata'].values():verify(entry)
    return dict(segment=segment,global_frames=[start,stop],frames=stop-start+1,
        all_prediction_seal=artifact(run/'ALL_PREDICTIONS_SEALED.json'),prediction_seal=artifact(public/'PREDICTIONS_SEALED.json'),
        cache=selected,source_manifest=artifact(base/'SOURCE_MANIFEST.json'),source_list=artifact(base/'sources.json'),
        derived_inputs=derived,measurement_producer=producer,actual_sources=actual,
        actual_native_depth=frozen['native_depth_sources'],restored_sources=frozen['restored_sources'],
        current_metadata=frozen['current_metadata'])


def cached_rows(segment):
    """Fresh streaming rows; caller must first run verify_cached_segment."""
    start,stop=SEGMENTS[segment];base=input_dir(segment);public=DS10/'run'/segment/'public'
    previous_time=None
    streams=(rows(base/'observations.jsonl.gz'),rows(base/'profiles.jsonl.gz'),
             rows(public/'predictions.jsonl.gz'),rows(public/'DEPTH_OBSERVATIONS.jsonl.gz'))
    for frame,items in enumerate(zip_longest(*streams),1):
        assert all(item is not None for item in items),segment
        observation,profile,prediction,measurement=items
        global_frame=start+frame-1
        assert all(item['frame']==frame and item['global_frame']==global_frame and item['time']==observation['time'] for item in items)
        assert math.isfinite(observation['time']) and (previous_time is None or observation['time']>previous_time)
        previous_time=observation['time']
        assert prediction['variants']['SAM3_NATIVE']==observation['native']
        native={item['id'] for item in observation['observations']}
        assert len(native)==len(observation['observations']) and all(type(n) is int and n>=0 for n in native)
        assert native=={int(item['mask'][2:]) for item in observation['native']}
        assert all(item['id']==int(item['mask'][2:]) for item in observation['native'])
        assert native==set(map(int,measurement['adaptive_raw']))==set(map(int,measurement['restored']))
        assert profile['evidence_max_global_frame']<=global_frame
        timing=measurement['timing']
        assert timing['available_at_us']==max(timing['rgb_timestamp_us'],timing['depth_timestamp_us'])
        yield dict(segment=segment,frame=frame,global_frame=global_frame,time=observation['time'],
            native=observation['native'],observations=observation['observations'],profiles=profile['observations'],
            raw=measurement['adaptive_raw'],v2=measurement['restored'],timing=timing,
            full_raw=measurement['adaptive_full'],full_v2=measurement['restored_full'],restored_source=measurement['restored_source'])
    assert frame==stop-start+1


def input_clean(observation):
    """Exactly the existing confidence/area/contact gate, not single-fish truth."""
    presence=observation.get('presence')
    confidence=math.isfinite(presence) and presence>=.5 if presence is not None else observation.get('score_birth',0)>=.5
    return observation['area']>=64 and not observation.get('neighbors') and confidence


def census(segment):
    seen=set();previous=set();last={};generation={};births=[];returns=[];deaths=[]
    live_run={'raw':{},'v2':{}};totals=Counter();cohorts=Counter();initial=[];intervals=[];previous_time=None
    for row in cached_rows(segment):
        frame,now=row['frame'],row['time'];present={o['id'] for o in row['observations']}
        by_id={o['id']:o for o in row['observations']}
        if previous_time is not None:intervals.append(now-previous_time)
        previous_time=now
        for native in previous-present:
            old=last[native]
            deaths.append(dict(native=native,missing_first_global_frame=row['global_frame'],last_global_frame=old['global_frame'],
                raw_contiguous_clean_at_last_appearance=old['raw_run'],v2_contiguous_clean_at_last_appearance=old['v2_run'],
                raw_three_at_last_appearance=old['raw_run']>=3,generation=old['generation']))
            live_run['raw'].pop(native,None);live_run['v2'].pop(native,None)
        for native in sorted(present-previous):
            generation[native]=generation.get(native,0)+1
            measurement=row['raw'][str(native)];v2=row['v2'][str(native)];clean=input_clean(by_id[native])
            if native not in seen:
                entry=dict(native=native,global_frame=row['global_frame'],local_frame=frame,time=now,
                    kind='INITIAL_FRAME' if frame==1 else 'FIRST_EVER_NATIVE_BIRTH',generation=generation[native],
                    input_quality_clean=clean,raw_core_usable=measurement['core_usable'],v2_core_usable=v2['core_usable'],
                    v2_cohort=v2['cohort'],raw_fact_id=measurement['fact_id'],v2_fact_id=v2['fact_id'],
                    current_raw_n=measurement['core']['n'],current_raw_actual_mad=measurement['core']['mad'],
                    current_v2_actual_mad=v2['actual_selected_mad_mm'],current_v2_effective_mad=v2['core']['mad'],
                    first_three_contiguous_raw_clean=False,first_raw_clean_run3_global_frame=None)
                dormant=[old for n,old in last.items() if n not in present and old['raw_run']>=3]
                entry['past_absent_raw_clean3_count_by_age_seconds']={str(age):sum(0<now-old['time']<=age for old in dormant) for age in AGE_BINS}
                if frame==1:initial.append(entry)
                else:births.append(entry)
                seen.add(native)
            else:
                old=last[native]
                returns.append(dict(native=native,global_frame=row['global_frame'],generation=generation[native],
                    gap_missing_frames=frame-old['frame']-1,gap_seconds=now-old['time'],association_retry=False))
        for native in present:
            clean=input_clean(by_id[native]);raw=row['raw'][str(native)];v2=row['v2'][str(native)]
            totals['observations']+=1;totals['input_clean']+=clean
            totals['raw_core_usable']+=raw['core_usable'];totals['v2_core_usable']+=v2['core_usable'];cohorts[v2['cohort']]+=1
            totals['raw_clean_usable']+=clean and raw['core_usable'];totals['v2_clean_usable']+=clean and v2['core_usable']
            for modality,fact in [('raw',raw),('v2',v2)]:
                prior=live_run[modality].get(native)
                run=(prior['run']+1 if prior and prior['frame']==frame-1 else 1) if clean and fact['core_usable'] else 0
                live_run[modality][native]=dict(frame=frame,run=run)
            last[native]=dict(frame=frame,global_frame=row['global_frame'],time=now,generation=generation[native],
                raw_run=live_run['raw'][native]['run'],v2_run=live_run['v2'][native]['run'])
            # Census only: diagnostic qualification of the first continuous native life.
            birth=next((item for item in reversed(births) if item['native']==native),None)
            if birth and generation[native]==1 and live_run['raw'][native]['run']>=3:
                if birth['first_raw_clean_run3_global_frame'] is None:birth['first_raw_clean_run3_global_frame']=row['global_frame']
                if frame==birth['local_frame']+2:birth['first_three_contiguous_raw_clean']=True
        previous=present
    def birth_summary(items):
        return dict(count=len(items),input_quality_clean=sum(i['input_quality_clean'] for i in items),
            raw_core_usable=sum(i['raw_core_usable'] for i in items),v2_core_usable=sum(i['v2_core_usable'] for i in items),
            v2_cohorts=dict(Counter(i['v2_cohort'] for i in items)),first_three_contiguous_raw_clean=sum(i['first_three_contiguous_raw_clean'] for i in items),
            first_native_life_eventually_raw_clean3=sum(i['first_raw_clean_run3_global_frame'] is not None for i in items),
            with_past_raw_clean3_candidate_by_age_seconds={str(age):sum(i.get('past_absent_raw_clean3_count_by_age_seconds',{}).get(str(age),0)>0 for i in items) for age in AGE_BINS})
    return dict(segment=segment,frames=frame,observations=dict(totals),v2_cohorts=dict(cohorts),
        initial_summary=birth_summary(initial),birth_summary=birth_summary(births),initial=initial,births=births,
        returns_count=len(returns),returns=returns,disappearance_count=len(deaths),
        disappearances_last_raw_clean3=sum(i['raw_three_at_last_appearance'] for i in deaths),disappearances=deaths,
        unique_sources=len(seen),generation_increments=sum(generation.values()),
        adjacent_timestamp_seconds=dict(min=min(intervals),max=max(intervals)))


def write_new(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def main():
    HERE.mkdir(parents=True,exist_ok=True)
    inventory={name:verify_cached_segment(name) for name in SEGMENTS}
    summaries=[census(name) for name in SEGMENTS]
    total=dict(frames=sum(i['frames'] for i in summaries),observations=sum(i['observations']['observations'] for i in summaries),
        initial=sum(i['initial_summary']['count'] for i in summaries),first_ever_births=sum(i['birth_summary']['count'] for i in summaries),
        returns=sum(i['returns_count'] for i in summaries),disappearances=sum(i['disappearance_count'] for i in summaries))
    assert total['frames']==1471 and total['observations']==39208
    code=artifact(Path(__file__))
    write_new(HERE/'SOURCE_INVENTORY.json',dict(status='CURRENT_SOURCE_AND_DS10_MEASUREMENT_CACHE_BYTES_VERIFIED',code=code,segments=inventory,
        no_GT_scoring_reference_reads=True,no_RGB_pixels=True,no_depth_pixel_reads=True,no_new_models=True))
    write_new(HERE/'BIRTH_INPUT_CENSUS.json',dict(status='EXHAUSTIVE_GT_FREE_NATIVE_INPUT_CENSUS',code=code,
        aggregate=total,segments=summaries,age_bins_descriptive_only=list(AGE_BINS),
        cohort_note='Retained/inferred are data provenance; neither authenticates pixel fish ownership. Inferred effective MAD is a noise adapter.',
        clean_note='Existing area/confidence/no-neighbor gate plus core usability; not certified no-merge. No DS10 alias or state reused.',
        no_GT_scoring_reference_reads=True,no_RGB_pixels=True,no_new_models=True))
    write_new(HERE/'INPUT_REVIEW.json',dict(status='GT_FREE_INPUT_REVIEW_COMPLETE',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        code=code,inventory=artifact(HERE/'SOURCE_INVENTORY.json'),census=artifact(HERE/'BIRTH_INPUT_CENSUS.json'),aggregate=total,
        identity_contract=dict(namespace='SEGMENT_LOCAL_NATIVE_ID',first_frame='INITIAL_FRAME_NOT_RECONNECT_TRIAL',
            birth='NATIVE_NEVER_SEEN_IN_THIS_SEGMENT_AND_FRAME_GT_1',return_policy='PREVIOUSLY_SEEN_NATIVE_NO_NEW_RECONNECT_RETRY',
            generation='INCREMENT_ON_EVERY_NONCONTIGUOUS_NATIVE_APPEARANCE',alias_state='OWN_DS11_BRANCH_ONLY'),
        history_contract=dict(raw_required=True,min_contiguous_clean_points=3,
            endpoint='LAST_CLEAN_POINT_MUST_EQUAL_SOURCE_LAST_APPEARANCE',
            breaks=['SOURCE_GAP','NONINCREASING_TIME','PUBLIC_EPOCH_OR_SOURCE_GENERATION_CHANGE','QUALITY_CONTACT_RISK','UNUSABLE_RAW_CORE'],
            forbidden='DO_NOT_REUSE_EARLY_LATEST_FRAGMENT_ACROSS_FINAL_RISK; DO_NOT_JOIN_FRAGMENTS; NO_CROSS_SEGMENT_HISTORY'),
        measurement_contract=dict(reuse='DS10_CURRENT_FRAME_PURE_ADAPTIVE_RAW_AND_V2_COHORT_FACTS',
            conditional_on='SAME_MASK_RAW_AND_NATIVE_V2_BYTES_PRODUCER_CODE_CONFIG_CHECKS',
            fields='raw/core_usable/fact_id; v2/core/cohorts/actual_selected_mad/core_mad_semantics/provenance_counts; timing',
            v2='UPSTREAM_RGB_I_PLUS_1_OFFLINE; CURRENT_INFERRED_NOT_AUTHENTIC_DEPTH_CERTIFICATE',
            state_cache_reuse=False,physical_surface_identity='UNKNOWN',physical_calibration_accuracy='UNKNOWN'),
        observed_extra_risk_boundary='DS10 manager additionally excludes GROUP_MEASUREMENT, ANONYMOUS_RESIDUAL, POST_UNASSIGNED and unresolved event observations. If DS11 omits that manager, input-clean alone cannot certify one fish.',
        data_time_contract='global=start+local-1; source/profile/native/measurement timestamps exact; profiles evidence<=current; available_at=max(rgb_us,depth_us)',
        no_GT_scoring_reference_reads=True,no_API=True,no_v3=True,no_new_SAM3=True))
    print(json.dumps(total,ensure_ascii=False))
    for item in summaries:print(item['segment'],json.dumps(item['birth_summary'],ensure_ascii=False))


if __name__=='__main__':main()
