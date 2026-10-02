"""Same-population measurement bindings for D1 whole, Birth fixed core and S0 adaptive core."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Reuse the frozen layer/ownership policy; no new depth threshold or peak selection.
_old = _module('ds18_frozen_ds17_measurement', ROOT / 'experiments/ds17_mixed_depth_activity_repair/mixed_depth.py')
FIXED_CORE_SOURCE = Path('E:/CAU/D-MOT/tools/sam3_depth_birth_inherit_20260917/features.py')
_fixed = _module('ds18_original_fixed_core', FIXED_CORE_SOURCE)
fixed_core = _fixed.exclusive_core
adaptive_core, array_binding, PARAMETERS = _old.adaptive_core, _old.array_binding, _old.PARAMETERS
SCHEMA = 'DS18_SAME_ROI_RAW_MEASUREMENT_V1'
ROLES = {'D1_WHOLE': 'whole', 'BIRTH_WHOLE': 'whole',
         'BIRTH_CORE': 'birth_core', 'S0_ADAPTIVE_CORE': 'core'}
SCALAR_FIELDS = ('area', 'n', 'valid_fraction', 'median', 'mad', 'q10', 'q25', 'q75', 'q90')
REQUIRED_SCALARS = ('n', 'valid_fraction', 'median', 'mad')
_VALIDATED_CERTIFICATE = object()


def _readonly(*args, **kwargs):
    raise TypeError('Validated measurement facts are immutable')


class _FrozenDict(dict):
    """Keep JSON's dictionary shape while branch copies share read-only facts."""
    __slots__ = ('_certificate_token',)

    def __new__(cls, values):
        result = dict.__new__(cls)
        dict.update(result, values)
        object.__setattr__(result, '_certificate_token', None)
        return result

    def __init__(self, values):
        pass

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self

    def __copy__(self):
        return self

    __setitem__ = __delitem__ = __setattr__ = __delattr__ = _readonly
    clear = pop = popitem = setdefault = update = __ior__ = _readonly


class _FrozenList(list):
    __slots__ = ()

    def __new__(cls, values):
        result = list.__new__(cls)
        list.extend(result, values)
        return result

    def __init__(self, values):
        pass

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self

    def __copy__(self):
        return self

    __setitem__ = __delitem__ = __iadd__ = __imul__ = _readonly
    append = extend = insert = pop = remove = clear = reverse = sort = _readonly


def _freeze_facts(value):
    if type(value) in (_FrozenDict, _FrozenList):
        return value
    if isinstance(value, dict):
        return _FrozenDict((key, _freeze_facts(child)) for key, child in value.items())
    if isinstance(value, list):
        return _FrozenList(_freeze_facts(child) for child in value)
    if isinstance(value, tuple):
        return tuple(_freeze_facts(child) for child in value)
    return value


def _validated_facts(certificate):
    assert validate_certificate(certificate)
    frozen = _freeze_facts(certificate)
    object.__setattr__(frozen, '_certificate_token', _VALIDATED_CERTIFICATE)
    return frozen


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def _seal(certificate):
    certificate['certificate_sha256'] = _digest({k: v for k, v in certificate.items() if k != 'certificate_sha256'})


def _roi_fact(representation, roi, depth, index, definition, roles):
    positions = np.flatnonzero(roi & np.isfinite(depth) & (depth > 0))
    representation.update(roi_definition=definition, roi_binding=array_binding(roi),
        association_roles=roles, actual_scalar_population='ORIGINAL_FINITE_POSITIVE_ALIGNED_PIXELS_IN_THIS_EXACT_ROI',
        inclusive_population_binding=dict(positions=array_binding(positions),
            depth=array_binding(depth.ravel()[positions]), source_indices=array_binding(index.ravel()[positions])),
        inclusive_statistics_sha256=_digest(representation['inclusive_summary']))


def measure_mixed(depth, source_index, masks, segment, frame, global_frame, *, source_binding, native_depth=None):
    """All three actual ROIs, current raw sources and unchanged legacy statistics."""
    packet = _old.measure_mixed(depth, source_index, masks, segment, frame, global_frame,
                               source_binding=source_binding, native_depth=native_depth)
    depth, index = np.asarray(depth), np.asarray(source_index)
    regions = {int(n): np.asarray(mask, dtype=bool) for n, mask in masks.items()}
    occupancy = sum((m.astype('u2') for m in regions.values()), np.zeros(depth.shape, 'u2'))
    valid = np.isfinite(depth) & (depth > 0) & (index >= 0)
    if native_depth is not None:
        native = np.asarray(native_depth).ravel()
        valid[valid] &= np.isfinite(native[index[valid]]) & (native[index[valid]] > 0)
    each = [np.unique(index[m & valid]) for m in regions.values()]
    ids, counts = np.unique(np.concatenate(each) if each else np.array([], dtype=index.dtype), return_counts=True)
    shared = ids[counts > 1]
    with FIXED_CORE_SOURCE.open('rb') as handle:
        fixed_source_sha = hashlib.file_digest(handle, 'sha256').hexdigest()
    packet.update(schema=SCHEMA, fixed_core_source=dict(path=str(FIXED_CORE_SOURCE),
        bytes=FIXED_CORE_SOURCE.stat().st_size, sha256=fixed_source_sha),
        association_roi_policy=dict(ROLES), no_cross_ROI_certification=True)
    for native, certificate in packet['objects'].items():
        region = regions[native]
        fixed_exclusive, fixed = fixed_core(region, occupancy)
        adaptive, _ = adaptive_core(region, occupancy)
        base = f'{segment}/F{frame}/n:{native}/mixed'
        certificate['birth_core'] = _old._representation(depth, index, fixed, valid, shared,
            base + '/birth_fixed_core/raw', certificate['annulus'])
        certificate.update(schema=SCHEMA, birth_core_binding=array_binding(fixed),
            birth_exclusive_binding=array_binding(fixed_exclusive),
            fixed_core_definition='ORIGINAL_EXCLUSIVE_MASK_CV2_ERODE_7X7_DEFAULT_BORDER_ONE_ITERATION',
            no_cross_ROI_certification=True)
        for part, roi, definition, roles in (
            ('whole', region, 'ORIGINAL_FULL_MASK', ['D1_WHOLE', 'BIRTH_WHOLE']),
            ('birth_core', fixed, certificate['fixed_core_definition'], ['BIRTH_CORE']),
            ('core', adaptive, 'DS12_EXACT_L2_EXCLUSIVE_COMPONENT_ADAPTIVE_CORE', ['S0_ADAPTIVE_CORE'])):
            _roi_fact(certificate[part], roi, depth, index, definition, roles)
        _seal(certificate)
        packet['objects'][native] = _validated_facts(certificate)
    return packet


def validate_certificate(certificate):
    """Internal producer integrity; use an actual trusted certificate when validating a binding."""
    if type(certificate) is _FrozenDict and certificate._certificate_token is _VALIDATED_CERTIFICATE:
        return True
    try:
        c = certificate
        assert c['schema'] == SCHEMA and c['no_cross_ROI_certification']
        assert c['certificate_sha256'] == _digest({k: v for k, v in c.items() if k != 'certificate_sha256'})
        assert _old.validate_certificate(c)
        # The same frozen representation checks apply to the separate fixed ROI.
        fixed_view = dict(c, core=c['birth_core'], core_binding=c['birth_core_binding'])
        _seal(fixed_view)
        assert _old.validate_certificate(fixed_view)
        for part, roles, roi in (
            ('whole', ['D1_WHOLE', 'BIRTH_WHOLE'], c['mask_binding']),
            ('birth_core', ['BIRTH_CORE'], c['birth_core_binding']),
            ('core', ['S0_ADAPTIVE_CORE'], c['core_binding'])):
            fact = c[part]
            assert fact['association_roles'] == roles and fact['roi_binding'] == roi
            assert fact['inclusive_statistics_sha256'] == _digest(fact['inclusive_summary'])
            assert fact['actual_scalar_population'] == 'ORIGINAL_FINITE_POSITIVE_ALIGNED_PIXELS_IN_THIS_EXACT_ROI'
            assert fact['inclusive_summary']['area'] >= fact['inclusive_summary']['n']
            for value in fact['inclusive_population_binding'].values():
                assert value['shape'] == [fact['inclusive_summary']['n']] and len(value['sha256']) == 64
        assert c['whole']['roi_definition'] == 'ORIGINAL_FULL_MASK'
        assert c['birth_core']['roi_definition'] == c['fixed_core_definition'] == 'ORIGINAL_EXCLUSIVE_MASK_CV2_ERODE_7X7_DEFAULT_BORDER_ONE_ITERATION'
        assert c['core']['roi_definition'] == 'DS12_EXACT_L2_EXCLUSIVE_COMPONENT_ADAPTIVE_CORE'
        return True
    except (KeyError, TypeError, ValueError, AssertionError, OverflowError):
        return False


def _scalars(stats):
    assert isinstance(stats, dict) and all(k in stats for k in REQUIRED_SCALARS)
    result = {k: stats[k] for k in SCALAR_FIELDS if k in stats}
    assert all(v is None or isinstance(v, (int, float)) and math.isfinite(v) for v in result.values())
    return result


def bind_measurement(certificate, role, stats, *, source_version=None, version_key=None):
    """A scalar is admitted only by its own exact population; identity is a separate context."""
    assert validate_certificate(certificate) and role in ROLES
    part = ROLES[role]
    fact, scalar = certificate[part], _scalars(stats)
    assert all(fact['inclusive_summary'][k] == v for k, v in scalar.items()), 'actual scalar/ROI population mismatch'
    measurement_valid = bool(scalar['median'] is not None and scalar['median'] > 0 and
        scalar['n'] >= 16 and scalar['valid_fraction'] >= .2 and
        (role == 'D1_WHOLE' or scalar['mad'] is not None and max(15., 1.4826 * scalar['mad']) <= 60.))
    if version_key is not None:
        assert len(version_key) == 5 and version_key[0] == certificate['segment']
    binding = dict(schema=SCHEMA, association_role=role, representation=part,
        native=certificate['native'], mask_token=f'n:{certificate["native"]}',
        segment=certificate['segment'], frame=certificate['frame'], global_frame=certificate['global_frame'],
        time=certificate['time'], frame_binding_sha256=certificate['frame_binding_sha256'],
        certificate_fact_id=certificate['fact_id'], measurement_fact_id=fact['fact_id'],
        certificate_sha256=certificate['certificate_sha256'], roi_definition=fact['roi_definition'],
        roi_binding=copy.deepcopy(fact['roi_binding']), inclusive_population_binding=copy.deepcopy(fact['inclusive_population_binding']),
        independent_source_population=dict(selected_pixel_binding=copy.deepcopy(fact['selected_pixel_binding']),
            selected_source_index_binding=copy.deepcopy(fact['selected_source_index_binding'])),
        actual_scalar=scalar, actual_scalar_sha256=_digest(scalar),
        eligible_single=fact['eligible_single'], measurement_valid=measurement_valid,
        screened_eligible=measurement_valid and fact['eligible_single'], status=fact['status'], reason=fact['reason'],
        source_version=copy.deepcopy(source_version), version_key=list(version_key) if version_key is not None else None,
        identity_state=('IDENTITY_CONTEXT_BOUND' if version_key is not None and
                        version_key[3] is not None and version_key[4] is not None else 'IDENTITY_UNASSIGNED'),
        physical_identity='UNKNOWN; SOURCE_AND_MEASUREMENT_BINDING_IS_NOT_IDENTITY_TRUTH')
    binding['binding_sha256'] = _digest(binding)
    return binding


def validate_bound_measurement(binding, stats, role, certificate, *, source_version=None,
                               version_key=None, native=None, frame=None, before_frame=None):
    """Bool contract check against the actual current/registered old-anchor certificate."""
    try:
        b = binding
        assert role in ROLES and validate_certificate(certificate)
        assert b['binding_sha256'] == _digest({k: v for k, v in b.items() if k != 'binding_sha256'})
        rebuilt = bind_measurement(certificate, role, stats,
            source_version=b['source_version'], version_key=b['version_key'])
        assert b == rebuilt
        if source_version is not None:
            assert b['source_version'] == source_version
        if version_key is not None:
            assert b['version_key'] == list(version_key)
        if native is not None:
            assert b['native'] == native
        if frame is not None:
            assert b['frame'] == frame
        if before_frame is not None:
            assert b['frame'] < before_frame
        return True
    except (KeyError, TypeError, ValueError, AssertionError, OverflowError):
        return False


def _unavailable(stats, binding):
    result = dict(stats)
    for key in ('median', 'mad', 'q10', 'q25', 'q75', 'q90'):
        if key in result:
            result[key] = None
    result.update(n=0, valid_fraction=0., mixed_guard_status='UNKNOWN_INDIVIDUAL_SCALAR',
        mixed_fact_id=binding['measurement_fact_id'])
    return result


def guard_inputs(row, profiles, mixed, *, source_versions=None, versions=None, screen=True):
    """Whole certifies D1/whole profiles; only the fixed ROI certifies Birth core."""
    result, output = copy.deepcopy(row), copy.deepcopy(profiles)
    source_versions, versions = source_versions or {}, versions or {}
    assert set(output) == {o['id'] for o in result['observations']} == set(mixed)
    for observation in result['observations']:
        native, profile = observation['id'], output[observation['id']]
        c = mixed[native]
        assert c['native'] == native and c['frame'] == row['frame'] and c['time'] == row['time']
        assert c['global_frame'] == row['global_frame'] and observation['mask'] == f'n:{native}'
        assert profile['id'] == native and profile['mask'] == f'n:{native}' and profile['frame'] == row['frame']
        context = dict(source_version=source_versions.get(native), version_key=versions.get(native))
        bindings = dict(D1_WHOLE=bind_measurement(c, 'D1_WHOLE', observation['depth'], **context),
            BIRTH_WHOLE=bind_measurement(c, 'BIRTH_WHOLE', profile['whole'], **context),
            BIRTH_CORE=bind_measurement(c, 'BIRTH_CORE', profile['core'], **context))
        if screen and not bindings['D1_WHOLE']['screened_eligible']:
            observation['depth'] = _unavailable(observation['depth'], bindings['D1_WHOLE'])
        for part, role in (('whole', 'BIRTH_WHOLE'), ('core', 'BIRTH_CORE')):
            if screen and not bindings[role]['screened_eligible']:
                profile[part] = _unavailable(profile[part], bindings[role])
        observation['measurement_bindings'] = copy.deepcopy(bindings)
        profile['measurement_bindings'] = copy.deepcopy(bindings)
        observation['mixed_depth_screen_applied'] = profile['mixed_depth_screen_applied'] = bool(screen)
        observation['mixed_depth_fact_id'] = profile['mixed_depth_fact_id'] = c['fact_id']
    return result, output


def guard_raw(raw, mixed, *, source_versions=None, versions=None, screen=True):
    """Only adaptive ROI certifies adaptive raw/pre/S0; preserve original numeric facts."""
    output = copy.deepcopy(raw)
    source_versions, versions = source_versions or {}, versions or {}
    assert set(output) == set(mixed)
    for native, measurement in output.items():
        c = mixed[native]
        assert measurement['native'] == native == c['native']
        assert measurement['fact_id'] == f'{c["segment"]}/F{c["frame"]}/n:{native}/adaptive/raw'
        for part in ('whole', 'core'):
            assert all(c[part]['inclusive_summary'][k] == v for k, v in _scalars(measurement[part]).items())
        binding = bind_measurement(c, 'S0_ADAPTIVE_CORE', measurement['core'],
            source_version=source_versions.get(native), version_key=versions.get(native))
        old = bool(measurement['core_usable'])
        usable = old and binding['screened_eligible'] if screen else old
        measurement.update(core_usable=usable,
            measurement_bindings={'S0_ADAPTIVE_CORE': binding},
            mixed_depth_screen_applied=bool(screen),
            mixed_fact_id=binding['measurement_fact_id'], mixed_certificate_sha256=c['certificate_sha256'],
            mixed_guard=dict(old_core_usable=old, new_core_usable=usable,
                core_mixture_flag=c['core']['mixture_flag'], core_source_quality=c['core']['quality_usable'],
                whole_mixture_flag=c['whole']['mixture_flag'], whole_eligible_single=c['whole']['eligible_single']))
    return output
