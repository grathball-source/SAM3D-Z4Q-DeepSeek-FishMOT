"""Append-only correction of a malformed copied reference digest, before scoring."""
from common import *
import ast
import evaluate
def main():
    evaluate.verify_all()
    source=OLD/'score.py';tree=ast.parse(source.read_text(encoding='utf-8'))
    pin=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='GT_SHA' for t in n.targets))
    assert len(pin)==64 and len(evaluate.GT_DEV_SHA)!=64
    assert sha(evaluate.GT_DEV)==pin
    write_new(HERE/'SCORING_FREEZE.json',dict(status='CORRECTED_REFERENCE_PIN_BEFORE_FIRST_SCORE',
        all_predictions_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),scoring_wrapper=artifact(__file__),
        unchanged_frozen_scorer=artifact(HERE/'evaluate.py'),authoritative_original_pin_source=artifact(source),
        old_malformed_pin=evaluate.GT_DEV_SHA,actual_original_reference_sha256=pin,
        correction='Only malformed digest string; original reference path/raster/protocol and ALL prediction/state bytes unchanged',
        no_prediction_or_parameter_edit=True,no_GT_used_for_input=True))
    evaluate.GT_DEV_SHA=pin
    evaluate.main()
if __name__=='__main__':main()
