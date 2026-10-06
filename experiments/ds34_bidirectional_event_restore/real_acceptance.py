"""Real first automatic split with a mocked H2 decision: engineering only, no GT."""
import guard  # Install the same sensor/network/annotation access restrictions first.
from common import *
import copy
from bridge import Bridge, stream
from transaction import GroupBridge, outside_state, bridge_hash
from manager import EventManager
from history import History
from lag import LagBuffer, state_hash
_runner=module('ds34_real_slice_runner',HERE/'runner.py')
decode,runtime,DEPTH=_runner.decode,_runner.runtime,_runner.DEPTH
from sensor import Sensor, _source
from flow import PairMotion


def main():
    suffix=sys.argv[1] if len(sys.argv)>1 else ''
    assert suffix in ('','CASCADE_READY','FINAL_READY')
    name='feeding_000351_000555';base=input_dir(name)
    branch=GroupBridge(read(CONFIG_PATH));original=Bridge(read(CONFIG_PATH));history=History(name)
    assignments={};packets={};manager=EventManager('MOCK_ENGINEERING_H2',branch,
        read(base/'scan_v4.json')['suspects'],CFG,assignments);lag=LagBuffer(branch)
    sensor=Sensor(name);pins_path=ROOT/'experiments/ds33_rgbd_fixed_lag/RGB_INPUT_PINS.jsonl'
    rgb_pins={r['global_frame']:r['rgb'] for r in rows(pins_path) if r['segment']==name}
    publications=[];target=None;checkpoint=qspec=history_checkpoint=None;resolved=False;receipt=None
    def publication(arrival,flush=False):
        for row in lag.pop_ready(arrival,flush):
            publications.append(dict(frame=row['frame'],arrival=arrival,flush=flush,mapping=row['mapping'],
                state_sha256=row['transaction']['full_state_sha256'],source_row_sha256=row_sha({k:row[k] for k in ('frame','global_frame','time','observations','native')})))
    cached=DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz'
    try:
        source=zip(stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz'),rows(base/'assignments.jsonl.gz'),
            rows(base/'DEPTH_OBSERVATIONS.jsonl.gz'),rows(cached),strict=True)
        for f,((row,profiles),assignment,measured,quality) in enumerate(source,1):
            assert row['frame']==assignment['frame']==measured['frame']==quality['frame']==f
            assert row['time']==assignment['time']==measured['time']==quality['time']
            assert row['global_frame']==assignment['global_frame_id']==measured['global_frame']==quality['global_frame']
            assert quality['source_binding']==dict(measured['raw_source_binding'],frame=f)
            extracts={int(n):DEPTH.extract(cert) for n,cert in quality['objects'].items()}
            for n,cert in quality['objects'].items():
                assert cert['certificate_sha256']==digest({k:v for k,v in cert.items() if k!='certificate_sha256'})
                assert (cert['native'],cert['frame'],cert['time'])==(int(n),f,row['time'])
            assignments[f]=assignment;packets[f]=dict(row=row,profiles=profiles,assignment=assignment,measured=measured,extracts=extracts)
            original.commit_once(original.preview(f,row['time'],row['observations'],profiles))
            if not resolved:
                manager.before(row,profiles);episode=manager.active
                if episode and episode['suspect_frame']==f:
                    episode['joint_pre']=history.freeze_pre(episode)
                if target is None and episode and episode.get('q') is not None:
                    target=episode;checkpoint=lag.checkpoint(f-1);qspec=copy.deepcopy(branch.engine.protected[episode['id']])
                    history_checkpoint=copy.deepcopy(history)
            view=branch.preview(f,row['time'],row['observations'],profiles);transaction=None
            if not resolved and manager.release_episode:
                transaction,_=branch.local_release(view,manager.release_episode)
            ids,trace=branch.commit_once(view,transaction);lag.buffer(runtime(row,ids,trace,branch),branch)
            history.observe(row,ids,branch.epochs,branch.engine,classes=manager.frame_class if not resolved else None)
            if not resolved:
                manager.after(row,profiles)
                if manager.release_episode:manager.finish(f,manager.release_episode['status'])
            if target is not None and not resolved:
                assert target is manager.active
                for k,h in target['bank_snapshot'].items():assert branch.engine.bank[k]==h,'protected group bank drift'
                if f==target['q']+2:
                    q=target['q'];selected=copy.deepcopy(checkpoint)
                    selected.engine.protected={target['id']:copy.deepcopy(qspec)};new_history=copy.deepcopy(history_checkpoint)
                    wanted=dict(zip(target['post_roles'],target['public_ids'][::-1]));replay=[];fallback=None
                    first=packets[q];qview=selected.preview(q,first['row']['time'],first['row']['observations'],first['profiles'])
                    authority=bridge_hash(selected);tx,error=selected.stage_group_restore(qview,target,wanted)
                    assert bridge_hash(selected)==authority
                    staged=tx is not None
                    if not staged:tx,fallback=selected.local_fallback(qview,target)
                    natives=set(target['member_sources'])|set(target['post_roles'])|{target['group_source']}
                    if staged:
                        assert outside_state(tx['engine'],natives,set(target['public_ids']))==outside_state(qview['engine'],natives,set(target['public_ids']))
                        assert tx['mapping']==dict(qview['mapping'],**{})|wanted
                        for k in target['public_ids']:
                            assert all(t<=first['row']['time'] for t,_ in tx['engine'].bank[k]['motion'])
                            assert tx['engine'].bank[k]['anchor']['frame']<=q
                    for current in range(q,f+1):
                        p=packets[current];r=p['row']
                        try:v=qview if current==q else selected.preview(current,r['time'],r['observations'],p['profiles'])
                        except AssertionError:
                            print(json.dumps(dict(actual_engine_failure_frame=current,q=q,staged=staged,wanted=wanted,
                                alias=selected.engine.alias,previous=selected.previous,
                                native=[dict(id=o['id'],area=o['area'],neighbors=o.get('neighbors')) for o in r['observations']])),flush=True)
                            raise
                        mapping,tr=selected.commit_once(v,tx if current==q else None)
                        new_history.observe(r,mapping,selected.epochs,selected.engine)
                        replay.append((runtime(r,mapping,tr,selected),copy.deepcopy(selected)))
                    resolution=lag.resolve(q-1,selected,replay,f);branch=selected;manager.bridge=branch;history=new_history
                    public_episode=copy.deepcopy(target)
                    public_episode['temporary_ids']=[dict(native=n,generation=g,anonymous_token=k)
                        for (n,g),k in public_episode['temporary_ids'].items()]
                    receipt=dict(episode=public_episode,mock_choice='H2',not_a_method_result=True,
                        q=q,cutoff=f,wanted_mapping=wanted,staged=staged,error=error,fallback=fallback,
                        actual_q_mapping=replay[0][0]['mapping'],checkpoint_sha256=state_hash(checkpoint),
                        replay_state_sha256=[state_hash(s) for _,s in replay],lag_resolution=resolution,
                        current_actual_native_tokens=[o['id'] for o in first['row']['native']],
                        outside_mapping_at_q={n:k for n,k in qview['mapping'].items() if n not in natives},
                        exact_pre_status={r:p['status'] for r,p in target['joint_pre'].items()},
                        bank_frozen_during_group_and_pending=True,future_measurement_written_to_q=False,
                        all_masks_and_residuals_retained=True)
                    # Actual data for endpoint motion is explicitly acquired past, not speculative future.
                    pre_frames=sorted(set(p['frame'] for values in target['joint_pre'].values() for p in values['samples'][-3:]))
                    used=sorted(set(pre_frames)|set(range(q,f+1)));actual={}
                    for frame in used:
                        p=packets[frame];r=p['row'];sensor.previous=None;sensor.raw.previous_frame=None
                        data=sensor.read(r['global_frame'],r['time']);assert data['binding']['rgb']==rgb_pins[r['global_frame']]
                        for k in ('aligned_depth','aligned_source_index','native_depth'):
                            assert data['binding'][k]==p['measured']['raw_source_binding'][k]
                        assert data['binding']['global_frame']<=packets[f]['row']['global_frame']
                        actual[frame]=data;decode(p)
                    flow=[]
                    for left in pre_frames:
                        for right in range(q,f+1):
                            assert left<right<=f<=q+CFG['lag_frames']
                            pair=PairMotion(actual[left],actual[right],CFG['flow'])
                            role_masks={str(n):pair.summarize_roi(mask) for n,mask in packets[left]['masks'].items()
                                if n in {p['native'] for values in target['joint_pre'].values() for p in values['samples'][-3:] if p['frame']==left}}
                            flow.append(dict(pre_frame=left,post_frame=right,actual_pair=pair.numeric_summary,source_ROI_quality=role_masks))
                    receipt['actual_sensor_bindings']={str(frame):data['binding'] for frame,data in actual.items()}
                    receipt['actual_flow_pairs']=flow
                    manager.finish(f,'MOCK_ENGINEERING_TRANSACTION_ONLY');resolved=True
            publication(f)
            if resolved and f>=target['q']+CFG['lag_frames']:
                break
        assert resolved,'No automatic first split in the fixed source; no substitute event chosen'
        q_public=[p for p in publications if p['frame']==receipt['q']]
        assert len(q_public)==1 and not q_public[0]['flush'] and q_public[0]['arrival']==receipt['q']+CFG['lag_frames']
        assert q_public[0]['mapping']==receipt['actual_q_mapping']
        prior=copy.deepcopy(publications);publication(f,True);assert publications[:len(prior)]==prior
        assert [p['frame'] for p in publications]==list(range(1,f+1))
        receipt.update(status='PASS',engineering_only=True,performance_or_identity_accuracy_claim=False,
            segment=name,frames=f,publication=q_public[0],published_frames=len(publications),published_once=True,
            complete_selected_state_continues=True,tail_scope='ORIGINAL_Z4Q_LIFECYCLE_AFTER_THE_FIRST_MOCKED_EVENT',
            publications_sha256=digest(publications),code={p.name:sha(p) for p in (HERE/'real_acceptance.py',HERE/'manager.py',HERE/'transaction.py')},
            actual_new_model_http=0,cost_usd=0,no_GT=True)
        write_new(HERE/('REAL_INPUT_SLICE'+('_'+suffix if suffix else '')+'.json'),receipt)
        write_new(HERE/('REAL_INPUT_SLICE_ACCESS'+('_'+suffix if suffix else '')+'.json'),dict(status='ACTUAL_RGB_RAW_DEPTH_NO_GT_NETWORK',
            observed_data_paths=sorted(guard.SEEN),npz_field_reads=[dict(path=p,key=k) for p,k in sorted(guard.NPZ)],
            h5_field_reads=[dict(path=p,key=k) for p,k in sorted(guard.H5)],original_sensor_field_reads=_source().FIELD_READS,
            no_GT=True,restored_depth_read=False,model_http=0))
        print(json.dumps(dict(status='PASS',segment=name,q=receipt['q'],cutoff=receipt['cutoff'],
            staged=receipt['staged'],error=receipt['error'],first_publish=q_public[0]['arrival'],
            flow_pairs=len(receipt['actual_flow_pairs']),engineering_only=True)),flush=True)
    finally:sensor.close()


if __name__=='__main__':main()
