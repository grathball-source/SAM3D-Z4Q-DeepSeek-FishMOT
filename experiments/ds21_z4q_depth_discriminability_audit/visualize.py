"""Fixed postseal action diagnostics from original raw pixels and published IDs."""
from pathlib import Path
from datetime import datetime
import json
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DS20 = ROOT / 'experiments/ds20_pending_confirmation_isolation'
sys.path.insert(0, str(DS20))
from common import artifact, input_dir, read, rows, sha, write_new, SEGMENTS
from source import RawDepth, native_masks

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ARMS = ('SAM3_NATIVE', 'Z4Q_FROZEN')
UNITS = ('Feeding', 'fishsa_development_8400', 'fishsa_validation_2888', 'L3', 'LW')
GRADES = ('CORRECT', 'WRONG', 'UNSCORABLE')


def select_cases(actions):
    """Earliest action in every fixed unit/grade; never replace an awkward case."""
    result, absent = [], []
    for unit in UNITS:
        eligible = [a for a in actions if
            (a['segment'].startswith('feeding_') if unit == 'Feeding' else a['segment'] == unit)]
        for grade in GRADES:
            candidates = [a for a in eligible if a['physical'] == grade]
            if candidates:
                result.append(min(candidates, key=lambda a:
                    (a['global_frame'], a['segment'], a['frame'], a['source'], a['target'], a['action_id'])))
            else:
                absent.append(dict(unit=unit, physical=grade, reason='NO_SEALED_ACTION_IN_THIS_STRATUM'))
    assert len(result) <= 15 and len({a['action_id'] for a in result}) == len(result)
    return result, absent


def requested_frames(action):
    query = action['frame']
    last = SEGMENTS[action['segment']][1] - SEGMENTS[action['segment']][0] + 1
    anchor = action['actual_old_anchor']['frame']
    assert 1 <= anchor < query <= last
    return [('ACTUAL_OLD_ANCHOR', anchor), ('COMMIT_PREVIOUS_FRAME', max(1, query - 1)),
            ('ACTUAL_COMMIT_FRAME', query), ('POSTSEAL_ONLY_COMMIT_PLUS_5', min(last, query + 5))]


def selfcheck():
    """Selection and time bounds without reading labels, pixels or old artifacts."""
    def action(identifier, segment, frame, original, grade, source=2):
        return dict(action_id=identifier, segment=segment, frame=frame, global_frame=original,
            physical=grade, source=source, target=1, actual_old_anchor=dict(frame=1, native_id=1))
    samples = [action('later-feeding', 'feeding_000351_000555', 2, 352, 'CORRECT'),
        action('first-feeding', 'feeding_000000_000199', 3, 2, 'CORRECT'),
        action('wrong', 'feeding_000000_000199', 4, 3, 'WRONG'),
        action('lw-unknown', 'LW', 3628, 3627, 'UNSCORABLE')]
    selected, absent = select_cases(list(reversed(samples)))
    assert [a['action_id'] for a in selected] == ['first-feeding', 'wrong', 'lw-unknown']
    assert len(absent) == 12 and dict(unit='Feeding', physical='UNSCORABLE',
        reason='NO_SEALED_ACTION_IN_THIS_STRATUM') in absent
    assert requested_frames(samples[-1])[-1][1] == 3629
    broken = dict(samples[1], actual_old_anchor=dict(frame=3, native_id=1))
    try:
        requested_frames(broken)
    except AssertionError:
        pass
    else:
        raise AssertionError('Noncausal old anchor accepted')
    return dict(status='PASS', checks=4, scope='Fixed chronology/absent strata/segment-end clamp/causal anchor')


def verified_actions():
    """Read the complete feature/action/old-label chain before choosing pictures."""
    freeze_path = HERE / 'FREEZE.json'
    freeze = read(freeze_path)
    assert freeze['status'] == 'FROZEN_BEFORE_DIAGNOSTIC_FEATURES_AND_LABEL_JOIN'
    assert str(Path(__file__).resolve()) in freeze['code']
    for name, expected in freeze['code'].items():
        path = Path(name)
        assert path.stat().st_size == expected['bytes'] and sha(path) == expected['sha256'], name
    action_path, feature_path = HERE / 'ACTIONS.json', HERE / 'FEATURES_SEALED.json'
    summary, actions, seal = read(HERE / 'AUDIT_SUMMARY.json'), read(action_path), read(feature_path)
    assert summary['status'] == 'COMPLETE_READONLY_ALL_EIGHT_SEGMENT_ACTION_AUDIT'
    assert actions['status'] == 'ALL_ORIGINAL_DURABLE_ACTIONS_EXACTLY_BOUND_TO_EXISTING_POSTSEAL_LABELS'
    assert seal['status'] == 'ALL_PRELABEL_FEATURES_SEALED_BEFORE_EXISTING_LABEL_READ'
    assert summary['action_artifact'] == artifact(action_path)
    assert summary['feature_seal'] == actions['feature_seal'] == artifact(feature_path)
    assert seal['code'] == artifact(HERE / 'audit.py')
    expected_features = {str((HERE / name).resolve()) for name in
        ('FEATURES.jsonl.gz', 'OBSERVATION_FACTS.jsonl.gz', 'CANDIDATES.jsonl.gz')}
    assert {str(Path(item['path']).resolve()) for item in seal['artifacts']} == expected_features
    for item in seal['artifacts']:
        assert artifact(item['path']) == item
    assert seal['begin_source_check'] == artifact(HERE / 'BEGIN_SOURCE_CHECK.json')
    begin = read(HERE / 'BEGIN_SOURCE_CHECK.json')
    assert begin['status'] == 'ALL_EIGHT_ORIGINAL_PREDICTION_AND_CACHE_SEALS_VERIFIED'
    assert begin['freeze'] == artifact(freeze_path) and begin['physical_labels_opened'] is False
    assert datetime.fromisoformat(seal['sealed_at_utc']) <= datetime.fromisoformat(
        actions['label_join_started_at_utc']) <= datetime.fromisoformat(actions['label_join_finished_at_utc'])
    pins = {Path(item['path']).resolve(): item for item in begin['artifacts']}
    records = actions['actions']
    features = {item['action_id']: item for item in rows(HERE / 'FEATURES.jsonl.gz')}
    assert len(features) == len(records) == seal['accepted_actions'] == summary['accepted_actions']
    assert {item['action_id'] for item in records} == set(features)
    for action in records:
        assert all(action[key] == value for key, value in features[action['action_id']].items())
    for name in SEGMENTS:
        public = DS20 / 'run' / name / 'public'
        for filename in ('PREDICTIONS_SEALED.json', 'FREEZE.json', 'AUTOMATIC_RECONNECT_AUDIT.json'):
            path = public / filename
            assert artifact(path) == pins[path.resolve()], (name, filename, 'PRELABEL_SOURCE_PIN_MISMATCH')
        old_audit = read(public / 'AUTOMATIC_RECONNECT_AUDIT.json')['arms']['Z4Q_FROZEN']
        own = [item for item in records if item['segment'] == name]
        assert len(own) == len(old_audit)
        labels = {(item['frame'], item['source'], item['target'], item['origin_rule']): item for item in old_audit}
        assert len(labels) == len(old_audit)
        for action in own:
            label = labels[(action['frame'], action['source'], action['target'], action['origin_rule'])]
            assert action['sealed_physical_record'] == label
            assert action['original_action'] == label['actual_controller_action']
            assert action['actual_old_anchor'] == label['actual_old_anchor']
            assert action['physical'] == label['physical'] and action['physical'] in GRADES
    return records, dict(feature_seal=artifact(feature_path), begin_source_check=artifact(HERE / 'BEGIN_SOURCE_CHECK.json'),
        frozen_code=artifact(freeze_path), action_records=artifact(action_path),
        exact_complete_old_physical_audits_bound=True)


def prepare_segment(name, frames):
    """Verify saved predictions, original masks and exact actual raw depth binding."""
    public = DS20 / 'run' / name / 'public'
    seal_path = public / 'PREDICTIONS_SEALED.json'
    seal = read(seal_path)
    assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
    paths = {key: public / key for key in ('predictions.jsonl.gz', 'DEPTH_OBSERVATIONS.jsonl.gz')}
    for key, path in paths.items():
        assert sha(path) == seal['artifacts_sha256'][key], (name, key)
    source = input_dir(name)
    manifest = read(source / 'SOURCE_MANIFEST.json')
    assignment_path = source / 'assignments.jsonl.gz'
    expected = manifest['derived_inputs']['assignments.jsonl.gz']
    assert assignment_path.stat().st_size == expected['bytes'] and sha(assignment_path) == expected['sha256']
    predictions = {r['frame']: r for r in rows(paths['predictions.jsonl.gz']) if r['frame'] in frames}
    measurements = {r['frame']: r for r in rows(paths['DEPTH_OBSERVATIONS.jsonl.gz']) if r['frame'] in frames}
    assignments = {r['frame']: r for r in rows(assignment_path) if r['frame'] in frames}
    assert set(predictions) == set(measurements) == set(assignments) == set(frames)
    sensor, material = RawDepth(name), {}
    try:
        for frame in sorted(frames):
            row, measured, assignment = predictions[frame], measurements[frame], assignments[frame]
            assert (measured['segment'], measured['frame'], measured['global_frame'], measured['time']) == (
                name, frame, row['global_frame'], row['time'])
            assert (assignment['frame'], assignment['global_frame_id'], assignment['time']) == (
                frame, row['global_frame'], row['time'])
            depth, _, _, binding = sensor(row['global_frame'], row['time'])
            assert binding == measured['raw_source_binding'], (name, frame, 'ACTUAL_RAW_BINDING_MISMATCH')
            masks = native_masks(assignment)
            maps = {arm: {int(item['mask'][2:]): item['id'] for item in row['variants'][arm]} for arm in ARMS}
            assert all(set(mapping) == set(masks) and len(set(mapping.values())) == len(mapping)
                       for mapping in maps.values())
            material[frame] = dict(depth=depth, masks=masks, mapping=maps,
                global_frame=row['global_frame'], time=row['time'], raw_source_binding=binding)
    finally:
        sensor.close()
    evidence = dict(prediction_seal=artifact(seal_path), predictions=artifact(paths['predictions.jsonl.gz']),
        original_assignments=artifact(assignment_path), original_source_manifest=artifact(source / 'SOURCE_MANIFEST.json'),
        depth_observations=artifact(paths['DEPTH_OBSERVATIONS.jsonl.gz']))
    return material, evidence


def draw_case(action, material, evidence, number, out):
    name, query, anchor = action['segment'], action['frame'], action['actual_old_anchor']
    panels = requested_frames(action)
    current = material[query]
    shape = current['depth'].shape
    assert shape == (360, 640) and all(material[f]['depth'].shape == shape for _, f in panels)
    assert action['source'] in current['masks'] and anchor['native_id'] in material[anchor['frame']]['masks']
    assert current['mapping']['Z4Q_FROZEN'][action['source']] == action['target']
    union = current['masks'][action['source']] | material[anchor['frame']]['masks'][anchor['native_id']]
    ys, xs = np.where(union)
    assert len(xs), 'Actual source/anchor masks cannot be empty'
    x0, y0 = max(0, int(xs.min()) - 24), max(0, int(ys.min()) - 24)
    x1, y1 = min(shape[1], int(xs.max()) + 25), min(shape[0], int(ys.max()) + 25)
    values = np.concatenate([material[f]['depth'][np.isfinite(material[f]['depth']) &
        (material[f]['depth'] > 0)] for f in sorted(set(f for _, f in panels))])
    lo, hi = map(float, np.quantile(values, [.02, .98])) if len(values) else (0., 1.)
    if hi <= lo:
        hi = lo + 1.
    fig, axes = plt.subplots(2, 4, figsize=(18, 9), squeeze=False)
    for col, (role, frame) in enumerate(panels):
        item = material[frame]
        depth = item['depth'][y0:y1, x0:x1]
        for row, arm in enumerate(ARMS):
            ax = axes[row, col]
            ax.imshow(np.where(np.isfinite(depth) & (depth > 0), depth, np.nan),
                cmap='viridis', vmin=lo, vmax=hi)
            visible = 0
            for native, mask in sorted(item['masks'].items()):
                cropped = mask[y0:y1, x0:x1]
                if not cropped.any():
                    continue
                visible += 1
                color = 'red' if native == action['source'] else 'orange' if native == anchor['native_id'] else 'white'
                if cropped.any() and not cropped.all():
                    ax.contour(cropped, levels=[.5], colors=color, linewidths=.8)
                yy, xx = np.where(cropped)
                ax.text(xx.mean(), yy.mean(), f'n{native}:p{item["mapping"][arm][native]}', fontsize=7,
                    color='black', bbox=dict(facecolor='white', alpha=.8, pad=.3))
            ax.set_title(f'{arm}\n{role}\nlocal {frame} / original {item["global_frame"]} / {visible} visible masks', fontsize=9)
            ax.axis('off')
    fig.suptitle(f'{name}: {action["origin_rule"]} n{action["source"]} -> p{action["target"]}; '
        f'sealed physical grade={action["physical"]}\n'
        f'raw depth {lo:.0f}-{hi:.0f} mm; surface/layer ownership UNKNOWN; no RGB/GT raster; '
        'right column is postseal diagnosis only', fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, .94))
    path = out / f'{number:02d}_{name}_local{query}_{action["physical"]}.png'
    assert not path.exists(), 'Never overwrite a diagnostic figure'
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return dict(action_id=action['action_id'], segment=name, frame=query,
        global_frame=action['global_frame'], physical=action['physical'], origin_rule=action['origin_rule'],
        source=action['source'], target=action['target'], actual_old_anchor=anchor,
        selection_policy='EARLIEST_SEALED_ORIGINAL_Z4Q_ACTION_PER_FIXED_EVALUATION_UNIT_AND_PHYSICAL_GRADE',
        artifact=artifact(path), panels=[dict(role=role, frame=frame,
            global_frame=material[frame]['global_frame'], time=material[frame]['time'],
            raw_source_binding=material[frame]['raw_source_binding'],
            actual_mapping=material[frame]['mapping'], all_frame_native_masks=len(material[frame]['masks']))
            for role, frame in panels],
        roi=dict(xyxy=[x0, y0, x1, y1], full_shape=list(shape), padding_px=24,
            source_frame=query, source_native=action['source'], anchor_frame=anchor['frame'],
            anchor_native=anchor['native_id'], definition='ACTUAL_CURRENT_SOURCE_AND_EXACT_OLD_ANCHOR_MASK_UNION',
            coordinates='SAME_FROZEN_640X360_RGB_CAMERA_GRID',
            transform='crop(x,y)=(full_x-x0,full_y-y0); no resampling', GT_selected=False),
        depth_scale_mm=[lo, hi], same_scale_across_frames_and_branches=True,
        original_evidence=evidence, layer_ownership='UNKNOWN', future_used_for_prediction=False)


def main():
    actions, chain = verified_actions()
    cases, absent = select_cases(actions)
    assert cases and not (HERE / 'PRIVATE_VISUALS.json').exists()
    material, evidence = {}, {}
    for name in sorted({a['segment'] for a in cases}):
        frames = {frame for a in cases if a['segment'] == name for _, frame in requested_frames(a)}
        material[name], evidence[name] = prepare_segment(name, frames)
    out = HERE / 'private/visuals'
    out.mkdir(parents=True, exist_ok=True)
    figures = [draw_case(a, material[a['segment']], evidence[a['segment']], i, out)
               for i, a in enumerate(cases, 1)]
    write_new(HERE / 'PRIVATE_VISUALS.json', dict(status='FIXED_POSTSEAL_ORIGINAL_Z4Q_ACTION_DIAGNOSTICS',
        verified_input_chain=chain, action_count=len(actions), figures=figures, absent_strata=absent,
        evaluation_units=list(UNITS), physical_grades=list(GRADES), maximum_cases=15,
        private_pixels=True, GT_raster=False, RGB=False, postseal_future_diagnosis_only=True,
        no_tracking_replay=True, new_model_http=0, cost_usd=0,
        not_independent_validation=True, no_case_replacement=True))
    print(json.dumps(dict(status='PASS', figures=len(figures), absent_strata=len(absent),
        layer_ownership='UNKNOWN', new_predictions=0, new_model_http=0)))


if __name__ == '__main__':
    main()
