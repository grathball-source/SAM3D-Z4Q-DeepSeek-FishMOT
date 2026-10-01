"""Post-seal actual-publication images; no replay, RGB, GT raster or relabeling."""
from pathlib import Path
import sys, json, gzip, hashlib, datetime
from functools import lru_cache
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
RUN = HERE/'run'
ARMS = ('SAM3_NATIVE', 'F9_RESTORED', 'D10_RAW', 'D10_RESTORED')
OLD_WRONG = {470, 764, 1390, 1805}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


@lru_cache(maxsize=None)
def artifact(path):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest)


def verify(entry):
    assert artifact(Path(entry['path'])) == entry, entry['path']


def mapping(prediction, arm):
    objects = prediction['variants'][arm]
    result = {int(item['mask'][2:]): item['id'] for item in objects}
    assert len(result) == len(objects) and all(type(v) is int for v in result.values())
    assert all(item['mask'] == 'n:'+str(int(item['mask'][2:])) for item in objects)
    return result


def sample_frames(event):
    q, suspect = event['q'], event['suspect_frame']
    groups = [frame for frame in event['group_frames'] if frame < q]
    assert 1 <= suspect <= q and groups and min(groups) >= suspect
    result = dict(before=max(1, suspect-1), merge=min(groups), q=q)
    assert all(1 <= frame <= q for frame in result.values())
    return result


def changed_q(prediction):
    result = []
    for arm in ('D10_RAW', 'D10_RESTORED'):
        for baseline in ('F9_RESTORED', 'SAM3_NATIVE'):
            if mapping(prediction, arm) != mapping(prediction, baseline):
                result.append(arm+'_vs_'+baseline)
    return result


def self_check():
    frames = sample_frames(dict(q=7, suspect_frame=3, group_frames=[3,4,5,6]))
    assert frames == dict(before=2, merge=3, q=7)
    row = dict(variants={arm:[dict(mask='n:1', id=1),dict(mask='n:2', id=2)] for arm in ARMS})
    assert changed_q(row) == []
    row['variants']['D10_RESTORED'] = [dict(mask='n:1', id=2),dict(mask='n:2', id=1)]
    assert changed_q(row) == ['D10_RESTORED_vs_F9_RESTORED', 'D10_RESTORED_vs_SAM3_NATIVE']
    # Actual prior rows remain independent: no current mapping is applied to history.
    assert mapping(row, 'SAM3_NATIVE') == {1:1,2:2}
    print('Publication visualization checks PASS: bounded sample times, exhaustive q differences, actual independent mappings')


def main():
    # First gate before reading any new prediction row or source depth.
    all_path, score_path = RUN/'ALL_PREDICTIONS_SEALED.json', RUN/'SCORING_SEALED.json'
    assert all_path.is_file() and score_path.is_file(), 'Wait for prediction AND scoring seals'
    complete, scoring = read(all_path), read(score_path)
    assert complete['status'] == 'ALL_FOUR_BRANCHES_FOUR_SEGMENTS_SEALED'
    assert complete['frames'] == 1471 and tuple(complete['arms']) == ARMS
    assert scoring['status'] == 'ALL_SEGMENTS_AND_EVENTS_SCORED'
    assert scoring['all_prediction_seal_sha256'] == artifact(all_path)['sha256']
    for name, digest in scoring['artifacts_sha256'].items():
        assert artifact(RUN/name)['sha256'] == digest, name
    destination = HERE/'private/publication'
    inventory_path = HERE/'diagnosis/PUBLICATION_INVENTORY.json'
    assert not destination.exists() and not inventory_path.exists(), 'Exclusive publication outputs already exist'

    from common import DATA, SEGMENTS, input_dir, rows
    from restored_source import RestoredDepth
    from depth_measurement import decode
    import numpy as np
    import cv2
    cv2.setNumThreads(1)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.cm import ScalarMappable
    old_stats_path = HERE/'diagnosis/CASE_STATS.json'
    old_stats = read(old_stats_path)
    assert {case['global_q'] for case in old_stats['cases']
            if case['branches']['J2_RESTORED_DEPTH']['first_public_reference']=='WRONG'} == OLD_WRONG
    bindings = dict(all_prediction_seal=artifact(all_path), scoring_seal=artifact(score_path),
                    old_diagnosis=artifact(old_stats_path), code=artifact(Path(__file__)), segments={})
    datasets = []
    for segment, (start, stop) in SEGMENTS.items():
        public = RUN/segment/'public'
        seal = read(public/'PREDICTIONS_SEALED.json')
        assert artifact(public/'PREDICTIONS_SEALED.json')['sha256'] == complete['seals'][segment]
        assert seal['frames'] == stop-start+1 and tuple(seal['arms']) == ARMS
        bound = dict(prediction_seal=artifact(public/'PREDICTIONS_SEALED.json'), files={})
        for name in ('predictions.jsonl.gz', 'EVENTS.json', 'PUBLISH_LEDGER.jsonl', 'FREEZE.json'):
            entry = artifact(public/name)
            assert entry['sha256'] == seal['artifacts_sha256'][name]
            bound['files'][name] = entry
        freeze = read(public/'FREEZE.json')
        base = input_dir(segment)
        assert artifact(base/'sources.json')['sha256'] == freeze['source_list_sha256']
        derived = [entry for entry in freeze['derived_inputs'].values()
                   if Path(entry['path']).name == 'assignments.jsonl.gz']
        assert len(derived) == 1
        verify(derived[0])
        for entry in freeze['restored_sources'].values(): verify(entry)
        for entry in freeze['current_metadata'].values(): verify(entry)
        bound['assignments'] = derived[0]
        bound['source_list'] = artifact(base/'sources.json')
        bound['restored_sources'] = freeze['restored_sources']
        bound['current_metadata'] = freeze['current_metadata']
        events = read(public/'EVENTS.json')
        canonical = {event['id']:event for event in events['F9_RESTORED'] if event['q'] is not None}
        assert all({event['id']:event['q'] for event in events[arm] if event['q'] is not None}
                   == {key:event['q'] for key,event in canonical.items()} for arm in ARMS[1:])
        q_frames = {event['q'] for event in canonical.values()}
        qrows = {row['frame']:row for row in rows(public/'predictions.jsonl.gz') if row['frame'] in q_frames}
        selected=[]
        for key,event in canonical.items():
            prediction=qrows[event['q']]
            assert prediction['global_frame'] == start+event['q']-1
            reasons = changed_q(prediction)
            if prediction['global_frame'] in OLD_WRONG: reasons.insert(0,'OLD_DS9_WRONG_FIRST_PUBLICATION')
            if reasons: selected.append((event,reasons))
        required = {frame for event,_ in selected for frame in sample_frames(event).values()}
        # Load row contents only for selected <=q samples; other rows used only for q selection.
        predictions, line_hashes, disk_line_hashes = {}, {}, {}
        with gzip.open(public/'predictions.jsonl.gz','rt',encoding='utf-8',newline='') as stream:
            for line in stream:
                row=json.loads(line)
                if row['frame'] in required:
                    predictions[row['frame']]=row
                    disk_line_hashes[row['frame']]=hashlib.sha256(line.encode('utf-8')).hexdigest()
                    # Windows TextIOWrapper writes CRLF; ledger hashes the prewrite LF row.
                    prewrite=line[:-2]+'\n' if line.endswith('\r\n') else line
                    line_hashes[row['frame']]=hashlib.sha256(prewrite.encode('utf-8')).hexdigest()
        ledgers={row['frame']:row for row in rows(public/'PUBLISH_LEDGER.jsonl') if row['frame'] in required}
        assert set(predictions) == set(ledgers) == required
        assert all(ledgers[frame]['prediction_row_sha256']==line_hashes[frame] for frame in required)
        assignments={row['frame']:row for row in rows(Path(derived[0]['path'])) if row['frame'] in required}
        assert set(assignments)==required
        bindings['segments'][segment]=bound
        datasets.append((segment,start,selected,predictions,line_hashes,disk_line_hashes,assignments,read(base/'sources.json'),events))

    destination.mkdir(parents=True)
    reader=RestoredDepth()
    images=[]
    try:
        for segment,start,selected,predictions,line_hashes,disk_line_hashes,assignments,sources,events in datasets:
            for event,reasons in selected:
                frames=sample_frames(event)
                sample_data={}; samples=[]
                for role,frame in frames.items():
                    global_frame=start+frame-1
                    source=sources[frame-1]
                    raw_path=Path(source['depth_path'])
                    raw_binding=artifact(raw_path)
                    assert raw_binding['bytes']==source['depth_bytes'] and raw_binding['sha256']==source['depth_sha256']
                    with np.load(raw_path) as values:
                        raw=values['depth_mm'].copy(); index=values['source_index']
                        index_hash=hashlib.sha256(index.astype('<i4').tobytes()).hexdigest()
                    v2, provenance, meta=reader(global_frame)
                    assert meta['index']==global_frame and raw.shape==v2.shape==(360,640)
                    masks={int(key[2:]):decode(rle) for key,rle in assignments[frame]['masks'].items()}
                    prediction=predictions[frame]
                    assert prediction['global_frame']==global_frame
                    assert all(set(mapping(prediction,arm))==set(masks) for arm in ARMS)
                    sample_data[role]=(raw,v2,masks,prediction)
                    samples.append(dict(role=role,local_frame=frame,global_frame=global_frame,time=prediction['time'],
                        actual_prediction_row_sha256=line_hashes[frame],actual_disk_line_sha256=disk_line_hashes[frame],
                        ledger_line_semantics='PREWRITE_LF; ONLY_TERMINAL_CRLF_NORMALIZED; SEALED_DISK_FILE_SHA_VERIFIED',raw_aligned=raw_binding,
                        raw_source_index_sha256=index_hash,v2_source_index_sha256=hashlib.sha256(reader.current_source_index.astype('<i4').tobytes()).hexdigest(),
                        v2_native=artifact(Path(meta['native_path'])),v2_row=meta['native_row'],
                        future_support=meta['future_support'],published={arm:mapping(prediction,arm) for arm in ARMS},
                        displayed_all_masks=len(masks)))
                positives=np.concatenate([depth[np.isfinite(depth)&(depth>0)] for raw,v2,_,_ in sample_data.values() for depth in (raw,v2)])
                assert positives.size
                norm=LogNorm(vmin=float(positives.min()),vmax=max(float(positives.max()),float(positives.min())+1))
                fig,axes=plt.subplots(4,6,figsize=(30,16),constrained_layout=True)
                focus=set(event['member_sources'])|set(map(int,event['post_first_observations']))
                focus.update(x['source'] for x in event['group_observations'] if x['frame']<=event['q'])
                for row_index,arm in enumerate(ARMS):
                    own_event=next(item for item in events[arm] if item['id']==event['id']) if arm!='SAM3_NATIVE' else None
                    residual=set(own_event['restore']['unassigned_member_residual']) if own_event else set()
                    for time_index,role in enumerate(('before','merge','q')):
                        raw,v2,masks,prediction=sample_data[role]
                        actual=mapping(prediction,arm)
                        for modality,depth in enumerate((raw,v2)):
                            ax=axes[row_index,time_index*2+modality]
                            ax.imshow(np.ma.masked_where(~np.isfinite(depth)|(depth<=0),depth),cmap='viridis',norm=norm)
                            suspect=np.argwhere(np.isfinite(depth)&(depth>5000))
                            if suspect.size:ax.scatter(suspect[:,1],suspect[:,0],s=2,c='red',marker='.')
                            for native,mask in masks.items():
                                public_id=actual[native]
                                color=plt.get_cmap('tab20')((public_id%20)/19)
                                outline='magenta' if role=='q' and native in residual else color
                                contours,_=cv2.findContours(mask.astype('u1'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                                for contour in contours:
                                    contour=contour[:,0,:]
                                    if len(contour)>1:ax.plot(*contour.T,color=outline,linewidth=1.2 if native in focus|residual else .55)
                                yy,xx=np.nonzero(mask)
                                if len(xx):ax.text(float(xx.mean()),float(yy.mean()),f'{public_id}\nn{native}',fontsize=4.5,color='white',ha='center',va='center',
                                    bbox=dict(boxstyle='square,pad=.05',facecolor='black',edgecolor='none',alpha=.5))
                            ax.set_xlim(-.5,639.5);ax.set_ylim(359.5,-.5)
                            ax.set_title(f'{arm}\n{role} F{prediction["global_frame"]} / '+('RAW' if modality==0 else 'saved native V2')+
                                f' / >5000 SUSPECT={len(suspect)} / max={float(depth[np.isfinite(depth)].max()):.1f} mm',fontsize=8)
                            ax.set_xticks([]);ax.set_yticks([])
                fig.colorbar(ScalarMappable(norm=norm,cmap='viridis'),ax=axes,shrink=.7,label='recorded camera-Z mm; full positive value range; >5000 red is diagnostic, not sensor limit')
                qglobal=start+event['q']-1
                fig.suptitle(f'DS10 actual publication F{qglobal} / {event["id"]}\n'
                    'Every ID is its branch/time actual prediction row; no retroactive relabel; all masks retained; magenta q visible residual.\n'
                    'No RGB / GT raster. V2 is upstream RGB + future-supported offline data; surface ownership/calibration UNKNOWN.\n'
                    'Selection: '+', '.join(reasons)+'; sample policy before=suspect-1, merge=first recorded group, q=first split.',fontsize=13)
                path=destination/f'{segment}_F{qglobal}_{event["id"]}.png'
                assert not path.exists()
                fig.savefig(path,dpi=140)
                plt.close(fig)
                images.append(dict(segment=segment,event=event['id'],global_q=qglobal,selection=reasons,
                    sample_frames=samples,pixel_artifact=artifact(path),no_frames_after_q=True,no_retroactive_relabel=True))
                print('Actual publication comparison',qglobal,event['id'],'saved',flush=True)
    finally:
        reader.close()
    assert OLD_WRONG <= {image['global_q'] for image in images}
    inventory=dict(status='SEALED_ACTUAL_PUBLICATION_COMPARISON_COMPLETE',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        arms=list(ARMS),bindings=bindings,images=images,selected_q=len(images),private_pixels_not_for_Git=True,
        selection='ALL_OLD_WRONG_PLUS_ALL_NEW_Q_ROWS_DIFFERING_FROM_F9_OR_NATIVE; NOT_NEW_GT_SELECTED',
        labels='ACTUAL_PREDICTION_ROW_ONLY_EACH_ARM_TIME; NO_BACKFILL_OR_REFERENCE_RELABEL',
        sample_policy='BEFORE_MAX_1_SUSPECT_MINUS_1; MERGE_FIRST_RECORDED_GROUP; Q; NO_SAMPLED_TIME_AFTER_Q',
        RGB_reads=0,GT_raster_reads=0,new_model_calls=0,new_replays=0)
    with inventory_path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(inventory,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    print('Publication comparison PASS:',len(images),'cases; actual IDs; sealed source/prediction/scoring bindings')


if __name__=='__main__':
    if sys.argv[1:]==['--self-check']: self_check()
    else:
        assert sys.argv[1:] in ([], ['--ledger-lf-repair'])
        main()
