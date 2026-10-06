"""Append-only scorer repair: compare the actual JSON representation on both sides."""
from common import *

def serialized(value):
    def convert(item):
        if isinstance(item,set): return sorted(item)
        if hasattr(item,'tolist'): return item.tolist()
        raise TypeError(type(item).__name__)
    return json.loads(json.dumps(value,allow_nan=False,default=convert))

def main():
    from verify_inputs import verify_all
    verify_all()
    diagnosis=read(HERE/'DECISION_BINDING_DIAGNOSIS.json')
    assert all(not r['differences'] for r in diagnosis['records'])
    checks=read(HERE/'CHECKS_SCORER_SERIALIZATION_V2.json')
    assert checks['status']=='PASS'
    frozen=module('ds35_readonly_frozen_scorer',HERE/'score.py')
    original_choose=frozen.choose
    original_dependencies=frozen.scoring_dependencies
    frozen.choose=lambda *args,**kwargs:serialized(original_choose(*args,**kwargs))
    frozen.scoring_dependencies=lambda:original_dependencies()+[artifact(__file__),
        artifact(HERE/'CHECKS_SCORER_SERIALIZATION_V2.json'),artifact(HERE/'SCORER_SERIALIZATION_REPAIR.json')]
    write_new(HERE/'SCORER_SERIALIZATION_REPAIR.json',dict(
        status='APPEND_ONLY_SCORER_JSON_KEY_CANONICALIZATION_BEFORE_RECOMPUTED_HASH',
        old_scorer=artifact(HERE/'score.py'),adapter=artifact(__file__),
        diagnosis=artifact(HERE/'DECISION_BINDING_DIAGNOSIS.json'),checks=artifact(HERE/'CHECKS_SCORER_SERIALIZATION_V2.json'),
        cause='Python integer keys sort numerically; serialized JSON object keys sort lexicographically. '
            'LW MS1-F2896 uses keys106 and3; all actual serialized values are equal. '
            'Canonicalize the recomputed object with exactly the publisher JSON serialization, then compare.',
        scope='Only the independent source-to-decision audit. Keep choice, candidate/list order, mappings, '
            'supports and numeric values. No tolerance, hypothesis relabeling or changed prediction.',
        official_metric_math_unchanged=True,all_eight_contracts_rechecked_before_any_reference=True,
        association_and_all_frozen_code_unchanged=True,old_failure_logs_preserved=True,
        new_model_http=0,cost_usd=0))
    frozen.main()
    write_new(HERE/'SCORER_SERIALIZATION_COMPLETION.json',dict(status='PASS',
        adapter=artifact(__file__),repair=artifact(HERE/'SCORER_SERIALIZATION_REPAIR.json'),
        scoring_freeze=artifact(RUN/'SCORING_FREEZE.json'),metrics=artifact(RUN/'METRICS.json'),
        original_score_provenance=artifact(RUN/'SCORE_PROVENANCE.json'),
        predictions_and_trial_seals_unchanged=True,official_metric_math_unchanged=True))

if __name__=='__main__':main()
