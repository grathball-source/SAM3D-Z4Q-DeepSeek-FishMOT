"""Read-only audit of every sealed original Z4Q candidate and durable action.

No tracker replay, metric calculation, pixel raster, GT loader or model route.
Features are written and hashed before opening existing postseal physical labels.
"""
from __future__ import annotations
import copy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DS20 = ROOT / 'experiments/ds20_pending_confirmation_isolation'
BASE = '71e86e3daeca33b86497d002be8cc0894e4bd99f'
sys.dont_write_bytecode = True
sys.path.insert(0, str(DS20))
import common as old
from mixed_depth import bind_measurement, validate_bound_measurement, validate_certificate, PARAMETERS, SCALAR_FIELDS, SCHEMA

ROLE_PART = {'D1_WHOLE': 'whole', 'BIRTH_WHOLE': 'whole',
             'BIRTH_CORE': 'birth_core', 'S0_ADAPTIVE_CORE': 'core'}
PART_ROLE = {'whole': 'D1_WHOLE', 'birth_core': 'BIRTH_CORE', 'core': 'S0_ADAPTIVE_CORE'}
UNCERTIFIED = 'UNKNOWN: ORIGINAL_TRACE_DOES_NOT_EXPORT_SOURCE_GENERATION_OR_IDENTITY_EPOCH'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def physical_files(path):
    """Expand only immutable JSONL headers; no pixel files are opened."""
    path = Path(path)
    result = [path]
    if str(path).endswith('.jsonl.gz'):
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            line = next(handle, None)
        header = json.loads(line) if line else {}
        if header.get('kind') == 'CHUNKED_JSONL_REFERENCE':
            for part in header['parts']:
                target = path.parent / part['name']
                assert target.resolve().parent == path.resolve().parent
                assert target.stat().st_size == part['bytes'] and old.sha(target) == part['sha256']
                result.append(target)
    return result


def sourced_rows(path):
    """Citations hash UTF-8 logical text with LF; compressed file SHA is separate."""
    path = Path(path)
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as handle:
        first = next(handle, None)
        if first is None:
            return
        header = json.loads(first)
        if header.get('kind') == 'CHUNKED_JSONL_REFERENCE':
            assert next(handle, None) is None
            count = 0
            for part in header['parts']:
                for value, citation in sourced_rows(path.parent / part['name']):
                    count += 1
                    yield value, citation
            assert count == header['rows']
            return
        assert header.get('kind') != 'SEALED_EXTERNAL_JSONL_REFERENCE', 'Explicit cache producer only'
        def entry(line, ordinal):
            return json.loads(line), dict(path=str(path.resolve()), line=ordinal,
                logical_text_lf_sha256=hashlib.sha256(line.encode()).hexdigest())
        yield entry(first, 1)
        for ordinal, line in enumerate(handle, 2):
            yield entry(line, ordinal)


def verify_freeze():
    frozen = old.read(HERE / 'FREEZE.json')
    assert frozen['status'] == 'FROZEN_BEFORE_DIAGNOSTIC_FEATURES_AND_LABEL_JOIN'
    for path, expected in frozen['code'].items():
        actual = old.artifact(path)
        assert actual['sha256'] == expected['sha256'] and actual['bytes'] == expected['bytes'], ('frozen code changed', path)
    return old.artifact(HERE / 'FREEZE.json')


def check_sources():
    task_freeze = verify_freeze()
    manifest_path = DS20 / 'PUBLIC_ARTIFACT_MANIFEST.json'
    all_seal_path = DS20 / 'run/ALL_PREDICTIONS_SEALED.json'
    for path in (manifest_path, all_seal_path):
        saved = subprocess.run(['git', 'show', BASE + ':' + path.relative_to(ROOT).as_posix()],
            cwd=ROOT, check=True, capture_output=True).stdout
        assert hashlib.sha256(saved).hexdigest() == old.sha(path), ('base pin changed', path)
    manifest = old.read(manifest_path)
    pins = {Path(item['path']).resolve(): item for item in manifest['files']}
    all_seal = old.read(all_seal_path)
    assert all_seal['status'] == 'ALL_PREDICTIONS_AND_ACCESS_SEALED'
    assert all_seal['frames'] == sum(b-a+1 for a, b in old.SEGMENTS.values()) == 20098
    checks = {str(manifest_path.resolve()): old.artifact(manifest_path),
              str(all_seal_path.resolve()): old.artifact(all_seal_path)}
    for name in old.SEGMENTS:
        old.verify_item(all_seal['seals'][name])
        public = DS20 / 'run' / name / 'public'
        seal_path = public / 'PREDICTIONS_SEALED.json'
        seal = old.read(seal_path)
        assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
        assert seal['frames'] == old.SEGMENTS[name][1] - old.SEGMENTS[name][0] + 1
        assert seal['published_frames'] == seal['frames'] and 'Z4Q_FROZEN' in seal['arms']
        checks[str(seal_path.resolve())] = old.artifact(seal_path)
        for filename, expected in seal['artifacts_sha256'].items():
            path = public / filename
            assert path.resolve().parent == public.resolve()
            item = old.artifact(path)
            assert item['sha256'] == expected, (name, filename, 'prediction seal')
            checks[str(path.resolve())] = item
        source_freeze = old.read(public / 'FREEZE.json')
        source_manifest = old.input_dir(name) / 'SOURCE_MANIFEST.json'
        assert source_freeze['source_manifest'] == old.artifact(source_manifest)
        source = old.read(source_manifest)
        assert source['no_GT'] and source['no_RGB'] and source['no_restored_values']
        checks[str(source_manifest.resolve())] = old.artifact(source_manifest)
        for item in source['derived_inputs'].values():
            old.verify_item(item)
            checks[str(Path(item['path']).resolve())] = item
        # Hash raw-source inventory, never open its private raster dependencies.
        old.verify_item(source['raw_sources'])
        checks[str(Path(source['raw_sources']['path']).resolve())] = source['raw_sources']
        reference = old.cache_reference(name)
        for key in ('source', 'source_seal', 'source_freeze', 'source_ledger'):
            item = reference[key]
            checks[str(Path(item['path']).resolve())] = item
        for item in reference['parts']:
            checks[str(Path(item['path']).resolve())] = item
        label_path = public / 'AUTOMATIC_RECONNECT_AUDIT.json'
        # Existing postseal label file is pinned, but content is opened only after feature seal.
        label_pin = pins[label_path.resolve()]
        old.verify_item(label_pin)
        checks[str(label_path.resolve())] = {k: label_pin[k] for k in ('path', 'bytes', 'sha256')}
        print('SOURCE_CHECK', name, 'PASS', flush=True)
    return dict(status='ALL_EIGHT_ORIGINAL_PREDICTION_AND_CACHE_SEALS_VERIFIED',
        base_commit=BASE, freeze=task_freeze, verified_at_utc=datetime.now(timezone.utc).isoformat(), artifacts=list(checks.values()),
        parameters=PARAMETERS, physical_labels_opened=False, GT_raster_read=False,
        new_model_http=0, model_cost_usd=0,
        row_hash_policy='UTF8_LOGICAL_TEXT_LF_NORMALIZED; PHYSICAL_COMPRESSED_SOURCE_SHA_SEPARATE')


def action_id(name, frame, action):
    rule = 'BIRTH_REFINE' if action.get('phase') == 'birth' else 'D1_DELAYED'
    return f'{name}/F{frame}/n:{action["native_id"]}->p:{action["canonical_id"]}/{rule}'


def fact_id(name, frame, native):
    return f'{name}/F{frame}/n:{native}/observation'


def source_binding(action, transaction):
    n, k = action['native_id'], action['canonical_id']
    candidates = [v for v in transaction['automatic_candidate_events'] if v['event'] == action]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate['applied_at_first_publication'] == (transaction['actual_published_mapping'][str(n)] == k)
    assert candidate['durable_alias_after_commit'] == (transaction['actual_alias_targets'].get(str(n)) == k)
    assert candidate['applied_at_first_publication'] and candidate['durable_alias_after_commit']
    assert not candidate['overridden_by_explicit_transaction']
    assert candidate in transaction['durable_automatic_commits']
    return copy.deepcopy(candidate)


def anchor_refs(name, action, frame):
    """Only literal exported anchors; a scalar's age never invents an endpoint."""
    anchor = action.get('old_anchor')
    refs = {}
    if action.get('phase') == 'birth':
        for part, role in (('core', 'BIRTH_CORE'), ('whole', 'BIRTH_WHOLE')):
            history = action.get('depth_anchors', {}).get(part)
            if history is not None:
                current = history['anchor']
                assert current['frame'] < frame and current['canonical_id'] == action['canonical_id']
                refs[role] = fact_id(name, current['frame'], current['native_id'])
    elif anchor is not None:
        assert anchor['frame'] < frame and anchor['canonical_id'] == action['canonical_id']
        refs['D1_WHOLE'] = fact_id(name, anchor['frame'], anchor['native_id'])
    if anchor is not None:
        assert anchor['frame'] < frame and anchor['mask'] == f'n:{anchor["native_id"]}'
    return refs


def endpoint_requests(name, frame, action):
    requested = {(frame, action['native_id'])}
    anchor_refs(name, action, frame)
    if action.get('old_anchor') is not None:
        a = action['old_anchor']; requested.add((a['frame'], a['native_id']))
    for history in action.get('depth_anchors', {}).values():
        if history is not None:
            a = history['anchor']; requested.add((a['frame'], a['native_id']))
    return requested


def validate_endpoint(name, row, profile, measured, certificate, *, cutoff=None):
    """Semantics bind original profile, measurement population and exact ROI."""
    f, g, now, n = row['frame'], row['global_frame'], row['time'], certificate['native']
    if cutoff is not None:
        assert f <= cutoff, 'future endpoint rejected'
    assert (certificate['segment'], certificate['frame'], certificate['global_frame'], certificate['time']) == (name, f, g, now)
    assert (measured['segment'], measured['frame'], measured['global_frame'], measured['time']) == (name, f, g, now)
    assert profile['frame'] == f and profile['id'] == n and profile['mask'] == f'n:{n}'
    observation = next(x for x in row['observations'] if x['id'] == n)
    assert observation['mask'] == profile['mask']
    assert validate_certificate(certificate), 'trusted certificate self-consistency'
    actual = measured['adaptive_raw'][str(n)]
    populations = {'D1_WHOLE': observation['depth'], 'BIRTH_WHOLE': profile['whole'],
                   'BIRTH_CORE': profile['core'], 'S0_ADAPTIVE_CORE': actual['core']}
    bindings = {}
    for role, scalar in populations.items():
        binding = bind_measurement(certificate, role, scalar)
        assert validate_bound_measurement(binding, scalar, role, certificate, native=n, frame=f)
        bindings[role] = binding
    for key, value in actual['whole'].items():
        if key in SCALAR_FIELDS:
            assert value == certificate['whole']['inclusive_summary'][key]
    return bindings


def validate_packet(name, row, measured, packet):
    f,g,t=row['frame'],row['global_frame'],row['time']
    assert (packet['segment'],packet['frame'],packet['global_frame'],packet['time'])==(name,f,g,t)
    assert (measured['segment'],measured['frame'],measured['global_frame'],measured['time'])==(name,f,g,t)
    assert packet['schema']==SCHEMA and packet['parameters']==PARAMETERS
    assert packet['no_GT_RGB_future_or_restored_input'] and packet['no_sensor_completion']
    assert packet['source_binding']==dict(measured['raw_source_binding'],frame=f)
    assert not any(packet['source_binding'].get(k,False) for k in ('GT_read','RGB_read','restored_read'))
    shared={k:packet[k] for k in ('segment','frame','global_frame','time','source_binding',
        'actual_depth_binding','actual_source_index_binding','native_depth_binding')}
    assert packet['frame_binding_sha256']==digest(shared)
    for outer,inner in (('actual_depth_binding','aligned_depth'),
            ('actual_source_index_binding','aligned_source_index'),('native_depth_binding','native_depth')):
        assert packet[outer]==measured['raw_source_binding'][inner]
    for n,certificate in packet['objects'].items():
        assert certificate['native']==int(n) and certificate['frame_binding_sha256']==packet['frame_binding_sha256']
        assert (certificate['segment'],certificate['frame'],certificate['global_frame'],certificate['time'])==(name,f,g,t)


def compact_fact(name, row, profile, measured, certificate, citations):
    bindings = validate_endpoint(name, row, profile, measured, certificate)
    return dict(fact_id=fact_id(name, row['frame'], certificate['native']), segment=name,
        frame=row['frame'], global_frame=row['global_frame'], time=row['time'], native=certificate['native'],
        actual_observation=next(x for x in row['observations'] if x['id'] == certificate['native']),
        actual_profile=profile, actual_adaptive_measurement=measured['adaptive_raw'][str(certificate['native'])],
        measurement_bindings=bindings, certificate=certificate,
        citations=citations, source_generation_and_identity_epoch=UNCERTIFIED,
        physical_identity='UNKNOWN: PROVENANCE_AND_SINGLE_LAYER_ARE_NOT_IDENTITY_TRUTH')


def quality_status(current, anchor):
    if anchor is None:
        return 'UNKNOWN_MISSING_EXACT_OLD_ANCHOR'
    return ('BOTH_ELIGIBLE' if current and anchor else 'CURRENT_ONLY_ELIGIBLE' if current
            else 'ANCHOR_ONLY_ELIGIBLE' if anchor else 'NEITHER_ELIGIBLE')


def roi_feature(current, anchor, part, role):
    c = current['certificate'][part]
    cb = current['measurement_bindings'][role]
    a = anchor['certificate'][part] if anchor else None
    ab = anchor['measurement_bindings'][role] if anchor else None
    ce, ae = cb['screened_eligible'], ab['screened_eligible'] if ab else None
    def summary(fact):
        return None if fact is None else {k: fact[k] for k in (
            'fact_id', 'status', 'reason', 'eligible_single', 'summary', 'inclusive_summary',
            'mixture_flag', 'independent_mixture_flag', 'inclusive_mixture_flag',
            'source_ownership_exclusive', 'source_population_unverified_n',
            'scalar_population_difference', 'selected_independent_native_source_n',
            'shared_source_pixels_excluded', 'within_mask_duplicate_pixels_excluded',
            'roi_definition', 'roi_binding', 'inclusive_population_binding')}
    cz, az = c['inclusive_summary']['median'], a['inclusive_summary']['median'] if a else None
    return dict(role=role, part=part, current=summary(c), anchor=summary(a),
        current_eligible=ce, anchor_eligible=ae, both_eligible=bool(ce and ae),
        quality_status=quality_status(ce, ae), current_binding=cb, anchor_binding=ab,
        absolute_inclusive_median_difference_mm=None if cz is None or az is None else abs(cz-az),
        same_identity_version='UNKNOWN', physical_surface_identity='UNKNOWN',
        interpretation='DESCRIPTIVE_DIAGNOSTIC; NO_EDGE_VETO_OR_NEW_TRACKER_ACTION')


def build_feature(record, facts):
    action = record['original_action']; name, frame = record['segment'], record['frame']
    current = facts[fact_id(name, frame, record['source'])]
    primary = record['actual_old_anchor']
    primary_fact = facts[fact_id(name, primary['frame'], primary['native_id'])]
    features = {}
    for part, role in PART_ROLE.items():
        if record['origin_rule']=='BIRTH_REFINE' and part=='whole':
            role='BIRTH_WHOLE'
        requested = record['anchor_fact_ids'].get(role)
        # Alternative ROIs are diagnostic on the literal accepted bank endpoint;
        # Birth core/whole use their separately recorded actual view-bank anchors.
        anchor = facts[requested] if requested else primary_fact
        features[part] = roi_feature(current, anchor, part, role)
        features[part]['anchor_is_actual_scoring_roi'] = requested is not None
    if record['origin_rule'] == 'D1_DELAYED':
        assert action['current_depth'] == current['actual_observation']['depth']['median']
        assert action['history_depth'] == primary_fact['actual_observation']['depth']['median']
        assert action['residual_mm'] == abs(action['current_depth']-action['history_depth'])
    else:
        for part, role in (('core', 'BIRTH_CORE'), ('whole', 'BIRTH_WHOLE')):
            actual = action.get('current_depths', {}).get(part)
            historical = action.get('depth_anchors', {}).get(part)
            if actual is not None:
                stats = current['actual_profile'][part]
                assert all(actual[k] == stats[v] for k, v in (('z','median'),('n','n'),('fraction','valid_fraction'),('mad','mad')))
                assert actual['u'] == max(15., 1.4826 * stats['mad'])
            if historical is not None:
                anchor = facts[record['anchor_fact_ids'][role]]
                stats = anchor['actual_profile'][part]
                assert all(historical[k] == stats[v] for k, v in (('z','median'),('n','n'),('fraction','valid_fraction'),('mad','mad')))
                assert historical['time'] == anchor['time']
                assert historical['u'] == max(15., 1.4826 * stats['mad'])
    return dict(record, current_fact_id=current['fact_id'], actual_anchor_fact_id=primary_fact['fact_id'],
        roi_features=features, current_time=current['time'], actual_anchor_time=primary_fact['time'],
        endpoint_time_gap_s=current['time']-primary_fact['time'], identity_history_contract=UNCERTIFIED,
        original_scoring_roi='birth_core' if record['origin_rule']=='BIRTH_REFINE' else 'whole',
        three_roi_diagnostics_prelabel=True)


def dump(handle, value):
    handle.write(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n')


def collect_segment(name, candidate_output, facts_output):
    public = DS20 / 'run' / name / 'public'
    needed, accepted, counts = set(), [], Counter()
    for transaction, citation in sourced_rows(public / 'TRANSACTIONS.jsonl.gz'):
        if transaction['arm'] != 'Z4Q_FROZEN':
            continue
        counts['frames'] += 1
        frame = transaction['frame']; trace = transaction['controller_trace']
        actions = [e for e in trace['events'] if e.get('kind') == 'reconnect']
        d1_edges, birth_checks = trace.get('edges', []), trace.get('birth_checks', [])
        counts['D1_matrix_edges'] += len(d1_edges)
        counts['BIRTH_checks'] += len(birth_checks)
        counts['D1_matrix_rounds'] += bool(d1_edges)
        counts['BIRTH_check_rounds'] += bool(birth_checks)
        for edge in d1_edges:
            counts['D1_rejected:'+str(edge.get('rejection'))] += 1
        for check in birth_checks:
            counts['BIRTH_rejected:'+str(check.get('rejection'))] += 1
        for action in actions:
            rule = 'BIRTH_REFINE' if action.get('phase') == 'birth' else 'D1_DELAYED'
            counts[rule+'_accepted' if action.get('accepted') else rule+'_uncommitted_proposals'] += 1
            needed.update(endpoint_requests(name, frame, action))
            if not action.get('accepted'):
                continue
            accepted.append(dict(action_id=action_id(name,frame,action), segment=name,
                frame=frame, global_frame=transaction['global_frame'], source=action['native_id'],
                target=action['canonical_id'], origin_rule=rule, original_action=copy.deepcopy(action),
                actual_old_anchor=copy.deepcopy(action['old_anchor']), anchor_fact_ids=anchor_refs(name,action,frame),
                actual_publication_binding=source_binding(action,transaction), transaction_citation=citation,
                candidate_matrix_facts=copy.deepcopy(d1_edges if rule=='D1_DELAYED' else birth_checks),
                D1_other_edge_exact_anchors='UNKNOWN_NOT_EXPORTED; AGE_OR_TARGET_INTEGER_IS_NOT_ANCHOR'))
        if d1_edges or birth_checks or actions:
            for edge in d1_edges + birth_checks:
                if 'native_id' in edge:
                    needed.update(endpoint_requests(name, frame, edge))
            references=[dict(origin_rule=rule,
                native_id=edge['native_id'],canonical_id=edge.get('canonical_id'),
                current_fact_id=fact_id(name,frame,edge['native_id']),
                exact_anchor_fact_ids=anchor_refs(name,edge,frame),
                anchor_status='EXPORTED_EXACT_ANCHOR' if anchor_refs(name,edge,frame) else 'UNKNOWN_NOT_EXPORTED')
                for rule,edges in (('D1_DELAYED',d1_edges),('BIRTH_REFINE',birth_checks))
                for edge in edges if 'native_id' in edge]
            dump(candidate_output,dict(segment=name,frame=frame,global_frame=transaction['global_frame'],
                citation=citation,D1_matrix_edges=d1_edges,BIRTH_checks=birth_checks,proposals=actions,
                measurement_references=references,
                eligible_old=trace['eligible_old'],eligible_new=trace['eligible_new'],
                dummy_cost=1.,ineligible_matrix_entry_cost=1e6,
                complete_D1_matrix_anchor_provenance='UNKNOWN; REJECTED_EDGES_OMIT_EXACT_OLD_ANCHOR',
                missing_eligibility_or_assignment_is_not_reconstructed=True))
    assert counts['frames']==old.SEGMENTS[name][1]-old.SEGMENTS[name][0]+1
    facts = {}
    selected_by_frame = defaultdict(set)
    for frame,n in needed:selected_by_frame[frame].add(n)
    streams = [sourced_rows(old.input_dir(name)/filename) for filename in (
        'observations.jsonl.gz','profiles.jsonl.gz','DEPTH_OBSERVATIONS.jsonl.gz')]
    streams.append(sourced_rows(old.DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz'))
    for entries in zip(*streams, strict=True):
        row, profile_row, measured, packet = [x[0] for x in entries]
        f,g,t=row['frame'],row['global_frame'],row['time']
        assert (profile_row['frame'],profile_row['global_frame'],profile_row['time'])==(f,g,t)
        assert (packet['segment'],packet['frame'],packet['global_frame'],packet['time'])==(name,f,g,t)
        if f not in selected_by_frame:continue
        profiles={x['id']:dict(x,frame=profile_row['frame']) for x in profile_row['observations']}
        assert profile_row['evidence_max_global_frame']<=g
        validate_packet(name,row,measured,packet)
        for n in selected_by_frame[f]:
            certificate=packet['objects'][str(n)]
            record=compact_fact(name,row,profiles[n],measured,certificate,
                dict(zip(('observation','profile','adaptive_measurement','DS18_certificate'),[x[1] for x in entries])))
            facts[record['fact_id']]=record
            dump(facts_output,record)
    assert len(facts)==len(needed),(name,'missing exact endpoint')
    result=[build_feature(record,facts) for record in accepted]
    counts['selected_endpoint_facts']=len(facts)
    counts['accepted_actions']=len(result)
    print('FEATURES',name,dict(counts),flush=True)
    return result,dict(counts)


def bind_labels(features):
    seal=old.read(HERE/'FEATURES_SEALED.json')
    assert seal['status']=='ALL_PRELABEL_FEATURES_SEALED_BEFORE_EXISTING_LABEL_READ'
    for item in seal['artifacts']:old.verify_item(item)
    old.verify_item(seal['begin_source_check'])
    begin=old.read(seal['begin_source_check']['path'])
    pins={Path(item['path']).resolve():item for item in begin['artifacts']}
    output=[];counts=Counter();bank_counts=Counter();quality=Counter()
    for name in old.SEGMENTS:
        label_path=DS20/'run'/name/'public/AUTOMATIC_RECONNECT_AUDIT.json'
        old.verify_item(pins[label_path.resolve()])
        audit=old.read(label_path)
        labels=audit['arms']['Z4Q_FROZEN']
        mine=[x for x in features if x['segment']==name]
        indexed={action_id(name,x['frame'],x['actual_controller_action']):x for x in labels}
        assert len(indexed)==len(labels)==len(mine),(name,'accepted action population mismatch')
        assert Counter(x['physical'] for x in labels)==Counter(audit['counts']['Z4Q_FROZEN'])
        for record in mine:
            label=indexed[record['action_id']]
            assert label['actual_controller_action']==record['original_action']
            assert label['actual_old_anchor']==record['actual_old_anchor']
            assert (label['frame'],label['global_frame'],label['source'],label['target'],label['origin_rule'])==(
                record['frame'],record['global_frame'],record['source'],record['target'],record['origin_rule'])
            assert label['durable_automatic_commit'] and label['applied_at_first_publication'] and label['durable_alias_after_commit']
            item=dict(record,physical=label['physical'],actual_reference_physical=label['actual_reference_physical'],
                relations=label['relations'],sealed_physical_record=label)
            output.append(item);counts[item['physical']]+=1;bank_counts[item['actual_reference_physical']]+=1
            for part, values in item['roi_features'].items():
                quality[(part,values['quality_status'],item['physical'])]+=1
    return output,dict(counts),dict(bank_counts),[
        dict(roi=k[0],quality_status=k[1],physical=k[2],actions=v) for k,v in sorted(quality.items())]


def main():
    assert not (HERE/'ACTIONS.json').exists(),'Exclusive new audit output only'
    begin=check_sources();old.write_new(HERE/'BEGIN_SOURCE_CHECK.json',begin)
    features=[];coverage={}
    with gzip.open(HERE/'CANDIDATES.jsonl.gz','xt',encoding='utf-8') as candidates, \
         gzip.open(HERE/'OBSERVATION_FACTS.jsonl.gz','xt',encoding='utf-8') as facts:
        for name in old.SEGMENTS:
            records,counts=collect_segment(name,candidates,facts)
            features.extend(records);coverage[name]=counts
    with gzip.open(HERE/'FEATURES.jsonl.gz','xt',encoding='utf-8') as handle:
        for feature in features:dump(handle,feature)
    old.write_new(HERE/'FEATURES_SEALED.json',dict(status='ALL_PRELABEL_FEATURES_SEALED_BEFORE_EXISTING_LABEL_READ',
        sealed_at_utc=datetime.now(timezone.utc).isoformat(),
        accepted_actions=len(features),coverage=coverage,begin_source_check=old.artifact(HERE/'BEGIN_SOURCE_CHECK.json'),
        artifacts=[old.artifact(HERE/filename) for filename in ('FEATURES.jsonl.gz','OBSERVATION_FACTS.jsonl.gz','CANDIDATES.jsonl.gz')],
        code=old.artifact(__file__),parameters=PARAMETERS,GT_raster_read=False,new_model_http=0,cost_usd=0,
        no_fit_no_threshold_search_no_prediction_replay=True))
    label_join_started=datetime.now(timezone.utc).isoformat()
    verify_freeze()
    records,counts,bank_counts,crosstab=bind_labels(features)
    old.write_new(HERE/'ACTIONS.json',dict(status='ALL_ORIGINAL_DURABLE_ACTIONS_EXACTLY_BOUND_TO_EXISTING_POSTSEAL_LABELS',
        label_join_started_at_utc=label_join_started,
        label_join_finished_at_utc=datetime.now(timezone.utc).isoformat(),
        actions=records,physical_counts=counts,actual_reference_physical_counts=bank_counts,
        feature_seal=old.artifact(HERE/'FEATURES_SEALED.json'),quality_physical_crosstab=crosstab,
        UNKNOWN_is_not_safe=True,no_edge_veto_executed=True,no_track_or_metric_replay=True,
        interpretation='EXPOSED_DESCRIPTIVE_AUDIT; NO_NEW_ACCURACY_OR_GAIN_CLAIM',
        weak_reference_units=['L3','LW'],new_model_http=0,cost_usd=0))
    old.write_new(HERE/'AUDIT_SUMMARY.json',dict(status='COMPLETE_READONLY_ALL_EIGHT_SEGMENT_ACTION_AUDIT',
        accepted_actions=len(records),coverage=coverage,physical_counts=counts,
        actual_reference_physical_counts=bank_counts,quality_physical_crosstab=crosstab,
        action_artifact=old.artifact(HERE/'ACTIONS.json'),feature_seal=old.artifact(HERE/'FEATURES_SEALED.json'),
        no_qualifying_by_GT=True,no_new_tracker_prediction=True,new_model_http=0,cost_usd=0,
        limits=['Rejected D1 matrix edges lack exact anchor: UNKNOWN, not reconstructed.',
               'Original bank endpoints do not certify one same-version clean identity fragment.',
               'Single compatible depth layers do not certify fish surfaces or identities.',
               'No threshold fitting, semantic candidate change, veto or counterfactual replay.',
               'L3/LW references are weak prediction-derived diagnostics.']))
    print('COMPLETE',len(records),counts,bank_counts,flush=True)


if __name__=='__main__':main()
