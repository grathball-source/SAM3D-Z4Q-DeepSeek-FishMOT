"""Fixed DS21 cases: exact raw depth, local plane residual and retained support.

All rasters are private diagnostic products. A retained support component is
a measurement region, never certified fish ownership or identity truth.
"""
from pathlib import Path
import json
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DS21 = ROOT / 'experiments/ds21_z4q_depth_discriminability_audit'
sys.path.insert(0, str(HERE))
import run
from measurement import measure_local_background
from common import artifact, read, rows, write_new
from source import RawDepth
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def endpoint_ids(action):
    """Primary reference and actual current only; no post-query frame enters."""
    current, anchor = action['current_fact_id'], action['actual_anchor_fact_id']
    for identifier in (current, anchor):
        assert identifier.startswith(action['segment'] + '/F')
    af = int(anchor.split('/F')[1].split('/')[0])
    cf = int(current.split('/F')[1].split('/')[0])
    assert af < cf == action['frame'], 'Exact prior reference and current query required'
    return [('ACTUAL_PRIMARY_REFERENCE', anchor), ('ACTUAL_CURRENT_OBSERVATION', current)]


def crop_bounds(masks, shape, padding=24):
    """A shared geometric crop; no resampling or depth-selected pixel region."""
    assert all(mask.shape == shape for mask in masks)
    yy, xx = np.where(np.logical_or.reduce(masks))
    assert len(xx), 'An actual endpoint mask is empty'
    return (max(0, int(xx.min()) - padding), max(0, int(yy.min()) - padding),
            min(shape[1], int(xx.max()) + padding + 1), min(shape[0], int(yy.max()) + padding + 1))


def selfcheck():
    sample = dict(segment='L3', frame=9,
        current_fact_id='L3/F9/n:4/observation', actual_anchor_fact_id='L3/F3/n:1/observation')
    assert endpoint_ids(sample) == [('ACTUAL_PRIMARY_REFERENCE', 'L3/F3/n:1/observation'),
        ('ACTUAL_CURRENT_OBSERVATION', 'L3/F9/n:4/observation')]
    rejected = False
    try:
        endpoint_ids(dict(sample, actual_anchor_fact_id='L3/F10/n:1/observation'))
    except AssertionError:
        rejected = True
    assert rejected
    a, b = np.zeros((5, 8), bool), np.zeros((5, 8), bool)
    a[0, 2], b[4, 5] = True, True
    box = crop_bounds([a, b], a.shape, padding=1)
    assert box == (1, 0, 7, 5)
    raster = np.arange(40).reshape(5, 8)
    x0, y0, x1, y1 = box
    assert np.array_equal(raster[y0:y1, x0:x1], raster[:, 1:7])
    return dict(status='PASS', checks=2,
        scope='Only exact pre-query/current endpoints; common union crop without resampling')


def verified_selection():
    """Use the already fixed ten figures; neither a new score nor support picks cases."""
    old = read(DS21 / 'PRIVATE_VISUALS.json')
    action_path = DS21 / 'ACTIONS.json'
    assert old['verified_input_chain']['action_records'] == artifact(action_path)
    actions = {a['action_id']: a for a in read(action_path)['actions']}
    selected = [actions[item['action_id']] for item in old['figures']]
    assert len(actions) == 90 and len(selected) == 10 and len(old['absent_strata']) == 5
    assert len({a['action_id'] for a in selected}) == 10
    for item, action in zip(old['figures'], selected, strict=True):
        assert (item['segment'], item['frame'], item['global_frame'], item['physical']) == (
            action['segment'], action['frame'], action['global_frame'], action['physical'])
        endpoint_ids(action)
    return selected, old['absent_strata'], dict(
        original_fixed_inventory=artifact(DS21 / 'PRIVATE_VISUALS.json'),
        original_actions=artifact(action_path), unchanged_action_ids=True)


def sealed_measurements():
    seal_path, data_path = HERE / 'MEASUREMENTS_SEALED.json', HERE / 'MEASUREMENTS.jsonl.gz'
    seal = run.verify_measurement_seal()
    assert artifact(data_path) == seal['measurement_artifact']
    measured = {item['fact_id']: item for item in rows(data_path)}
    assert len(measured) == sum(1 for _ in rows(data_path)), 'Duplicate endpoint measurements'
    return measured, dict(measurement_seal=artifact(seal_path), measurements=artifact(data_path))


def prepare_cases(cases, features, measured):
    facts, assignments, pins = run.load_sources(features)
    requests = {fid for action in cases for _, fid in endpoint_ids(action)}
    assert requests <= set(facts) & set(measured)
    materials = {}
    for name in sorted({facts[fid]['segment'] for fid in requests}):
        sensor = RawDepth(name)
        try:
            for fid in sorted((fid for fid in requests if facts[fid]['segment'] == name),
                              key=lambda fid: (facts[fid]['frame'], facts[fid]['native'])):
                fact = facts[fid]
                frame = run.load_endpoint_frame(name, fact['frame'], facts, assignments, sensor)
                numeric, private = measure_local_background(frame['depth'], frame['source_index'],
                    frame['native_depth'], frame['masks'], fact['native'], name, fact['frame'],
                    fact['global_frame'], fact['time'], source_binding=frame['source_binding'],
                    expected_source_binding=fact['_raw_measurement']['raw_source_binding'])
                assert numeric == measured[fid]['measurement'], (fid, 'Reopened raw-source measurement differs')
                assert numeric['source_binding'] == frame['source_binding'], (fid, 'Actual source-binding differs')
                materials[fid] = dict(frame=frame, fact=fact, measurement=numeric, arrays=private)
        finally:
            sensor.close()
    return materials, pins


def finite_limits(values):
    valid = np.concatenate([v[np.isfinite(v) & (v > 0)] for v in values])
    lo, hi = map(float, np.quantile(valid, [.02, .98])) if len(valid) else (0., 1.)
    return (lo, hi if hi > lo else lo + 1.)


def draw_case(action, material, number, out):
    endpoints = endpoint_ids(action)
    examples = [material[fid] for _, fid in endpoints]
    shape = examples[0]['frame']['depth'].shape
    assert shape == (360, 640) and all(item['frame']['depth'].shape == shape for item in examples)
    mask_list = [item['frame']['masks'][item['fact']['native']] for item in examples]
    x0, y0, x1, y1 = crop_bounds(mask_list, shape)
    crop = np.s_[y0:y1, x0:x1]
    lo, hi = finite_limits([item['frame']['depth'][crop] for item in examples])
    fig, axes = plt.subplots(2, 4, figsize=(19, 10), squeeze=False)
    for row, ((role, fid), item) in enumerate(zip(endpoints, examples, strict=True)):
        frame, fact, measured, arrays = (item[key] for key in ('frame', 'fact', 'measurement', 'arrays'))
        depth = frame['depth'][crop]
        plane = arrays['plane_mm'][crop]
        residual = arrays['residual_mm'][crop]
        support = np.where(arrays['qualified_support'], arrays['component_labels'], 0)[crop]
        ring = arrays['background_selected'][crop]
        fit = measured['plane'] or {}
        threshold = fit.get('contrast_threshold_mm')
        res_limit = max(60., 2. * threshold) if threshold is not None else 60.
        views = [np.where(np.isfinite(depth) & (depth > 0), depth, np.nan), plane, residual,
                 np.where(support > 0, support, np.nan)]
        cmaps = ('viridis', 'viridis', 'coolwarm', 'tab20')
        titles = ('Raw aligned depth [mm]', 'Fitted local background [mm]',
                  'Depth minus local background [mm]', 'Retained measurement components')
        for col, (view, cmap, title) in enumerate(zip(views, cmaps, titles, strict=True)):
            ax = axes[row, col]
            limits = dict(vmin=lo, vmax=hi) if col < 2 else dict(vmin=-res_limit, vmax=res_limit) if col == 2 else {}
            image = ax.imshow(view, cmap=cmap, **limits)
            for native, mask in sorted(frame['masks'].items()):
                region = mask[crop]
                if region.any() and not region.all():
                    ax.contour(region, levels=[.5], colors='black' if native == fact['native'] else 'orange',
                               linewidths=1.2 if native == fact['native'] else .5)
            if col == 1:
                yy, xx = np.where(ring)
                ax.scatter(xx, yy, s=2, c='black', alpha=.35)
            ax.set_title(title, fontsize=10)
            ax.axis('off')
            if col < 3:
                fig.colorbar(image, ax=ax, fraction=.04, pad=.02)
            if not np.isfinite(view).any():
                ax.text(.5, .5, 'UNKNOWN / no usable support', transform=ax.transAxes, ha='center',
                    va='center', fontsize=9, bbox=dict(facecolor='white', alpha=.9))
        axes[row, 0].text(0, -.10, f'{role}\n{fid}\noriginal F{fact["global_frame"]}; '
            f'local F{fact["frame"]}; native n{fact["native"]}', transform=axes[row, 0].transAxes, fontsize=8)
        axes[row, 1].text(0, -.10, f'background fit={"PRESENT" if fit else "UNKNOWN"}; '
            f'independent samples={fit.get("sample_n", measured["background"]["summary"]["n"])}\n'
            f'residual scale={fit.get("residual_scale_mm")} mm; contrast={threshold} mm',
            transform=axes[row, 1].transAxes, fontsize=8)
        axes[row, 2].text(0, -.10, 'Orange outlines: other actual masks\n'
            'Black outline: target mask; sign describes sensor Z', transform=axes[row, 2].transAxes, fontsize=8)
        axes[row, 3].text(0, -.10, f'endpoint status={measured["status"]}; '
            f'qualified independent N={measured["qualified_independent_n"]}\n'
            'Component support is not fish ownership or identity truth', transform=axes[row, 3].transAxes, fontsize=8)
    fig.suptitle(f'{action["segment"]}: original {action["origin_rule"]} '
        f'n{action["source"]} -> p{action["target"]}; existing postseal grade={action["physical"]}\n'
        'Raw depth only; exact original endpoints; no RGB, GT raster or future frame; '
        'surface ownership UNKNOWN', fontsize=12)
    fig.tight_layout(rect=(0, .05, 1, .92), h_pad=5)
    path = out / f'{number:02d}_{action["segment"]}_local{action["frame"]}_{action["physical"]}.png'
    assert not path.exists(), 'Never overwrite a diagnostic figure'
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return dict(action_id=action['action_id'], segment=action['segment'], frame=action['frame'],
        global_frame=action['global_frame'], physical=action['physical'], artifact=artifact(path),
        actual_endpoint_fact_ids=[fid for _, fid in endpoints],
        panels=[dict(role=role, fact_id=fid, frame=material[fid]['fact']['frame'],
            global_frame=material[fid]['fact']['global_frame'], native=material[fid]['fact']['native'],
            raw_source_binding=material[fid]['frame']['source_binding'],
            measurement_record_sha256=run.digest(material[fid]['measurement']),
            public_measurement_equals_reopened_actual_source=True)
            for role, fid in endpoints],
        roi=dict(xyxy=[x0, y0, x1, y1], full_shape=list(shape), padding_px=24,
            definition='EXACT_ACTUAL_PRIMARY_REFERENCE_AND_CURRENT_MASK_UNION',
            transform='crop(x,y)=(full_x-x0,full_y-y0); no resampling',
            coordinates='SAME_FROZEN_640X360_RGB_CAMERA_GRID', GT_selected=False),
        raw_and_plane_depth_scale_mm=[lo, hi], physical_surface_identity='UNKNOWN',
        future_read=False, no_new_prediction=True)


def main():
    run.verify_freeze()
    assert not (HERE / 'PRIVATE_VISUALS.json').exists()
    measured, measurement_chain = sealed_measurements()
    cases, absent, old_selection = verified_selection()
    features = run.load_features()
    materials, pins = prepare_cases(cases, features, measured)
    out = HERE / 'private/visuals'
    out.mkdir(parents=True, exist_ok=True)
    figures = [draw_case(action, materials, i, out) for i, action in enumerate(cases, 1)]
    write_new(HERE / 'PRIVATE_VISUALS.json', dict(status='FIXED_ORIGINAL_ENDPOINT_LOCAL_BACKGROUND_DIAGNOSTICS',
        figures=figures, absent_strata=absent, old_fixed_selection=old_selection,
        measurement_chain=measurement_chain, input_pins=pins,
        selection='IDENTICAL_DS21_TEN_ACTION_IDS_AND_FIVE_ABSENT_STRATA; NO_REPLACEMENT',
        private_pixels=True, RGB=False, GT_raster=False, no_future_frame_read=True,
        no_tracking_replay=True, surface_identity='UNKNOWN', new_model_http=0, cost_usd=0))
    print(json.dumps(dict(status='PASS', figures=len(figures), absent_strata=len(absent),
        exact_reopened_raw_numeric_equivalence=True, new_predictions=0, new_model_http=0)))


if __name__ == '__main__':
    main()
