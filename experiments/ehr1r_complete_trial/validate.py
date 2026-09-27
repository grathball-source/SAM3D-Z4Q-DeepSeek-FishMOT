"""Independent source, projected request, and final wire-body gate."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from build import ARMS, indexes, project_request, read, sha, save, wire

AO1=Path('/home/xiongxiong/ao1_input_fidelity_20260924/range_corrected_run/public/SOURCE_MANIFEST.json')
DEV_OBS=Path('/home/xiongxiong/dmot-experiments/sam3_depth_failure_repair_20260917/diagnosis/observations_development.jsonl.gz')
DEV_DEPTH=Path('/home/xiongxiong/dmot-experiments/sam3_depth_birth_inherit_20260917/features_r2/features_development.jsonl.gz')
VAL=Path('/home/xiongxiong/deepseek_z4q_closedloop_20260923_side/inputs')
DEPTH_COLUMNS=('depth_median_pipeline_mm','depth_valid_fraction','depth_sensor_available',
    'depth_synchronized','depth_core_n','depth_core_mad','depth_whole_n','depth_whole_mad',
    'depth_overlap_pixels','depth_quality')


def stream(path, frames):
    with gzip.open(path,'rt',encoding='utf-8') as fh:
        return {row['frame']:row for line in fh if (row:=json.loads(line))['frame'] in frames}


def item(row,n):
    matches=[x for x in row['observations'] if x['id']==n]
    assert len(matches)==1
    return matches[0]


def native(source_id):
    frame, n=source_id.split('-N')
    return int(frame.split('F')[1]),int(n)


def risk(x):
    if x['area']<=0:return 'ZERO_AREA'
    if x.get('neighbors'):return 'CONTACT_RISK'
    return None


def depth_expect(obs,profile,depth_row,row,frame):
    if profile is None:
        assert obs['depth']['epistemic_type']=='UNKNOWN'
        return
    actual=obs['depth']
    assert actual['epistemic_type']=='MEASUREMENT'
    assert actual['source_frame']==frame and actual['source_time_seconds']==depth_row['time']
    assert actual['raw_array_sha256']==depth_row['raw_array_sha256']
    assert actual['sensor_available']==depth_row['sensor_available']
    assert actual['synchronized']==(depth_row['frame']==frame and depth_row['time']==row['time'])
    for part in ('core','whole'):
        for key in ('median','mad','n','valid_fraction'):
            assert actual[part][key]==profile[part][key],(frame,part,key)
    assert actual['overlap_pixels']==profile['overlap_pixels']


def check_source_episode(episode,split):
    frames={row['frame'] for row in episode['INTERACTION_OBSERVATIONS']}
    frames.update(o['source_frame'] for part in ('PRE_HISTORY','POST_HISTORY_TO_Q')
        for s in episode[part].values() for o in s['observations'])
    op=DEV_OBS if split=='development' else VAL/'observations_validation.jsonl.gz'
    dp=DEV_DEPTH if split=='development' else VAL/'features_validation.jsonl.gz'
    observations, depths=stream(op,frames),stream(dp,frames)
    assert set(observations)==set(depths)==frames
    expected={}
    for part in ('PRE_HISTORY','POST_HISTORY_TO_Q'):
        for role,segment in episode[part].items():
            seq=segment['observations']
            assert segment['status']=='CLEAN_SOURCE_FRAGMENT' and seq
            assert [x['source_frame'] for x in seq]==list(range(seq[0]['source_frame'],seq[-1]['source_frame']+1))
            assert segment['anchor_frame'] in [x['source_frame'] for x in seq]
            if len(seq)<3:assert segment['velocity']['epistemic_type']=='UNKNOWN'
            for o in seq:
                frame,n=native(o['source_fact_ids'][0]);assert frame==o['source_frame']
                row=observations[frame];src=item(row,n);drow=depths[frame]
                assert risk(src) is None
                box=src['box'];center=[round((box[0]+box[2])/2,3),round((box[1]+box[3])/2,3)]
                assert o['source_time_seconds']==row['time'] and o['bbox_px']==box
                assert o['bbox_center_px']==center and o['area_px']==src['area']
                assert o['neighbor_count']==len(src.get('neighbors',[]))
                assert o['quality']['risk']=='CLEAN' and o['quality']['presence']==src.get('presence')
                profile=item(drow,n) if any(x['id']==n for x in drow['observations']) else None
                depth_expect(o,profile,drow,row,frame)
                expected[(frame,n)]=o
    for frame_row in episode['INTERACTION_OBSERVATIONS']:
        frame=frame_row['frame'];row=observations[frame];drow=depths[frame]
        assert frame<=episode['q_frame'] and frame_row['time_seconds']==row['time']
        for o in frame_row['anonymous_observations']:
            f,n=native(o['source_fact_ids'][0]);assert f==frame
            src=item(row,n);box=src['box']
            profile=item(drow,n) if any(x['id']==n for x in drow['observations']) else None
            core=(profile or {}).get('core') or {};whole=(profile or {}).get('whole') or {}
            predicted=dict(depth_median_pipeline_mm=core.get('median'),
                depth_valid_fraction=core.get('valid_fraction'),depth_sensor_available=drow.get('sensor_available'),
                depth_synchronized=(drow['frame']==frame and drow['time']==row['time']),
                depth_core_n=core.get('n'),depth_core_mad=core.get('mad'),
                depth_whole_n=whole.get('n'),depth_whole_mad=whole.get('mad'),
                depth_overlap_pixels=None if profile is None else profile.get('overlap_pixels'),
                depth_quality='UNKNOWN' if profile is None else
                    'CONTACT_OR_MIXED_RISK' if risk(src) or (profile.get('overlap_pixels') or 0)>0 else 'OBSERVED_PROFILE')
            assert all(o[k]==predicted[k] for k in DEPTH_COLUMNS),(frame,n)
            assert o['risk']==(risk(src) or 'ANONYMOUS_CLEAN_ISLAND')
            assert o['neighbor_count']==len(src.get('neighbors',[]))
            assert o['center_px']==[round((box[0]+box[2])/2,1),round((box[1]+box[3])/2,1)]
            assert o['area_px']==src['area'] and (frame,n) not in expected
            expected[(frame,n)]=o
        assert len(frame_row['anonymous_observations'])==len({x['fact_id'] for x in frame_row['anonymous_observations']})
    full={(f,x['id']) for f in frames for x in observations[f]['observations']}
    assert set(expected)==full
    return observations,depths,expected


def validate_image(packet, episode, token_ledger, observations, expected, nodes):
    source_to_fact,_=indexes(episode)
    for image in packet['IMAGE_INDEX']:
        frame=image['frame'];assert frame<=packet['q_frame']
        assert image['time_seconds']==observations[frame]['time']
        x0,y0,x1,y1=image['roi_full_mask_xyxy'];w,h=image['width'],image['height']
        assert w==x1-x0 and h==y1-y0
        for token in image['role_tokens']:
            role=token['role'];section='PRE_HISTORY' if role in 'AB' else 'POST_HISTORY_TO_Q'
            old=[o for o in episode[section][role]['observations'] if o['source_frame']==frame]
            assert len(old)==1 and token['fact_id']==old[0]['fact_id']
            box=old[0]['bbox_px']
            assert token['bbox_full_px']==box
            assert token['bbox_image_px']==[round(box[0]-x0),round(box[1]-y0),round(box[2]-x0),round(box[3]-y0)]
        if image.get('anonymous_tokens'):
            matching=[x for x in token_ledger if x['frame']==frame and x['image_sha256']==image['sha256']]
            assert len(matching)==1
            source_tokens={x['token']:x for x in matching[0]['observations']}
            assert set(source_tokens)=={x['token'] for x in image['anonymous_tokens']}
            for token in image['anonymous_tokens']:
                meta=source_tokens[token['token']]
                assert token['bbox_norm']==meta['bbox_norm']
                n=int(meta['native_mask_key'].split(':')[1]);box=item(observations[frame],n)['box']
                norm=[round((box[0]-x0)/w,5),round((box[1]-y0)/h,5),
                      round((box[2]-x0)/w,5),round((box[3]-y0)/h,5)]
                bx=token['bbox_norm']
                assert all(0<=v<=1 for v in bx) and bx[0]<bx[2] and bx[1]<bx[3]
                overlap=max(0,min(norm[2],bx[2])-max(norm[0],bx[0]))*max(0,min(norm[3],bx[3])-max(norm[1],bx[1]))
                assert overlap/((bx[2]-bx[0])*(bx[3]-bx[1]))>.5,(image['image_id'],token['token'],norm,bx)
                key=f'SRC-F{frame}-N{n}'
                assert key in source_to_fact
                assert token['fact_id']=='EV-'+nodes[key][4:]


def check_projection(run):
    run=Path(run);source=Path(read(run/'private/SOURCE_LOCATION.json')['source'])
    manifest=read(run/'public/REQUEST_MANIFEST.json')
    for name,digest in manifest['source_sha256'].items():assert sha(source/name)==digest,name
    logical_source=Path(read(run/'private/SOURCE_LOCATION.json')['logical_source'])
    assert sha(logical_source)==manifest['logical_source_sha256']
    old=read(logical_source)['requests']
    episodes=read(source/'EPISODE_FACTS.json')
    by_case={e['request_id'].split('-')[-1]:e for e in episodes}
    nodes=read(run/'private/NODE_MAP.json')
    ledger=read(read(run/'private/SOURCE_LOCATION.json')['token_ledger'])
    actual=read(run/'public/REQUESTS_LOGICAL.json')['requests']
    assert [x['attempt_id'] for x in actual]==manifest['schedule']==[x['attempt_id'] for x in old]
    assert len(actual)==25
    cases={x['case_alias']:x for x in read(AO1)['cases']}
    source_checks=[]
    for case,episode in by_case.items():
        obs,depth,expected=check_source_episode(episode,cases[case]['split'])
        packet=next(x for x in actual if x['case']==case and x['arm']=='H-D')
        validate_image(json.loads(packet['text']),episode,ledger[case],obs,expected,nodes)
        source_checks.append(dict(case=case,frames=len(obs),source_observations=len(expected),
                                  entry_side='NOT_ESTIMATED',q=episode['q_frame']))
    for old_request,request,record in zip(old,actual,manifest['requests'],strict=True):
        case=request['case'];arm=request['arm']
        assert request==project_request(old_request,by_case[case],nodes,ledger[case])
        assert hashlib.sha256(request['text'].encode()).hexdigest()==record['text_sha256']
        assert [x['sha256'] for x in request['images']]==record['image_sha256']
        p=json.loads(request['text']);assert p['q_frame']==by_case[case]['q_frame']
        assert all(x['frame']<=p['q_frame'] for x in p['IMAGE_INDEX'])
        if arm=='E':
            assert not p['INTERACTION_OBSERVATIONS'] and not any('fragment_id' in x or 'first_position_fact_id' in x
                for part in ('PRE_HISTORY','POST_HISTORY_TO_Q') for x in p[part].values())
        else:
            table=p['INTERACTION_TABLE'];columns=table['columns']
            assert len(table['rows'])==sum(len(x['anonymous_observations']) for x in by_case[case]['INTERACTION_OBSERVATIONS'])
            if arm in ('H-D','H-D-REPEAT','H-D-PERMUTE'):
                assert set(DEPTH_COLUMNS)<=set(columns)
                event={x['fact_id']:x for frame in by_case[case]['INTERACTION_OBSERVATIONS'] for x in frame['anonymous_observations']}
                original=json.loads(old_request['text'])['INTERACTION_TABLE']
                for projected,prior in zip(table['rows'],original['rows'],strict=True):
                    actual_obs=event[prior[0]]
                    assert all(projected[columns.index(k)]==actual_obs[k] for k in DEPTH_COLUMNS)
            else:assert not any(x.startswith('depth_') for x in columns)
        assert 'SRC-F' not in request['text'] and 'frame_local:n:' not in request['text']
        for image in request['images']:
            path=run/'private/media'/image['media_file']
            assert sha(path)==image['sha256'] and path.stat().st_size==image['bytes']
    return dict(status='SOURCE_TO_LOGICAL_PASS',cases=source_checks,requests=25,
                logical_sha256=sha(run/'public/REQUESTS_LOGICAL.json'),manifest_sha256=sha(run/'public/REQUEST_MANIFEST.json'))


def check_bodies(run):
    from sender import body, wire as send_wire
    run=Path(run);logical=read(run/'public/REQUESTS_LOGICAL.json')['requests']
    uploads=[json.loads(line) for line in (run/'send/UPLOAD_LEDGER.jsonl').read_text().splitlines()]
    done={x['sha256']:x['file_id'] for x in uploads if x['phase']=='END'}
    assert len(done)==55
    records=[]
    for request in logical:
        data=(run/'send/bodies'/(request['attempt_id']+'.json')).read_bytes()
        assert data==send_wire(body(request,done))
        parsed=json.loads(data);content=parsed['messages'][1]['content']
        assert content[0]['text']==request['text']
        assert [x['file_id'] for x in content[1:]]==[done[x['sha256']] for x in request['images']]
        assert parsed['model']=='deepseek-flash' and parsed['thinking']=={'type':'enabled'}
        records.append(dict(attempt_id=request['attempt_id'],payload_sha256=hashlib.sha256(data).hexdigest(),
                            payload_bytes=len(data)))
    return dict(status='BODY_GATE_PASS',records=records)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--bodies',action='store_true');args=parser.parse_args()
    result=check_projection(args.run)
    if args.bodies:result['bodies']=check_bodies(args.run)
    save(args.run/'public'/('BODY_GATE.json' if args.bodies else 'SOURCE_TO_BODY_AUDIT.json'),result)
    print(result['status'],len(result['cases']),result['requests'],flush=True)
