"""Reproduction entry in an empty result copy, with authoritative reference pins."""
from common import *
import ast
import evaluate
import finish_scoring
def main():
    assert not (RUN/'METRICS.json').exists(),'Never rescore/overwrite this sealed completed trial'
    evaluate.verify_all()
    tree=ast.parse((OLD/'score.py').read_text(encoding='utf-8'))
    pin=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='GT_SHA' for t in n.targets))
    assert len(pin)==64 and sha(evaluate.GT_DEV)==pin
    if not (HERE/'SCORING_FREEZE.json').exists():
        write_new(HERE/'SCORING_FREEZE.json',dict(status='AUTHORITATIVE_REFERENCE_PIN_BEFORE_SCORE',
            prediction_all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),source=artifact(OLD/'score.py'),
            actual_original_reference_sha256=pin,canonical_scoring_entry=artifact(__file__),no_prediction_or_parameter_edit=True))
    evaluate.GT_DEV_SHA=pin
    finish_scoring.main()
if __name__=='__main__':main()
