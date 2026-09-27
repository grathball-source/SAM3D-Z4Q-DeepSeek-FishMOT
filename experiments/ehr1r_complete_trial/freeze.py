"""Prepare an isolated sender tree, conservative budget, and immutable pre-call lock."""
import argparse
import json
import shutil
from pathlib import Path

from build import read, save, sha
from sender import SYSTEM, wire

CODE=('build.py','validate.py','sender.py','score.py','freeze.py','test_acceptance.py')
INPUT=('REQUESTS_LOGICAL.json','REQUEST_MANIFEST.json','SOURCE_TO_BODY_AUDIT.json',
       'PLAN.json','SENDER_GATE.json','BUDGET.json','BODY_GATE.json','PREUPLOAD_LOCK.json')


def prepare(run):
    run=Path(run);public=run/'public';send=run/'send'
    assert read(public/'SOURCE_TO_BODY_AUDIT.json')['status']=='SOURCE_TO_LOGICAL_PASS'
    logical=read(public/'REQUESTS_LOGICAL.json')['requests']
    manifest=read(public/'REQUEST_MANIFEST.json')
    assert [x['attempt_id'] for x in logical]==manifest['schedule'] and len(logical)==25
    send.mkdir(exist_ok=False)
    (send/'media').mkdir()
    for image in {x['media_file']:x for r in logical for x in r['images']}.values():
        src=run/'private/media'/image['media_file'];dst=send/'media'/image['media_file']
        assert sha(src)==image['sha256'];shutil.copyfile(src,dst);assert sha(dst)==image['sha256']
    for name in ('REQUESTS_LOGICAL.json','REQUEST_MANIFEST.json'):
        shutil.copyfile(public/name,send/name)
    shutil.copyfile(Path(__file__).parent/'sender.py',send/'sender.py')
    plan=dict(model='deepseek-flash',max_tokens=65536,cap_usd=3,smoke_max=1,requests=logical)
    save(public/'PLAN.json',plan);shutil.copyfile(public/'PLAN.json',send/'PLAN.json')
    budget=[]
    for request in logical:
        # Peak cache-miss input, 1024/image, 65536 output, twice published text heuristic.
        chars=len(request['text']+SYSTEM)
        tokens=int(chars*.60+.999999)+len(request['images'])*1024
        value=(tokens*.30+65536*1.20)/1_000_000
        budget.append(dict(attempt_id=request['attempt_id'],text_characters=chars,
            images=len(request['images']),input_token_reserve=tokens,output_token_reserve=65536,
            reserve_usd=round(value,9)))
    smoke=(4096*.30+65536*1.20)/1_000_000
    total=sum(x['reserve_usd'] for x in budget)+smoke
    save(public/'BUDGET.json',dict(status='PRE_CALL_CONSERVATIVE_PEAK_RESERVE',
        rate_checked_utc='2026-09-27',official_pricing='https://api-docs.deepseek.com/quick_start/pricing/',
        official_vision='https://api-docs.deepseek.com/guides/vision/',
        peak_cache_miss_input_usd_per_m=.30,peak_output_usd_per_m=1.20,
        image_tokens_upper_each=1024,text_token_factor=.60,max_output_tokens=65536,
        request_budget=budget,smoke_reserve_usd=round(smoke,9),total_reserve_usd=round(total,9),cap_usd=3,
        feasible=total<=3,assumption='upper reserve, not billed usage or a guarantee'))
    assert total<=3,('budget blocked; retain all 25 evidence requests',total)
    gate=dict(status='PASS',request_count=25,plan_sha256=sha(public/'PLAN.json'),
        source_audit_sha256=sha(public/'SOURCE_TO_BODY_AUDIT.json'),
        request_budget=budget,smoke_reserve_usd=round(smoke,9),
        total_reserve_usd=round(total,9),cap_usd=3)
    save(public/'SENDER_GATE.json',gate);shutil.copyfile(public/'SENDER_GATE.json',send/'SENDER_GATE.json')
    print(dict(status='SENDER_TREE_PREPARED',images=55,requests=25,reserve_usd=round(total,9)))


def lock(run):
    run=Path(run);public=run/'public';send=run/'send'
    assert read(public/'BODY_GATE.json')['bodies']['status']=='BODY_GATE_PASS'
    assert read(public/'BUDGET.json')['feasible']
    code={name:sha(Path(__file__).parent/name) for name in CODE}
    inputs={name:sha(public/name) for name in INPUT}
    value=dict(status='CODE_INPUT_BUDGET_GATES_FROZEN_BEFORE_INFERENCE',
        base='e95f1a776c62028a7f0d6d5e8a48d26b7c7f4f37',
        code_sha256=code,input_sha256=inputs,
        request_order=read(public/'REQUEST_MANIFEST.json')['schedule'],
        scoring_gates=dict(min_structurally_parseable=24,
            B01_requires_all_three_HD_correct_valid=True,
            four_negatives_require_all_three_HD_valid_correct_or_legal_defer=True,
            E_to_history_requires_valid_scoreable_pair=True,
            semantic_citation_review_separate=True,
            numeric_same_information_comparator='NOT_AVAILABLE'))
    save(public/'CODE_AND_INPUT_LOCK.json',value)
    for name in ('BODY_GATE.json','CODE_AND_INPUT_LOCK.json'):
        shutil.copyfile(public/name,send/name)
    print('PRE_CALL_LOCK_FROZEN')


def preupload(run):
    run=Path(run);public=run/'public';send=run/'send'
    assert read(public/'END_TO_END_ACCEPTANCE.json')['status']=='PASS'
    assert read(public/'SCORER_METAMORPHIC_TESTS.json')['status']=='PASS'
    assert read(public/'BUDGET.json')['feasible']
    names=('REQUESTS_LOGICAL.json','REQUEST_MANIFEST.json','SOURCE_TO_BODY_AUDIT.json',
           'PLAN.json','SENDER_GATE.json','BUDGET.json','END_TO_END_ACCEPTANCE.json',
           'SCORER_METAMORPHIC_TESTS.json')
    value=dict(status='CODE_LOGICAL_REQUEST_BUDGET_SCORER_GATES_FROZEN_BEFORE_UPLOAD',
        code_sha256={name:sha(Path(__file__).parent/name) for name in CODE},
        input_sha256={name:sha(public/name) for name in names},
        total_reserve_usd=read(public/'BUDGET.json')['total_reserve_usd'],
        inference_limit=26,cap_usd=3)
    save(public/'PREUPLOAD_LOCK.json',value)
    shutil.copyfile(public/'PREUPLOAD_LOCK.json',send/'PREUPLOAD_LOCK.json')
    print('PREUPLOAD_LOCK_FROZEN')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','preupload','lock'))
    parser.add_argument('--run',type=Path,required=True);args=parser.parse_args()
    globals()[args.phase](args.run)
