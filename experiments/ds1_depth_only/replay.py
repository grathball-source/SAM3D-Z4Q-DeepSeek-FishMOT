"""Causal, CPU-only SOURCE_OLD replay with three independent event branches."""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import sys
import time
import tracemalloc
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FEED = ROOT/'experiments/feeding_first_two_s0p'
OLD = ROOT/'experiments/ms1_s0_development_8400'
S0P = ROOT/'experiments/s0p_identity_publication'
NE1 = ROOT/'experiments/ne1_native_first_event_association'
for path in (str(HERE), str(FEED), str(OLD), str(S0P), str(NE1),
             str(ROOT/'online/closed_loop_2888/z4q_source')):
    if path not in sys.path:
        sys.path.insert(0,path)

import numpy as np
from bridge import read, rows, sha, stream
from manager_p import MergeSplitManagerP
from merge_split_manager import choice_mapping, numeric_choice
from prepare import DATA, SEGMENTS, write_new
from ne_controller import NativeFirstGroupBridgeP
from depth_measurement import extract_frame
from depth_score import dynamic_choice, geometry_choice
from depth_state import DepthState

ARMS = ('SAM3_NATIVE','D0_GEOMETRY','D1_STATIC_LEGACY','D2_DYNAMIC')
EVENT_ARMS = ARMS[1:]
CONFIG_PATH = ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'
EVENT_CONFIG = OLD/'CONFIG_V7.json'
CODE = [HERE/name for name in ('CONFIG.json','replay.py','depth_measurement.py','depth_state.py',
                               'depth_score.py','score.py','postseal.py','verify.py','tests.py')]
CODE += [FEED/'prepare.py', OLD/'merge_split_manager.py', OLD/'source_scan_v4.py',
         S0P/'manager_p.py', ROOT/'experiments/ne1_native_first_event_association/ne_controller.py',
         ROOT/'online/closed_loop_2888/z4q_source/bridge.py', CONFIG_PATH, EVENT_CONFIG]


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
    for name,(start,stop) in SEGMENTS.items():
        base=FEED/'private'/name
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
            only_sensor_field='depth_mm', new_model_http=0, model_cost_usd=0,
            branch_policy='separate state; native-first, S0-P, same frozen scanner and 2D term'))


def run_segment(name, output, slice_mode=False):
    start,stop=SEGMENTS[name]
    base=FEED/'private'/name
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
    branches={arm:NativeFirstGroupBridgeP(config) for arm in EVENT_ARMS}
    managers={arm:MergeSplitManagerP(arm,branches[arm],suspects,event_config,assignments)
              for arm in EVENT_ARMS}
    states={arm:DepthState(name,arm) for arm in EVENT_ARMS}
    observed=processed=0
    first_slice=None
    began=time.perf_counter()
    tracemalloc.start()
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
            full, measured, _, _ = extract_frame(depth,assignments[frame],profile_by_id)
            extraction_seconds=time.perf_counter()-extraction
            assert set(measured)=={o['id'] for o in row['observations']}
            for native,measurement in measured.items():
                measurement['fact_id']=f'{name}/F{frame}/n:{native}'
            observations.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],time=now,
                depth_path=str(depth_path),depth_sha256=original[index]['depth_sha256'],
                timing=timing[row['global_frame']],full=full,objects=measured),separators=(',',':'),allow_nan=False)+'\n')
            output_row={'SAM3_NATIVE':row['native']}
            event_publish={}
            for arm in EVENT_ARMS:
                branch,manager,state=branches[arm],managers[arm],states[arm]
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
                        state.record_pending(native,measured[native],frame)
                    residual=sorted((set(episode['member_sources']) &
                        {item['id'] for item in row['observations']})-set(episode['post_roles']))
                    legacy,legacy_detail=numeric_choice(episode)
                    if arm=='D0_GEOMETRY':
                        choice,detail=geometry_choice(episode)
                    elif arm=='D1_STATIC_LEGACY':
                        choice,detail=legacy,legacy_detail
                    else:
                        choice,detail=dynamic_choice(episode,episode['depth_frozen'],measured,full)
                    episode['numeric']=dict(choice=choice,detail=detail,legacy_choice=legacy)
                    mapping=choice_mapping(episode,choice) if choice in ('H1','H2') else None
                    error='visible_member_residual_outside_two_member_restore' if residual else 'numeric_unresolved'
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
                    episode['restore']=restore
                    manager.finish(frame,status)
                ids,trace=branch.commit_once(view,transaction)
                assert all(check['veto'] for check in trace.get('native_first_auto_edge_checks',[]))
                assert not any(x.get('kind')=='reconnect' and x.get('accepted') for x in trace.get('events',[]))
                post_restored=(set(episode['post_roles']) if episode and restore and
                               restore['status'] in ('COMMIT','RESOLVE_NO_ID_CHANGE') else set())
                for item in row['observations']:
                    n=item['id']
                    cls=manager.frame_class.get(n,'SOURCE_OBSERVATION')
                    if n in post_restored:
                        cls='RESTORED_POST'
                    if (cls in ('SOURCE_OBSERVATION','RESTORED_POST') and
                            (item['area']<64 or item.get('neighbors') or not branch.engine.quality(item))):
                        cls='QUALITY_OR_CONTACT_RISK'
                    state.update(n,measured[n],frame,now,ids[n],branch.epochs.get(n),
                                 manager._generation(n,frame),cls)
                manager.after(row,profile_by_id)
                output_row[arm]=emit(row,ids)
                states_file.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],
                    arm=arm, active_event=episode['id'] if episode else None,signal=signal,
                    live={str(n):dict(key=list(item['key']),last_frame=item['last_frame'],
                        sample_frames=[x['frame'] for x in item['samples']])
                          for n,item in state.live.items()},breaks=state.breaks,updates=state.updates,
                    group_count=len(state.groups),pending_count=len(state.pending)),
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
                    if first_slice is None and arm=='D2_DYNAMIC' and not restore['unassigned_member_residual']:
                        first_slice=dict(segment=name,event=episode['id'],q=frame,
                            original_q=row['global_frame'],restore=restore,
                            frozen_depth=episode['depth_frozen'],score=episode['numeric'],
                            measured={str(n):measured[n] for n in episode['post_roles']},
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
            if slice_mode and first_slice:
                break
    peak=tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    write_new(public/'EVENTS.json',{arm:[public_event(e) for e in managers[arm].events] for arm in EVENT_ARMS})
    summary=dict(segment=name,frames=processed,observations=observed,
                 elapsed_seconds=time.perf_counter()-began,peak_python_allocated_bytes=peak,
                 state={arm:dict(updates=states[arm].updates,breaks=states[arm].breaks,
                                 groups=len(states[arm].groups),pending=len(states[arm].pending)) for arm in EVENT_ARMS},
                 new_model_http=0,model_cost_usd=0)
    write_new(public/'RUN_SUMMARY.json',summary)
    if slice_mode:
        if first_slice:
            write_new(output/'REAL_SLICE.json',first_slice)
        return first_slice
    assert processed==stop-start+1
    seal=dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',segment=name,
        original_frames=[start,stop],frames=processed,published_frames=processed,
        new_model_http=0,model_cost_usd=0,
        artifacts_sha256={filename:sha(public/filename) for filename in (
            'predictions.jsonl.gz','DEPTH_OBSERVATIONS.jsonl.gz','DEPTH_STATES.jsonl.gz',
            'TRANSACTIONS.jsonl.gz','PUBLISH_LEDGER.jsonl','EVENTS.json','RUN_SUMMARY.json','FREEZE.json')})
    write_new(public/'PREDICTIONS_SEALED.json',seal)
    return first_slice


def main(mode):
    assert mode in ('slice','full')
    output=HERE/('slice_v2' if mode=='slice' else 'run')
    if mode=='full':
        freeze_inputs(output)
    else:
        assert not output.exists(),output
        output.mkdir()
    selected=None
    for name in SEGMENTS:
        candidate=run_segment(name,output,slice_mode=(mode=='slice'))
        if selected is None and candidate:
            selected=candidate
        if mode=='slice' and selected:
            break
    if mode=='slice':
        assert selected,'no complete legal first-split event'
    else:
        write_new(output/'SELECTION.json',dict(first_complete_event=selected,
            policy='earliest prediction-triggered q with two post sources and no visible member residual',
            new_model_http=0,model_cost_usd=0))


if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('usage: replay.py slice|full')
    main(sys.argv[1])
