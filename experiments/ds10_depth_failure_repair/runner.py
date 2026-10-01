"""Current-frame state replay with saved offline RGB/future-supported v2 depth."""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import sys
import time
import tracemalloc
from pathlib import Path

from common import (HERE,ROOT,DATA,RUN,DS1,DS2,DS6,FEED,OLD,S0P,NE1,SEGMENTS,ARMS,
                    input_dir,read,rows,sha,write_new,artifact)
import numpy as np
import cv2
cv2.setNumThreads(1)
from bridge import stream
from manager_p import MergeSplitManagerP
from merge_split_manager import choice_mapping,numeric_choice
from ne_controller import NativeFirstGroupBridgeP
from depth_measurement import extract_frame
from depth_state import DepthState
from measurement import measure_restored, measure_raw
from restored_source import RestoredDepth
import importlib.util
_spec=importlib.util.spec_from_file_location("ds10_native_controller",HERE/"controller.py")
_native=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_native)
DepthNativeBridge,DepthNativeManager=_native.DepthNativeBridge,_native.DepthNativeManager
from association import choose
_spec9=importlib.util.spec_from_file_location("ds9_frozen_association",HERE.parent/"ds9_joint_h0_depth/association.py")
_old9=importlib.util.module_from_spec(_spec9)
_spec9.loader.exec_module(_old9)

EVENT_ARMS = ARMS[1:]
CONFIG_PATH = ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'
EVENT_CONFIG = OLD/'CONFIG_V7.json'
CODE = [HERE/n for n in (
 'CONFIG.json','PLAN.md','README.md','runner.py','prepare.py','common.py',
 'execute.py','preflight.py','check_real_slice.py','freeze_review.py','EFFECTIVE_PARAMETERS.json',
 'controller.py','controller_tests.py','CONTROLLER_CHECKS.json','measurement.py',
 'association.py','forecast.py','forecast_tests.py','FORECAST_CHECKS.json','association_tests.py','ASSOCIATION_CHECKS.json','PREFLIGHT_REVIEW.md','restored_source.py','adaptive_core.py','adaptive_tests.py',
 'ADAPTIVE_CHECKS.json','measurement_tests.py','MEASUREMENT_CHECKS.json',
 'REAL_INPUT_CHECKS.json','launch.py','evaluate.py','event_audit.py','score_checks.py',
 'SCORE_CHECKS.json','ENVIRONMENT.json','OLD_READONLY_LOCK.json')]
if (HERE/'REAL_SLICE_ACCEPTANCE.json').exists():
    CODE.append(HERE/'REAL_SLICE_ACCEPTANCE.json')
CODE += [HERE.parent/'ds9_joint_h0_depth/association.py',HERE.parent/'ds9_joint_h0_depth/CONFIG.json']
CODE += [DS1/n for n in ('CONFIG.json','depth_measurement.py','depth_state.py','depth_score.py','postseal.py')]
CODE += [DS6/'runner.py',DS6/'evaluate.py',DS6/'event_audit.py',FEED/'prepare.py',
 OLD/'merge_split_manager.py',OLD/'source_scan_v4.py',S0P/'manager_p.py',NE1/'ne_controller.py',
 ROOT/'online/closed_loop_2888/z4q_source/bridge.py',CONFIG_PATH,EVENT_CONFIG]



def emit(row, mapping):
    result = [dict(id=mapping[x['id']], mask=x['mask']) for x in row['native']]
    assert len(result)==len(row['native'])==len(set(x['id'] for x in result))
    return result


def public_event(e):
    keys=('id','suspect_frame','confirm_frame','q','end','status','numeric','restore',
          'member_sources','public_ids','group_source','evidence_cutoff_frame','depth_frozen')
    result={key:copy.deepcopy(e.get(key)) for key in keys}
    result['reference_anchors']={str(k):copy.deepcopy(v.get('anchor')) for k,v in e['bank_snapshot'].items()}
    result['post_first_observations']={str(n):copy.deepcopy(series[0]) for n,series in e['post_roles'].items() if series}
    result['pre_geometry_history']=copy.deepcopy(e['pre'])
    result['group_frames']=[s['frame'] for s in e['group']]
    result['group_observations']=[dict(frame=s['frame'],source=s['source']) for s in e['group']]
    return result


def freeze_inputs(output):
    """Seal source and code before the formal prediction pass; no GT is imported."""
    assert not output.exists(), output
    output.mkdir(parents=True)
    dependencies={Path(module.__file__).resolve() for module in list(sys.modules.values())
        if getattr(module,'__file__',None) and str(Path(module.__file__).resolve()).lower().startswith(str(ROOT).lower())
        and str(module.__file__).endswith('.py')}
    dependencies.update((NE1/'score.py',OLD/'score.py'))
    code_hashes={str(path):sha(path) for path in set(CODE)|dependencies}
    restored_sources={str(p):artifact(p) for p in RestoredDepth.paths()}
    for name,(start,stop) in SEGMENTS.items():
        base=input_dir(name)
        source=read(base/'SOURCE_MANIFEST.json')
        scan=read(base/'SCAN_MANIFEST.json')
        assert source['frames']==scan['frames']==stop-start+1
        assert sha(base/'scan_v4.json')==scan['scan_sha256']
        for item in source['derived'].values():
            path=Path(item['path'])
            assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
        original=read(base/'sources.json')
        assert len(original)==stop-start+1 and sha(base/'sources.json')==source['sources_sha256']
        for item in original:
            for prefix in ('prediction','depth'):
                path=Path(item[prefix+'_path'])
                assert path.stat().st_size==item[prefix+'_bytes'] and sha(path)==item[prefix+'_sha256'],path
        public=output/name/'public'
        public.mkdir(parents=True)
        write_new(public/'FREEZE.json',dict(status='FROZEN_BEFORE_PREDICTION',
            segment=name, original_frames=[start,stop], frames=stop-start+1,
            code_sha256=code_hashes, source_manifest_sha256=sha(base/'SOURCE_MANIFEST.json'),
            source_list_sha256=sha(base/'sources.json'), derived_inputs=source['derived'],
            scan_sha256=scan['scan_sha256'], no_gt_before_seal=True,
            sensor_fields=['depth_mm','source_index','v2_h5_current_depth_mm','filled_mask','invalidated_reason','original_depth_mm'],
            restored_sources=restored_sources,
            restored_scope='NO_ANNOTATION_V2_OFFLINE_RGB_FUTURE_SUPPORTED',new_model_http=0,model_cost_usd=0,
            current_metadata={str(p):artifact(p) for p in (DATA/'manifest.jsonl',DATA/'calibration.json')},
            native_depth_sources=[artifact(DATA/'depth_native_mm'/f'{f:06d}.npy')
                                  for f in range(start,stop+1)],
            branch_policy='separate state; native-first, S0-P, same frozen scanner and 2D term'))


def run_segment(name, output, slice_mode=False, stop_at=None):
    start,stop=SEGMENTS[name]
    base=input_dir(name)
    public=output/name/'public'
    public.mkdir(parents=True, exist_ok=True)
    source=stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz',stop-start+1)
    assignments={x['frame']:x for x in rows(base/'assignments.jsonl.gz')}
    original=read(base/'sources.json')
    timing={x['frame']:{k:x[k] for k in ('rgb_timestamp_us','depth_timestamp_us','delta_us')}
            for x in map(json.loads,(DATA/'manifest.jsonl').read_text(encoding='utf-8').splitlines())}
    for pair in timing.values():
        pair['available_at_us']=max(pair['rgb_timestamp_us'],pair['depth_timestamp_us'])
    suspects={x['frame']:x for x in read(base/'scan_v4.json')['suspects']}
    config=read(CONFIG_PATH)
    event_config={'max_episode_seconds':read(EVENT_CONFIG)['max_episode_seconds']}
    branches={arm:DepthNativeBridge(config) for arm in EVENT_ARMS}
    managers={arm:DepthNativeManager(arm,branches[arm],suspects,event_config,assignments)
              for arm in EVENT_ARMS}
    states={arm:DepthState(name,arm) for arm in EVENT_ARMS}
    observed=processed=0
    shadow=[]
    candidate_times=[]
    update_times=[]
    first_slice=None
    restored_source=RestoredDepth()
    began=time.perf_counter()
    # No allocation tracing in performance replay; elapsed time includes all work.
    with gzip.open(public/'predictions.jsonl.gz','wt',encoding='utf-8') as predictions, \
         gzip.open(public/'DEPTH_OBSERVATIONS.jsonl.gz','wt',encoding='utf-8') as observations, \
         gzip.open(public/'DEPTH_STATES.jsonl.gz','wt',encoding='utf-8') as states_file, \
         gzip.open(public/'TRANSACTIONS.jsonl.gz','wt',encoding='utf-8') as transactions, \
         (public/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8') as publisher:
        for index,(row,profiles) in enumerate(source):
            frame,now=row['frame'],row['time']
            assert frame==index+1 and row['global_frame']==start+index
            assert assignments[frame]['frame']==frame
            received=time.perf_counter()
            depth_path=Path(original[index]['depth_path'])
            with np.load(depth_path) as sensor:
                assert 'depth_mm' in sensor.files
                depth=sensor['depth_mm']
            profile_by_id=profiles
            extraction=time.perf_counter()
            full, measured, masks, occupancy = extract_frame(depth,assignments[frame],profile_by_id)
            restored,provenance,restored_meta=restored_source(row['global_frame'])
            adaptive_full,adaptive_measured=measure_raw(depth,masks,occupancy,name,frame)
            restored_full,restored_measured=measure_restored(restored,provenance,masks,occupancy,name,frame)
            extraction_seconds=time.perf_counter()-extraction
            assert set(measured)=={o['id'] for o in row['observations']}
            for native,measurement in measured.items():
                measurement['fact_id']=f'{name}/F{frame}/n:{native}'
            observations.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],time=now,
                depth_path=str(depth_path),depth_sha256=original[index]['depth_sha256'],
                timing=timing[row['global_frame']],full=full,objects=measured,adaptive_raw=adaptive_measured,adaptive_full=adaptive_full,restored_full=restored_full,restored=restored_measured,restored_source=restored_meta),separators=(',',':'),allow_nan=False)+'\n')
            output_row={'SAM3_NATIVE':row['native']}
            event_publish={}
            for arm in EVENT_ARMS:
                branch,manager,state=branches[arm],managers[arm],states[arm]
                state_measured=adaptive_measured if arm=='D10_RAW' else restored_measured
                previous=dict(branch.previous)
                signal=manager.before(row,profile_by_id)
                episode=manager.active
                if episode and episode['suspect_frame']==frame:
                    episode['depth_frozen']=state.freeze(episode,frame,branch.epochs,manager.source_generation)
                    for native in episode['member_sources']:
                        state.break_source(native)
                view=branch.preview(frame,now,row['observations'],profile_by_id)
                transaction=restore=None
                if episode and episode['q']==frame:
                    assert episode['evidence_cutoff_frame']==frame
                    assert all(len(items)==1 for items in episode['post_roles'].values())
                    for native in episode['post_roles']:
                        state.record_pending(native,state_measured[native],frame)
                    residual=sorted((set(episode['member_sources']) &
                        {item['id'] for item in row['observations']})-set(episode['post_roles']))
                    legacy,legacy_detail=numeric_choice(episode)
                    candidate_start=time.perf_counter()
                    mode='RAW_DEPTH' if arm=='D10_RAW' else 'RESTORED_DEPTH'
                    selector=_old9.choose if arm=='F9_RESTORED' else choose
                    choice,detail=selector(episode,episode['depth_frozen'],state_measured,
                        adaptive_full if arm=='D10_RAW' else restored_full,
                        view['mapping'],mode,name)
                    candidate_times.append(dict(arm=arm,frame=frame,seconds=time.perf_counter()-candidate_start))
                    episode['numeric']=dict(choice=choice,detail=detail,legacy_choice=legacy)
                    mapping=choice_mapping(episode,choice) if choice in ('H1','H2') else None
                    error=('visible_member_residual_outside_two_member_restore' if residual else
                           'H0_KEEP_LAWFUL_MAPPING' if choice=='H0' else 'numeric_unresolved')
                    if mapping and not residual:
                        transaction,error=branch.stage_group_restore(view,episode,mapping)
                    if transaction is None:
                        transaction,fallback=branch.local_fallback(view,episode)
                        status=fallback['status']
                        decision_source='OWN_BRANCH_LOCAL_FALLBACK'
                    else:
                        fallback=None
                        status='COMMIT' if transaction['changes'] else 'RESOLVE_NO_ID_CHANGE'
                        decision_source=arm
                    restore=dict(status=status,selected_choice=choice,numeric_choice=legacy,
                        mapping=mapping,unassigned_member_residual=residual,
                        changes=transaction['changes'],stage_error=error,
                        decision_source=decision_source,fallback=fallback)
                    restore['mapping_relative_to_native']={n:k for n,k in (mapping or {}).items() if n!=k}
                    restore['published_previous_mapping']={n:previous.get(n) for n in episode['post_roles']}
                    restore['baseline_preview_mapping']={n:view['mapping'][n] for n in episode['post_roles']}
                    restore['changed_relative_to_previous']={n:k for n,k in transaction['mapping'].items()
                        if n in previous and previous[n]!=k}
                    episode['restore']=restore
                    manager.finish(frame,status)
                ids,trace=branch.commit_once(view,transaction)
                assert all(check['veto'] for check in trace.get('native_first_auto_edge_checks',[]))
                assert not any(x.get('kind')=='reconnect' and x.get('accepted') for x in trace.get('events',[]))
                post_restored=(set(episode['post_roles']) if episode and restore and
                               restore['status'] in ('COMMIT','RESOLVE_NO_ID_CHANGE') else set())
                update_start=time.perf_counter()
                for item in row['observations']:
                    n=item['id']
                    cls=manager.frame_class.get(n,'SOURCE_OBSERVATION')
                    if n in post_restored:
                        cls='RESTORED_POST'
                    if (cls in ('SOURCE_OBSERVATION','RESTORED_POST') and
                            (item['area']<64 or item.get('neighbors') or not branch.engine.quality(item))):
                        cls='QUALITY_OR_CONTACT_RISK'
                    state.update(n,state_measured[n],frame,now,ids[n],branch.epochs.get(n),
                                 manager._generation(n,frame),cls)
                update_times.append(dict(arm=arm,frame=frame,seconds=time.perf_counter()-update_start))
                manager.after(row,profile_by_id)
                output_row[arm]=emit(row,ids)
                states_file.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],
                    arm=arm, active_event=episode['id'] if episode else None,signal=signal,
                    live={str(n):dict(key=list(item['key']),last_frame=item['last_frame'],
                        sample_frames=[x['frame'] for x in item['samples']])
                          for n,item in state.live.items()},breaks=state.breaks,updates=state.updates,
                    group_count=len(state.groups),pending_count=len(state.pending),
                    resident_live_objects=len(state.live), resident_cache_samples=sum(len(x['cache']) for x in state.live.values()),
                    resident_current_samples=sum(len(x['samples']) for x in state.live.values()),
                    resident_latest_fragment_samples=sum(len(x['latest_fragment']) for x in state.live.values())),
                    separators=(',',':'),allow_nan=False,default=str)+'\n')
                transactions.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],
                    arm=arm,signal=signal,active_event=episode['id'] if episode else None,
                    restore=restore,actual_published_mapping=ids,
                    previous_mapping=previous,epochs=branch.epochs,
                    bank_anchors={str(k):copy.deepcopy(v.get('anchor')) for k,v in branch.engine.bank.items()},
                    controller_trace=trace),ensure_ascii=False,separators=(',',':'),default=str)+'\n')
                if episode and restore:
                    actual={int(item['mask'][2:]):item['id'] for item in output_row[arm]}
                    event_publish[arm]=dict(episode=episode['id'],q=frame,original_frame=row['global_frame'],
                        post_sample_count=1,first_public_pair={str(n):actual[n] for n in episode['post_roles']},
                        decision_source=restore['decision_source'])
                    if first_slice is None and arm=='D10_RESTORED' and not restore['unassigned_member_residual']:
                        first_slice=dict(segment=name,event=episode['id'],q=frame,
                            original_q=row['global_frame'],restore=restore,
                            frozen_depth=episode['depth_frozen'],score=episode['numeric'],
                            measured={str(n):state_measured[n] for n in episode['post_roles']},
                            full_frame=full,first_public_pair=event_publish[arm]['first_public_pair'])
            prediction=dict(frame=frame,global_frame=row['global_frame'],time=now,variants=output_row)
            line=json.dumps(prediction,separators=(',',':'),allow_nan=False)+'\n'
            predictions.write(line)
            published=time.perf_counter()
            publisher.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],
                extraction_seconds=extraction_seconds,receive_to_publish_seconds=published-received,
                prediction_row_sha256=hashlib.sha256(line.encode()).hexdigest(),
                event_publish=event_publish),separators=(',',':'),allow_nan=False)+'\n')
            processed+=1
            observed+=len(row['observations'])
            if frame%50==0:
                print(name,frame,'/',stop-start+1,'observations',observed,flush=True)
            if stop_at is not None and frame==stop_at:
                break
            if slice_mode and first_slice:
                break
    restored_source.close()
    peak=None
    write_new(public/'EVENTS.json',{arm:[public_event(e) for e in managers[arm].events] for arm in EVENT_ARMS})
    write_new(public/'COMMON_STATE_SHADOW.json',shadow)
    write_new(public/'PERFORMANCE.json',dict(candidate_times=candidate_times,state_update_times=update_times,
        note='one OpenCV and native math thread; state update excludes controller preview/commit; extraction excludes NPZ disk load; elapsed includes all; no allocation tracing'))
    summary=dict(segment=name,frames=processed,observations=observed,
                 elapsed_seconds=time.perf_counter()-began,peak_python_allocated_bytes=peak,
                 state={arm:dict(updates=states[arm].updates,breaks=states[arm].breaks,
                                 groups=len(states[arm].groups),pending=len(states[arm].pending)) for arm in EVENT_ARMS},
                 new_model_http=0,model_cost_usd=0)
    write_new(public/'RUN_SUMMARY.json',summary)
    if stop_at is not None:
        return first_slice
    if slice_mode:
        if first_slice:
            write_new(output/'REAL_SLICE.json',first_slice)
        return first_slice
    assert processed==stop-start+1
    seal=dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',segment=name,
        original_frames=[start,stop],frames=processed,published_frames=processed,
        arms=list(ARMS),new_model_http=0,model_cost_usd=0,
        artifacts_sha256={filename:sha(public/filename) for filename in (
            'predictions.jsonl.gz','DEPTH_OBSERVATIONS.jsonl.gz','DEPTH_STATES.jsonl.gz',
            'TRANSACTIONS.jsonl.gz','PUBLISH_LEDGER.jsonl','EVENTS.json','RUN_SUMMARY.json','FREEZE.json',
            'COMMON_STATE_SHADOW.json','PERFORMANCE.json')})
    write_new(public/'PREDICTIONS_SEALED.json',seal)
    return first_slice


def main(mode='full'):
    assert mode in ('slice','full')
    output=HERE/'slice' if mode=='slice' else RUN
    freeze_inputs(output)
    for name in SEGMENTS:
        value=run_segment(name,output,slice_mode=mode=='slice')
        if mode=='slice' and value:
            return
    assert mode=='full'
    write_new(output/'ALL_PREDICTIONS_SEALED.json',dict(status='ALL_FOUR_BRANCHES_FOUR_SEGMENTS_SEALED',
        seals={name:sha(output/name/'public/PREDICTIONS_SEALED.json') for name in SEGMENTS},
        frames=sum(b-a+1 for a,b in SEGMENTS.values()),arms=list(ARMS),new_model_http=0,model_cost_usd=0))


if __name__=='__main__': main(sys.argv[1] if len(sys.argv)>1 else 'full')
