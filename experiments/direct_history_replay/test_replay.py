"""Only the parser, physical binding, and real model-off parity checks."""
import copy
import json
from pathlib import Path

from replay import HERE, cases, hypotheses, parse_choice, read, sha


def main():
    old = read(HERE.parent/'ehr_contract_first_trial/run/public/responses/S02.json')
    assert parse_choice(old['content'], old['finish_reason']) == ('DEFER', 'VALID')
    assert parse_choice('{"preferred_hypothesis":"H1","version":2,"type":"object"}', 'stop') == ('H1', 'VALID')
    assert parse_choice('{"preferred_hypothesis":"H1","choice":"H2"}', 'stop')[1] == 'CONFLICTING_CHOICE'
    assert parse_choice('{"preferred_hypothesis":"H1","preferred_hypothesis":"H2"}', 'stop')[1] == 'UNPARSEABLE'
    assert parse_choice('{"preferred_hypothesis":"H3"}', 'stop')[1] == 'INVALID_CHOICE'
    assert parse_choice('{"preferred_hypothesis":"H1"}', 'length')[1] == 'TRUNCATED_OR_MISSING'
    b01 = cases()['B01']
    packet = b01['packet']
    refs = {'A': {'public_id': 1}, 'B': {'public_id': 4}}
    view = {'mapping': {1: 1, 3: 3, 4: 4, 5: 5, 6: 2, 7: 7}}
    first = hypotheses(packet, refs, view, b01['native'])
    renamed = copy.deepcopy(packet)
    for h in renamed['hypotheses']:
        h['id'] = {'H1': 'H2', 'H2': 'H1'}[h['id']]
    second = hypotheses(renamed, refs, view, b01['native'])
    assert first['H1']['full'] == second['H2']['full']
    assert first['H2']['full'] == second['H1']['full']
    dry = HERE/'dry_run'
    seal = read(dry/'PREDICTIONS_SEALED.json')
    assert seal['frames'] == 2888 and seal['HTTP_attempts'] == 0
    assert sha(dry/'predictions_validation.jsonl.gz') == seal['predictions_sha256']
    assert sha(dry/'transactions_validation.jsonl.gz') == seal['transactions_sha256']
    result = dict(status='PASS', checks=['S02_EXTRA_FIELDS', 'INVALID_AND_CONFLICTING_CHOICE',
                  'CANDIDATE_RENAME_PHYSICAL_EQUIVALENCE', 'MODEL_OFF_B0_EXACT_2888'],
                  frames=2888, model_off_prediction_sha256=seal['predictions_sha256'])
    path = HERE/'TEST_REPORT.json'
    path.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(result['status'], result['checks'])


if __name__ == '__main__':
    main()
