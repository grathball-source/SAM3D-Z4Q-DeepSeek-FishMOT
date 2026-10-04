"""Read-only summaries of the unchanged DS25 producer, never an identity rule."""
from common import *
import copy
import math
import numpy as np


def _assert_fact(fact):
    original = {k: v for k, v in fact.items() if k != 'measurement_sha256'}
    assert fact['measurement_sha256'] == digest(original), 'Producer fact was changed'
    assert fact['parameters'] == old_measurement.PARAMETERS, 'Frozen measurement parameters differ'
    assert fact['identity'] == fact['foreground_identity'] == fact['physical_fish_count'] == 'UNKNOWN'


def summarize(fact):
    """A sole proxy support is observable even though DS25 requires two layers.

    The original status and every weak/background/missing support remain intact.
    This diagnostic does not certify a foreground fish, clean state or identity.
    """
    _assert_fact(fact)
    cfg, background, plane = fact['parameters'], fact['background']['summary'], fact['plane']
    declared = list(fact['qualified_support_ids'])
    flagged = [x['support_id'] for x in fact['layers'] if x['qualified']]
    gates = dict(
        nonempty_original_roi=fact['original_roi_area'] > 0,
        independent_background_count=background['n'] >= cfg['background_minimum_n'],
        independent_background_coverage=background['valid_fraction'] >= cfg['minimum_coverage_fraction'],
        background_plane_available=plane is not None,
        background_geometry=None if plane is None else
            plane['design_rank'] == 3 and plane['condition'] <= cfg['background_max_condition'],
        background_residual_scale=None if plane is None else plane['residual_scale_mm'] <= cfg['max_scale_mm'],
        independent_roi_count=fact['summary']['n'] >= cfg['minimum_layer_n'],
        independent_roi_coverage=fact['summary']['valid_fraction'] >= cfg['minimum_coverage_fraction'],
        inclusive_independent_partition_agreement=fact.get('inclusive_independent_partition_agreement'),
        inclusive_independent_support_agreement=fact.get('inclusive_independent_support_agreement'),
        no_substantial_unresolved_support=None if 'substantial_unresolved_support_ids' not in fact else
            not fact['substantial_unresolved_support_ids'])
    eligible = bool(fact['status'] == 'UNKNOWN' and
        fact['reason'] == 'EXACTLY_TWO_QUALIFIED_LOCAL_SUPPORTS_REQUIRED' and
        len(declared) == 1 and declared == flagged and
        gates['inclusive_independent_partition_agreement'] is True and
        gates['inclusive_independent_support_agreement'] is True and
        gates['no_substantial_unresolved_support'] is True)
    return dict(fact_id=fact['fact_id'], fact_sha256=digest(fact),
        producer_measurement_sha256=fact['measurement_sha256'],
        original_status=fact['status'], original_reason=fact['reason'],
        original_roi_area=fact['original_roi_area'], original_roi_missing_n=fact['original_roi_missing_n'],
        independent_summary=copy.deepcopy(fact['summary']), inclusive_summary=copy.deepcopy(fact['inclusive_summary']),
        background=copy.deepcopy(fact['background']), plane=copy.deepcopy(plane),
        parent_gates=gates, qualified_support_ids=declared, qualified_support_count=len(declared),
        qualified_layer_flag_ids=flagged, qualified_layer_flag_count=len(flagged),
        layer_count=len(fact['layers']), layers=copy.deepcopy(fact['layers']),
        independent_depth_groups=copy.deepcopy(fact['independent_depth_groups']),
        inclusive_depth_groups=copy.deepcopy(fact['inclusive_depth_groups']),
        substantial_unresolved_support_ids=copy.deepcopy(fact.get('substantial_unresolved_support_ids')),
        sole_proxy_eligible=eligible,
        sole_proxy_support_id=declared[0] if eligible else None,
        diagnostic='EXACTLY_ONE_UNAMBIGUOUS_ANNULUS_PROXY_DIFFERENT_SUPPORT' if eligible else 'UNKNOWN',
        foreground_identity='UNKNOWN', physical_fish_count='UNKNOWN', identity='UNKNOWN',
        no_new_measurement_threshold=True, no_identity_veto=True, no_state_write=True)


def _source_sets(fact, maps, index):
    _assert_fact(fact)
    roi = np.asarray(maps['roi'])
    assert roi.dtype == np.dtype(bool) and roi.shape == index.shape
    assert old_measurement.array_binding(roi) == fact['roi_binding']
    selected = np.asarray(maps['mask_selected'])
    assert selected.dtype == np.dtype(bool) and selected.shape == roi.shape
    assert not np.any(selected & ~roi)
    raw = np.unique(index[roi & (index >= 0)])
    canonical = index[selected]
    assert len(canonical) == fact['summary']['n'] and np.all(canonical >= 0)
    assert len(np.unique(canonical)) == len(canonical), 'Within-ROI sources are not canonical'
    populations = []
    layers = {x['support_id']: x for x in fact['layers']}
    for sid in fact['qualified_support_ids']:
        layer = layers[sid]
        assert layer['qualified'] and sid in maps['selected_positions'] and sid in maps['support_masks']
        positions = np.asarray(maps['selected_positions'][sid])
        assert positions.ndim == 1 and np.issubdtype(positions.dtype, np.integer)
        assert len(positions) == layer['independent_n'] and np.all(np.diff(positions) > 0)
        assert np.all(positions >= 0) and np.all(positions < roi.size)
        assert roi.ravel()[positions].all() and selected.ravel()[positions].all()
        assert np.asarray(maps['support_masks'][sid]).ravel()[positions].all()
        sources = index.ravel()[positions]
        assert np.all(sources >= 0) and len(np.unique(sources)) == len(sources)
        assert old_measurement.array_binding(sources) == layer['population_binding']['selected_source_index_binding']
        populations.append(sources)
    qualified = np.unique(np.concatenate(populations)) if populations else np.array([], dtype=index.dtype)
    return raw, np.sort(canonical), qualified


def _population(values):
    values = np.asarray(values)
    return dict(n=int(len(values)), binding=old_measurement.array_binding(values))


def pair_summary(factA, mapsA, factB, mapsB, index):
    """Report frame-local source reuse and a sole-support depth difference.

    No temporal correspondence, fish identity, chosen mapping or veto follows
    from disjoint source populations or the sign of a depth difference.
    """
    index = np.asarray(index)
    assert index.ndim == 2 and np.issubdtype(index.dtype, np.signedinteger)
    for key in ('segment', 'frame', 'global_frame', 'time', 'source_binding', 'actual_source_index_binding'):
        assert factA[key] == factB[key], 'Paired roles are not the same actual frame/source'
    assert old_measurement.array_binding(index) == factA['actual_source_index_binding']
    summaries = {'A': summarize(factA), 'B': summarize(factB)}
    sets = dict(zip(('A', 'B'), (_source_sets(factA, mapsA, index), _source_sets(factB, mapsB, index))))
    names = ('inclusive_raw_native_sources', 'canonical_raw_native_sources', 'qualified_native_sources')
    populations = {role: {name: _population(values) for name, values in zip(names, sets[role])}
        for role in ('A', 'B')}
    overlaps = {name: _population(np.intersect1d(sets['A'][i], sets['B'][i])) for i, name in enumerate(names)}
    overlap = overlaps['qualified_native_sources']['n']
    eligible = summaries['A']['sole_proxy_eligible'] and summaries['B']['sole_proxy_eligible'] and not overlap
    out = dict(schema='DS26_READONLY_PAIRED_SOLE_PROXY_MEASUREMENT_V1',
        segment=factA['segment'], frame=factA['frame'], global_frame=factA['global_frame'], time=factA['time'],
        fact_ids={'A': factA['fact_id'], 'B': factB['fact_id']},
        fact_sha256={'A': digest(factA), 'B': digest(factB)}, populations=populations,
        source_overlaps=overlaps,
        qualified_source_populations='SHARED_NATIVE_SOURCES' if overlap else 'DISJOINT_FRAME_LOCAL_NATIVE_SOURCES',
        identity_independence='UNKNOWN', physical_identity='UNKNOWN', foreground_identity='UNKNOWN',
        pair_proxy_eligible=bool(eligible), measured_depth_difference_mm=None,
        propagated_sigma_mm=None, standardized_difference=None, measured_order='UNKNOWN',
        reason='SOLE_SUPPORT_DIAGNOSTIC_OR_SOURCE_INDEPENDENCE_UNKNOWN',
        no_threshold_added=True, no_source_points_deleted=True, no_identity_veto=True, no_state_write=True,
        source_index_temporal_correspondence=False,
        propagated_sigma_assumption='ROOT_SUM_OF_EXISTING_SIGMAS; SHARED_ANNULUS_COVARIANCE_NOT_ESTIMATED',
        uncertainty='UNCHANGED_DS25_ANNULUS_PROXY_AND_MEASUREMENT_SCALES; NOT_PHYSICAL_ACCURACY')
    if overlap:
        out['reason'] = 'QUALIFIED_NATIVE_SOURCE_REUSED_BY_BOTH_ROLES'
    if eligible:
        layers = {}
        for role, fact in (('A', factA), ('B', factB)):
            sid = summaries[role]['sole_proxy_support_id']
            layers[role] = next(x for x in fact['layers'] if x['support_id'] == sid)
        delta = float(layers['B']['z_mm'] - layers['A']['z_mm'])
        scale = math.hypot(layers['A']['sigma_mm'], layers['B']['sigma_mm'])
        assert math.isfinite(delta) and math.isfinite(scale) and scale > 0
        out.update(measured_depth_difference_mm=delta, propagated_sigma_mm=scale,
            standardized_difference=delta / scale,
            measured_order='A_PROXY_NEARER' if delta > 0 else 'B_PROXY_NEARER' if delta < 0 else 'EQUAL_PROXY_MEDIANS',
            reason='DISJOINT_SOLE_PROXY_SUPPORTS; SIGN_ONLY_NOT_CONFIDENT_ORDER_OR_IDENTITY',
            sole_proxy_support_ids={role: summaries[role]['sole_proxy_support_id'] for role in ('A', 'B')})
    json.dumps(out, allow_nan=False)
    return out
