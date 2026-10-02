"""Actual ROI/signature checks without GT, future observations or model calls."""
import copy
import json
import unittest

import numpy as np

from mixed_depth import (SCHEMA, _digest, _seal, _validated_facts, adaptive_core, bind_measurement,
                         fixed_core, guard_inputs, guard_raw, measure_mixed,
                         validate_bound_measurement, validate_certificate)


def fixture(frame=1):
    depth = np.full((48, 48), 1500., dtype='f4')
    index = np.arange(depth.size, dtype='i4').reshape(depth.shape)
    mask = np.zeros(depth.shape, bool)
    mask[12:36, 12:36] = True
    depth[mask] = 1000.
    data = [depth, index, {1: mask}, 'test', frame, frame - 1]
    source = dict(global_frame=frame - 1, frame=frame, time=frame / 30., GT_read=False, RGB_read=False)
    return data, source


def packet(data, source):
    return measure_mixed(*data, source_binding=source, native_depth=np.full(data[0].shape, 1000., 'f4'))


def inputs(c):
    def stat(part):
        return json.loads(json.dumps(c[part]['inclusive_summary']))
    whole, fixed, adaptive = stat('whole'), stat('birth_core'), stat('core')
    row = dict(frame=c['frame'], global_frame=c['global_frame'], time=c['time'],
        observations=[dict(id=1, mask='n:1', box=[12, 12, 36, 36], depth=dict(whole))])
    profiles = {1: dict(id=1, frame=c['frame'], mask='n:1', whole=whole, core=fixed)}
    raw = {1: dict(native=1, fact_id=f'test/F{c["frame"]}/n:1/adaptive/raw',
                  core_usable=True, core=adaptive, whole=stat('whole'))}
    return row, profiles, raw


class SameROIContractTests(unittest.TestCase):
    def test_three_roles_match_their_actual_roi_and_original_statistics(self):
        data, source = fixture()
        c = packet(data, source)['objects'][1]
        occupancy = data[2][1].astype('u2')
        _, fixed = fixed_core(data[2][1], occupancy)
        adaptive, _ = adaptive_core(data[2][1], occupancy)
        self.assertNotEqual(int(fixed.sum()), int(adaptive.sum()))
        self.assertEqual(c['birth_core']['inclusive_summary']['area'], int(fixed.sum()))
        self.assertEqual(c['core']['inclusive_summary']['area'], int(adaptive.sum()))
        row, profiles, raw = inputs(c)
        new_row, new_profiles = guard_inputs(row, profiles, {1: c})
        new_raw = guard_raw(raw, {1: c})
        self.assertEqual(new_profiles[1]['core'], profiles[1]['core'])
        self.assertEqual(new_raw[1]['core'], raw[1]['core'])
        self.assertEqual(new_profiles[1]['measurement_bindings']['BIRTH_CORE']['roi_binding'], c['birth_core_binding'])
        self.assertEqual(new_raw[1]['measurement_bindings']['S0_ADAPTIVE_CORE']['roi_binding'], c['core_binding'])
        self.assertEqual(new_row['observations'][0]['measurement_bindings']['D1_WHOLE']['roi_binding'], c['mask_binding'])
        self.assertEqual(new_profiles[1]['measurement_bindings']['BIRTH_CORE']['identity_state'], 'IDENTITY_UNASSIGNED')

    def test_other_roi_cannot_protect_legacy_birth_scalar(self):
        data, source = fixture()
        c = packet(data, source)['objects'][1]
        row, profiles, raw = inputs(c)
        profiles[1]['core'] = dict(raw[1]['core'])
        with self.assertRaisesRegex(AssertionError, 'scalar/ROI'):
            guard_inputs(row, profiles, {1: c})
        binding = bind_measurement(c, 'S0_ADAPTIVE_CORE', raw[1]['core'])
        self.assertFalse(validate_bound_measurement(binding, raw[1]['core'], 'BIRTH_CORE', c))

    def test_current_frame_native_and_fact_id_bindings_reject_wrong_inputs(self):
        data, source = fixture()
        c = packet(data, source)['objects'][1]
        row, profiles, raw = inputs(c)
        binding = bind_measurement(c, 'BIRTH_CORE', profiles[1]['core'])
        self.assertTrue(validate_bound_measurement(binding, profiles[1]['core'], 'BIRTH_CORE', c, frame=1, native=1))
        self.assertFalse(validate_bound_measurement(binding, profiles[1]['core'], 'BIRTH_CORE', c, frame=2))
        self.assertFalse(validate_bound_measurement(binding, profiles[1]['core'], 'BIRTH_CORE', c, native=11))
        raw[1]['fact_id'] = 'test/F2/n:1/adaptive/raw'
        with self.assertRaises(AssertionError):
            guard_raw(raw, {1: c})
        row['frame'] = 2
        with self.assertRaises(AssertionError):
            guard_inputs(row, profiles, {1: c})

    def test_old_anchor_is_bound_to_past_certificate_and_source_not_public_integer(self):
        data, source = fixture()
        old = packet(data, source)['objects'][1]
        row, profiles, _ = inputs(old)
        source_version = dict(native=1, generation=3)
        key = ['test', 'arm', 3, 11, 5]  # Actual source1 carried public11, never assume1==11.
        binding = bind_measurement(old, 'BIRTH_CORE', profiles[1]['core'], source_version=source_version, version_key=key)
        self.assertTrue(validate_bound_measurement(binding, profiles[1]['core'], 'BIRTH_CORE', old,
            before_frame=2, source_version=source_version, version_key=key))
        self.assertFalse(validate_bound_measurement(binding, profiles[1]['core'], 'BIRTH_CORE', old, before_frame=1))
        now_data, now_source = fixture(2)
        current = packet(now_data, now_source)['objects'][1]
        self.assertFalse(validate_bound_measurement(binding, profiles[1]['core'], 'BIRTH_CORE', current, before_frame=3))
        self.assertFalse(validate_bound_measurement(binding, profiles[1]['core'], 'BIRTH_CORE', old,
            source_version=dict(native=1, generation=4)))
        self.assertFalse(validate_bound_measurement(binding, profiles[1]['core'], 'BIRTH_CORE', old,
            version_key=['test', 'arm', 3, 11, 6]))

    def test_partial_current_identity_context_remains_unassigned(self):
        data, source = fixture()
        c = packet(data, source)['objects'][1]
        _, profiles, _ = inputs(c)
        binding = bind_measurement(c, 'BIRTH_CORE', profiles[1]['core'],
            source_version=['test', 'arm', 1, 3], version_key=['test', 'arm', 3, None, None])
        self.assertEqual(binding['identity_state'], 'IDENTITY_UNASSIGNED')
        self.assertTrue(binding['measurement_valid'])

    def test_rehashed_fake_scalar_and_role_certificates_are_semantically_rejected(self):
        data, source = fixture()
        c = packet(data, source)['objects'][1]
        _, profiles, _ = inputs(c)
        binding = bind_measurement(c, 'BIRTH_CORE', profiles[1]['core'])
        forged = copy.deepcopy(binding)
        forged['actual_scalar']['median'] += 1
        forged['actual_scalar_sha256'] = _digest(forged['actual_scalar'])
        forged['binding_sha256'] = _digest({k: v for k, v in forged.items() if k != 'binding_sha256'})
        self.assertFalse(validate_bound_measurement(forged, forged['actual_scalar'], 'BIRTH_CORE', c))
        forged_certificate = json.loads(json.dumps(c))
        forged_certificate['birth_core']['association_roles'] = ['S0_ADAPTIVE_CORE']
        _seal(forged_certificate)
        self.assertFalse(validate_certificate(forged_certificate))
        self.assertFalse(validate_bound_measurement(binding, profiles[1]['core'], 'BIRTH_CORE', forged_certificate))

    def test_immutable_certificate_keeps_json_bytes_and_branch_context_independent(self):
        data, source = fixture()
        certificate = packet(data, source)['objects'][1]
        ordinary = json.loads(json.dumps(certificate))
        frozen = _validated_facts(ordinary)
        for options in ({}, dict(sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)):
            self.assertEqual(json.dumps(ordinary, **options), json.dumps(frozen, **options))
        self.assertEqual(certificate, ordinary)
        self.assertIs(copy.deepcopy(certificate), certificate)
        self.assertIs(copy.deepcopy(certificate['birth_core']), certificate['birth_core'])
        self.assertIs(copy.deepcopy(certificate['core']['association_roles']), certificate['core']['association_roles'])
        _, profiles, _ = inputs(certificate)
        binding = bind_measurement(certificate, 'BIRTH_CORE', profiles[1]['core'],
            source_version=['test', 'arm', 1, 0], version_key=['test', 'arm', 0, 1, 0])
        cloned = copy.deepcopy(binding)
        cloned['version_key'][3] = 2
        cloned['source_version'][3] = 1
        cloned['actual_scalar']['median'] += 1
        self.assertEqual(binding['version_key'][3], 1)
        self.assertEqual(binding['source_version'][3], 0)
        self.assertEqual(binding['actual_scalar']['median'], 1000.)
        self.assertFalse(validate_bound_measurement(cloned, profiles[1]['core'], 'BIRTH_CORE', certificate))

    def test_nested_certificate_blocks_common_dictionary_and_list_mutations(self):
        data, source = fixture()
        c = packet(data, source)['objects'][1]
        d, a = c['core']['inclusive_summary'], c['core']['association_roles']
        original = json.dumps(c)
        mutations = [
            lambda: d.__setitem__('median', 9), lambda: d.__delitem__('median'),
            lambda: d.clear(), lambda: d.pop('median'), lambda: d.popitem(),
            lambda: d.setdefault('new', 9), lambda: d.update(median=9), lambda: d.__ior__({'median': 9}),
            lambda: a.__setitem__(0, 'other'), lambda: a.__setitem__(slice(None), ['other']),
            lambda: a.__delitem__(0), lambda: a.append('other'), lambda: a.extend(['other']),
            lambda: a.insert(0, 'other'), lambda: a.pop(), lambda: a.remove(a[0]),
            lambda: a.clear(), lambda: a.reverse(), lambda: a.sort(),
            lambda: a.__iadd__(['other']), lambda: a.__imul__(2),
            lambda: setattr(c, '_certificate_token', None), lambda: delattr(c, '_certificate_token'),
        ]
        for mutation in mutations:
            with self.assertRaises(TypeError):
                mutation()
            self.assertEqual(json.dumps(c), original)
        self.assertTrue(validate_certificate(c))
        untrusted = json.loads(original)
        untrusted['birth_core']['association_roles'] = ['S0_ADAPTIVE_CORE']
        _seal(untrusted)
        self.assertFalse(validate_certificate(untrusted))

    def test_all_layers_are_retained_for_fixed_and_adaptive_populations(self):
        data, source = fixture()
        data[0][12:36, 24:36] = 1200.
        c = packet(data, source)['objects'][1]
        for part in ('whole', 'birth_core', 'core'):
            self.assertTrue(c[part]['mixture_flag'])
            self.assertEqual([layer['median'] for layer in c[part]['inclusive_layers']], [1000., 1200.])
            self.assertFalse(c[part]['eligible_single'])
            self.assertTrue(all(layer['fish_count'] == 'UNKNOWN' for layer in c[part]['inclusive_layers']))

    def test_no_filter_control_only_adds_bindings_and_preserves_values(self):
        data, source = fixture()
        data[0][12:36, 28:36] = 1200.
        c = packet(data, source)['objects'][1]
        row, profiles, raw = inputs(c)
        saved = copy.deepcopy((row, profiles, raw))
        new_row, new_profiles = guard_inputs(row, profiles, {1: c}, screen=False)
        new_raw = guard_raw(raw, {1: c}, screen=False)
        self.assertEqual(new_row['observations'][0]['depth'], row['observations'][0]['depth'])
        self.assertEqual(new_profiles[1]['core'], profiles[1]['core'])
        self.assertTrue(new_raw[1]['core_usable'])
        binding = new_profiles[1]['measurement_bindings']['BIRTH_CORE']
        self.assertTrue(binding['measurement_valid'])
        self.assertFalse(binding['screened_eligible'])
        filtered_row, filtered_profiles = guard_inputs(row, profiles, {1: c})
        filtered_raw = guard_raw(raw, {1: c})
        self.assertIsNone(filtered_profiles[1]['core']['median'])
        self.assertFalse(filtered_raw[1]['core_usable'])
        self.assertEqual(filtered_raw[1]['core'], raw[1]['core'])
        self.assertEqual((row, profiles, raw), saved)

    def test_shared_sources_and_sparse_duplicates_do_not_fabricate_depth_quality(self):
        data, source = fixture()
        data[1][data[2][1]] = 0
        c = packet(data, source)['objects'][1]
        for part in ('whole', 'birth_core', 'core'):
            self.assertFalse(c[part]['eligible_single'])
            self.assertEqual(c[part]['summary']['n'], 1)
        data, source = fixture()
        data[2][2] = data[2][1].copy()
        c = packet(data, source)['objects'][1]
        self.assertFalse(c['whole']['source_ownership_exclusive'])
        self.assertFalse(c['whole']['eligible_single'])
        self.assertEqual(c['birth_core']['inclusive_summary']['n'], 0)

    def test_empty_masks_remain_unknown_and_keep_original_tokens(self):
        data, source = fixture()
        data[2][1][:] = False
        c = packet(data, source)['objects'][1]
        for part in ('whole', 'birth_core', 'core'):
            self.assertEqual(c[part]['status'], 'UNKNOWN')
            self.assertEqual(c[part]['inclusive_summary']['n'], 0)
        row, profiles, raw = inputs(c)
        raw[1]['core_usable'] = False
        new_row, _ = guard_inputs(row, profiles, {1: c})
        self.assertEqual(new_row['observations'][0]['mask'], 'n:1')
        self.assertFalse(guard_raw(raw, {1: c})[1]['core_usable'])
        self.assertTrue(validate_certificate(c))

    def test_future_gt_rgb_and_restored_sources_are_rejected(self):
        data, source = fixture()
        for key in ('GT_read', 'RGB_read', 'restored_read'):
            with self.assertRaises(AssertionError):
                packet(data, dict(source, **{key: True}))
        with self.assertRaises(AssertionError):
            packet(data, dict(source, global_frame=1))
        output = packet(data, source)
        self.assertEqual(output['schema'], SCHEMA)
        json.dumps(output, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
