"""Freeze one 27-call budget, sender tree, code/input lock, and scoring gates."""
import argparse
import math
import shutil
from pathlib import Path

from build import read, save, sha
from contract import system

CODE = ('build.py', 'validate.py', 'contract.py', 'smoke.py', 'sender.py',
        'score.py', 'freeze.py', 'test_contract.py', 'source_recheck.py',
        'cost.py', 'artifact.py')
PREINPUT = ('REQUESTS_LOGICAL.json', 'SMOKE_REQUESTS.json', 'REQUEST_MANIFEST.json',
            'CONTRACT.json', 'CONTRACT_EXAMPLES.json', 'SOURCE_TO_BODY_AUDIT.json', 'UPSTREAM_SOURCE_RECHECK.json',
            'END_TO_END_ACCEPTANCE.json', 'CONTRACT_TESTS.json', 'PLAN.json',
            'BUDGET.json', 'SENDER_GATE.json')


def prepare(run):
    run = Path(run); public = run/'public'; send = run/'send'
    assert read(public/'SOURCE_TO_BODY_AUDIT.json')['status'] == 'SOURCE_TO_LOGICAL_PASS'
    assert read(public/'UPSTREAM_SOURCE_RECHECK.json')['status'] == 'PASS'
    assert read(public/'END_TO_END_ACCEPTANCE.json')['status'] == 'PASS'
    assert read(public/'CONTRACT_TESTS.json')['status'] == 'PASS'
    formal = read(public/'REQUESTS_LOGICAL.json')['requests']
    smoke = read(public/'SMOKE_REQUESTS.json')['requests']
    assert len(formal) == 25 and len(smoke) == 2
    assert not send.exists()
    (send/'media').mkdir(parents=True); (send/'public').mkdir()
    media = {x['media_file']: x for r in formal+smoke for x in r['images']}
    assert len(media) == 59
    for image in media.values():
        source = run/'private/media'/image['media_file']; target = send/'media'/image['media_file']
        assert sha(source) == image['sha256'] and source.stat().st_size == image['bytes']
        shutil.copyfile(source, target); assert sha(target) == image['sha256']
    for name in ('REQUESTS_LOGICAL.json', 'SMOKE_REQUESTS.json', 'CONTRACT.json', 'REQUEST_MANIFEST.json'):
        shutil.copyfile(public/name, send/name)
    for name in ('sender.py', 'contract.py', 'build.py', 'score.py'):
        shutil.copyfile(Path(__file__).parent/name, send/name)
    plan = {'model': 'deepseek-flash', 'max_tokens': 65536, 'thinking': 'enabled',
            'reasoning_effort': 'high', 'response_format': 'json_object', 'cap_usd': 4,
            'smoke_schedule': [x['attempt_id'] for x in smoke],
            'formal_schedule': [x['attempt_id'] for x in formal],
            'no_retry': True, 'formal_after_both_smoke_qualified': True}
    save(public/'PLAN.json', plan); shutil.copyfile(public/'PLAN.json', send/'PLAN.json')
    rates = []
    for request in smoke+formal:
        chars = len(request['text']+system())
        # Peak cache-miss reserve: generous text heuristic, image allowance, full output cap.
        tokens = math.ceil(chars*.60)+len(request['images'])*1024
        dollars = round((tokens*.30+65536*1.20)/1_000_000, 9)
        rates.append({'attempt_id': request['attempt_id'], 'text_characters': chars,
                      'images': len(request['images']), 'input_token_reserve': tokens,
                      'output_token_reserve': 65536, 'reserve_usd': dollars})
    total = round(sum(x['reserve_usd'] for x in rates), 9)
    budget = {'status': 'PRECALL_PEAK_CACHE_MISS_RESERVE', 'checked_utc': '2026-09-27',
              'official_pricing': 'https://api-docs.deepseek.com/quick_start/pricing/',
              'official_vision': 'https://api-docs.deepseek.com/guides/vision/',
              'official_files': 'https://api-docs.deepseek.com/guides/files_api/',
              'peak_input_usd_per_m': .30, 'peak_output_usd_per_m': 1.20,
              'text_token_factor': .60, 'image_token_reserve_each': 1024,
              'request_budget': rates, 'total_reserve_usd': total, 'cap_usd': 4,
              'feasible': total <= 4, 'invoice': False}
    save(public/'BUDGET.json', budget)
    assert total <= 4, ('budget blocked without evidence removal', total)
    gate = {'status': 'PASS', 'request_count': 27, 'plan_sha256': sha(public/'PLAN.json'),
            'source_audit_sha256': sha(public/'SOURCE_TO_BODY_AUDIT.json'),
            'request_budget': rates, 'total_reserve_usd': total, 'cap_usd': 4}
    save(public/'SENDER_GATE.json', gate)
    shutil.copyfile(public/'SENDER_GATE.json', send/'SENDER_GATE.json')
    print({'prepared': 27, 'media': 59, 'peak_reserve_usd': total})


def preupload(run):
    run = Path(run); public = run/'public'; send = run/'send'
    assert not (send/'public/CALL_LEDGER.jsonl').exists()
    code = {name: sha(Path(__file__).parent/name) for name in CODE}
    inputs = {name: sha(public/name) for name in PREINPUT}
    lock = {'status': 'CODE_LOGICAL_REQUEST_BUDGET_FROZEN_BEFORE_UPLOAD',
            'review_base': 'f68552be88c20cc500be8281f6f1ec04db34b4ee',
            'code_sha256': code, 'input_sha256': inputs,
            'inference_limit': 27, 'cap_usd': 4}
    save(public/'PREUPLOAD_LOCK.json', lock)
    shutil.copyfile(public/'PREUPLOAD_LOCK.json', send/'PREUPLOAD_LOCK.json')
    for name in PREINPUT:
        if not (send/name).exists():
            shutil.copyfile(public/name, send/name)
    print('PREUPLOAD_LOCK_FROZEN')


def lock(run):
    run = Path(run); public = run/'public'; send = run/'send'
    assert read(public/'BODY_GATE.json')['status'] == 'BODY_GATE_PASS'
    assert read(public/'BUDGET.json')['feasible']
    prior = read(public/'PREUPLOAD_LOCK.json')
    assert all(sha(Path(__file__).parent/name) == digest for name, digest in prior['code_sha256'].items())
    assert all(sha(public/name) == digest for name, digest in prior['input_sha256'].items())
    value = {'status': 'CODE_INPUT_BUDGET_SCORING_GATES_FROZEN_BEFORE_INFERENCE',
             'review_base': prior['review_base'],
             'code_sha256': prior['code_sha256'],
             'input_sha256': {name: sha(public/name) for name in PREINPUT+('PREUPLOAD_LOCK.json', 'BODY_GATE.json')},
             'request_order': read(public/'REQUEST_MANIFEST.json')['schedule'],
             'scoring_gates': {'all_25_formal_sealed': True, 'all_score_propositions_eligible': True,
                 'B01_HD_repeat_permute_correct': True,
                 'four_negative_HD_valid_correct_or_defer': True,
                 'E_to_history_valid_paired_gain': True,
                 'repeat_not_voted_or_best_selected': True,
                 'numeric_same_information_baseline': 'UNAVAILABLE'}}
    save(public/'CODE_AND_INPUT_LOCK.json', value)
    for name in ('BODY_GATE.json', 'CODE_AND_INPUT_LOCK.json'):
        shutil.copyfile(public/name, send/name)
    print('CODE_AND_INPUT_LOCK_FROZEN')


def collect(run):
    run = Path(run)
    for source in (run/'send/public').rglob('*'):
        if not source.is_file():
            continue
        target = run/'public'/source.relative_to(run/'send/public')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert sha(source) == sha(target), target
        else:
            shutil.copyfile(source, target)
            assert sha(source) == sha(target)
    print('SENDER_PUBLIC_COLLECTED')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('phase', choices=('prepare', 'preupload', 'lock', 'collect'))
    p.add_argument('--run', type=Path, required=True); a = p.parse_args()
    globals()[a.phase](a.run)
