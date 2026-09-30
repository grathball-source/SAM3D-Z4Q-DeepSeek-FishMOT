"""Synthetic, hand-computable checks of fixed-population proxy accounting."""
from copy import deepcopy
import json
import sys
import unittest

sys.dont_write_bytecode = True
from score_helpers import summarize, classify_primary


ARM = 'F2_DS3'


def occupancy(n, fish, other=0):
    return dict(n=n, fish=fish, other_fish=other, background=n-fish-other)


def fixture():
    rows = []
    for status, scorable, sample, compatible, error in (
        ('AVAILABLE', True, occupancy(8, 6, 1), True, 5.),
        ('AVAILABLE', True, occupancy(4, 2), False, 200.),
        ('UNKNOWN', True, occupancy(0, 0), None, None),
        ('AVAILABLE', False, None, None, None),
    ):
        rows.append(dict(reference_status='SCORABLE' if scorable else 'LOW_OR_AMBIGUOUS_IOU',
            reference_usable=scorable, whole=occupancy(12, 10) if scorable else None,
            core=occupancy(4, 4) if scorable else None, methods={ARM:dict(status=status,
                occupancy=sample, selected_n=sample['n'] if sample is not None else 7,
                median_mm=1000. if status == 'AVAILABLE' else None,
                reference_compatible=compatible, reference_abs_error_mm=error)}))
    return rows


def refuse(row):
    method = row['methods'][ARM]
    method.update(status='UNKNOWN', occupancy=occupancy(0, 0) if row['reference_status'] == 'SCORABLE' else None,
                  selected_n=0, median_mm=None, reference_compatible=None, reference_abs_error_mm=None)


class Checks(unittest.TestCase):
    def test_four_row_hand_accounting(self):
        result = summarize(fixture(), ARM)
        self.assertEqual((result['source_objects'], result['accepted'], result['unknown']), (4, 3, 1))
        self.assertEqual((result['q_n'], result['r_n'], result['unscorable']), (3, 3, 1))
        self.assertEqual(result['fixed_R'], dict(n=3, compatible=1, discordant=1, unknown=1,
            compatible_yield=1/3, discordant_yield=1/3, unknown_yield=1/3))
        self.assertEqual(result['Q']['fish_denominator'], 30)
        self.assertEqual(result['Q']['selected_counts'], occupancy(12, 8, 1))
        self.assertEqual(result['Q']['fish_yield'], 8/30)
        self.assertEqual(result['Q']['nonfish_yield'], 4/30)
        self.assertEqual(result['conditional_available']['micro_purity'], 8/12)
        self.assertEqual(result['conditional_available']['mean_purity'], (.75+.5)/2)
        self.assertEqual(result['source_selected_n'], 19)
        self.assertEqual(result['cross_tab'], {'SCORABLE':{'AVAILABLE':2, 'UNKNOWN':1},
                                              'UNSCORABLE':{'AVAILABLE':1, 'UNKNOWN':0}})

    def test_refusal_cannot_increase_fixed_compatible_yield(self):
        rows = fixture(); base = summarize(rows, ARM)
        refuse(rows[1]); full = summarize(rows, ARM)
        self.assertEqual(full['r_n'], base['r_n'])
        self.assertEqual(full['Q']['fish_denominator'], base['Q']['fish_denominator'])
        self.assertEqual(full['fixed_R']['compatible_yield'], base['fixed_R']['compatible_yield'])
        self.assertLess(full['Q']['fish_yield'], base['Q']['fish_yield'])
        self.assertEqual(classify_primary(full, base), 'PROXY_GAIN_ONLY')
        refuse(rows[0]); loss = summarize(rows, ARM)
        self.assertLess(loss['fixed_R']['compatible_yield'], base['fixed_R']['compatible_yield'])
        self.assertEqual(classify_primary(loss, base), 'NO_PROXY_GAIN')

    def test_all_refused_is_not_gain(self):
        rows = fixture(); base = summarize(rows, ARM)
        for row in rows: refuse(row)
        full = summarize(rows, ARM)
        self.assertEqual(full['source_selected_n'], 0)
        self.assertEqual(full['Q']['fish_yield'], 0)
        self.assertEqual(full['fixed_R']['unknown_yield'], 1)
        self.assertIsNone(full['conditional_available']['micro_purity'])
        self.assertIsNone(full['conditional_available']['mean_purity'])
        self.assertEqual(classify_primary(full, base), 'NO_PROXY_GAIN')

    def test_all_references_unusable_and_empty_population(self):
        rows = fixture()
        for row in rows:
            row['reference_usable'] = False
            row['methods'][ARM].update(reference_compatible=None, reference_abs_error_mm=None)
        result = summarize(rows, ARM)
        self.assertEqual(result['r_n'], 0)
        self.assertIsNone(result['fixed_R']['compatible_yield'])
        self.assertEqual(classify_primary(result, result), 'NO_PROXY_GAIN')
        empty = summarize([], ARM)
        self.assertIsNone(empty['Q']['fish_yield'])
        self.assertIsNone(empty['conditional_available']['micro_purity'])
        self.assertEqual(classify_primary(empty, empty), 'NO_PROXY_GAIN')

    def test_unscorable_fields_null_and_missing_source_count(self):
        rows = [fixture()[-1]]
        method = rows[0]['methods'][ARM]
        self.assertIsNone(method['occupancy'])
        self.assertIsNone(method['reference_compatible'])
        result = summarize(rows, ARM)
        self.assertEqual(result['source_selected_n'], 7)
        self.assertEqual(result['Q']['selected_counts'], occupancy(0, 0))
        self.assertIsNone(result['Q']['fish_yield'])
        del method['selected_n']
        result = summarize(rows, ARM)
        self.assertIsNone(result['source_selected_n'])
        self.assertEqual(result['source_selected_n_unavailable_objects'], 1)
        method['reference_compatible'] = False
        with self.assertRaisesRegex(ValueError, 'UNSCORABLE'):
            summarize(rows, ARM)

    def test_tradeoff_and_population_mismatch(self):
        rows = fixture()
        extra = deepcopy(rows[0]); rows.append(extra)
        base = summarize(rows, ARM)
        refuse(rows[0]); refuse(rows[1]); full = summarize(rows, ARM)
        self.assertEqual(classify_primary(full, base), 'TRADEOFF')
        mismatch = summarize(rows[:-1], ARM)
        with self.assertRaisesRegex(ValueError, 'same'):
            classify_primary(mismatch, base)
        self.assertEqual(classify_primary(base, base), 'NO_PROXY_GAIN')

    def test_input_not_modified_and_count_integrity(self):
        rows = fixture(); original = deepcopy(rows)
        summarize(rows, ARM)
        self.assertEqual(rows, original)
        rows[0]['methods'][ARM]['occupancy']['fish'] = 99
        with self.assertRaisesRegex(ValueError, 'partition'):
            summarize(rows, ARM)
        rows = fixture(); rows[2]['methods'][ARM]['selected_n'] = 1
        with self.assertRaisesRegex(ValueError, 'UNKNOWN'):
            summarize(rows, ARM)


if __name__ == '__main__':
    from bootstrap import HERE, ARMS, write_new
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    record = dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        passed=result.wasSuccessful(), fixture='FOUR_HAND_COMPUTED_SYNTHETIC_ROWS_NO_GT',
        arms=list(ARMS), physical_depth_truth='NOT_ASSUMED', new_thresholds=0,
        source_or_annotation_reads=0, network_calls=0)
    write_new(HERE/'SCORE_CHECKS.json', record)
    print(json.dumps(record, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
