"""Independent TrackEval: every DS6 prediction must be sealed before reference access."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from common import (HERE, RUN, DATA, NE1, DS1, DS2, SEGMENTS, ARMS, input_dir,
                    read, rows, sha, write_new, verify_item)

spec = importlib.util.spec_from_file_location('ds6_legacy_metric_helpers', NE1/'score.py')
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
mask_rles, metrics, original_score = legacy.mask_rles, legacy.metrics, legacy.original_score
np, coco = original_score.np, original_score.coco
# The legacy helper prepends its own directory; local imports must remain DS6.
sys.path.insert(0, str(HERE))

SEALED_FILES = {'predictions.jsonl.gz', 'DEPTH_OBSERVATIONS.jsonl.gz',
    'DEPTH_STATES.jsonl.gz', 'TRANSACTIONS.jsonl.gz', 'PUBLISH_LEDGER.jsonl',
    'EVENTS.json', 'RUN_SUMMARY.json', 'FREEZE.json', 'COMMON_STATE_SHADOW.json',
    'PERFORMANCE.json'}


def check_all_manifest(manifest, segments=SEGMENTS, arms=ARMS):
    assert manifest['status'] == 'ALL_FIVE_BRANCHES_FOUR_SEGMENTS_SEALED'
    assert manifest['frames'] == sum(b-a+1 for a, b in segments.values())
    assert tuple(manifest['arms']) == tuple(arms)
    assert set(manifest['seals']) == set(segments)
    assert manifest['new_model_http'] == manifest['model_cost_usd'] == 0


def verify_seal(run, name, start, stop):
    public = Path(run)/name/'public'
    seal = read(public/'PREDICTIONS_SEALED.json')
    assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
    assert seal['segment'] == name and seal['original_frames'] == [start, stop]
    assert seal['frames'] == seal['published_frames'] == stop-start+1
    assert tuple(seal['arms']) == ARMS
    assert seal['new_model_http'] == seal['model_cost_usd'] == 0
    assert SEALED_FILES <= set(seal['artifacts_sha256'])
    for filename, expected in seal['artifacts_sha256'].items():
        assert sha(public/filename) == expected, filename
    freeze = read(public/'FREEZE.json')
    assert freeze['status'] == 'FROZEN_BEFORE_PREDICTION'
    assert freeze['segment'] == name and freeze['original_frames'] == [start, stop]
    assert freeze['frames'] == stop-start+1 and freeze['no_gt_before_seal'] is True
    for path, expected in freeze['code_sha256'].items():
        assert sha(path) == expected, path
    for item in freeze['derived_inputs'].values():
        verify_item(item)
    for item in freeze['current_metadata'].values():
        verify_item(item)
    assert len(freeze['native_depth_sources']) == stop-start+1
    for item in freeze['native_depth_sources']:
        verify_item(item)
    base = input_dir(name)
    assert sha(base/'SOURCE_MANIFEST.json') == freeze['source_manifest_sha256']
    assert sha(base/'sources.json') == freeze['source_list_sha256']
    assert sha(base/'scan_v4.json') == freeze['scan_sha256']
    for source in read(base/'sources.json'):
        for prefix in ('prediction', 'depth'):
            verify_item(dict(path=source[prefix+'_path'], bytes=source[prefix+'_bytes'],
                             sha256=source[prefix+'_sha256']))
    with gzip.open(public/'predictions.jsonl.gz', 'rt', encoding='utf-8') as predictions:
        count = 0
        for count, (line, entry) in enumerate(zip(predictions,
                rows(public/'PUBLISH_LEDGER.jsonl'), strict=True), 1):
            assert entry['frame'] == count and entry['global_frame'] == start+count-1
            assert hashlib.sha256(line.encode()).hexdigest() == entry['prediction_row_sha256']
        assert count == stop-start+1
    return seal


def verify_all_seals(run=RUN):
    manifest = read(Path(run)/'ALL_PREDICTIONS_SEALED.json')
    check_all_manifest(manifest)
    for name, expected in manifest['seals'].items():
        assert sha(Path(run)/name/'public/PREDICTIONS_SEALED.json') == expected, name
    seals = {name: verify_seal(run, name, *bounds) for name, bounds in SEGMENTS.items()}
    access = read(Path(run)/'ACCESS_SEALED.json')
    verify_item(access['artifact'])
    verify_item(access['prediction_all_seal'])
    assert Path(access['artifact']['path']).resolve() == (Path(run)/'PREDICTION_ACCESS_AUDIT.json').resolve()
    assert Path(access['prediction_all_seal']['path']).resolve() == (Path(run)/'ALL_PREDICTIONS_SEALED.json').resolve()
    check_access_audit(read(Path(run)/'PREDICTION_ACCESS_AUDIT.json'))
    return seals


def check_access_audit(audit):
    assert audit['status'] == 'NO_REFERENCE_OR_RESTORED_FILE_OPEN_DURING_PREDICTION'
    assert audit['new_model_http'] == audit['cost_usd'] == 0
    required = {'labels_640x360', 'depth_restored', 'restored_v3', 'sealed_test'}
    assert required <= set(audit['forbidden_path_tokens'])
    for path in audit['observed_data_paths']:
        normalized = path.replace('\\', '/').lower()
        assert not any(token in normalized for token in required), path


def check_legacy_row(current, previous, old_core):
    assert all(current[key] == previous[key] for key in ('frame', 'global_frame', 'time'))
    for new, old in (('SAM3_NATIVE', 'SAM3_NATIVE'), ('D0_GEOMETRY', 'D0_GEOMETRY'),
                     ('D2_CORE_FROZEN', old_core)):
        assert current['variants'][new] == previous['variants'][old], (current['frame'], new)


def verify_legacy_equivalence(name, actual):
    """Old sealed outputs only: no old scorer, human labels or revised predictions."""
    start, stop = SEGMENTS[name]
    old_root = DS1 if start < 701 else DS2
    old_core = 'D2_DYNAMIC' if start < 701 else 'D2_FROZEN'
    public = old_root/'run'/name/'public'
    seal = read(public/'PREDICTIONS_SEALED.json')
    assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
    assert seal['segment'] == name and seal['original_frames'] == [start, stop]
    assert seal['frames'] == seal['published_frames'] == stop-start+1
    for filename, expected in seal['artifacts_sha256'].items():
        assert sha(public/filename) == expected, (name, filename)
    count = 0
    for count, (current, previous) in enumerate(zip(actual, rows(public/'predictions.jsonl.gz'), strict=True), 1):
        check_legacy_row(current, previous, old_core)
    assert count == stop-start+1
    return dict(old_experiment=old_root.name, old_core_arm=old_core, checked_frames=count,
                seal_sha256=sha(public/'PREDICTIONS_SEALED.json'), exact=True)


def check_objects(assignment, prediction):
    assert prediction['variants']['SAM3_NATIVE'] == assignment['variants']['N0']
    native = [x['mask'] for x in assignment['variants']['N0']]
    assert set(prediction['variants']) == set(ARMS)
    for arm in ARMS:
        objects = prediction['variants'][arm]
        assert [x['mask'] for x in objects] == native
        ids = [int(x['id']) for x in objects]
        assert len(ids) == len(set(ids)), arm
    return native


def verify_publication(run=RUN):
    """No labels: seals, immutable masks, q publication and causal history only."""
    verify_all_seals(run)
    checked = []
    q_checks = group_checks = history_checks = shadow_checks = 0
    for name, (start, stop) in SEGMENTS.items():
        public = Path(run)/name/'public'
        actual = list(rows(public/'predictions.jsonl.gz'))
        inputs = list(rows(input_dir(name)/'assignments.jsonl.gz'))
        states = {(x['frame'], x['arm']): x for x in rows(public/'DEPTH_STATES.jsonl.gz')}
        measured = {x['frame']: x for x in rows(public/'DEPTH_OBSERVATIONS.jsonl.gz')}
        ledger = {x['frame']: x for x in rows(public/'PUBLISH_LEDGER.jsonl')}
        events = read(public/'EVENTS.json')
        assert len(actual) == len(inputs) == len(measured) == len(ledger) == stop-start+1
        assert len(states) == (stop-start+1)*(len(ARMS)-1)
        assert set(events) == set(ARMS[1:])
        for local, (prediction, assignment) in enumerate(zip(actual, inputs, strict=True), 1):
            assert prediction['frame'] == assignment['frame'] == local
            assert prediction['global_frame'] == assignment['global_frame_id'] == start+local-1
            check_objects(assignment, prediction)
        for arm in ARMS[1:]:
            for event in events[arm]:
                for group in event['group_observations']:
                    live = states[(group['frame'], arm)]['live'].get(str(group['source']))
                    assert not live or group['frame'] not in live['sample_frames']
                    group_checks += 1
                for frozen in (event['depth_frozen'] or {}).values():
                    samples = frozen['samples']
                    assert frozen['cutoff_frame'] == event['suspect_frame']-1
                    assert all(x['frame'] < event['suspect_frame'] for x in samples)
                    assert all(b['frame'] == a['frame']+1 and b['time'] > a['time']
                               for a, b in zip(samples, samples[1:]))
                    if samples:
                        assert frozen['key'][0] == name and frozen['key'][1] == arm
                        assert frozen['key'][3] == frozen['public']
                    for sample in samples:
                        live = states[(sample['frame'], arm)]['live'].get(str(frozen['source']))
                        assert live and live['key'] == frozen['key']
                        assert sample['frame'] in live['sample_frames']
                        if arm in ('D4_F6_SCALAR', 'D5_MULTIFRAGMENT'):
                            fact = measured[sample['frame']]['f6'][str(frozen['source'])]
                            assert fact['history_usable'] and fact['qualified_piece_count'] == 1
                            assert sample['z_mm'] == fact['history_core']['median']
                            assert sample['fact_id'] == fact['fact_id']
                        history_checks += 1
                q = event['q']
                if q is None:
                    continue
                assert event['evidence_cutoff_frame'] == q
                assert all(x['frame'] == q for x in event['post_first_observations'].values())
                pub = ledger[q]['event_publish'][arm]
                assert pub['episode'] == event['id'] and pub['q'] == q
                assert pub['post_sample_count'] == 1
                mapping = {int(x['mask'][2:]): x['id'] for x in actual[q-1]['variants'][arm]}
                sources = {int(n) for n in event['post_first_observations']}
                assert len(sources) == 2
                assert {int(n): v for n, v in pub['first_public_pair'].items()} == {n: mapping[n] for n in sources}
                if not event['restore']['status'].startswith('LOCAL_FALLBACK'):
                    assert {int(n): v for n, v in event['restore']['mapping'].items()} == {n: mapping[n] for n in sources}
                    for n in sources:
                        live = states[(q, arm)]['live'].get(str(n))
                        assert not live or all(f >= q for f in live['sample_frames'])
                detail = event['numeric']['detail']
                if arm in ('D4_F6_SCALAR', 'D5_MULTIFRAGMENT') and 'edges' in detail:
                    assert detail['evidence_max_frame'] == q
                    if not detail['joint_available']:
                        assert detail['used_edges'] == 0
                        assert all(x['cost'] == 0 and not x['available'] for x in detail['edges'].values())
                q_checks += 1
        for shadow in read(public/'COMMON_STATE_SHADOW.json'):
            event = next(x for x in events['D5_MULTIFRAGMENT'] if x['id'] == shadow['event'])
            assert shadow['submitted'] is False and shadow['frame'] == event['q']
            assert shadow['multi_choice'] == event['numeric']['choice']
            assert shadow['multi'] == event['numeric']['detail']
            assert shadow['multi'].get('joint_available') == shadow['scalar'].get('joint_available')
            shadow_checks += 1
        checked.append(dict(segment=name, frames=len(actual), native_exact=True,
                            legacy_equivalence=verify_legacy_equivalence(name, actual)))
    result = dict(status='PASS_BEFORE_GT_SCORING', segments=checked,
        first_publication_checks=q_checks, group_checks=group_checks,
        frozen_sample_checks=history_checks, common_state_shadow_checks=shadow_checks,
        group_violations=0, deleted_masks=0, all_prediction_seals_verified=True,
        access_audit_sha256=sha(Path(run)/'PREDICTION_ACCESS_AUDIT.json'),
        access_seal_sha256=sha(Path(run)/'ACCESS_SEALED.json'))
    write_new(Path(run)/'VERIFICATION.json', result)
    return result


def namespaced(ids, segment_index):
    return [(segment_index, int(identity)) for identity in ids]


def score(run=RUN):
    verify_all_seals(run)
    verification = read(Path(run)/'VERIFICATION.json')
    assert verification['status'] == 'PASS_BEFORE_GT_SCORING'
    combined_truth, combined_sims = [], []
    combined = {arm: [] for arm in ARMS}
    segment_metrics, reference, changed = {}, {}, {}
    pairs = [(arm, 'SAM3_NATIVE') for arm in ARMS[1:]] + [
        ('D5_MULTIFRAGMENT', arm) for arm in ('D0_GEOMETRY', 'D2_CORE_FROZEN', 'D4_F6_SCALAR')]
    for index, (name, (start, stop)) in enumerate(SEGMENTS.items()):
        truth, sims = [], []
        predictions = {arm: [] for arm in ARMS}
        reference_hash = hashlib.sha256()
        changed[name] = {f'{a}_vs_{b}': 0 for a, b in pairs}
        for local, (assignment, prediction) in enumerate(zip(
                rows(input_dir(name)/'assignments.jsonl.gz'),
                rows(Path(run)/name/'public/predictions.jsonl.gz'), strict=True), 1):
            native = check_objects(assignment, prediction)
            assert assignment['frame'] == prediction['frame'] == local
            assert assignment['global_frame_id'] == prediction['global_frame'] == start+local-1
            path = DATA/'labels_640x360'/f'{start+local-1:06d}.json'
            raw = path.read_bytes()
            reference_hash.update(path.name.encode()+b'\0'+raw)
            gt_ids, gt_masks = mask_rles(json.loads(raw)['shapes'])
            masks = [original_score.rle(assignment['masks'][key]) for key in native]
            sim = (np.asarray(coco.iou(gt_masks, masks, [0]*len(masks)), float)
                   if gt_masks and masks else np.zeros((len(gt_ids), len(native))))
            truth.append(gt_ids); sims.append(sim)
            combined_truth.append(namespaced(gt_ids, index)); combined_sims.append(sim)
            for arm in ARMS:
                ids = [int(x['id']) for x in prediction['variants'][arm]]
                predictions[arm].append(ids)
                combined[arm].append(namespaced(ids, index))
            for a, b in pairs:
                changed[name][f'{a}_vs_{b}'] += prediction['variants'][a] != prediction['variants'][b]
        assert len(truth) == stop-start+1
        segment_metrics[name] = {arm: metrics(truth, predictions[arm], sims) for arm in ARMS}
        reference[name] = dict(label_dir=str(DATA/'labels_640x360'), frames=len(truth),
            ordered_file_bytes_sha256=reference_hash.hexdigest(),
            qualification='existing human-edited RGB polygons; not independently certified',
            physical_depth_gt=False, pixel_surface_gt=False)
    pooled = {arm: metrics(combined_truth, combined[arm], combined_sims) for arm in ARMS}
    for arm in ARMS:
        for key in ('IDSW', 'FP', 'FN', 'GT', 'predictions'):
            assert pooled[arm][key] == sum(x[arm][key] for x in segment_metrics.values()), (arm, key)
    delta = {f'{a}_vs_{b}': {key: pooled[a][key]-pooled[b][key]
        for key in ('IDF1', 'HOTA', 'AssA', 'DetA', 'IDSW', 'FP', 'FN')} for a, b in pairs}
    support = {other: dict(rate_improvements={key: pooled['D5_MULTIFRAGMENT'][key] > pooled[other][key]
                  for key in ('IDF1', 'HOTA', 'AssA')},
                  idsw_not_increased=pooled['D5_MULTIFRAGMENT']['IDSW'] <= pooled[other]['IDSW'])
               for other in ('D0_GEOMETRY', 'SAM3_NATIVE')}
    supported = all(all(x['rate_improvements'].values()) and x['idsw_not_increased'] for x in support.values())
    result = dict(status='SCORED_AFTER_ALL_PREDICTION_SEALS', frames=len(combined_truth),
        segment_metrics=segment_metrics, pooled_metrics=pooled, pooled_delta=delta,
        changed_frames=changed, reference=reference,
        seal_sha256={name: sha(Path(run)/name/'public/PREDICTIONS_SEALED.json') for name in SEGMENTS},
        all_seal_sha256=sha(Path(run)/'ALL_PREDICTIONS_SEALED.json'),
        no_negative_id_filtering=True, segment_identity_reset=True,
        pooled_method='direct_TrackEval_on_all_frames_with_tuple_segment_identity_namespaces',
        frozen_support_rule=support, frozen_support_rule_met=supported,
        interpretation='exposed development-set tracking result; no physical-depth or surface-ownership GT',
        new_model_http=0, model_cost_usd=0)
    assert result['frames'] == 1471
    write_new(Path(run)/'METRICS.json', result)
    write_new(Path(run)/'SCORE_PROVENANCE.json', dict(evaluate_sha256=sha(__file__),
        event_audit_sha256=sha(HERE/'event_audit.py'), legacy_helpers_sha256=sha(NE1/'score.py'),
        scored_after_all_seals=True, trackeval_path=str(original_score.DEPS),
        reference=reference, segment_seal_sha256=result['seal_sha256'],
        all_seal_sha256=result['all_seal_sha256'], verification_sha256=sha(Path(run)/'VERIFICATION.json')))
    return result


def main():
    verify_publication()
    result = score()
    import event_audit
    event_audit.audit(sys.modules[__name__])
    print(json.dumps(dict(pooled=result['pooled_metrics'], delta=result['pooled_delta'],
                          support_rule_met=result['frozen_support_rule_met']), ensure_ascii=False))


if __name__ == '__main__':
    main()
