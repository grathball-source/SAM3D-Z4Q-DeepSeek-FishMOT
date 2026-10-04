"""Fixed actual correspondence audit; no transform search or tracker state."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip, hashlib, importlib.util, json, math, platform, shutil, subprocess, sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = '1ff8896254cde32efa79927fe95af29b8ac4937c'
DS22 = ROOT / 'experiments/ds22_local_background_depth'
sys.path.insert(0, str(DS22))
spec = importlib.util.spec_from_file_location('ds23_prior_ds22', DS22/'run.py')
prior = importlib.util.module_from_spec(spec); spec.loader.exec_module(prior)
old = prior.old
import source
from source import RawDepth
from geometry import Geometry
from build_aligned_dataset import rasterize
import cv2
import numpy as np
cv2.setNumThreads(1)
sys.path.insert(0, str(HERE))

def save(name, value): old.write_new(HERE/name, value)
def verify_freeze():
    f = old.read(HERE/'FREEZE.json')
    for p in f['files']: old.verify_item(p)
    return f

def calibration(segment):
    if segment.startswith('feeding_'):
        path = old.DATA/'calibration.json'; profiles = old.read(path)['recorded_profiles']
    elif segment.startswith('fishsa_'):
        path = old.WORK/'data/AlignedDataset_v1/calibration/recorded_profiles.json'; profiles = old.read(path)
    else:
        path = old.WORK/'data/AnnotationNewBags_20260919'/segment/'calibration.json'; profiles = old.read(path)
    geom = Geometry(profiles,640,360)
    geom.kc[0,2] += (640/geom.color['width']-1)/2
    geom.kc[1,2] += (360/geom.color['height']-1)/2
    assert (geom.color['width'],geom.color['height']) == (1920,1080)
    return geom, old.artifact(path)

def describe(a):
    a = np.asarray(a)
    if not a.size: return dict(n=0,median=None,p90=None,max=None)
    assert np.isfinite(a).all()
    return dict(n=int(a.size),median=float(np.median(a)),p90=float(np.percentile(a,90)),max=float(np.max(a)))

def check_projection(arrays, geom):
    """Rebuild original nearest-Z; independently project real winning points."""
    depth,index,native = (arrays[k] for k in ('depth','source_index','native_depth'))
    valid = np.isfinite(depth)&(depth>0); available = arrays['source_binding']['sensor_available']
    if not available:
        assert not valid.any() and np.all(index == -1)
        return dict(status='MISSING_BY_ORIGINAL_POLICY',valid_pixels=0,physical_accuracy='UNKNOWN')
    flat = native.ravel(); candidates = np.flatnonzero(np.isfinite(flat)&(flat>0))
    xyz = geom.rc.reshape(-1,3)[candidates]*flat[candidates,None]+geom.t
    rebuilt,reindex = rasterize(geom.project_xyz(xyz),xyz[:,2],candidates,360,640)
    assert np.array_equal(rebuilt,depth), 'REPROJECTED_DEPTH_MISMATCH'
    assert np.array_equal(reindex,index), 'REPROJECTED_SOURCE_INDEX_MISMATCH'
    winners = index[valid]; xyz = geom.rc.reshape(-1,3)[winners]*flat[winners,None]+geom.t
    custom = geom.project_xyz(xyz)
    independent = cv2.projectPoints(xyz,np.zeros(3),np.zeros(3),geom.kc,geom.dc)[0].reshape(-1,2)
    yy,xx = np.nonzero(valid); expected = np.column_stack((xx,yy))
    assert np.array_equal(depth[valid],xyz[:,2].astype('f4'))
    assert np.array_equal(np.rint(custom).astype(int),expected)
    error = np.linalg.norm(independent-custom,axis=1)
    assert float(error.max(initial=0.)) < 1e-6
    return dict(status='EXACT_REPROJECTION_AND_SOURCE_INDEX_PASS',valid_pixels=int(valid.sum()),
        unique_native_sources=int(len(np.unique(winners))),
        independent_opencv_formula_error_px=describe(error),
        raster_pixel_component_error_px=describe(np.abs(independent-expected).ravel()),
        independently_rounded_pixel_mismatches=int(np.any(np.rint(independent).astype(int)!=expected,axis=1).sum()),
        rgb_camera_Z_bit_exact=True,nearest_Z_and_native_index_tie_bit_exact=True,
        depth_undistortion_roundtrip_max_px=geom.roundtrip_max_px,
        physical_accuracy='UNKNOWN; RECORDED_CALIBRATION_SOFTWARE_CONSISTENCY_ONLY')

def rgb_frame(sensor, arrays):
    """Same timestamp row; RGB is private input diagnosis only."""
    g = arrays['global_frame']; row = sensor.metadata[g]
    if sensor.kind == 'FEEDING':
        original,small = old.DATA/row['rgb_original'],old.DATA/row['rgb']; timestamp = row['rgb_timestamp_us']
        expected_sha = row['source_rgb_sha256']
    elif sensor.kind == 'FISHSA':
        original,small = sensor.base/row['rgb_original'],sensor.base/row['rgb']; timestamp = row['color_timestamp_us']
        assert row['source_color_index']+1 == g
        expected_sha = row['source_rgb_sha256']
    else:
        original,small = Path(row['rgb_source']),None; timestamp = row['rgb_timestamp_us']
        expected_sha = row['rgb_sha256']
    pin = old.artifact(original); assert pin['sha256'] == expected_sha
    image = cv2.imread(str(original)); assert image.shape == (1080,1920,3)
    resized = cv2.resize(image,(640,360),interpolation=cv2.INTER_AREA)
    pins = [pin]
    if small:
        actual = cv2.imread(str(small)); assert np.array_equal(actual,resized)
        pins.append(old.artifact(small))
    assert abs(timestamp/1e6-arrays['time']) < 1e-6
    delta = int(timestamp-row['depth_timestamp_us']); assert delta == row['delta_us']
    assert (abs(delta)<=5000) == arrays['source_binding']['sensor_available']
    return resized,dict(original=pin,all_RGB_files=pins,original_shape=[1080,1920,3],
        resized_shape=[360,640,3],original_sha_matches_manifest=True,
        saved_small_RGB_bit_exact_to_INTER_AREA=True if small else None,
        original_to_small_pixel_center='(old+.5)/3-.5',RGB_timestamp_us=timestamp,
        depth_timestamp_us=row['depth_timestamp_us'],delta_us=delta,
        physical_synchronization='RECORDED_TIMESTAMP_ONLY; WATER_PATH_OR_HARDWARE_LATENCY_UNKNOWN',
        use='PRIVATE_INPUT_DIAGNOSIS_ONLY; NO_TRACKER_APPEARANCE')

def initialize():
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==BASE
    assert not subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).strip()
    prior.verify_measurement_seal()
    files = [old.artifact(DS22/n) for n in ('FREEZE.json','MEASUREMENTS_SEALED.json','MEASUREMENTS.jsonl.gz','PRIVATE_VISUALS.json')]
    files += [old.artifact(prior.DS21/n) for n in ('FEATURES_SEALED.json','FEATURES.jsonl.gz','OBSERVATION_FACTS.jsonl.gz','BEGIN_SOURCE_CHECK.json')]
    for p in files:
        path = Path(p['path']); blob=subprocess.check_output(['git','show',BASE+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest()==p['sha256']
    save('INPUT_PINS.json',dict(files=files,base_commit=BASE,no_new_GT=True))
    ps="$ds23OS=Get-CimInstance Win32_OperatingSystem; $ds23CPU=Get-CimInstance Win32_Processor; [pscustomobject]@{free_ram_kib=$ds23OS.FreePhysicalMemory;total_ram_kib=$ds23OS.TotalVisibleMemorySize;cpu_name=$ds23CPU.Name;physical_cores=$ds23CPU.NumberOfCores;logical_processors=$ds23CPU.NumberOfLogicalProcessors} | ConvertTo-Json -Compress"
    live=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True)); disk=shutil.disk_usage(ROOT)
    assert live['free_ram_kib']>1024**2 and disk.free>1024**3
    save('ENVIRONMENT_INITIAL.json',dict(checked_utc=datetime.now(timezone.utc).isoformat(),live=live,disk_free_bytes=disk.free,
        python=sys.executable,version=platform.python_version(),numpy=np.__version__,opencv=cv2.__version__,
        CPU_jobs=1,library_threads=1,GPU=False,server=False,new_model_http=0,cost_usd=0))
    save('OLD_TRACKED_BASE.json',dict(base_commit=BASE,handoff=old.artifact(ROOT/'research/HANDOFF.md'),gitignore=old.artifact(ROOT/'.gitignore')))
    print('Actual previous seals, source commits and live local resources verified',flush=True)

def freeze():
    from spatial import PARAMETERS
    checks=old.read(HERE/'CHECKS_FINAL.json');assert checks['status']=='PASS'
    for p in checks['code']:old.verify_item(p)
    assert old.read(HERE/'PROJECTION_CHECKS.json')['passed'] is True
    assert old.read(HERE/'MASK_TIME_CHECKS.json')['status']=='PASS_FIXED_MASK_FRAME_SOURCE_CONTRACT'
    files = old.read(HERE/'INPUT_PINS.json')['files'] + old.read(prior.DS21/'BEGIN_SOURCE_CHECK.json')['artifacts']
    files += [old.artifact(p) for p in HERE.iterdir() if p.suffix in ('.py','.md')]
    for name in old.SEGMENTS:
        _,pin = calibration(name); files.append(pin)
        sensor = RawDepth(name)
        path = (old.DATA/'manifest.jsonl' if sensor.kind=='FEEDING' else sensor.base/('manifest.jsonl' if sensor.kind=='FISHSA' else 'manifest.json'))
        files.append(old.artifact(path));sensor.close()
    for mod in tuple(sys.modules.values()):
        path=getattr(mod,'__file__',None)
        if path and Path(path).suffix=='.py' and (str(ROOT) in str(Path(path).resolve()) or 'E:\\CAU\\D-MOT\\tools' in str(Path(path).resolve())):files.append(old.artifact(path))
    files={p['path']:p for p in files}
    for p in files.values():old.verify_item(p)
    save('FREEZE.json',dict(status='FIXED_SOURCES_AND_DIAGNOSTIC_RULES_FROZEN_BEFORE_FULL_AUDIT',frozen_utc=datetime.now(timezone.utc).isoformat(),
        base_commit=BASE,files=list(files.values()),parameters=PARAMETERS,actions=90,unique_endpoints=171,source_frames=168,
        actual_source_module=source.__file__,RGB_use='PRIVATE_INPUT_DIAGNOSIS',GT=False,transform_search=False,
        new_prediction=False,new_scoring=False,new_model_http=0,cost_usd=0))
    print('All source bytes and fixed no-shift diagnostics frozen',flush=True)

def audit():
    from spatial import spatial_metrics,render_figure
    verify_freeze(); features=prior.load_features(); facts,assignments,pins=prior.load_sources(features)
    saved={r['fact_id']:r['measurement'] for r in old.rows(DS22/'MEASUREMENTS.jsonl.gz')}
    visual=old.read(DS22/'PRIVATE_VISUALS.json')
    selected={fid for v in visual['figures'] for fid in v['actual_endpoint_fact_ids']}
    frames=[]; endpoints=[]; figures=[]; allpins={}
    with gzip.open(HERE/'ENDPOINTS.jsonl.gz','xt',encoding='utf-8',newline='\n') as out:
        for segment in old.SEGMENTS:
            geom,cal=calibration(segment);sensor=RawDepth(segment)
            try:
                for frame in sorted({f['frame'] for f in facts.values() if f['segment']==segment}):
                    arrays=prior.load_endpoint_frame(segment,frame,facts,assignments,sensor)
                    projection=check_projection(arrays,geom); rgb,binding=rgb_frame(sensor,arrays)
                    for pin in binding['all_RGB_files']:allpins[pin['path']]=pin
                    record=dict(segment=segment,frame=frame,global_frame=arrays['global_frame'],time=arrays['time'],
                        projection=projection,calibration=cal,RGB_binding=binding,raw_source_binding=arrays['source_binding'])
                    frames.append(record)
                    for fact in sorted((f for f in facts.values() if (f['segment'],f['frame'])==(segment,frame)),key=lambda f:f['native']):
                        fid=fact['fact_id']; m,debug=spatial_metrics(arrays['masks'][fact['native']],arrays['depth'],rgb)
                        entry=dict(fact_id=fid,segment=segment,frame=frame,global_frame=arrays['global_frame'],native=fact['native'],
                            time=arrays['time'],spatial=m,DS22_status=saved[fid]['status'],DS22_reason=saved[fid]['reason'],
                            original_mask_binding=fact['certificate']['mask_binding'],frame_record_sha256=prior.digest(record),
                            physical_mask_truth='UNKNOWN',physical_depth_structure_truth='UNKNOWN',identity='UNKNOWN',state_action='NONE')
                        endpoints.append(entry);out.write(json.dumps(entry,separators=(',',':'),allow_nan=False)+'\n')
                        if fid in selected:
                            path=HERE/'private'/f'{segment}_F{frame}_n{fact["native"]}.png'
                            detail=render_figure(path,rgb,arrays['depth'],arrays['masks'],fact['native'],fid,m,debug)
                            figures.append(dict(fact_id=fid,artifact=old.artifact(path),render=detail,
                                RGB_binding=binding,endpoint_record_sha256=prior.digest(entry),GT=False,future=False))
                print('AUDITED',segment,'frames',sum(r['segment']==segment for r in frames),flush=True)
            finally:sensor.close()
    assert len(endpoints)==171 and len(frames)==168 and {e['fact_id'] for e in endpoints}==set(facts)
    assert {f['fact_id'] for f in figures}==selected
    save('FRAMES.json',dict(frames=frames,no_transform_search=True,no_GT=True))
    save('PRIVATE_VISUALS.json',dict(figures=figures,fixed_old_selection=old.artifact(DS22/'PRIVATE_VISUALS.json'),private=True,
        images_are_input_diagnostics_not_tracking_features=True,all_pixels_excluded_from_git=True))
    save('SOURCE_ACCESS.json',dict(raw_depth_fields_read=source.FIELD_READS,source_pins=pins,RGB_files=list(allpins.values()),
        no_GT_raster=True,no_instance_id=True,no_restored=True,no_later_RGB_frame_after_original_action=True,
        archived_depth_pair_can_be_1_to_2_ms_after_RGB=True,strict_sensor_realtime_causality='NOT_CERTIFIED',
        upstream_saved_SAM3_lookahead='NOT_CERTIFIED',new_model_http=0,cost_usd=0))
    verify_freeze()
    save('AUDIT_SEALED.json',dict(status='ALL_FIXED_CORRESPONDENCE_FACTS_SEALED',sealed_utc=datetime.now(timezone.utc).isoformat(),
        endpoints=171,frames=168,actions=90,files=[old.artifact(HERE/n) for n in ('ENDPOINTS.jsonl.gz','FRAMES.json','PRIVATE_VISUALS.json','SOURCE_ACCESS.json')],
        freeze=old.artifact(HERE/'FREEZE.json'),new_prediction=False,new_scoring=False,new_model_http=0,cost_usd=0))
    print('All171 endpoints/168frames sealed; private figures',len(figures),flush=True)

if __name__=='__main__': {'initialize':initialize,'freeze':freeze,'audit':audit}[sys.argv[1]]()
