"""One frozen spatial measurement experiment on all original Z4Q action endpoints."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
import gzip, hashlib, json, os, platform, shutil, subprocess, sys, math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DS21 = ROOT / 'experiments/ds21_z4q_depth_discriminability_audit'
BASE = 'bc1526e89e16040f270639c7620ecb67570775f0'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'experiments/ds20_pending_confirmation_isolation'))
import common as old
from source import RawDepth, native_masks, FIELD_READS
from mixed_depth import array_binding, validate_certificate

def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def save(name, value):
    old.write_new(HERE / name, value)

def endpoint_requests(feature):
    primary = feature['actual_anchor_fact_id']
    assert primary == feature['anchor_fact_ids'][primary_role(feature)]
    return {feature['current_fact_id'], primary, *feature['anchor_fact_ids'].values()}

def primary_role(feature):
    return 'BIRTH_CORE' if feature['origin_rule'] == 'BIRTH_REFINE' else 'D1_WHOLE'

def load_features():
    seal = old.read(DS21 / 'FEATURES_SEALED.json')
    for pin in seal['artifacts']:
        old.verify_item(pin)
    features = list(old.rows(DS21 / 'FEATURES.jsonl.gz'))
    assert len(features) == 90 and len({f['action_id'] for f in features}) == 90
    assert all(not {'physical', 'sealed_physical_record'} & f.keys() for f in features)
    return features

def load_sources(features):
    """Original endpoint facts and same-frame assignments; no physical grades."""
    wanted = set().union(*(endpoint_requests(f) for f in features))
    facts = {r['fact_id']: r for r in old.rows(DS21 / 'OBSERVATION_FACTS.jsonl.gz') if r['fact_id'] in wanted}
    assert set(facts) == wanted
    frames = defaultdict(set)
    for fact in facts.values():
        name, frame, native = fact['segment'], fact['frame'], fact['native']
        assert fact['fact_id'] == f'{name}/F{frame}/n:{native}/observation'
        assert fact['global_frame'] == old.SEGMENTS[name][0] + frame - 1
        assert validate_certificate(fact['certificate'])
        frames[name].add(frame)
    pins = {Path(i['path']).resolve(): i for i in old.read(DS21 / 'BEGIN_SOURCE_CHECK.json')['artifacts']}
    assignments, materials, selected = {}, {}, []
    for name in old.SEGMENTS:
        needed = frames[name]
        source = old.input_dir(name)
        paths = [source / n for n in ('SOURCE_MANIFEST.json', 'assignments.jsonl.gz', 'DEPTH_OBSERVATIONS.jsonl.gz')]
        for p in paths:
            pin = pins[p.resolve()]; old.verify_item(pin); selected.append(pin)
        manifest = old.read(paths[0]); assert manifest['no_GT'] and manifest['no_RGB'] and manifest['no_restored_values']
        assignments[name] = {r['frame']: r for r in old.rows(paths[1]) if r['frame'] in needed}
        materials[name] = {r['frame']: r for r in old.rows(paths[2]) if r['frame'] in needed}
        assert set(assignments[name]) == set(materials[name]) == needed
    for fact in facts.values():
        m = materials[fact['segment']][fact['frame']]
        assert (m['segment'], m['frame'], m['global_frame'], m['time']) == (
            fact['segment'], fact['frame'], fact['global_frame'], fact['time'])
        fact['_raw_measurement'] = m
    return facts, assignments, selected

def load_endpoint_frame(segment, frame, facts, assignments, sensor):
    entries = [f for f in facts.values() if (f['segment'], f['frame']) == (segment, frame)]
    assert entries
    f = entries[0]; m = f['_raw_measurement']; a = assignments[segment][frame]
    assert (a['frame'], a['global_frame_id'], a['time']) == (frame, f['global_frame'], f['time'])
    depth, index, native, binding = sensor(f['global_frame'], f['time'])
    assert binding == m['raw_source_binding'], (segment, frame, 'RAW_SOURCE_MISMATCH')
    masks = native_masks(a)
    for e in entries:
        assert (e['global_frame'], e['time']) == (f['global_frame'], f['time'])
        assert array_binding(masks[e['native']]) == e['certificate']['mask_binding']
        assert e['actual_profile']['frame'] == frame
        assert int(masks[e['native']].sum()) == e['actual_observation']['area']
    return dict(depth=depth, source_index=index, native_depth=native, source_binding=binding,
        masks=masks, segment=segment, frame=frame, global_frame=f['global_frame'], time=f['time'])

def verify_freeze():
    freeze = old.read(HERE / 'FREEZE.json')
    for pin in freeze['files']:
        old.verify_item(pin)
    return freeze

def verify_measurement_seal():
    verify_freeze()
    seal = old.read(HERE / 'MEASUREMENTS_SEALED.json')
    for pin in seal['artifacts']: old.verify_item(pin)
    assert seal['action_count'] == 90 and not seal['physical_labels_read']
    return seal

def compare_endpoints(current, anchor):
    """Measured depth explanations, never a physical identity oracle or veto."""
    pairs = []
    for c in current['components']:
        if not c['qualified']: continue
        for a in anchor['components']:
            if not a['qualified']: continue
            scale = math.sqrt(c['scale_mm']**2 + a['scale_mm']**2 +
                current['background']['residual_scale_mm']**2 + anchor['background']['residual_scale_mm']**2)
            threshold = 90.  # four unchanged 15mm floors -> common scale30, sigma factor3
            gap = abs(c['median_residual_mm'] - a['median_residual_mm'])
            pairs.append(dict(current_support_id=c['support_id'], anchor_support_id=a['support_id'],
                current_sign=c['sign'], anchor_sign=a['sign'], difference_mm=gap,
                common_scale_mm=30., threshold_mm=threshold, compatible=gap <= threshold,
                actual_uncertainty_scale_mm=scale, actual_uncertainty_threshold_mm=max(30.,3.*scale),
                actual_uncertainty_compatible=gap<=max(30.,3.*scale)))
    available = current['status'] == anchor['status'] == 'AVAILABLE'
    status = ('UNKNOWN' if not available or not pairs else
        'DEPTH_EXPLANATION_COMPATIBLE_PROXY' if any(p['compatible'] for p in pairs) else
        'DEPTH_EXPLANATION_CONFLICT_PROXY')
    return dict(status=status, all_qualified_layer_pairs=pairs,
        rule='ANY_PAIR_COMPATIBLE_RETAINS_EXPLANATION; ALL_PAIRS_CONFLICT_REQUIRED; NO_SIGN_PREFERENCE',
        identity='UNKNOWN', state_action='NONE', unknown_is_zero_cost=False)

def measure():
    from measurement import measure_local_background
    verify_freeze(); features = load_features(); facts, assignments, pins = load_sources(features)
    endpoint_measurements = {}; endpoint_frames = defaultdict(set)
    for f in facts.values(): endpoint_frames[f['segment']].add(f['frame'])
    with gzip.open(HERE / 'MEASUREMENTS.jsonl.gz', 'xt', encoding='utf-8', newline='\n') as handle:
        for segment in old.SEGMENTS:
            sensor = RawDepth(segment)
            try:
                for frame in sorted(endpoint_frames[segment]):
                    arrays = load_endpoint_frame(segment, frame, facts, assignments, sensor)
                    for fact in sorted((f for f in facts.values() if (f['segment'], f['frame']) == (segment, frame)), key=lambda f:f['native']):
                        result, _ = measure_local_background(arrays['depth'], arrays['source_index'], arrays['native_depth'],
                            arrays['masks'], fact['native'], segment, frame, arrays['global_frame'], arrays['time'],
                            source_binding=arrays['source_binding'], expected_source_binding=fact['_raw_measurement']['raw_source_binding'])
                        entry = dict(fact_id=fact['fact_id'], measurement=result, old_certificate_sha256=fact['certificate']['certificate_sha256'],
                            original_fact_citations=fact['citations'], original_identity_history=fact['source_generation_and_identity_epoch'])
                        endpoint_measurements[fact['fact_id']] = entry
                        handle.write(json.dumps(entry,separators=(',', ':'),allow_nan=False)+'\n')
                print('MEASURED', segment, len(endpoint_frames[segment]), 'frames', flush=True)
            finally: sensor.close()
    features_out=[]
    for feature in features:
        current = endpoint_measurements[feature['current_fact_id']]['measurement']
        comparisons = {}
        for role, fid in feature['anchor_fact_ids'].items():
            assert facts[fid]['time'] < feature['current_time'] and facts[fid]['frame'] < feature['frame']
            comparisons[role] = dict(anchor_fact_id=fid, current_fact_id=feature['current_fact_id'],
                comparison=compare_endpoints(current, endpoint_measurements[fid]['measurement']))
        features_out.append(dict(action_id=feature['action_id'], segment=feature['segment'], frame=feature['frame'],
            global_frame=feature['global_frame'], origin_rule=feature['origin_rule'],
            original_scoring_roi=feature['original_scoring_roi'], comparisons=comparisons,
            primary_role=primary_role(feature),
            original_actual_publication_binding=feature['actual_publication_binding'],
            original_action_feature_sha256=digest(feature)))
    save('ACTION_FEATURES.json', dict(actions=features_out, physical_labels_read=False))
    save('SOURCE_ACCESS.json',dict(raw_depth_fields_read=FIELD_READS,selected_source_files=pins,
        RGB=False,GT=False,restored=False,future_after_action=False,source_frames=len(set((f['segment'],f['frame']) for f in facts.values()))))
    save('MEASUREMENTS_SEALED.json',dict(status='ALL_FIXED_MEASUREMENTS_AND_EXPLANATIONS_SEALED_BEFORE_LABEL_JOIN',
        sealed_at_utc=datetime.now(timezone.utc).isoformat(),action_count=90,unique_endpoint_count=len(endpoint_measurements),
        primary_endpoint_roles=180,birth_secondary_roles=8,physical_labels_read=False,
        measurement_artifact=old.artifact(HERE/'MEASUREMENTS.jsonl.gz'),
        artifacts=[old.artifact(HERE/n) for n in ('MEASUREMENTS.jsonl.gz','ACTION_FEATURES.json','SOURCE_ACCESS.json')],
        freeze=old.artifact(HERE/'FREEZE.json'),new_prediction=False,new_scoring=False,new_model_http=0,cost_usd=0))
    print('All90 actions measured and sealed',len(endpoint_measurements),'unique endpoints',flush=True)

def join_labels():
    seal = verify_measurement_seal(); started = datetime.now(timezone.utc).isoformat()
    original = {f['action_id']:f for f in load_features()}
    actions = old.read(DS21/'ACTIONS.json')['actions']
    measures = {r['fact_id']:r['measurement'] for r in old.rows(HERE/'MEASUREMENTS.jsonl.gz')}
    extracted = {r['action_id']:r for r in old.read(HERE/'ACTION_FEATURES.json')['actions']}
    result=[]; counts=Counter(); endpoints=Counter()
    for action in actions:
        f=original[action['action_id']]; new=extracted[action['action_id']]
        assert all(action[k] == v for k,v in f.items()) and new['original_action_feature_sha256']==digest(f)
        primary=new['comparisons'][new['primary_role']]
        counts[(action['physical'],primary['comparison']['status'])]+=1
        for side,fid in (('current',primary['current_fact_id']),('anchor',primary['anchor_fact_id'])):
            endpoints[(action['physical'],side,measures[fid]['status'])]+=1
        result.append(dict(new,physical=action['physical'],actual_reference_physical=action['actual_reference_physical'],
            original_actual_anchor=action['actual_old_anchor'],primary_comparison=primary))
    assert len(result)==90
    save('RESULTS.json',dict(status='COMPLETE_FIXED_LOCAL_BACKGROUND_MEASUREMENT_EXPERIMENT',
        actions=result,edge_crosstab=[dict(physical=g,explanation=s,actions=n) for (g,s),n in sorted(counts.items())],
        endpoint_crosstab=[dict(physical=g,side=t,availability=s,endpoints=n) for (g,t,s),n in sorted(endpoints.items())],
        unique_measurement_statuses=dict(Counter(m['status'] for m in measures.values())),
        original_grades=dict(Counter(a['physical'] for a in actions)),
        measurements_seal=old.artifact(HERE/'MEASUREMENTS_SEALED.json'),label_source=old.artifact(DS21/'ACTIONS.json'),
        label_join_started_utc=started,label_join_finished_utc=datetime.now(timezone.utc).isoformat(),
        new_metrics=None,new_prediction=False,new_scoring=False,new_model_http=0,cost_usd=0,
        background_and_fish_truth='UNKNOWN; OBSERVED_PROXY_SUPPORT_ONLY',independent_validation=False))
    print('LABEL_JOIN',json.dumps([dict(grade=g,status=s,n=n) for(g,s),n in sorted(counts.items())]),flush=True)

def initialize():
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==BASE
    ps="$ds22OS=Get-CimInstance Win32_OperatingSystem; $ds22CPU=Get-CimInstance Win32_Processor; $ds22P=Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' }; [pscustomobject]@{free_ram_kib=$ds22OS.FreePhysicalMemory;total_ram_kib=$ds22OS.TotalVisibleMemorySize;cpu_name=$ds22CPU.Name;physical_cores=$ds22CPU.NumberOfCores;logical_processors=$ds22CPU.NumberOfLogicalProcessors;existing_python_processes=@($ds22P).Count} | ConvertTo-Json -Compress"
    live=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True)); disk=shutil.disk_usage(ROOT)
    assert live['free_ram_kib']>1024**2 and disk.free>1024**3
    save('ENVIRONMENT_INITIAL.json',dict(base_commit=BASE,checked_utc=datetime.now(timezone.utc).isoformat(),
        live=live,disk_free_bytes=disk.free,python=sys.executable,version=platform.python_version(),
        cpu_jobs=1,library_threads=1,GPU=False,server=False,new_model_http=0,cost_usd=0))
    save('OLD_TRACKED_BASE.json',dict(base_commit=BASE,
        handoff=old.artifact(ROOT/'research/HANDOFF.md'),gitignore=old.artifact(ROOT/'.gitignore')))
    selected=[old.artifact(DS21/n) for n in ('FEATURES_SEALED.json','BEGIN_SOURCE_CHECK.json','FEATURES.jsonl.gz',
        'OBSERVATION_FACTS.jsonl.gz','ACTIONS.json','PRIVATE_VISUALS.json','DIAGNOSTIC_RESULTS.json')]
    for p in selected:
        path=Path(p['path']); blob=subprocess.check_output(['git','show',BASE+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest()==p['sha256']
    save('INPUT_PINS.json',dict(status='EXACT_DS21_BASE_BYTES_VERIFIED',files=selected,physical_labels_content_opened=False))
    print('DS22 live local resources and exact previous-source bytes verified')

def freeze():
    from measurement import PARAMETERS
    checks=old.read(HERE/'CHECKS.json'); assert checks['status']=='PASS'
    for p in checks['code']:old.verify_item(p)
    files=[old.artifact(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.suffix in ('.py','.md')]
    files+=old.read(HERE/'INPUT_PINS.json')['files']
    files+=old.read(DS21/'BEGIN_SOURCE_CHECK.json')['artifacts']
    # Imported repository and task helpers are science dependencies, not environments to modify.
    for mod in tuple(sys.modules.values()):
        path=getattr(mod,'__file__',None)
        if path and Path(path).suffix=='.py' and (str(ROOT) in str(Path(path).resolve()) or 'E:\\CAU\\D-MOT\\tools' in str(Path(path).resolve())):
            files.append(old.artifact(path))
    unique={p['path']:p for p in files}
    for p in unique.values():old.verify_item(p)
    save('FREEZE.json',dict(status='FROZEN_BEFORE_FULL_MEASUREMENT_AND_LABEL_JOIN',base_commit=BASE,
        frozen_utc=datetime.now(timezone.utc).isoformat(),files=list(unique.values()),parameters=PARAMETERS,
        comparison_rule='ALL_QUALIFIED_SUPPORT_PAIRS_CONFLICT_ONLY; COMMON_4_COMPONENT_SCALE; UNKNOWN_PRESERVED',
        cohort_actions=90,new_model_http=0,cost_usd=0,new_prediction=False,new_scoring=False))
    print('DS22 fixed single representation and all dependencies frozen')

if __name__=='__main__':
    {'initialize':initialize,'freeze':freeze,'measure':measure,'join':join_labels}[sys.argv[1]]()
