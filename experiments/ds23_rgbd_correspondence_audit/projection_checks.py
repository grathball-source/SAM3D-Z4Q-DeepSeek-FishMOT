"""Independent metadata/math checks; never opens RGB, depth pixels or labels."""
from pathlib import Path
import os, sys, json, hashlib
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
sys.dont_write_bytecode = True
WORK = Path('E:/CAU/D-MOT')
REPO = Path('E:/CAU/SAM3D-Z4Q-DeepSeek-FishMOT')
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(WORK/'tools/depth_restoration'), str(WORK/'tools/jev_z4q_scene_v1_20260922/deps')]
import numpy as np
import cv2
from geometry import Geometry
cv2.setNumThreads(1)

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def binding(p):
    return dict(path=str(p), bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())

def records(p):
    return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()]

def nearest(source, query):
    pos = int(np.searchsorted(source, query))
    return min((i for i in (pos-1, pos) if 0 <= i < len(source)), key=lambda i: abs(int(source[i])-query))

def projection(name, profiles):
    small = Geometry(profiles, 640, 360)
    small.kc[0,2] += (640/small.color['width']-1)/2
    small.kc[1,2] += (360/small.color['height']-1)/2
    full = Geometry(profiles, small.color['width'], small.color['height'])
    # Fixed regular native-pixel positions and numeric Z, not research endpoints.
    source = np.arange(0, small.rc.reshape(-1,3).shape[0], 251)
    depths = 500 + (source % 1201).astype(float)
    xyz = small.rc.reshape(-1,3)[source]*depths[:,None] + small.t
    direct = small.project_xyz(xyz)
    cv = cv2.projectPoints(xyz,np.zeros(3),np.zeros(3),small.kc,small.dc)[0].reshape(-1,2)
    scaled = (full.project_xyz(xyz)+.5)*np.array([640/small.color['width'],360/small.color['height']])-.5
    cv_error, scale_error = float(np.max(np.abs(direct-cv))),float(np.max(np.abs(direct-scaled)))
    assert cv_error < 1e-8 and scale_error < 1e-8
    row_xyz = small.rays.reshape(-1,3)[source]*depths[:,None]@small.r.T + small.t
    assert np.allclose(xyz,row_xyz,rtol=0,atol=1e-10)
    return dict(name=name, independent_opencv_max_error_px=cv_error, pixel_center_scaling_max_error_px=scale_error,
                native_roundtrip_max_error_px=small.roundtrip_max_px,
                R_determinant=float(np.linalg.det(small.r)),R_orthogonality_max_abs=float(np.max(np.abs(small.r.T@small.r-np.eye(3)))),
                recorded_R_preserved=True, synthesized_positions=len(source),physical_accuracy='UNKNOWN')

def main():
    paths = [REPO/'experiments/ds16_relative_depth_order/source.py', REPO/'experiments/ds14_raw_multidataset/source.py',
             WORK/'tools/depth_restoration/geometry.py', WORK/'tools/depth_restoration/build_aligned_dataset.py',
             WORK/'data/AlignedDataset_v1/provenance/geometry.py',WORK/'data/AlignedDataset_v1/provenance/build_aligned_dataset.py',
             WORK/'tools/prelabel_feeding_20260924/build_aligned_feeding.py', WORK/'tools/prelabel_feeding_20260924/prepare.py',
             WORK/'tools/prelabel_new_bags_20260919/prepare.py', WORK/'tools/extract_all_bag.py']
    assert paths[0].read_bytes() == paths[1].read_bytes(), 'DS16 vs DS14 source differs'
    assert paths[2].read_bytes() == paths[4].read_bytes(), 'current vs producer Geometry differs'
    assert paths[3].read_bytes() == paths[5].read_bytes(), 'current vs producer build differs'
    feed_cal = WORK/'data/AlignedFeeding_v1/calibration.json'
    feed = read(feed_cal)
    calibrations = {'FEEDING':feed['recorded_profiles'],'FISHSA':read(WORK/'data/AlignedDataset_v1/calibration/recorded_profiles.json'),
                    'L3':read(WORK/'data/AnnotationNewBags_20260919/L3/calibration.json'),
                    'LW':read(WORK/'data/AnnotationNewBags_20260919/LW/calibration.json')}
    report = dict(passed=True,math=[projection(n,c) for n,c in calibrations.items()],metadata={},sources=[binding(p) for p in paths])
    # Inspect recorded SDK values only; do not invoke playback, exporter or SDK pipeline.
    sdk = [s for s in feed['sdk']['camera_calibration_sets'] if (s['depth_intrinsic']['width'],s['depth_intrinsic']['height'],s['rgb_intrinsic']['width'],s['rgb_intrinsic']['height'])==(640,576,640,360)]
    assert len(sdk)==1 and feed['sdk']['sdk_playback_depth_scale_mm']==1
    d = next(p for p in feed['recorded_profiles'] if p['streamType']==3)
    assert np.array_equal(sdk[0]['depth_to_color']['rotation'], d['rotationMatrix'])
    assert np.array_equal(sdk[0]['depth_to_color']['translation_mm'],d['translationMatrix'])
    report['feeding_recorded_sdk_extrinsics_and_scale_exact'] = True
    report['sources'].append(binding(feed_cal))
    stems = dict(FEEDING='FEEDING Orbbec Femto Bolt_CL8654103ML_20260918124300',
                 FISHSA='G10 Orbbec Femto Bolt_CL8654103L3_20260826094541',L3='20260816_132923_CL8654103L3',LW='20260816_132950_CL8654103LW')
    for name, stem in stems.items():
        metadata_path = WORK/'data/Metadata'/f'{stem}_frame_timestamps.json'
        meta = read(metadata_path)
        colors = sorted(meta['color']['frame_list'],key=lambda x:x['timestamp_us'])
        depths = sorted(meta['depth']['frame_list'],key=lambda x:x['timestamp_us'])
        ct = np.array([x['timestamp_us'] for x in colors],dtype=np.int64)
        dt = np.array([x['timestamp_us'] for x in depths],dtype=np.int64)
        assert np.all(np.diff(ct)>0) and np.all(np.diff(dt)>0)
        if name=='FEEDING':
            rows = records(WORK/'data/AlignedFeeding_v1/manifest.jsonl')
            for r in rows:
                i=r['frame']; assert r['rgb_timestamp_us']==ct[i] and r['depth_timestamp_us']==dt[i]
                assert r['delta_us']==int(ct[i]-dt[i]) and abs(r['delta_us'])<=5000
                assert nearest(dt,int(ct[i]))==i
            used = [r['frame'] for r in rows]
            policy = 'SORTED_ORDINAL_BOTH_STREAMS; EVERY_STORED_PAIR_ALSO_NEAREST_DEPTH'
        elif name=='FISHSA':
            rows=records(WORK/'data/AlignedDataset_v1/manifest.jsonl')
            for r in rows:
                di,ci=r['source_depth_index'],r['source_color_index']
                assert r['depth_timestamp_us']==dt[di] and r['color_timestamp_us']==ct[ci]
                assert r['delta_us']==int(ct[ci]-dt[di]) and abs(r['delta_us'])<=5000
                assert nearest(ct,int(dt[di]))==ci and r['frame_id']==di+1
            used=[r['source_depth_index'] for r in rows]
            assert len(set(r['source_color_index'] for r in rows))==len(rows)
            policy='DEPTH_CENTRIC_NEAREST_RGB; UNIQUE_RGB; FRAME_ID_DEPTH_INDEX_PLUS_1'
        else:
            rows=read(WORK/'data/AnnotationNewBags_20260919'/name/'manifest.json')['frames']
            for r in rows:
                ci,di=r['frame'],r['depth_index']
                assert r['rgb_timestamp_us']==ct[ci] and r['depth_timestamp_us']==dt[di]
                assert r['delta_us']==int(ct[ci]-dt[di]) and r['depth_usable']==(abs(r['delta_us'])<=5000)
                assert nearest(dt,int(ct[ci]))==di
            used=[r['depth_index'] for r in rows]
            policy='RGB_CENTRIC_NEAREST_DEPTH; REUSE_ALLOWED; ABOVE_5_MS_MISSING'
        report['metadata'][name]=dict(rows=len(rows),policy=policy,unique_depth_frames=len(set(used)),reused_depth_assignments=len(used)-len(set(used)),
                                    usable_pairs=sum(abs(r['delta_us'])<=5000 for r in rows),minimum_delta_us=min(r['delta_us'] for r in rows),maximum_delta_us=max(r['delta_us'] for r in rows))
        report['sources'].append(binding(metadata_path))
    report['scope']=dict(RGB_read=False,depth_pixels_read=False,GT_read=False,SDK_playback=False,model_HTTP=0,tracker_run=False)
    with (HERE/'PROJECTION_CHECKS.json').open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(passed=True,math=report['math'],metadata=report['metadata']),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
