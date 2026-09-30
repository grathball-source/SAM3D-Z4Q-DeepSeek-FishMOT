"""Record real exits and prefreeze fixture repairs without relabeling research outcomes."""
from common import *
from datetime import datetime,timezone
entries=[
dict(step='preflight',exit_code=0,old_byte_locks=456),
dict(step='unit_fixture_attempt1',exit_code=1,reason='inferred-only fixture mistakenly kept two physical depths; quality gate correctly rejected it; fixture changed to one uniform inferred cohort'),
dict(step='unit_fixture_attempt2',exit_code=1,reason='synthetic post fixture lacked mandatory frame field; supplied frame=2'),
dict(step='runner_import_attempt1',exit_code=1,reason='generated CODE list referenced DS6 missing from explicit common import; fixed before any prediction output'),
dict(step='unit_checks',exit_code=0,result=artifact(HERE/'UNIT_CHECKS.json')),
dict(step='controller_checks',exit_code=0,result=artifact(HERE/'CONTROLLER_CHECKS.json')),
dict(step='score_checks',exit_code=0,result=artifact(HERE/'SCORE_CHECKS.json')),
]
for name,token in [('slice','SLICE'),('full','FULL'),('score','SCORE'),('report','REPORT')]:
    p=HERE/(token+'_EXIT.txt')
    if p.exists():
        code=int(p.read_text(encoding='utf-8-sig').strip())
        entries.append(dict(step=name,exit_code=code,log=artifact(HERE/(token+'_LOG.txt'))))
write_new(HERE/'EXECUTION_LOG.json',dict(entries=entries,new_model_http=0,cost_usd=0,
    UTC=datetime.now(timezone.utc).isoformat(),predictions_sealed_before_reference_scoring=True,
    no_semantic_tuning_after_full_freeze=True))
print('Recorded',len(entries),'steps')

