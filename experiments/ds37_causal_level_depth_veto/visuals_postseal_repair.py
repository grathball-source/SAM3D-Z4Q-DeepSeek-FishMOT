"""Allow random anchor reads only in the sealed, result-only picture process."""
from common import *
from datetime import datetime, timezone

from score import verify_all
verify_all()
assert read(RUN/'METRICS.json')['status'] == 'SCORED_AFTER_ALL_SEALS'
assert read(RUN/'MECHANISM_AUDIT.json')['status'].endswith('RECOMPUTED')
original = HERE/'visuals.py'
assert sha(original) == read(HERE/'RUNTIME_FREEZE.json')['code'][str(original)]
attempts = [r for r in rows(HERE/'EXECUTION_LOG.jsonl')
            if Path(r['command'][1]).name == 'visuals.py' and r['exit_code'] != 0]
assert len(attempts) == 1
for key in ('stdout', 'stderr'):
    verify_item(attempts[0][key])
error = Path(attempts[0]['stderr']['path']).read_text(encoding='utf-8')
assert 'g>=self.previous_frame' in error
before = {str(RUN/p): sha(RUN/p) for p in ('METRICS.json', 'MECHANISM_AUDIT.json', 'ALL_PREDICTIONS_SEALED.json')}
source = original.read_text(encoding='utf-8')
old = "d,ix,nat,b=sensor(g,pr['time'])"
new = "sensor.previous_frame=None;d,ix,nat,b=sensor(g,pr['time'])"
assert source.count(old) == 1
source = source.replace(old, new)
archived = HERE/'visual_attempt_failure_v1'
write_new(archived/'PRESERVATION.json', dict(
    reason='Postseal anchor/decision picture order was rejected by the sequential prediction raw-depth adapter',
    actual_failed_execution=attempts[0], original_frozen_render_code=artifact(original),
    retained_public_files=[artifact(p) for p in (archived/'visuals').glob('*')],
    retained_private_files=[artifact(p) for p in (HERE/'private/visual_attempt_failure_v1').glob('*')],
    private_pixels_excluded=True, predictions_and_score_already_sealed=True))
write_new(HERE/'POSTSEAL_RENDER_REPAIR.json', dict(
    original_frozen_code=artifact(original), result_only_code=artifact(__file__),
    exact_replacement={old:new}, transformed_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
    pre_render_pins=before, attempt_preservation=artifact(archived/'PRESERVATION.json'),
    random_reads_only_after_all_prediction_seals_and_score=True,
    inference_adapter_and_future_frame_policy_unchanged=True, model_http=0, cost_usd=0))
scope = dict(__name__='ds37_postseal_random_access_render', __file__=str(Path(__file__).resolve()))
exec(compile(source, str(original)+':postseal_only_random_access', 'exec'), scope)
scope['main']()
verify_all()
assert all(sha(path) == value for path, value in before.items())
assert read(HERE/'PRIVATE_VISUALS.json')['pixels_private']
assert read(HERE/'PUBLIC_VISUALS.json')['private_cases'] == len(read(HERE/'VISUAL_CASES.json')['cases'])
write_new(RUN/'COMPLETE.json', dict(
    status='FULL_REPLAY_SCORE_MECHANISM_AND_VISUALS_COMPLETE_WITH_POSTSEAL_RENDER_REPAIR', frames=20098,
    completed_utc=datetime.now(timezone.utc).isoformat(), actual_failed_render=attempts[0],
    completed_render_code=artifact(__file__), repair=artifact(HERE/'POSTSEAL_RENDER_REPAIR.json'),
    prediction_score_and_mechanism_bytes_preserved=True, model_http=0, cost_usd=0))
print('POSTSEAL_RENDER_REPAIR_COMPLETE', flush=True)
