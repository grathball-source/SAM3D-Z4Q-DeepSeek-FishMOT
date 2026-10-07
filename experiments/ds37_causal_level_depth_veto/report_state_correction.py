"""Result-only wording correction; frozen inference and score stay unchanged."""
from common import *

review = read(HERE/'STATE_EFFECT_REVIEW.json')
assert review['status'] == 'PASS_ENGINE_STATE_PROPOSAL_COMMIT_AND_PUBLICATION_EFFECTS_SEPARATED'
path = HERE/'report.py'
source = path.read_text(encoding='utf-8')
assert sha(path) == read(HERE/'RUNTIME_FREEZE.json')['code'][str(path)]
replacements = {
    'NO_DEPTH_STATE_OR_METRIC_INCREMENT_STOP_FROZEN_VERSION':
        'NO_PUBLICATION_OR_METRIC_INCREMENT_STOP_FROZEN_VERSION',
    'write_new(HERE/\'RESULTS.json\',result)':
        "result['state_effect_review']=review\n    write_new(HERE/'RESULTS.json',result)",
    "'## main交付',":
        "'## 候选、状态与发布分层',\n        'STATE_EFFECT_REVIEW独立逐行回查了全部实际事务。零发布增量不代表完整engine状态不变；原engine的pending和诊断计数也属于状态。原合法边的真实删除、同前态状态SHA改变、未确认提议改变、已确认持久提交和发布分别计数。不能用零改帧推出零状态作用。详细真实数字和逐边出处见STATE_EFFECT_REVIEW与DEEP_REVIEW。',\n        '## main交付',",
}
for old, new in replacements.items():
    assert source.count(old) == 1, old
    source = source.replace(old, new)
write_new(HERE/'REPORT_WORDING_CORRECTION.json', dict(
    reason='Frozen automatic report status incorrectly equated zero publication changes with zero full engine-state changes',
    original_frozen_report_code=artifact(path), result_only_correction_code=artifact(__file__),
    exact_replacements=replacements, transformed_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
    state_review=artifact(HERE/'STATE_EFFECT_REVIEW.json'), inference_score_seals_unchanged=True,
    no_previous_report_or_result_overwrite=True, model_http=0, cost_usd=0))
scope = dict(__name__='ds37_postseal_corrected_report', __file__=str(Path(__file__).resolve()), review=review)
exec(compile(source, str(path)+':result_only_state_wording_correction', 'exec'), scope)
scope['main']()
