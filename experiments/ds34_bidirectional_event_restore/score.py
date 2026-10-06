"""Independent DS34 physical/public scoring after every source and publication seal."""
from common import *
from collections import Counter
from collections import OrderedDict
import copy
import re
import time
from bridge import stream

# Import the unchanged official DS33 adapter under an isolated common namespace.
_saved_common = sys.modules['common']
try:
    sys.modules['common'] = module('ds34_official_ds33_common', ROOT/'experiments/ds33_rgbd_fixed_lag/common.py')
    official = module('ds34_official_ds33_helpers', ROOT/'experiments/ds33_rgbd_fixed_lag/score.py')
finally:
    sys.modules['common'] = _saved_common
ref = official.ref
metrics, rle, np, coco, FIELDS = official.metrics, official.rle, official.np, official.coco, official.FIELDS
polygon_reference, unique_matches, clear_step, same = (
    official.polygon_reference, official.unique_matches, official.clear_step, official.same)
DEPTH = official.DEPTH
ENDPOINT = module('ds34_score_exact_depth_fact_binding', ROOT/'experiments/ds33_rgbd_fixed_lag/evidence.py')
EVIDENCE = module('ds34_score_frozen_evidence_math', HERE/'evidence.py')
STATE_ARMS, EVENT_ARMS = ARMS[1:], ARMS[2:]
ARCHIVED = ROOT/'experiments/ds33_rgbd_fixed_lag/run'
_mapping, _int_map = official._mapping, official._int_map
_source_array_binding = official._source_array_binding
_checked_sources = {}


def scoring_dependencies():
    paths = {Path(p['path']) for p in official.scoring_dependencies()}
    paths |= {Path(__file__), Path(ENDPOINT.__file__), Path(EVIDENCE.__file__), HERE/'sensor.py',
        HERE/'flow.py', HERE/'history.py', HERE/'verify_inputs.py',ROOT/'experiments/ds33_rgbd_fixed_lag/common.py'}
    return [artifact(p) for p in sorted(paths, key=str)]


def _hash(value):
    assert isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'invalid state or source SHA'


def _verify_source_files(value):
    if isinstance(value, dict):
        if {'path', 'bytes', 'sha256'} <= value.keys():
            pin = {k:value[k] for k in ('path', 'bytes', 'sha256')}
            previous = _checked_sources.get(pin['path'])
            if previous is None:
                verify_item(pin)
                _checked_sources[pin['path']] = pin
            else:
                assert previous == pin, 'conflicting actual source pin'
        else:
            for child in value.values():
                _verify_source_files(child)
    elif isinstance(value, list):
        for child in value:
            _verify_source_files(child)


def verify_frame_contract(name, current, assignment, row, measured, quality, bound, ledger, rgb_pin):
    frame, global_frame, now = current['frame'], current['global_frame'], current['time']
    assert (row['frame'], row['global_frame'], row['time']) == (frame, global_frame, now)
    assert (assignment['frame'], assignment['global_frame_id'], assignment['time']) == (frame, global_frame, now)
    for packet in (measured, quality, bound):
        assert (packet['frame'], packet['global_frame'], packet['time']) == (frame, global_frame, now)
    assert measured['segment'] == quality['segment'] == name
    assert bound['source_row_sha256'] == row_sha(row)
    assert bound['assignment_row_sha256'] == row_sha(assignment)
    assert bound['measured_row_sha256'] == row_sha(measured)
    assert bound['DS18_packet_sha256'] == digest(quality)
    assert ledger['frame_inputs_row_sha256'] == row_sha(bound)
    assert bound['rgb_pin'] == rgb_pin and bound['GT'] is False
    assert bound['actual_RGB_read'] == 'ONLY_EVENT_ENDPOINTS_SEPARATE_FLOW_LEDGER'
    assert bound['raw_source_binding'] == measured['raw_source_binding']
    assert quality['source_binding'] == dict(measured['raw_source_binding'], frame=frame)
    shared = {key:quality[key] for key in ('segment', 'frame', 'global_frame', 'time', 'source_binding',
        'actual_depth_binding', 'actual_source_index_binding', 'native_depth_binding')}
    assert quality['frame_binding_sha256'] == digest(shared)
    for outer, inner in (('actual_depth_binding', 'aligned_depth'),
                        ('actual_source_index_binding', 'aligned_source_index'), ('native_depth_binding', 'native_depth')):
        assert quality[outer] == measured['raw_source_binding'][inner]
    _verify_source_files(measured['raw_source_binding'])
    masks = {int(o['mask'][2:]):coco.decode(rle(assignment['masks'][o['mask']])).astype(bool)
             for o in assignment['variants']['N0']}
    assert set(masks) == {int(n) for n in quality['objects']} == {o['id'] for o in row['observations']}
    extracts = {str(n):DEPTH.extract(cert) for n, cert in quality['objects'].items()}
    assert bound['DS18_extracts'] == extracts
    raw = {int(n):v for n,v in measured['adaptive_raw'].items()}
    for native, cert in quality['objects'].items():
        assert cert['certificate_sha256'] == digest({k:v for k,v in cert.items() if k != 'certificate_sha256'})
        assert (cert['native'], cert['segment'], cert['frame'], cert['global_frame'], cert['time']) == (
            int(native), name, frame, global_frame, now)
        assert cert['frame_binding_sha256'] == quality['frame_binding_sha256']
        assert cert['mask_binding'] == _source_array_binding(masks[int(native)])
        for part in ('whole', 'core'):
            assert cert[part]['inclusive_statistics_sha256'] == digest(cert[part]['inclusive_summary'])
            assert cert[part]['source_quality_denominator'] == 'ORIGINAL_GEOMETRIC_ROI_AREA_INCLUDING_MISSING_SHARED_DUPLICATE_PIXELS'
            assert cert[part]['roi_binding'] == cert['mask_binding' if part == 'whole' else 'core_binding']
            for field in ('n', 'area', 'valid_fraction', 'median', 'mad'):
                assert cert[part]['inclusive_summary'][field] == raw[int(native)][part][field]
    return dict(row=row, source_row_sha256=row_sha(row), assignment_row_sha256=row_sha(assignment),
        masks={str(n):array_hash(mask) for n,mask in masks.items()}, extracts=extracts,
        raw_source_binding=measured['raw_source_binding'], adaptive_full=measured.get('adaptive_full'),
        encoded_masks=assignment['masks'])


def verify_sensor_binding(name, local_frame, binding, records, metadata, rgb_pins):
    record = records[local_frame]; row = record['row']; source = metadata[row['global_frame']]
    assert binding['schema'] == 'DS33_SENSOR_FRAME_V1' and binding['segment'] == name
    assert (binding['global_frame'], binding['time']) == (row['global_frame'], row['time'])
    assert binding['RGB_read'] and not any(binding[k] for k in ('GT_read', 'annotation_read', 'restored_read'))
    assert binding['no_future_sensor_lookup'] and not binding['depth_difference_is_motion']
    assert binding['rgb'] == rgb_pins[row['global_frame']] and binding['rgb']['path'] == source['rgb_path']
    for field in ('rgb_timestamp_us', 'depth_timestamp_us', 'delta_us'):
        assert binding[field] == source[field]
    assert abs(binding['rgb_timestamp_us']/1e6 - row['time']) < 1e-6
    for field in ('aligned_depth', 'aligned_source_index', 'native_depth'):
        assert binding[field] == record['raw_source_binding'][field]


def verify_flow_pair(value, event, name, records, metadata, rgb_pins):
    a, b, cutoff = value['pre_frame'], value['post_frame'], value['evidence_cutoff']
    assert value['event'] == event['id'] and a < b <= cutoff == event['decision_cutoff']
    assert event['q'] <= cutoff <= event['q'] + CFG['lag_frames']
    pair = value['actual_pair']
    assert (pair['previous_frame'], pair['current_frame'], pair['maximum_read_global_frame']) == (
        records[a]['row']['global_frame'], records[b]['row']['global_frame'], records[b]['row']['global_frame'])
    for role, f in (('previous', a), ('current', b)):
        source = pair[role+'_source_binding']
        verify_sensor_binding(name, f, source, records, metadata, rgb_pins)
        assert pair[role+'_gray'] == source['array_bindings']['gray']
        for modality in ('rgb', 'depth'):
            assert pair[role+'_'+modality+'_timestamp_us'] == source[modality+'_timestamp_us']
    before, after = pair['previous_source_binding'], pair['current_source_binding']
    assert abs(pair['rgb_dt_s'] - (after['rgb_timestamp_us'] - before['rgb_timestamp_us'])/1e6) < 1e-12
    assert pair['rgb_dt_s'] > 0
    if pair['depth_unknown_reasons']:
        assert pair['depth_status'] == 'UNKNOWN'
    else:
        assert pair['depth_status'] == 'AVAILABLE_RAW_SENSOR_PAIR' and pair['depth_dt_s'] > 0
        assert abs(pair['depth_dt_s'] - (after['depth_timestamp_us'] - before['depth_timestamp_us'])/1e6) < 1e-12
    if before['depth_timestamp_us'] == after['depth_timestamp_us']:
        assert pair['depth_status'] == 'UNKNOWN'
    assert pair['method']==CFG['flow']['algorithm']
    assert pair['actual_quality_parameters']=={k:v for k,v in CFG['flow'].items() if k!='algorithm'}
    assert pair['physical_surface_identity'] == 'UNKNOWN' and pair['no_depth_completion']
    assert pair['no_ID_or_bank_write'] and pair['no_mean_depth_subtraction_as_flow']
    for field in ('flow_forward', 'flow_backward', 'forward_reliable', 'backward_reliable'):
        _hash(pair[field]['sha256'])


def verify_endpoint_reference(value, sample, record, pre):
    row = record['row']; n = sample.get('native', sample.get('source'))
    actual = next(o for o in row['observations'] if o['id'] == n)
    box = sample.get('box', sample.get('bbox'))
    assert box == actual['box'] and sample['area'] == actual['area'] and not actual.get('neighbors')
    assert (value['frame'], value['global_frame'], value['time'], value['native'], value['mask']) == (
        row['frame'], row['global_frame'], row['time'], n, actual['mask'])
    assert value['current_mask_binding'] == record['masks'][str(n)]
    assert value['source_row_sha256'] == record['source_row_sha256']
    assert value['assignment_row_sha256'] == record['assignment_row_sha256']
    assert value['endpoint_version'] == sample.get('version')
    assert value['source_generation'] == sample.get('source_generation')
    assert value['public_epoch'] == sample.get('public_epoch')
    assert value['observation_is_actual'] and value['candidate_identity_is_not_certified']
    assert sample['frame'] == row['frame'] and sample['time'] == row['time']
    if pre:
        assert sample['observation_class'] == 'CLEAN_ACTUAL_BANK_ANCHOR'


def verify_event(event, arm, records, transactions, predictions, ledgers, flow_pairs):
    suspect = event['suspect_frame']; q = event.get('q')
    assert 1 <= suspect <= len(records)
    assert len(event['public_ids']) == len(set(event['public_ids'])) == 2
    if q is None:
        assert not event.get('joint_decision') and not event.get('lag_resolution')
        return
    assert suspect < q <= event['decision_cutoff'] <= min(q+CFG['lag_frames'], len(records))
    cutoff = event['decision_cutoff']; actual = _mapping(predictions[q], arm)
    assert _int_map(event['actual_first_mapping']) == _int_map(event['first_published_mapping']) == actual
    assert cutoff <= event['first_publish_at_arrival_frame'] == ledgers[q]['first_publish_at_arrival_frame']
    decision = event['joint_decision']; restore = event['restore']
    assert decision['choice'] in ('H1', 'H2', 'DEFER') and decision['status'] in ('CHOOSE', 'DEFER')
    assert q <= decision['causal_max_frame'] <= cutoff
    wanted = _int_map(decision.get('mapping'))
    sources = [int(n) for n in event['post_roles']]
    assert len(sources) == len(set(sources)) == 2
    if decision['choice'] == 'DEFER':
        assert not wanted and decision['status'] == 'DEFER' and not restore['staged']
    else:
        assert 'pre_references' in decision and 'post_references' in decision
        expected = dict(zip(sources if decision['choice'] == 'H1' else sources[::-1], event['public_ids']))
        assert wanted == expected and decision['status'] == 'CHOOSE'
        if restore['staged']:
            assert all(actual[n] == k for n,k in wanted.items())
            tx=transactions[arm,q];stage=tx['controller_trace']['ds34_group_restore']
            assert stage['episode']==event['id'] and stage['q']==q and _int_map(stage['selected'])==wanted
            assert stage['complete_member_bijection'] and stage['outside_state_preserved']
            assert stage['future_measurements_written'] is False and stage['physical_identity']=='UNKNOWN_UNTIL_POSTSEAL'
            for n,k in wanted.items():
                if n!=k:
                    assert tx['actual_aliases'][str(n)]['target']==k
                    assert tx['actual_aliases'][str(n)]['source']=='DS34_EVENT_NUMERIC'
    for n, change in restore.get('changes', {}).items():
        assert actual[int(n)] == change['after'] and type(change['before']) is int
    if 'preview_changes' in restore:
        assert restore['preview_changes']==restore['changes'] and restore['preview_was_never_published']
    for control,differences in restore.get('first_publication_differences_vs_controls',{}).items():
        baseline=_mapping(predictions[q],control)
        assert differences=={str(n):dict(before=baseline[n],after=k) for n,k in actual.items() if baseline[n]!=k}
    assert event['future_in_q_state'] is False and event['post_used_as_anonymous_until_selected']
    replay = event['lag_resolution']
    assert replay['checkpoint_frame'] == q-1 and replay['through_frame'] == cutoff
    assert replay['evidence_max_frame'] == cutoff
    _hash(replay['previous_state_sha256']); _hash(replay['selected_state_sha256'])
    assert [p['frame'] for p in replay['replay_state_sha256']] == list(range(q, cutoff+1))
    for point in replay['replay_state_sha256']:
        _hash(point['sha256'])
        assert point['sha256'] == transactions[arm, point['frame']]['full_state_sha256']
    assert replay['selected_state_sha256'] == transactions[arm, cutoff]['full_state_sha256']
    for role, public in zip(('A', 'B'), event['public_ids']):
        reference = event['joint_pre'][role]
        assert reference['public'] == public and reference['anchor'] == event['bank_snapshot'][str(public)]['anchor']
        samples = reference['samples']
        if not samples:
            assert reference['status'] == 'UNKNOWN_REFERENCE'
            continue
        anchor = reference['anchor']; version = reference['version']
        assert samples[-1]['frame'] == anchor['frame'] < suspect
        assert anchor['native_id'] == version[0] and anchor['canonical_id'] == public == version[2]
        assert all(s['version'] == version and s['public'] == public and s['native'] == anchor['native_id'] for s in samples)
        assert all(b['frame'] == a['frame']+1 and b['time'] > a['time'] for a,b in zip(samples,samples[1:]))
        for sample in samples:
            f, n = sample['frame'], sample['native']; tx = transactions[arm,f]
            assert sample['frame'] < suspect and sample['time'] == records[f]['row']['time']
            assert _int_map(tx['mapping'])[n] == public
            assert tx['bank_anchors'][str(public)] == dict(frame=f, native_id=n, canonical_id=public, mask=f'n:{n}')
            if 'actual_epochs' in tx:
                assert tx['actual_epochs'][str(n)] == version[3]
            assert sample['version'][1] == records[f]['source_generations'][str(n)]
    if 'pre_references' in decision:
        assert decision['confirmed_post_supplied_by_frozen_event_manager']
        assert decision['actual_reference_anchors'] == {role:event['joint_pre'][role]['anchor'] for role in ('A','B')}
        for role, refs in decision['pre_references'].items():
            samples = event['joint_pre'][role]['samples'][-CFG['fit_observations']:]
            assert len(refs) == len(samples)
            for value, sample in zip(refs,samples,strict=True):
                verify_endpoint_reference(value,sample,records[sample['frame']],True)
        for source, refs in decision['post_references'].items():
            n = int(source); selected = {p['frame']:p for p in event['post_roles'][source]}
            assert len(refs) == CFG['short_endpoint_frames'] and [v['frame'] for v in refs] == decision['post_frames'][source]
            assert [v['frame'] for v in refs] == [s['frame'] for s in event['confirmed_post_roles'][source]][:CFG['short_endpoint_frames']]
            assert all(q <= r['frame'] <= cutoff for r in refs)
            assert all(b['frame'] == a['frame']+1 and b['time'] > a['time'] for a,b in zip(refs,refs[1:]))
            generations = []
            for value in refs:
                sample = selected[value['frame']]
                verify_endpoint_reference(value,sample,records[sample['frame']],False)
                assert sample['source'] == n
                generations.append(sample['source_generation'])
                assert sample['source_generation'] == records[sample['frame']]['source_generations'][str(n)]
            assert len(set(generations)) == 1
            initial = next(s for s in event['post_roles'][source] if s['frame'] == q)
            assert initial['source_generation'] == generations[0]
        for key, facts in decision['depth_facts'].items():
            refs = decision['pre_references'][key] if key in ('A','B') else decision['post_references'][key]
            assert len(facts) == len(refs)
            for fact, reference in zip(facts,refs,strict=True):
                extract = copy.deepcopy(records[reference['frame']]['extracts'][str(reference['native'])])
                extract['usable'] = ENDPOINT.endpoint_depth_usable(extract,records[reference['frame']]['row'],reference['native'])
                assert fact['usable'] == extract['usable'] and fact['quality'] == extract['quality']
                assert fact['fact_binding'] == ENDPOINT.depth_fact_binding(extract)
        before = {role:event['joint_pre'][role]['samples'][-CFG['fit_observations']:] for role in ('A','B')}
        after = {n:event['confirmed_post_roles'][str(n)][:CFG['short_endpoint_frames']] for n in sources}
        pre_fit = {role:EVIDENCE.fit(samples) for role,samples in before.items()}
        post_fit = {str(n):EVIDENCE.fit(samples) for n,samples in after.items()}
        assert decision['pre_fits'] == pre_fit and decision['post_fits'] == post_fit
        motion_common=all(f['status']=='AVAILABLE_MEASURED_OLS' for f in list(pre_fit.values())+list(post_fit.values()))
        depth_samples = {}
        for role, samples in before.items():
            public = event['joint_pre'][role]['public']; depth_samples[public] = []
            for sample in samples:
                observed = records[sample['frame']]['extracts'][str(sample['native'])]
                usable = ENDPOINT.endpoint_depth_usable(observed,records[sample['frame']]['row'],sample['native'])
                depth_samples[public].append(dict(frame=sample['frame'],time=sample['time'],version=sample['version'],
                    usable=usable,z_mm=observed.get('z_mm'),mad_mm=observed.get('mad_mm'),fact_id=observed.get('fact_id')))
        for candidate in decision['scores']:
            assert candidate['choice'] in ('H1','H2')
            candidate_map = _int_map(candidate['mapping'])
            assert candidate_map == dict(zip(sources if candidate['choice']=='H1' else sources[::-1],event['public_ids']))
            assert len(candidate['edges']) == 2
            for edge in candidate['edges']:
                assert candidate_map[edge['native']] == edge['public']
                role, native = edge['role'], edge['native']; last = before[role][-1]
                assert edge['public'] == event['joint_pre'][role]['public']
                assert [g['frame'] for g in edge['geometry_samples']] == decision['post_frames'][str(native)]
                for geometry, sample in zip(edge['geometry_samples'],after[native],strict=True):
                    gap = sample['time']-last['time']; horizon = min(gap,CFG['geometry_prediction_horizon_seconds'])
                    fit = pre_fit[role]
                    predicted = (np.asarray(fit['center_at_last_time_px'])+np.asarray(fit['velocity_px_s'])*horizon
                        if fit['status']=='AVAILABLE_MEASURED_OLS' else np.asarray(EVIDENCE._center(last)))
                    assert geometry['actual_gap_seconds'] == gap and geometry['prediction_horizon_seconds'] == horizon
                    assert geometry['predicted_center_px'] == predicted.tolist()
                    diag=max(1.,float(np.hypot(EVIDENCE._box(last)[2]-EVIDENCE._box(last)[0],EVIDENCE._box(last)[3]-EVIDENCE._box(last)[1])))
                    assert abs(geometry['position']-float(np.linalg.norm(predicted-np.asarray(EVIDENCE._center(sample)))/diag))<1e-12
                    motion=float(np.linalg.norm(np.asarray(fit['velocity_px_s'])-np.asarray(post_fit[str(native)]['velocity_px_s'])))*horizon/diag if motion_common else None
                    assert geometry['motion']==motion
                    assert geometry['prediction_model']==('MEASURED_OLS' if fit['status']=='AVAILABLE_MEASURED_OLS' else 'LAST_OBSERVED_POSITION_MOTION_UNKNOWN')
                for depth_row,sample in zip(edge['depth_rows'],after[native],strict=True):
                    record=records[sample['frame']]; observed=copy.deepcopy(record['extracts'][str(native)])
                    observed['usable']=ENDPOINT.endpoint_depth_usable(observed,record['row'],native)
                    costs,detail=DEPTH.costs(depth_samples,observed,sample['time'],record['adaptive_full'])
                    assert depth_row['frame']==sample['frame'] and {int(k) for k in depth_row['costs']}==costs.keys()
                    assert {int(k):v for k,v in depth_row['costs'].items()} == costs and depth_row['detail']==json.loads(json.dumps(detail))
                    assert depth_row['current_fact']==dict(usable=observed['usable'],quality=observed['quality'],fact_binding=ENDPOINT.depth_fact_binding(observed))
                for contour in edge['contour_samples']:
                    if 'actual_pair' not in contour:
                        assert contour['status'] == 'UNKNOWN'
                        continue
                    a,b = contour['pre_frame'],contour['post_frame']
                    assert a in decision['pre_frames'][edge['role']][-CFG['short_endpoint_frames']:]
                    assert b in decision['post_frames'][str(edge['native'])]
                    pair = flow_pairs[event['id'],arm,a,b]['actual_pair']
                    assert contour['actual_pair'] == {key:pair.get(key) for key in contour['actual_pair']}
                    for field in ('forward_mask_binding','backward_mask_binding','forward_trusted_binding','backward_trusted_binding'):
                        _hash(contour[field]['sha256'])
                    if 'recomputed_contours' in flow_pairs[event['id'],arm,a,b]:
                        expected=flow_pairs[event['id'],arm,a,b]['recomputed_contours'][before[role][-1]['native'],native]
                        assert {k:contour[k] for k in expected}==expected
                assert edge['geometry']==float(np.mean([g['position']+(CFG['motion_weight']*g['motion'] if g['motion'] is not None else 0.) for g in edge['geometry_samples']]))
                expected_contour=float(np.mean([1-c['symmetric_dice'] for c in edge['contour_samples']])) if all(c['available'] for c in edge['contour_samples']) else None
                assert edge['contour_cost']==expected_contour
                assert edge['depth_cost']==float(np.mean([r['costs'][str(edge['public'])] for r in edge['depth_rows']]))
        weights = decision['common_weights']
        all_edges=[e for c in decision['scores'] for e in c['edges']]
        expected_weights=dict(motion=CFG['motion_weight'] if motion_common else 0.,
            contour=CFG['contour_weight'] if all(c['available'] for e in all_edges for c in e['contour_samples']) else 0.,
            depth=CFG['depth_weight'] if arm=='EVENT_RGBD' and all(r['detail']['used'] for e in all_edges for r in e['depth_rows']) else 0.)
        assert weights==expected_weights
        for candidate in decision['scores']:
            score=sum(edge['geometry']+weights['contour']*(edge['contour_cost'] or 0.)+weights['depth']*edge['depth_cost'] for edge in candidate['edges'])
            assert candidate['score']==score
        ranked=sorted(decision['scores'],key=lambda c:(c['score'],c['choice']))
        margin=ranked[1]['score']-ranked[0]['score']
        assert decision['winning_margin']==margin and decision['minimum_joint_margin']==CFG['min_joint_margin']
        assert decision['choice']==(ranked[0]['choice'] if margin>=CFG['min_joint_margin'] else 'DEFER')
        for native, diagnostic in decision['post_backward_to_q'].items():
            assert diagnostic.get('used_for_identity_score',False) is False
            for link in diagnostic['links']:
                a,b=link['previous_frame'],link['current_frame']
                assert q<=a<b<=cutoff and b==a+1
                pair=flow_pairs[event['id'],arm,a,b]['actual_pair']
                assert link['pair']=={key:pair.get(key) for key in link['pair']}
            if 'q_actual_mask_binding' in diagnostic:
                assert diagnostic['q_actual_mask_binding']==records[q]['masks'][native]


def verify_publications(name, public=None):
    """No references are opened until every saved observation and final state is bound."""
    public = Path(public) if public else RUN/name/'public'
    sealed=read(public/'PREDICTIONS_SEALED.json')
    for file,expected in sealed['artifacts_sha256'].items():
        assert sha(public/file)==expected
    frames=sealed['frames']; start,stop=SEGMENTS[name]
    if (public/'FREEZE.json').exists():
        frozen=read(public/'FREEZE.json')
    else:
        frozen=read(public/'PREFIX_FREEZE.json')
        frozen['sensor_audit']=artifact(ROOT/'experiments/ds33_rgbd_fixed_lag/SENSOR_AUDIT.json')
    rgb_pins={r['global_frame']:r['rgb'] for r in rows(frozen['rgb_pins']['path']) if r['segment']==name}
    metadata={r['global_frame']:r for s in read(frozen['sensor_audit']['path'])['segments'] if s['segment']==name for r in s['metadata']}
    original=ARCHIVED/name/'public'; original_seal=read(original/'PREDICTIONS_SEALED.json')
    assert sha(original/'predictions.jsonl.gz')==original_seal['artifacts_sha256']['predictions.jsonl.gz']
    transactions,records,predictions,ledgers={},{},{},{}
    first_public={arm:{} for arm in ARMS}; previous={}
    tx=iter(rows(public/'TRANSACTIONS.jsonl.gz')); ledger_rows=iter(rows(public/'PUBLISH_LEDGER.jsonl'))
    bindings=iter(rows(public/'FRAME_INPUTS_BINDINGS.jsonl.gz'))
    source=iter(stream(input_dir(name)/'observations.jsonl.gz',input_dir(name)/'profiles.jsonl.gz'))
    assignments=iter(rows(input_dir(name)/'assignments.jsonl.gz'))
    measurements=iter(rows(input_dir(name)/'DEPTH_OBSERVATIONS.jsonl.gz'))
    qualities=iter(rows(DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz'))
    archived=iter(rows(original/'predictions.jsonl.gz'))
    for f,current in enumerate(rows(public/'predictions.jsonl.gz'),1):
        assignment=next(assignments); prior=next(archived); row,profiles=next(source); ledger=next(ledger_rows)
        assert (current['frame'],current['global_frame'],current['time'])==(f,start+f-1,assignment['time'])
        assert (current['frame'],current['global_frame'],current['time'])==(prior['frame'],prior['global_frame'],prior['time'])
        assert set(current['variants'])==set(ARMS)
        assert current['variants']['SAM3_NATIVE']==assignment['variants']['N0']==prior['variants']['SAM3_NATIVE']
        assert current['variants']['Z4Q_FROZEN']==prior['variants']['Z4Q_FROZEN']
        assert ledger['frame']==f and ledger['global_frame']==current['global_frame']
        assert ledger['prediction_row_sha256']==row_sha(current)
        record=verify_frame_contract(name,current,assignment,row,next(measurements),next(qualities),next(bindings),ledger,rgb_pins[start+f-1])
        generations={}
        for o in row['observations']:
            n=o['id']; p=previous.get(n)
            generations[str(n)]=p[1] if p and p[0]==f-1 else p[1]+1 if p else 1
            previous[n]=(f,generations[str(n)])
        record['source_generations']=generations; records[f]=record; predictions[f]=current; ledgers[f]=ledger
        arrival=ledger['first_publish_at_arrival_frame']
        assert f<=arrival<=min(f+CFG['lag_frames'],frames)
        assert ledger['actual_delay_frames']==arrival-f and (ledger['EOF_flush'] or arrival==f+CFG['lag_frames'])
        assert ledger['model_http']==0 and ledger['published_history_rewritten'] is False
        assert ledger['receive_to_first_publish_seconds']>=0
        keys=[o['mask'] for o in assignment['variants']['N0']]
        assert len(keys)==len(set(keys))
        for arm in ARMS:
            objects=current['variants'][arm]
            assert [o['mask'] for o in objects]==keys and all(type(o['id']) is int for o in objects)
            assert len({o['id'] for o in objects})==len(objects)
            mapping=_mapping(current,arm)
            for n,k in mapping.items():
                first_public[arm].setdefault(k,dict(frame=f,global_frame=start+f-1,native_id=n))
            if arm=='SAM3_NATIVE':continue
            transaction=next(tx)
            assert (transaction['arm'],transaction['frame'],transaction['global_frame'],transaction['version'])==(arm,f,start+f-1,f)
            assert transaction['time']==row['time'] and transaction['source_row_sha256']==row_sha(row)
            assert _int_map(transaction['mapping'])==mapping
            assert ledger['transaction_row_sha256'][arm]==row_sha(transaction)
            assert transaction['decided_before_first_publish'] and transaction['already_published_history_rewritten'] is False
            _hash(transaction['engine_state_sha256']);_hash(transaction['full_state_sha256'])
            assert transaction['actual_actions']==[a for a in transaction['controller_trace'].get('events',[]) if a.get('kind')=='reconnect' and a.get('accepted')]
            assert set(_int_map(transaction['actual_epochs']))>=set(mapping)
            for action in transaction['actual_actions']:
                assert mapping[action['native_id']]==action['canonical_id']
                assert action['old_anchor']['frame']<f
            transactions[arm,f]=transaction
    assert len(predictions)==frames and all(next(it,None) is None for it in (tx,ledger_rows,bindings))
    if frames==stop-start+1:
        assert all(next(it,None) is None for it in (source,assignments,measurements,qualities,archived))
    events=read(public/'EVENTS.json');assert set(events)==set(EVENT_ARMS)
    event_index={(arm,e['id']):e for arm,values in events.items() for e in values}
    assert len(event_index)==sum(len(v) for v in events.values())
    pairs={}; actual_sensor_bindings={}
    for value in rows(public/'FLOW.jsonl.gz'):
        arm=value['arm'];event=event_index[arm,value['event']]
        verify_flow_pair(value,event,name,records,metadata,rgb_pins)
        assert value['no_cumulative_long_anchor_warp']
        key=value['event'],arm,value['pre_frame'],value['post_frame'];assert key not in pairs
        pairs[key]=value
        for role,f in (('previous',value['pre_frame']),('current',value['post_frame'])):
            binding=value['actual_pair'][role+'_source_binding']
            assert f not in actual_sensor_bindings or actual_sensor_bindings[f]==binding
            actual_sensor_bindings[f]=binding
    # Re-read only actual acquired endpoints from white-listed raw inputs. This
    # proves the serialized array hashes, calibration and timestamps are real.
    sensor_module=module('ds34_independent_scoring_sensor',HERE/'sensor.py')
    sensor=sensor_module.Sensor(name); sensor_cache=OrderedDict()
    def actual_sensor(f):
        if f not in sensor_cache:
            row=records[f]['row'];sensor.previous=None;sensor.raw.previous_frame=None
            actual=sensor.read(row['global_frame'],row['time'])
            assert actual['binding']==actual_sensor_bindings[f]
            sensor_cache[f]=actual
            while len(sensor_cache)>8:sensor_cache.popitem(last=False)
        return sensor_cache[f]
    try:
        from flow import PairMotion
        recomputed=OrderedDict()
        for key,value in sorted(pairs.items(),key=lambda v:(v[0][3],v[0][2])):
            event_id,arm,a,b=key
            if (a,b) not in recomputed:
                pair=PairMotion(actual_sensor(a),actual_sensor(b),CFG['flow'])
                actual=pair.numeric_summary; saved=value['actual_pair']
                assert {k:v for k,v in actual.items() if k!='flow_seconds'}=={k:v for k,v in saved.items() if k!='flow_seconds'}
                recomputed[a,b]=pair
                while len(recomputed)>8:recomputed.popitem(last=False)
            pair=recomputed[a,b];event=event_index[arm,event_id];decision=event['joint_decision']
            contours={}
            for role,pre in event['joint_pre'].items():
                if a not in [s['frame'] for s in pre['samples']][-CFG['short_endpoint_frames']:]:continue
                for native in map(int,event['post_roles']):
                    if b not in decision.get('post_frames',{}).get(str(native),[]):continue
                    n=pre['anchor']['native_id']
                    left=coco.decode(rle(records[a]['encoded_masks'][f'n:{n}'])).astype(bool)
                    right=coco.decode(rle(records[b]['encoded_masks'][f'n:{native}'])).astype(bool)
                    contours[n,native]=EVIDENCE._contour(pair,left,right)
            value['recomputed_contours']=contours
        for f in sorted(actual_sensor_bindings):actual_sensor(f)
    finally:
        sensor.close()
    for arm,values in events.items():
        for event in values:
            verify_event(event,arm,records,transactions,predictions,ledgers,pairs)
    return dict(status='PASS',frames=frames,original_native_and_Z4Q_every_frame_exact=True,
        masks_and_tokens_preserved=True,all_state_transactions_bound_to_first_publication=True,
        actual_frame_source_mask_quality_and_flow_bound_before_GT=True,
        source_generations_independently_reconstructed=True,actual_epochs_bound=True,
        events_bound_to_actual_q_and_finite_evidence=True,endpoint_sensors_independently_reread=len(actual_sensor_bindings),
        replay_full_state_hashes_bound_to_q_through_cutoff=True,GT_opened=False,
        source_original_seal=artifact(original/'PREDICTIONS_SEALED.json'),
        source_original_prediction=artifact(original/'predictions.jsonl.gz')),first_public


def _verdict(relation):
    return 'CORRECT' if relation=='SAME' else 'WRONG' if relation=='DIFFERENT' else 'UNSCORABLE'


def _combine(labels):
    return 'WRONG' if 'WRONG' in labels else 'CORRECT' if labels and all(v=='CORRECT' for v in labels) else 'UNSCORABLE'


def _consensus(values, minimum=3):
    ids=[v.get('gt_id') for v in values if v.get('status')=='UNIQUE_IOU_MATCH']
    if len(values)<minimum or len(ids)!=len(values) or len(set(ids))!=1:
        return dict(status='UNSCORABLE_FIXED_FRAGMENT_CONSENSUS',observations=len(values),actual_matches=values)
    return dict(status='UNIQUE_IOU_MATCH',gt_id=ids[0],observations=len(values),actual_matches=values)


def physical_audit(name,matches,predictions,first_public):
    public=RUN/name/'public'
    def match(frame,native):
        return matches.get(frame,{}).get(native,dict(status='SOURCE_OR_REFERENCE_MISSING'))
    def anchor_match(anchor):
        return match(anchor.get('frame'),anchor.get('native_id')) if isinstance(anchor,dict) else dict(status='REFERENCE_MISSING')
    def origin(arm,target,q):
        value=first_public[arm].get(target)
        return value,(anchor_match(value) if value and value['frame']<q else dict(status='NO_PRIOR_PUBLIC_ORIGIN_REFERENCE'))
    automatic=[]
    for transaction in rows(public/'TRANSACTIONS.jsonl.gz'):
        for action in transaction['actual_actions']:
            arm,f=transaction['arm'],transaction['frame'];n,k=action['native_id'],action['canonical_id']
            query,past=match(f,n),anchor_match(action['old_anchor']);reference,pub=origin(arm,k,f)
            automatic.append(dict(arm=arm,frame=f,global_frame=transaction['global_frame'],source=n,target=k,
                phase='BIRTH_REFINE' if action.get('phase')=='birth' else 'D1_DELAYED',actual_action=action,
                actual_pre_reference=action['old_anchor'],query_match=query,preanchor_match=past,
                physical_preanchor=_verdict(same(query,past)),public_origin_reference=reference,
                public_origin_match=pub,public_reference_correctness=_verdict(same(query,pub)),
                incidental_public_reference_return=same(query,pub)=='SAME' and same(query,past)=='DIFFERENT'))
    event_results={arm:[] for arm in EVENT_ARMS}
    for arm,events in read(public/'EVENTS.json').items():
        for event in events:
            q=event.get('q');decision=event.get('joint_decision',{});restore=event.get('restore',{})
            result=dict(event=event['id'],suspect_frame=event['suspect_frame'],q=q,status=event['status'],
                raw_choice=decision.get('choice'),reason=decision.get('reason'),staged=restore.get('staged',False),
                preview_changes=restore.get('changes',{}),changes_internal_unpublished_preview=bool(restore.get('changes')),
                changes_real_publication=False,
                physical_preanchor='UNSCORABLE',physical_prefragment='UNSCORABLE',
                postfragment_preanchor='UNSCORABLE',postfragment_prefragment='UNSCORABLE',
                public_reference_correctness='UNSCORABLE',postfragment_public_reference='UNSCORABLE',
                outcome_role='NO_FIRST_SPLIT' if q is None else 'LOCAL_FALLBACK' if not restore.get('staged') else 'JOINT_STAGE',
                no_model_inference=True,UNKNOWN_not_safe_pass=True,selected_sources=[])
            if q is not None:
                mapping=_mapping(predictions[q],arm);selected=[]
                for n in map(int,event['post_roles']):
                    k=mapping[n];role=next((r for r,p in zip(('A','B'),event['public_ids']) if p==k),None)
                    pre=event['joint_pre'].get(role,{}) if role else {};anchor=pre.get('anchor')
                    query,past=match(q,n),anchor_match(anchor)
                    pre_values=[match(s['frame'],s['native']) for s in pre.get('samples',[])]
                    pre_consensus=_consensus(pre_values)
                    refs=decision.get('post_references',{}).get(str(n),[])
                    post_values=[match(r['frame'],r['native']) for r in refs]
                    post_consensus=_consensus(post_values)
                    reference,pub=origin(arm,k,q)
                    selected.append(dict(source=n,public_id=k,actual_pre_reference=anchor,query_match=query,preanchor_match=past,
                        prefragment_frames=[s['frame'] for s in pre.get('samples',[])],prefragment_consensus=pre_consensus,
                        postfragment_frames=[r['frame'] for r in refs],postfragment_consensus=post_consensus,
                        literal_first_q_physical_preanchor=_verdict(same(query,past)),
                        literal_first_q_physical_prefragment=_verdict(same(query,pre_consensus)),
                        postfragment_preanchor=_verdict(same(post_consensus,past)),postfragment_prefragment=_verdict(same(post_consensus,pre_consensus)),
                        public_origin_reference=reference,public_origin_match=pub,
                        public_reference_correctness=_verdict(same(query,pub)),postfragment_public_reference=_verdict(same(post_consensus,pub)),
                        preanchor_already_wrong_public_reference=_verdict(same(past,pub)),
                        prefragment_already_wrong_public_reference=_verdict(same(pre_consensus,pub))))
                result.update(selected_sources=selected,actual_first_published_mapping=mapping,
                    evidence_max_frame=event['decision_cutoff'],first_publish_at_arrival_frame=event['first_publish_at_arrival_frame'],
                    publication_delay_frames=event['first_publish_at_arrival_frame']-q,
                    decision_delay_frames=event['decision_cutoff']-q)
                baseline_mapping=_mapping(predictions[q],'Z4Q_FROZEN');native_mapping=_mapping(predictions[q],'SAM3_NATIVE')
                result.update(changes_real_publication=mapping!=baseline_mapping,
                    actual_changes_vs_Z4Q={str(n):dict(before=baseline_mapping[n],after=k) for n,k in mapping.items() if baseline_mapping[n]!=k},
                    actual_changes_vs_native={str(n):dict(before=native_mapping[n],after=k) for n,k in mapping.items() if native_mapping[n]!=k},
                    first_frame_changes_are_against_same_source_final_controls=True)
                for field,edgefield in (('physical_preanchor','literal_first_q_physical_preanchor'),
                    ('physical_prefragment','literal_first_q_physical_prefragment'),('postfragment_preanchor','postfragment_preanchor'),
                    ('postfragment_prefragment','postfragment_prefragment'),('public_reference_correctness','public_reference_correctness'),
                    ('postfragment_public_reference','postfragment_public_reference')):
                    result[field]=_combine([edge[edgefield] for edge in selected])
                if not restore.get('staged'):
                    result['fallback_observed_mapping_diagnostics']={field:result[field] for field in (
                        'physical_preanchor','physical_prefragment','postfragment_preanchor','postfragment_prefragment',
                        'public_reference_correctness','postfragment_public_reference')}
                    for field in result['fallback_observed_mapping_diagnostics']:result[field]='UNSCORABLE'
            event_results[arm].append(result)
    result=dict(segment=name,automatic_actions=automatic,event_arms=event_results,
        automatic_counts={arm:dict(Counter(e['physical_preanchor'] for e in automatic if e['arm']==arm)) for arm in STATE_ARMS},
        event_counts={arm:dict(Counter(e['physical_preanchor'] for e in values)) for arm,values in event_results.items()},
        joint_stage_counts={arm:dict(Counter(e['physical_preanchor'] for e in values if e['staged'])) for arm,values in event_results.items()},
        altered_joint_counts={arm:dict(Counter(e['physical_preanchor'] for e in values if e['staged'] and e['changes_real_publication'])) for arm,values in event_results.items()},
        UNKNOWN_unscorable_and_no_reference_not_correct=True,
        public_origin_definition='First actual publication strictly before q; public integer is not GT integer.',
        post_consensus_definition='All three fixed, prediction-selected explicit post_references must uniquely match the same physical GT; no subset selection.',
        physical_depth_accuracy='UNKNOWN',old_scores_unchanged=True,postseal_only=True)
    write_new(public/'EVENT_AUDIT.json',result);return result


def switch_changes(switches):
    comparisons={};key=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'))
    occurrence=lambda v:(v['segment'],v['frame'],v['gt_id'])
    for baseline in ('SAM3_NATIVE','Z4Q_FROZEN','EVENT_RGB'):
        for arm in EVENT_ARMS:
            if arm==baseline:continue
            old_values={key(v):v for v in switches[baseline]};new_values={key(v):v for v in switches[arm]}
            before={occurrence(v):v for v in switches[baseline]};after={occurrence(v):v for v in switches[arm]}
            comparisons[baseline+'_TO_'+arm]=dict(added=[new_values[k] for k in sorted(new_values.keys()-old_values.keys())],
                eliminated=[old_values[k] for k in sorted(old_values.keys()-new_values.keys())],common_exact_records=len(old_values.keys()&new_values.keys()),
                occurrence_added=[after[k] for k in sorted(after.keys()-before.keys())],occurrence_eliminated=[before[k] for k in sorted(before.keys()-after.keys())],
                same_GT_frame_occurrences=[dict(before=before[k],after=after[k]) for k in sorted(after.keys()&before.keys())],
                net_IDSW=len(switches[arm])-len(switches[baseline]))
    return comparisons


def deltas(summary):
    return {base:{arm:{key:summary[arm][key]-summary[base][key] for key in FIELDS}
        for arm in EVENT_ARMS if arm!=base} for base in ('SAM3_NATIVE','Z4Q_FROZEN','EVENT_RGB')}


def score_segment(name,dev_pin,first_public):
    """Unchanged DS33 official mask scoring in the original coordinate systems."""
    public=RUN/name/'public';start,stop=SEGMENTS[name]
    gt,sims,predictions=[],[],{};pred={arm:[] for arm in ARMS}
    previous,step,switches=({arm:{} for arm in ARMS},{arm:{} for arm in ARMS},{arm:[] for arm in ARMS})
    matches={}
    for frame,(prediction,assignment,truth) in enumerate(zip(rows(public/'predictions.jsonl.gz'),
        rows(input_dir(name)/'assignments.jsonl.gz'),ref.reference_rows(name,dev_pin),strict=True),1):
        global_frame,ids,reference=truth
        assert prediction['frame']==frame and prediction['global_frame']==global_frame==start+frame-1
        keys=[o['mask'] for o in assignment['variants']['N0']];sources=[int(key[2:]) for key in keys]
        encoded=[rle(assignment['masks'][key]) for key in keys]
        if name in ('L3','LW'):
            label=read(WORK/'data/AnnotationNewBags_20260919'/name/'labels_raw'/f'{global_frame:06d}.json')
            native_ids,encoded=polygon_reference(label['shapes'],1080,1920);assert native_ids==sources
        similarity=(np.asarray(coco.iou(reference,encoded,[0]*len(encoded)),float).reshape(len(ids),len(encoded))
            if ids and encoded else np.zeros((len(ids),len(encoded))))
        gt.append(ids);sims.append(similarity);matches[frame]=unique_matches(ids,sources,similarity);predictions[frame]=prediction
        for arm in ARMS:
            public_ids=[o['id'] for o in prediction['variants'][arm]];pred[arm].append(public_ids)
            step[arm],added=clear_step(ids,keys,public_ids,similarity,previous[arm],step[arm],global_frame)
            switches[arm].extend(dict(value,segment=name) for value in added)
        if frame%1000==0:print('DS34 SCORE',name,frame,flush=True)
    assert len(gt)==stop-start+1
    summary={arm:metrics(gt,pred[arm],sims)[0] for arm in ARMS}
    archived=read(ARCHIVED/name/'public/METRICS.json')['metrics']
    for arm in ARMS[:2]:assert summary[arm]==archived[arm],(name,arm,'official same-source control mismatch')
    for arm in ARMS:
        assert len(switches[arm])==summary[arm]['IDSW']
        assert summary[arm]['predictions']==summary['SAM3_NATIVE']['predictions']
    result=dict(segment=name,frames=len(gt),metrics=summary,deltas=deltas(summary),
        reference_status='WEAK_UNREVIEWED_PREDICTION_DERIVED_PREANNOTATION' if name in ('L3','LW') else 'EXPOSED_EXISTING_ANNOTATION',
        score_protocol='Unchanged DS14/DS20/DS33 official mask CLEAR.5 Identity.5 HOTA19alphas; FishSA original raster/annotation version; L3/LW1080; Feeding640.',
        no_mask_or_ID_exclusion=True,physical_depth_accuracy='UNKNOWN')
    write_new(public/'METRICS.json',result);write_new(public/'SWITCHES.json',switches)
    write_new(public/'SWITCH_CHANGES.json',switch_changes(switches))
    with gzip.open(public/'REFERENCE_MATCHES.jsonl.gz','xt',encoding='utf-8',newline='\n') as output:
        for frame,values in matches.items():
            output.write(json.dumps(dict(frame=frame,matches=values),separators=(',',':'),allow_nan=False)+'\n')
    audit=physical_audit(name,matches,predictions,first_public)
    print(name,json.dumps(summary),flush=True)
    return result,(gt,pred,sims),audit


def main():
    from verify_inputs import verify_all
    assert not (RUN/'METRICS.json').exists(),'No rescore or sealed-output overwrite'
    began=time.perf_counter();seal=verify_all()
    assert seal['status']=='ALL_PREDICTIONS_AND_ACCESS_SEALED'
    assert set(seal['starts'])==set(seal['ends'])==set(SEGMENTS)
    for name in SEGMENTS:
        verify_item(seal['starts'][name]);verify_item(seal['ends'][name])
        end=read(seal['ends'][name]['path']);assert end['exit_code']==0
    parity,origins={},{}
    for name in SEGMENTS:parity[name],origins[name]=verify_publications(name)
    # First reference access is strictly below the complete eight-source gate.
    dev_pin=ref.authoritative_development_pin();assert sha(ref.GT_DEV)==dev_pin
    write_new(RUN/'SCORING_FREEZE.json',dict(status='ALL_PREDICTION_INPUT_ACCESS_AND_PUBLICATION_BINDINGS_VERIFIED',
        all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),scoring_sources=scoring_dependencies(),
        development_reference=artifact(ref.GT_DEV),development_reference_authority=artifact(old.OLD/'score.py'),
        validation_original_archive=artifact(ref.ARCHIVE),development_pin=dev_pin,
        reference_not_substituted_by_aligned_package=True,verified_before_reference_raster_read=True,
        prediction_parity=parity,new_model_http=0,cost_usd=0))
    write_new(RUN/'PREDICTION_PARITY.json',dict(status='PASS',segments=parity,GT_opened=False))
    results,audits={},{};pool_gt,pool_sims=[],[];pool_pred={arm:[] for arm in ARMS}
    for name in SEGMENTS:
        result,(gt,pred,sims),audit=score_segment(name,dev_pin,origins[name]);results[name]=result;audits[name]=audit
        if name.startswith('feeding_'):
            pool_gt.extend([[(name,identity) for identity in ids] for ids in gt]);pool_sims.extend(sims)
            for arm in ARMS:pool_pred[arm].extend([[(name,identity) for identity in ids] for ids in pred[arm]])
    pooled={arm:metrics(pool_gt,pool_pred[arm],pool_sims)[0] for arm in ARMS}
    original=read(ARCHIVED/'METRICS.json')['feeding_pooled']['metrics']
    assert all(pooled[arm]==original[arm] for arm in ARMS[:2])
    write_new(RUN/'METRICS.json',dict(status='SCORED_AFTER_ALL_EIGHT_FORMAL_PREDICTION_AND_ACCESS_SEALS',
        frames=20098,arms=ARMS,segments=results,feeding_pooled=dict(frames=1471,metrics=pooled,deltas=deltas(pooled)),
        event_audits=audits,all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),score_seconds=time.perf_counter()-began,
        no_cross_dataset_pooled_headline=True,future_prediction_authority='FINITE_UNPUBLISHED_30FRAME_LAG_NOT_S0_OR_REALTIME',
        depth_increment_comparison='EVENT_RGBD_MINUS_EVENT_RGB',new_model_http=0,cost_usd=0))
    write_new(RUN/'SCORE_PROVENANCE.json',dict(scorer=artifact(__file__),
        scoring_freeze=artifact(RUN/'SCORING_FREEZE.json'),prediction_parity=artifact(RUN/'PREDICTION_PARITY.json'),
        reference_opened_after_all_seals=True,official_metric_math_unchanged=True,ignored_public_ids=0,
        GT_used_for_prediction=False,original_controls_exact=True))


if __name__=='__main__':main()

