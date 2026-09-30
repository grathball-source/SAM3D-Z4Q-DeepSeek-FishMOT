"""Read-only DS3 mechanism audit; geometry first, sealed occupancy joined last."""
import json
import socket
import sys
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT/'experiments/ds3_depth_foreground_filter'
sys.path.insert(0, str(OLD))
from common import (SEGMENTS, CFG, records, decode, load_depth, KERNEL, cv2, np,
                    artifact, verify, write_new)  # noqa: E402
from foreground import scale  # noqa: E402


def quantiles(values):
    values = [v for v in values if v is not None]
    return dict(zip(('min', 'q10', 'median', 'q90', 'max'),
                    map(float, np.quantile(values, [0, .1, .5, .9, 1])))) if values else None


def geometry(own, exclusive, selected, support):
    """Seeds depend only on original mask geometry, before any depth selection."""
    core = cv2.erode(exclusive.astype('u1'), KERNEL).astype(bool)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(own.astype('u1'), connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA]
    main = 1+int(np.argmax(areas))
    radius = cv2.distanceTransform(exclusive.astype('u1'), cv2.DIST_L2, 5)
    peak = np.unravel_index(np.argmax(radius), radius.shape) if exclusive.any() else None
    n = int(selected.sum())
    result = dict(source_components=count-1, source_component_areas=areas.tolist(),
        source_main_unique=bool((areas == areas.max()).sum() == 1),
        core_area=int(core.sum()), selected_core_n=int((selected & core).sum()),
        support_core_area=int((support & core).sum()),
        selected_main_n=int((selected & (labels == main)).sum()),
        selected_source_labels=np.unique(labels[selected]).tolist(),
        core_source_labels=np.unique(labels[core]).tolist(),
        source_main_area=int(areas[main-1]),
        selected_main_fraction=float((selected & (labels == main)).sum()/n) if n else None,
        medial_radius_px=float(radius[peak]) if peak is not None else None,
        medial_peak_local_xy=[int(peak[1]), int(peak[0])] if peak is not None else None,
        medial_peak_in_selected=bool(selected[peak]) if peak is not None else False,
        medial_peak_in_support=bool(support[peak]) if peak is not None else False,
        support_min_core_distance_px=None,
        selected_distance_to_boundary=quantiles(radius[selected].tolist()))
    if core.any() and support.any():
        distance = cv2.distanceTransform((~core).astype('u1'), cv2.DIST_L2, 5)
        result['support_min_core_distance_px'] = float(distance[support].min())
    return result, core


def selfcheck():
    own = np.zeros((32, 50), bool); own[5:25, 5:25] = True; own[10:15, 35:40] = True
    selected = np.zeros_like(own); selected[10:15, 35:40] = True
    g, _ = geometry(own, own, selected, selected)
    assert g['source_components'] == 2 and g['selected_main_n'] == 0
    assert g['support_core_area'] == 0 and not g['medial_peak_in_support']
    assert g['support_min_core_distance_px'] > 0


def audit_geometry():
    started = time.perf_counter(); selfcheck(); cv2.setNumThreads(1)
    seal = json.loads((OLD/'MEASUREMENTS_SEALED.json').read_text())
    for item in seal['artifacts']: verify(item)
    inventory = json.loads((OLD/'SOURCE_INVENTORY.json').read_text())
    rows = []
    original_open = Path.open; original_key = np.lib.npyio.NpzFile.__getitem__
    def guarded_open(path, *args, **kwargs):
        text = str(path).lower()
        assert not any(part in text for part in ('labels_640x360', 'sealed_test', '/v3/', '\\v3\\')), path
        return original_open(path, *args, **kwargs)
    def guarded_key(sensor, key):
        assert key == 'depth_mm', key
        return original_key(sensor, key)
    with patch.object(Path, 'open', guarded_open), \
         patch.object(np.lib.npyio.NpzFile, '__getitem__', guarded_key), \
         patch.object(socket.socket, 'connect', side_effect=AssertionError('no network')):
        for name in SEGMENTS:
            streams = zip(inventory[name], records(OLD/f'{name}_measurements.jsonl.gz'),
                          records(OLD/'private'/f'{name}_pixels.jsonl.gz'), strict=True)
            for index, (source, measurement, private) in enumerate(streams, 1):
                frame = measurement['frame']
                assert frame == private['frame'] == source['frame'] == measurement['evidence_max_frame']
                verify(dict(path=source['depth_path'], bytes=source['depth_bytes'], sha256=source['depth_sha256']))
                depth = load_depth(source['depth_path'])
                masks = {t: decode(p['source_mask']) for t, p in private['objects'].items()}
                occupancy = sum((m.astype('u2') for m in masks.values()), np.zeros(depth.shape, 'u2'))
                for token, fact in measurement['objects'].items():
                    pp = private['objects'][token]; f = fact['foreground']; x0, y0, x1, y1 = pp['crop']
                    own = masks[token][y0:y1, x0:x1]
                    exclusive = own & (occupancy[y0:y1, x0:x1] == 1)
                    local = np.asarray(depth[y0:y1, x0:x1], dtype='f8')
                    valid = np.isfinite(local) & (local > 0)
                    p = {key: decode(rle) for key, rle in pp['regions'].items()}
                    selected, support, candidates = p['selected'], p['support'], p['candidates']
                    assert int(selected.sum()) == f['selected']['n']
                    assert int(candidates.sum()) == f['significant_n']
                    assert np.all(~selected | (exclusive & valid & candidates))
                    g, core = geometry(own, exclusive, selected, support)
                    peak_xy = g['medial_peak_local_xy']
                    peak_depth = local[peak_xy[1], peak_xy[0]] if peak_xy is not None else np.nan
                    g['medial_peak_raw_depth_mm'] = float(peak_depth) if np.isfinite(peak_depth) else None
                    g['medial_peak_raw_valid'] = bool(valid[peak_xy[1], peak_xy[0]]) if peak_xy is not None else False
                    assert int((core & valid).sum()) == fact['core']['n']
                    rebuilt = []; contrast = None; raw_background_scale = None; shadow30 = None
                    if f['plane'] is not None:
                        plane = f['plane']; yy, xx = np.indices(local.shape); cx, cy = plane['origin_px']
                        beta = plane['beta_mm']; unit = plane['coordinate_scale_px']
                        contrast = beta[0]+beta[1]*(xx+x0-cx)/unit+beta[2]*(yy+y0-cy)/unit-local
                        residual = contrast[p['annulus'] & valid]
                        raw_background_scale = 1.4826*float(np.median(np.abs(residual-np.median(residual))))
                        assert abs(max(CFG['scale_floor_mm'], raw_background_scale)-plane['residual_scale_mm']) < 1e-9
                        if f['reason'] == 'NO_SIGNIFICANT_DEPTH_CONTRAST':
                            weak_seed = exclusive & valid & (np.abs(contrast) >= CFG['contrast_floor_mm'])
                            shadow_qualified = []
                            for sign_mask in (contrast > 0, contrast < 0):
                                seed = weak_seed & sign_mask
                                closed = cv2.morphologyEx(seed.astype('u1'), cv2.MORPH_CLOSE,
                                    np.ones((CFG['closing_size_px'],)*2, 'u1')).astype(bool) & exclusive
                                count, labels = cv2.connectedComponents(closed.astype('u1'), connectivity=8)
                                for label in range(1, count):
                                    area = labels == label; retained = seed & area; n = int(retained.sum())
                                    if n >= CFG['foreground_min_n'] and n/max(1, int(area.sum())) >= CFG['foreground_min_support_fraction'] and scale(local[retained]) <= CFG['max_scale_mm']:
                                        shadow_qualified.append(n)
                            maximum = max(shadow_qualified, default=0)
                            shadow30 = dict(candidate_n=int(weak_seed.sum()),
                                qualified_components=len(shadow_qualified), largest_qualified_n=maximum,
                                dominant_qualified=bool(maximum and maximum/max(1, int(weak_seed.sum())) >= CFG['dominant_fraction']))
                    if candidates.any():
                        assert np.array_equal(candidates, exclusive & valid &
                                              (np.abs(contrast) >= f['plane']['contrast_threshold_mm']))
                        for sign, signmask in [('NEARER', contrast > 0), ('FARTHER', contrast < 0)]:
                            seed = candidates & signmask
                            closed = cv2.morphologyEx(seed.astype('u1'), cv2.MORPH_CLOSE,
                                                    np.ones((CFG['closing_size_px'],)*2, 'u1')).astype(bool) & exclusive
                            count, labels = cv2.connectedComponents(closed.astype('u1'), connectivity=8)
                            for label in range(1, count):
                                area = labels == label; retained = seed & area; n = int(retained.sum())
                                sigma = scale(local[retained]) if n else None
                                entry = dict(sign=sign, label=label, n=n, support_area=int(area.sum()),
                                    raw_scale_mm=sigma,
                                    qualified=bool(n >= CFG['foreground_min_n'] and
                                        n/max(1, int(area.sum())) >= CFG['foreground_min_support_fraction'] and
                                        sigma <= CFG['max_scale_mm']))
                                assert entry == f['components'][len(rebuilt)]
                                rebuilt.append(entry)
                        assert len(rebuilt) == len(f['components'])
                    components = f['components']; qualified = [c for c in components if c['qualified']]
                    largest_qualified_n = max((c['n'] for c in qualified), default=0)
                    row = dict(segment=name, frame=frame, token=token, status=f['status'], reason=f['reason'],
                        core_usable=fact['core_usable'], whole_n=fact['whole']['n'],
                        whole_area=fact['whole']['area'], exclusive_valid_n=f['exclusive_valid_n'],
                        core_n=fact['core']['n'], core_median_mm=fact['core']['median'],
                        significant_n=f['significant_n'], selected_n=f['selected']['n'],
                        selected_median_mm=f['selected']['median'], selected_sign=f.get('selected_sign'),
                        signed_contrast_mm=f['signed_contrast_median_mm'],
                        raw_valid_retention=f['raw_valid_retention'], dominance=f['dominance'],
                        background_median_mm=f['annulus']['median'],
                        background_scale_mm=f['plane']['residual_scale_mm'] if f['plane'] else None,
                        background_unfloored_scale_mm=raw_background_scale,
                        contrast_threshold_mm=f['plane']['contrast_threshold_mm'] if f['plane'] else None,
                        same_plane_30mm_shadow=shadow30,
                        component_count=len(components), qualified_component_count=len(qualified),
                        maximum_component_n=max((c['n'] for c in components), default=0),
                        largest_qualified_n=largest_qualified_n,
                        geometry=g,
                        component_constraints=dict(
                            n_at_least_16=sum(c['n'] >= CFG['foreground_min_n'] for c in components),
                            n_and_scale=sum(c['n'] >= CFG['foreground_min_n'] and
                                c['raw_scale_mm'] <= CFG['max_scale_mm'] for c in components),
                            scale_exceeded=sum(c['raw_scale_mm'] is not None and
                                c['raw_scale_mm'] > CFG['max_scale_mm'] for c in components)),
                        valid_abs_contrast_mm=quantiles(np.abs(contrast[exclusive & valid]).tolist())
                            if contrast is not None else None)
                    rows.append(row)
                if index % 200 == 0: print(f'{name} geometry {index}/{len(inventory[name])}', flush=True)
    assert len(rows) == seal['objects'] == 28382
    return rows, seal, time.perf_counter()-started


def cost(rows, keep):
    accepted = [r for r in rows if r['status'] == 'AVAILABLE']
    rejected = [r for r in accepted if not keep(r)]
    kept = [r for r in accepted if keep(r)]
    scorable = [r for r in rejected if r['reference_status'] == 'SCORABLE']
    return dict(accepted_before=len(accepted), accepted_after=len(kept), additionally_rejected=len(rejected),
        accepted_objects_lost_fraction=len(rejected)/len(accepted),
        core_usable_available_after=sum(r['core_usable'] for r in kept),
        original_core_usable=sum(r['core_usable'] for r in rows),
        rejected_scorable=len(scorable),
        rejected_selected_samples=sum(r['selected_n'] for r in rejected),
        rejected_inside_matched_silhouette=sum(r['sealed_selected_occupancy']['fish'] for r in scorable),
        rejected_outside_all_fish=sum(r['sealed_selected_occupancy']['background'] for r in scorable),
        zero_matched_fish_cases_rejected=sum(r['sealed_selected_occupancy']['fish'] == 0 for r in scorable),
        farther_cases_rejected=sum(r['selected_sign'] == 'FARTHER' for r in rejected),
        zero_matched_fish_cases_remaining=sum(r['reference_status'] == 'SCORABLE' and
            r['sealed_selected_occupancy']['fish'] == 0 for r in kept))


def summarize(rows, seal, seconds):
    # Occupancy is diagnostic only and cannot influence geometry or proposed gates.
    occupancy = {(r['segment'], r['frame'], r['token']): r
                 for r in records(OLD/'OCCUPANCY_AUDIT.jsonl.gz')}
    assert len(occupancy) == len(rows)
    for row in rows:
        old = occupancy[(row['segment'], row['frame'], row['token'])]
        assert old['filter_status'] == row['status'] and old['foreground']['n'] == row['selected_n']
        row.update(reference_status=old['reference_status'], sealed_selected_occupancy=old['foreground'],
                   sealed_whole_occupancy=old['whole'], sealed_core_occupancy=old['core'])
    accepted = [r for r in rows if r['status'] == 'AVAILABLE']
    zero = [r for r in accepted if r['reference_status'] == 'SCORABLE' and r['sealed_selected_occupancy']['fish'] == 0]
    far = [r for r in accepted if r['selected_sign'] == 'FARTHER']
    groups = {}
    for reason in sorted({r['reason'] for r in rows}):
        group = [r for r in rows if r['reason'] == reason]
        groups[reason] = dict(n=len(group), core_usable=sum(r['core_usable'] for r in group),
            original_valid_samples=sum(r['whole_n'] for r in group),
            matched_silhouette_valid_samples=sum(r['sealed_whole_occupancy']['fish'] for r in group
                if r['reference_status'] == 'SCORABLE'),
            selected_n=quantiles([r['selected_n'] for r in group]),
            maximum_component_n=quantiles([r['maximum_component_n'] for r in group]),
            raw_valid_retention=quantiles([r['raw_valid_retention'] for r in group]),
            dominance=quantiles([r['dominance'] for r in group]),
            background_scale_mm=quantiles([r['background_scale_mm'] for r in group]),
            background_unfloored_scale_mm=quantiles([r['background_unfloored_scale_mm'] for r in group]),
            background_floor15_active=sum(r['background_unfloored_scale_mm'] is not None and
                r['background_unfloored_scale_mm'] < CFG['scale_floor_mm'] for r in group),
            source_fragmented=sum(r['geometry']['source_components'] > 1 for r in group),
            no_geometric_core=sum(r['geometry']['core_area'] == 0 for r in group))
    unqualified = [r for r in rows if r['reason'] == 'NO_QUALIFIED_CONNECTED_COMPONENT']
    failtypes = Counter('EVERY_COMPONENT_BELOW_16' if r['maximum_component_n'] < CFG['foreground_min_n'] else
        'NO_SAMPLE_LARGE_COMPONENT_WITH_SCALE_AT_MOST_60' if r['component_constraints']['n_and_scale'] == 0 else
        'COMPONENT_SUPPORT_COVERAGE_FAILURE' for r in unqualified)
    low = []
    for lo, hi in [(0, .1), (.1, .25), (.25, .5), (.5, .75), (.75, 1.000001)]:
        group = [r for r in accepted if lo <= r['raw_valid_retention'] < hi]
        low.append(dict(raw_valid_retention_interval=[lo, min(hi, 1)], objects=len(group),
            core_usable=sum(r['core_usable'] for r in group),
            selected_samples=sum(r['selected_n'] for r in group),
            zero_matched_fish=sum(r in zero for r in group),
            no_support_core_intersection=sum(r['geometry']['support_core_area'] == 0 for r in group)))
    gates = {
        'SELECTED_ALL_IN_LARGEST_ORIGINAL_MASK_COMPONENT': lambda r: r['geometry']['selected_main_n'] == r['selected_n'],
        'SELECTED_ALL_IN_UNIQUE_LARGEST_ORIGINAL_MASK_COMPONENT': lambda r: r['geometry']['source_main_unique'] and
            r['geometry']['selected_main_n'] == r['selected_n'],
        'SUPPORT_INTERSECTS_FIXED_7X7_GEOMETRIC_CORE': lambda r: r['geometry']['support_core_area'] > 0,
        'SUPPORT_WITHIN_3PX_OF_FIXED_GEOMETRIC_CORE': lambda r: r['geometry']['support_min_core_distance_px'] is not None and
            r['geometry']['support_min_core_distance_px'] <= CFG['neighbor_margin_px'],
        'SUPPORT_CONTAINS_FIXED_MEDIAL_MAXIMUM': lambda r: r['geometry']['medial_peak_in_support'],
        'SELECTED_CONTAINS_FIXED_MEDIAL_MAXIMUM': lambda r: r['geometry']['medial_peak_in_selected'],
        'LARGEST_SOURCE_AND_SUPPORT_CORE': lambda r: r['geometry']['selected_main_n'] == r['selected_n'] and
            r['geometry']['support_core_area'] > 0,
    }
    geometric_costs = {name: cost(rows, gate) for name, gate in gates.items()}
    for row in zero+far:
        row['counterfactual_geometry_keep'] = {name: bool(gate(row)) for name, gate in gates.items()}
    weak = [r for r in rows if r['reason'] == 'NO_SIGNIFICANT_DEPTH_CONTRAST']
    floor_rejected = [r for r in weak if r['background_unfloored_scale_mm'] < CFG['scale_floor_mm'] and
                     r['same_plane_30mm_shadow']['dominant_qualified']]
    extreme_far = [r for r in far if r['selected_median_mm'] > 5000]
    return dict(status='READONLY_POSTSCORE_MECHANISM_AUDIT', base_requested='ace9a37b1c6a2a59d3d5397f335d081f1a5a8ae8',
        scope=dict(frames=seal['frames'], objects=len(rows), source='EXPOSED_DS3_1066_FRAMES',
            new_model_http=0, training=0, tracker_runs=0, changed_old_files=0,
            opened_npz_keys=['depth_mm'], newly_opened_manual_labels=0,
            geometry_computed_before_joining_sealed_occupancy=True),
        inputs=[artifact(OLD/'MEASUREMENTS_SEALED.json'), artifact(OLD/'SOURCE_INVENTORY.json'),
                artifact(OLD/'OCCUPANCY_AUDIT.jsonl.gz')]+seal['artifacts'],
        code=artifact(Path(__file__)), geometry_selfcheck_passed=True, reconstruction_checked_objects=len(rows),
        geometry_runtime_seconds=seconds, reason_groups=groups,
        no_qualified_component_mechanisms=dict(failtypes),
        weak_contrast=dict(objects=len(weak), zero_exclusive_valid=sum(r['exclusive_valid_n'] == 0 for r in weak),
            floor15_active=sum(r['background_unfloored_scale_mm'] < CFG['scale_floor_mm'] for r in weak),
            same_plane_30mm_candidates_nonempty=sum(r['same_plane_30mm_shadow']['candidate_n'] > 0 for r in weak),
            same_plane_30mm_at_least_16_candidates=sum(r['same_plane_30mm_shadow']['candidate_n'] >= CFG['foreground_min_n'] for r in weak),
            same_plane_30mm_has_qualified_component=sum(r['same_plane_30mm_shadow']['qualified_components'] > 0 for r in weak),
            same_plane_30mm_dominant_qualified=sum(r['same_plane_30mm_shadow']['dominant_qualified'] for r in weak),
            floor15_active_same_plane_30mm_dominant_qualified=sum(r['background_unfloored_scale_mm'] < CFG['scale_floor_mm'] and
                r['same_plane_30mm_shadow']['dominant_qualified'] for r in weak),
            floor15_active_background_scale=quantiles([r['background_unfloored_scale_mm'] for r in weak
                if r['background_unfloored_scale_mm'] < CFG['scale_floor_mm']]),
            maximum_absolute_contrast_mm=quantiles([r['valid_abs_contrast_mm']['max'] for r in weak
                if r['valid_abs_contrast_mm'] is not None])),
        accepted_geometry=dict(source_fragmented=sum(r['geometry']['source_components'] > 1 for r in accepted),
            source_main_nonunique=sum(not r['geometry']['source_main_unique'] for r in accepted),
            selected_touches_multiple_source_components=sum(len(r['geometry']['selected_source_labels']) > 1 for r in accepted),
            selected_not_in_largest_source_component=sum(r['geometry']['selected_main_n'] == 0 for r in accepted),
            no_core=sum(r['geometry']['core_area'] == 0 for r in accepted),
            no_support_core_intersection=sum(r['geometry']['support_core_area'] == 0 for r in accepted),
            support_min_core_distance_px=quantiles([r['geometry']['support_min_core_distance_px'] for r in accepted]),
            selected_sign=dict(Counter(r['selected_sign'] for r in accepted))),
        retention_strata=low, geometry_gate_costs=geometric_costs,
        all_object_geometry=dict(nonunique_main=sum(not r['geometry']['source_main_unique'] for r in rows),
            fragmented=sum(r['geometry']['source_components'] > 1 for r in rows)),
        zero_matched_fish_mechanisms=dict(objects=len(zero),
            selected_outside_main_source_component=sum(r['geometry']['selected_main_n'] == 0 for r in zero),
            selected_within_main_source_component=sum(r['geometry']['selected_main_n'] == r['selected_n'] for r in zero),
            support_touches_fixed_core=sum(r['geometry']['support_core_area'] > 0 for r in zero),
            minor_support_touches_fixed_core=sum(r['geometry']['selected_main_n'] == 0 and
                r['geometry']['support_core_area'] > 0 for r in zero),
            main_support_touches_fixed_core=sum(r['geometry']['selected_main_n'] == r['selected_n'] and
                r['geometry']['support_core_area'] > 0 for r in zero),
            raw_valid_retention=quantiles([r['raw_valid_retention'] for r in zero]),
            original_matched_valid_samples=quantiles([r['sealed_whole_occupancy']['fish'] for r in zero])),
        farther_mechanisms=dict(objects=len(far),
            all_original_masks_single_component=all(r['geometry']['source_components'] == 1 for r in far),
            numeric_median_over_5000mm=len(extreme_far),
            over_5000mm_silhouette_inside_samples=sum(r['sealed_selected_occupancy']['fish'] for r in extreme_far),
            over_5000mm_selected_samples=sum(r['selected_n'] for r in extreme_far),
            remaining_selected_median_mm=quantiles([r['selected_median_mm'] for r in far if r not in extreme_far]),
            range_split_is_descriptive_not_sensor_validity=True),
        weak_floor_examples=floor_rejected[:5],
        zero_matched_fish_cases=zero, all_farther_cases=far,
        limits=['Counterfactual gates only reject old selected pixels; no alternate component is selected.',
            'No gate or distance threshold is tuned against occupancy; 7x7 core and 3px margin reuse DS3/DS1 geometry.',
            'Single medial maximum is deterministic row-major argmax but can be too strict for elongated or holed fish.',
            'Silhouette occupancy does not certify depth or fish-surface correspondence.',
            'All inputs are previously exposed same-recording development data; no independent validation.'])


if __name__ == '__main__':
    rows, seal, seconds = audit_geometry()
    result = summarize(rows, seal, seconds)
    (HERE/'COMPONENT_AUDIT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('no_qualified_component_mechanisms', 'accepted_geometry',
          'geometry_gate_costs', 'weak_contrast')}, indent=2))
