"""Focused causal-history, partial-identity, missingness and symmetry checks."""
import copy
import unittest

from group_association import admission, choose, predict


def observation(frame, now, native, x, public):
    return dict(frame=frame, time=now, source=native, center=[x, 100.],
        bbox=[x-5, 95., x+5, 105.], area=100, neighbors=[],
        source_generation=1, public_id=public, public_epoch=0,
        observation_class='SOURCE_OBSERVATION', core=None)


def fixture(one_changed=False):
    times = [0., .04, .09, .15, .22]
    pre = {r: [observation(i+1, t, native, x, public) for i, t in enumerate(times)]
           for r, native, x, public in [('A', 11, 100., 1), ('B', 12, 400., 2)]}
    frozen = {r: dict(key=['test', 'RAW', 1, public, 0], source=native,
        public=public, cutoff_frame=5, acquired_interval_seconds=.07,
        samples=[dict(frame=i+1, time=t, z_mm=z, mad_mm=2., source='RAW',
            fact_id=f'test/F{i+1}/n:{native}/raw') for i, t in enumerate(times)])
        for r, native, public, z in [('A', 11, 1, 1000.), ('B', 12, 2, 1500.)]}
    if one_changed:
        posts = {11: [observation(8, .32, 11, 100., 1)],
                 21: [observation(8, .32, 21, 400., 21)]}
        values = {11: 1000., 21: 1500.}
        baseline = {11: 1, 21: 21}
        pre['A'] = pre['A'][-1:]
        frozen['A']['samples'] = frozen['A']['samples'][-1:]
    else:
        posts = {11: [observation(8, .32, 11, 400., 1)],
                 12: [observation(8, .32, 12, 100., 2)]}
        values = {11: 1000., 12: 1500.}
        baseline = {11: 1, 12: 2}
    episode = dict(q=8, suspect_frame=6, pre=pre, post_roles=posts,
                   public_ids=[1, 2], member_sources=[11, 12], temporary_choice='H1')
    measured = {n: dict(fact_id=f'test/F8/n:{n}/raw', core_usable=True,
        core=dict(n=100, median=z, mad=2., valid_fraction=1.), cohort='RAW', source='RAW')
        for n, z in values.items()}
    return episode, frozen, measured, dict(n=1000, median=2000., mad=100.), baseline


def run(data):
    return choose(*data, 'RAW_DEPTH', 'test')


class GroupTests(unittest.TestCase):
    def test_partial_history_cannot_force_two_identity_exchange(self):
        data = fixture()
        data[0]['pre']['A'] = []
        data[1]['A']['samples'] = []
        choice, detail = run(data)
        audit = detail['group_depth_admission']
        self.assertTrue(audit['joint_accepted'])
        self.assertNotEqual(audit['joint_selected_choice'], 'H0')
        self.assertEqual(choice, 'H0')
        self.assertEqual(detail['selected_mapping'], data[4])
        self.assertEqual(audit['reason'], 'GROUP_CHANGED_IDENTITY_HISTORY_UNKNOWN')

    def test_one_changed_role_can_use_depth_without_three_samples_everywhere(self):
        data = fixture(one_changed=True)
        choice, detail = run(data)
        self.assertNotEqual(choice, 'H0')
        self.assertEqual(detail['selected_mapping'], {11: 1, 21: 2})
        audit = detail['group_depth_admission']
        self.assertTrue(audit['accepted'])
        self.assertEqual([c['public'] for c in audit['changed_roles']], [2])
        self.assertEqual(detail['depth_forecasts']['A']['samples'], 1)
        self.assertIsNone(detail['depth_forecasts']['A']['slope_mm_s'])
        data[1]['A']['samples'] = []
        self.assertEqual(run(data)[1]['selected_mapping'], {11: 1, 21: 2})

    def test_future_version_risk_and_negative_mad_are_not_forecast_evidence(self):
        base = fixture(one_changed=True)[1]['B']
        for mutation in ('future', 'version', 'risk', 'negative_mad', 'gap'):
            with self.subTest(mutation=mutation):
                frozen = copy.deepcopy(base)
                if mutation == 'future': frozen['samples'][-1]['time'] = 1.
                if mutation == 'version': frozen['samples'][-1]['version_key'] = ['test', 'RAW', 1, 99, 0]
                if mutation == 'risk': frozen['samples'][-1]['observation_class'] = 'GROUP_MEASUREMENT'
                if mutation == 'negative_mad':
                    frozen['samples'] = frozen['samples'][-1:]
                    frozen['samples'][0]['mad_mm'] = -1.
                if mutation == 'gap': frozen['samples'][1]['frame'] += 1
                forecast = predict(frozen, .32)
                self.assertFalse(forecast['history_eligible'])
                self.assertIsNone(forecast['mu_mm'])

    def test_invalid_role_version_cannot_be_reassigned(self):
        data = fixture(one_changed=True)
        data[1]['B']['key'][3] = 99
        choice, detail = run(data)
        self.assertEqual(choice, 'H0')
        self.assertFalse(detail['group_depth_admission']['accepted'])

    def test_positive_foreground_support_does_not_override_opposing_depth_preference(self):
        data = fixture()
        for sample in data[1]['B']['samples']:
            sample['z_mm'] = 1040.
        data[2][12]['core']['median'] = 1040.
        choice, detail = run(data)
        audit = detail['group_depth_admission']
        self.assertTrue(audit['joint_accepted'])
        selected = detail['candidates'][audit['joint_selected_choice']]
        self.assertTrue(all(p['depth']['log_lr'] > 0 for p in selected['pairs']))
        self.assertEqual(choice, 'H0')
        self.assertEqual(audit['reason'], 'GROUP_CHANGED_IDENTITY_NONPOSITIVE_DEPTH_PREFERENCE')

    def test_missing_query_depth_is_common_and_cannot_create_advantage(self):
        data = fixture(one_changed=True)
        data[2][21]['core_usable'] = False
        choice, detail = run(data)
        self.assertEqual(choice, 'H0')
        self.assertEqual(detail['group_depth_admission']['reason'], 'GROUP_DEPTH_PAIR_UNINFORMATIVE')
        self.assertTrue(all(c['depth_log_lr'] == 0 for c in detail['candidates'].values()))
        self.assertTrue(all(not e['depth']['used'] for e in detail['edges'].values()))

    def test_post_and_candidate_container_order_does_not_change_physical_decision(self):
        data = fixture(one_changed=True)
        _, detail = run(data)
        reordered = list(copy.deepcopy(data))
        reordered[0]['post_roles'] = dict(reversed(list(reordered[0]['post_roles'].items())))
        reordered[2] = dict(reversed(list(reordered[2].items())))
        _, other = run(reordered)
        self.assertEqual(detail['selected_mapping'], other['selected_mapping'])
        self.assertEqual(detail['group_depth_admission']['accepted'], other['group_depth_admission']['accepted'])
        changed = copy.deepcopy(detail)
        changed['candidates'] = dict(reversed(list(changed['candidates'].items())))
        changed['edges'] = dict(reversed(list(changed['edges'].items())))
        selected = detail['group_depth_admission']['joint_selected_choice']
        self.assertEqual(admission(data[0], detail, selected), admission(data[0], changed, selected))


if __name__ == '__main__':
    unittest.main()
