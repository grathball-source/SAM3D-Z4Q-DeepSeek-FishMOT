"""Result-only ordinary-module render with reversible random raw-depth reads."""
from common import *
from datetime import datetime, timezone
from score import verify_all
import traceback
import visuals

verify_all()
assert read(RUN/'METRICS.json')['status'] == 'SCORED_AFTER_ALL_SEALS'
assert sha(HERE/'visuals.py') == read(HERE/'RUNTIME_FREEZE.json')['code'][str(HERE/'visuals.py')]
attempts = [r for r in rows(HERE/'EXECUTION_LOG.jsonl')
            if Path(r['command'][1]).name in ('visuals.py','visuals_postseal_repair.py') and r['exit_code'] != 0]
assert len(attempts) == 2
pins = {str(RUN/p): sha(RUN/p) for p in ('METRICS.json','MECHANISM_AUDIT.json','ALL_PREDICTIONS_SEALED.json')}
original_call = visuals.SOURCE.RawDepth.__call__

def postseal_read(sensor, frame, now):
    sensor.previous_frame = None
    return original_call(sensor, frame, now)

write_new(HERE/'POSTSEAL_RENDER_REPAIR_V2.json', dict(
    original_frozen_render=artifact(HERE/'visuals.py'), actual_repair=artifact(__file__),
    actual_failed_executions=attempts, before=pins, random_reads_only_after_all_seals_and_score=True,
    runtime_method_restored_in_finally=True, original_inference_source_bytes_unchanged=True,
    retained_second_attempt_files=[artifact(p) for p in (HERE/'visual_attempt_failure_v2').rglob('*') if p.is_file()],
    retained_second_private_files=[artifact(p) for p in (HERE/'private/visual_attempt_failure_v2').rglob('*') if p.is_file()],
    model_http=0,cost_usd=0))
try:
    visuals.SOURCE.RawDepth.__call__ = postseal_read
    visuals.main()
except BaseException as error:
    write_new(HERE/'POSTSEAL_RENDER_ERROR_V2.json', dict(
        exception_type=type(error).__name__, message=str(error), traceback=traceback.format_exc()))
    raise
finally:
    visuals.SOURCE.RawDepth.__call__ = original_call
verify_all()
assert all(sha(path) == value for path, value in pins.items())
assert read(HERE/'PUBLIC_VISUALS.json')['private_cases'] == len(read(HERE/'VISUAL_CASES.json')['cases'])
write_new(RUN/'COMPLETE.json', dict(
    status='FULL_REPLAY_SCORE_MECHANISM_AND_VISUALS_COMPLETE_WITH_POSTSEAL_RENDER_REPAIR', frames=20098,
    completed_utc=datetime.now(timezone.utc).isoformat(), actual_failed_renders=attempts,
    completed_render_code=artifact(__file__), repair=artifact(HERE/'POSTSEAL_RENDER_REPAIR_V2.json'),
    prediction_score_and_mechanism_bytes_preserved=True, model_http=0,cost_usd=0))
print('POSTSEAL_RENDER_REPAIR_COMPLETE',flush=True)
