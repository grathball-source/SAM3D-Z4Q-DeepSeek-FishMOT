"""Direct causal, quality and physical-permutation checks for paired depth order."""
import copy
import unittest

from order_association import choose, evidence, t4_cdf


def fixture():
    times = [0., .04, .09, .15, .22]
    def point(frame, now, native, public):
        return dict(frame=frame, time=now, source=native, center=[100., 100.],
            bbox=[95., 95., 105., 105.], area=100, neighbors=[], source_generation=1,
            public_id=public, public_epoch=0, observation_class='SOURCE_OBSERVATION')
    episode = dict(q=8, suspect_frame=6, member_sources=[11, 12], public_ids=[1, 2],
        temporary_choice='H1', pre={r: [point(i + 1, t, n, p) for i, t in enumerate(times)]
            for r, n, p in [('A', 11, 1), ('B', 12, 2)]},
        post_roles={n: [point(8, .32, n, p)] for n, p in [(11, 1), (12, 2)]})
    frozen = {r: dict(key=['test', 'RAW', 1, p, 0], source=n, public=p,
        cutoff_frame=5, acquired_interval_seconds=.07,
        samples=[dict(frame=i + 1, time=t, z_mm=z, mad_mm=2., source_native=n,
            n=100, valid_fraction=1., core_usable=True,
            fact_id=f'test/F{i + 1}/n:{n}/raw') for i, t in enumerate(times)])
        for r, n, p, z in [('A', 11, 1, 1000.), ('B', 12, 2, 1500.)]}
    measured = {n: dict(fact_id=f'test/F8/n:{n}/raw', core_usable=True,
        core=dict(n=100, median=z, mad=2., valid_fraction=1.)) for n, z in [(11, 1500.), (12, 1000.)]}
    return [episode, frozen, measured, dict(n=1000, median=2000., mad=100.), {11: 1, 12: 2}]


def run(data, mode='ORDER'):
    return choose(*data, mode, 'test')


class OrderTests(unittest.TestCase):
    def test_cdf_closed_form_symmetry_and_limits(self):
        self.assertEqual(t4_cdf(0.), .5)
        self.assertAlmostEqual(t4_cdf(2.), .9419417382415922)
        self.assertAlmostEqual(t4_cdf(-2.), 1. - t4_cdf(2.))
        self.assertAlmostEqual(t4_cdf(1.e6), 1.)

    def test_order_recovers_joint_swap_while_off_retains_h0(self):
        data = fixture()
        choice, result = run(data)
        self.assertNotEqual(choice, 'H0')
        self.assertEqual(result['selected_mapping'], {11: 2, 12: 1})
        self.assertEqual(run(data, 'ORDER_OFF')[0], 'H0')
        self.assertTrue(result['order_evidence']['eligible'])
        self.assertTrue(all(c['depth_log_lr'] == 0. for c in result['candidates'].values()))

    def test_common_depth_shift_does_not_change_score(self):
        data = fixture()
        original = run(data)[1]
        shifted = copy.deepcopy(data)
        for role in ('A', 'B'):
            for sample in shifted[1][role]['samples']:
                sample['z_mm'] += 1000.
        for measurement in shifted[2].values():
            measurement['core']['median'] += 2000.
        result = run(shifted)[1]
        self.assertEqual(result['selected_mapping'], original['selected_mapping'])
        for label in original['candidates']:
            self.assertEqual(result['candidates'][label]['log_score'], original['candidates'][label]['log_score'])

    def test_role_swap_preserves_physical_choice(self):
        data = fixture()
        original = run(data)[1]
        swapped = copy.deepcopy(data)
        swapped[0]['public_ids'].reverse()
        swapped[0]['member_sources'].reverse()
        swapped[0]['pre'] = {'A': swapped[0]['pre']['B'], 'B': swapped[0]['pre']['A']}
        swapped[1] = {'A': swapped[1]['B'], 'B': swapped[1]['A']}
        result = run(swapped)[1]
        self.assertEqual(result['selected_mapping'], original['selected_mapping'])
        before = {tuple(c['mapping'].items()): c['log_score'] for c in original['candidates'].values()}
        after = {tuple(c['mapping'].items()): c['log_score'] for c in result['candidates'].values()}
        self.assertEqual(before, after)

    def test_post_permutation_is_scoring_only(self):
        data = fixture()
        preserved = copy.deepcopy(data)
        self.assertEqual(run(data, 'ORDER_PERMUTE')[0], 'H0')
        result = run(data, 'ORDER_PERMUTE')[1]
        binding = result['order_evidence']['post_bindings']['11']
        self.assertEqual(binding['assigned_depth_source'], 12)
        self.assertEqual(binding['actual_state_source'], 11)
        self.assertEqual(binding['actual_core']['median'], 1500.)
        self.assertEqual(data, preserved)

    def test_missing_and_low_quality_are_neutral_in_all_arms(self):
        for mutation in ('missing', 'absent', 'core_missing', 'n', 'fraction', 'mad', 'fact'):
            for mode in ('ORDER_OFF', 'ORDER', 'ORDER_PERMUTE'):
                with self.subTest(mutation=mutation, mode=mode):
                    data = fixture()
                    current = data[2][11]
                    if mutation == 'missing': current['core_usable'] = False
                    if mutation == 'absent': data[2].pop(11)
                    if mutation == 'core_missing': current['core'] = None
                    if mutation == 'n': current['core']['n'] = 15
                    if mutation == 'fraction': current['core']['valid_fraction'] = .19
                    if mutation == 'mad': current['core']['mad'] = 1000.
                    if mutation == 'fact': current['fact_id'] = 'test/F9/n:11/raw'
                    choice, result = run(data, mode)
                    self.assertEqual(choice, 'H0')
                    self.assertFalse(result['order_evidence']['eligible'])
                    self.assertTrue(all(c['order_log_lr'] == 0. for c in result['candidates'].values()))

    def test_pre_version_gap_and_future_are_rejected(self):
        for mutation in ('version', 'generation', 'epoch', 'gap', 'future', 'risk', 'fact', 'time', 'pre_n', 'pre_fraction', 'pre_source', 'pre_quality_missing'):
            with self.subTest(mutation=mutation):
                data = fixture()
                sample = data[1]['A']['samples'][-1]
                if mutation == 'version': sample['version_key'] = ['test', 'RAW', 1, 99, 0]
                if mutation == 'generation': data[0]['pre']['A'][-1]['source_generation'] = 2
                if mutation == 'epoch': data[0]['pre']['A'][-1]['public_epoch'] = 2
                if mutation == 'gap': data[1]['A']['samples'].pop(2)
                if mutation == 'future': sample['time'] = .5
                if mutation == 'risk': sample['observation_class'] = 'GROUP_MEASUREMENT'
                if mutation == 'fact': sample['fact_id'] = 'test/F5/n:12/raw'
                if mutation == 'time': data[1]['B']['samples'][-1]['time'] += .001
                if mutation == 'pre_n': sample['n'] = 15
                if mutation == 'pre_fraction': sample['valid_fraction'] = .19
                if mutation == 'pre_source': sample['source_native'] = 12
                if mutation == 'pre_quality_missing': sample.pop('core_usable')
                self.assertFalse(run(data)[1]['order_evidence']['eligible'])

    def test_confident_pre_order_reversal_is_unknown(self):
        data = fixture()
        data[1]['A']['samples'][0]['z_mm'] = 2000.
        result = run(data)[1]
        self.assertEqual(result['order_evidence']['reason'], 'CONFIDENT_PRE_ORDER_REVERSAL')
        self.assertFalse(result['accepted'])

    def test_future_data_never_changes_current_request(self):
        data = fixture()
        original = run(data)
        data[2][99] = dict(fact_id='test/F9/n:99/raw', core_usable=True,
            core=dict(n=100, median=1., mad=0., valid_fraction=1.))
        data[0]['future_observations'] = [dict(frame=9, depth=999999.)]
        self.assertEqual(original, run(data))

    def test_matched_scale_larger_mad_reduces_order_preference(self):
        data = fixture()
        data[1]['B']['samples'] = [dict(p, z_mm=1030.) for p in data[1]['B']['samples']]
        data[2][11]['core']['median'] = 1030.
        result = run(data)[1]
        larger = copy.deepcopy(data)
        for role in ('A', 'B'):
            for sample in larger[1][role]['samples']:
                sample['mad_mm'] = 40.
        for measurement in larger[2].values():
            measurement['core']['mad'] = 40.
        widened = run(larger)[1]
        self.assertLess(abs(widened['candidates']['H0']['order_log_lr']),
                        abs(result['candidates']['H0']['order_log_lr']))
        self.assertEqual(widened['selected_mapping'], larger[4])

    def test_off_can_commit_geometry_and_order_requires_own_positive_support(self):
        data = fixture()
        for point in data[0]['pre']['B']:
            point['center'] = [400., 100.]
            point['bbox'] = [395., 95., 405., 105.]
        data[0]['post_roles'][12][0]['center'] = [400., 100.]
        data[0]['post_roles'][12][0]['bbox'] = [395., 95., 405., 105.]
        data[4] = {11: 2, 12: 1}
        self.assertNotEqual(run(data, 'ORDER_OFF')[0], 'H0')
        result = run(data)[1]
        self.assertEqual(result['selected_mapping'], data[4])
        self.assertEqual(result['reason'], 'NO_POSITIVE_ORDINAL_SUPPORT_OR_PREFERENCE')


if __name__ == '__main__':
    unittest.main()
