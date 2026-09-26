"""Small source/decision regressions; run without provider calls or GT."""
import json

from prepare import condition, fit
from score import parse


def test_decision_kept_when_explanation_is_invalid():
    fact = dict(fact_id='A-F1', source_time_seconds=1., bbox_center_px=[1, 2],
                neighbor_count=0, area_px=10)
    packet = dict(request_id='EHR1-TEST', PRE_HISTORY={'A': {'observations':[fact]}, 'B': {'observations':[]}},
                  POST_HISTORY_TO_Q={'X': {'observations':[]}, 'Y': {'observations':[]}},
                  INTERACTION_OBSERVATIONS=[])
    answer = dict(request_id='EHR1-TEST', preferred_hypothesis='H1', uncertainty_reason='uncertain',
                  hypothesis_assessments=[dict(id=h, supporting_fact_ids=['FAKE'], conflicting_fact_ids=[],
                                               unresolved_assumptions=['unknown']) for h in ('H1','H2')])
    parsed = parse(json.dumps(answer), packet)
    assert parsed['parseable'] and parsed['raw_preference'] == 'H1' and not parsed['usable']
    assert any('INVALID_SUPPORTING' in x for x in parsed['errors'])


def test_missing_contiguous_motion_is_unknown():
    points = [dict(fact_id=f'F{i}', source_time_seconds=t, bbox_center_px=[x, 0],
                   neighbor_count=0, area_px=10) for i, (t, x) in enumerate([(1., 0), (1.1, 10), (2., 20)])]
    assert fit(points)['epistemic_type'] == 'UNKNOWN'


def test_repeat_and_permutation_are_isolated():
    sample = dict(request_id='EHR1-TEST', q_frame=2, trigger=dict(original_frozen_trigger_frame=1),
                  IMAGE_INDEX=[dict(image_id='G1', frame=0), dict(image_id='G2', frame=2)],
                  PRE_HISTORY={'A': {'observations':[]}, 'B': {'observations':[]}},
                  POST_HISTORY_TO_Q={'X': {'observations':[]}, 'Y': {'observations':[]}},
                  INTERACTION_OBSERVATIONS=[],
                  hypotheses=[dict(id='H1', mapping={'X':'A','Y':'B'}), dict(id='H2', mapping={'X':'B','Y':'A'})])
    first, repeat, perm = [condition(sample, arm) for arm in ('H-D','H-D-REPEAT','H-D-PERMUTE')]
    assert first == repeat
    assert perm['hypotheses'][0]['mapping'] == first['hypotheses'][1]['mapping']
    perm['hypotheses'] = first['hypotheses']
    assert perm == first


if __name__ == '__main__':
    test_decision_kept_when_explanation_is_invalid()
    test_missing_contiguous_motion_is_unknown()
    test_repeat_and_permutation_are_isolated()
    print('3 EHR-1 regressions passed')
