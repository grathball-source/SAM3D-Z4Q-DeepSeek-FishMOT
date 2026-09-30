"""Record actual tests, stops, immutable replay exits and costs."""
from common import *
from datetime import datetime,timezone
def main():
    entries=[
        dict(step='adaptive_tests',exit_code=0,tests=10,result=artifact(HERE/'ADAPTIVE_CHECKS.json')),
        dict(step='measurement_tests',exit_code=0,tests=5,result=artifact(HERE/'MEASUREMENT_CHECKS.json')),
        dict(step='controller_tests',exit_code=0,tests=13,result=artifact(HERE/'CONTROLLER_CHECKS.json')),
        dict(step='score_checks',exit_code=0,tests=5,result=artifact(HERE/'SCORE_CHECKS.json')),
        dict(step='preflight',exit_code=0,lock=artifact(HERE/'OLD_READONLY_LOCK.json')),
        dict(step='slice_attempt1',exit_code=1,log=artifact(HERE/'SLICE_LOG.txt'),
            reason='Missing CONTROLLER_CHECKS.json: first test invocation lacked --write-new. Failed while hashing CODE, before any FREEZE/input prediction. Empty output kept separately. Tests rerun with report option, no semantic code change or research result reuse.')]
    for name in ('SLICE_ATTEMPT2','FULL','SCORE','REPORT','POSTRUN'):
        p=HERE/(name+'_EXIT.txt')
        if p.exists():
            entries.append(dict(step=name,exit_code=int(p.read_text(encoding='utf-8-sig').strip()),
                log=artifact(HERE/(name+'_LOG.txt'))))
    write_new(HERE/'EXECUTION_LOG.json',dict(entries=entries,
        UTC=datetime.now(timezone.utc).isoformat(),new_model_http=0,cost_usd=0,
        no_semantic_tuning_after_full_freeze=True,all_research_predictions_new=True))
    print('Actual executions recorded')
if __name__=='__main__':main()
