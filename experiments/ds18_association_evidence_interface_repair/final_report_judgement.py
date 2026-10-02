"""Postscore reporting-only goal judgement; no frozen scientific artifact edits."""
from common import HERE, RUN, read, artifact
import json


def main():
    assert read(RUN / 'SCORE_PROVENANCE.json')['reference_opened_after_all_seals']
    for filename in ('SUMMARY.json', 'MAIN_JUDGEMENT.json'):
        path = HERE / filename
        data = read(path)
        data['idf1_only_same_interface_pattern'] = data['status']
        data['status'] = 'COMPLETE_TRIAL_GOAL_NOT_ACHIEVED'
        data['engineering_source_checks_passed'] = True
        data['shared_state_policy_has_measured_failure'] = True
        data['depth_robust_gain_goal_achieved'] = False
        data['final_interpretation'] = artifact(HERE / 'CAUSAL_SYNTHESIS.md')
        data['sole_next_step'] = artifact(HERE / 'NEXT_STEP_PLAN.md')
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    path = HERE / 'FINAL_REVIEW.md'
    body = path.read_text(encoding='utf-8')
    body = body.replace('主判定：`COMPLETE_TRIAL_CONDITIONAL_DEPTH_GAIN_WITH_LOSSES`。',
                        '主判定：`COMPLETE_TRIAL_GOAL_NOT_ACHIEVED`。')
    note = ('\n工程来源检查通过，共用身份恢复政策仍有实测缺陷；深度策略没有达到稳定超过同源原生与原Z4Q的目标。'
            '初始报告程序的CONDITIONAL模式仅代表dev IDF1较同接口微增0.031787且其他段下降，不是任务成功。'
            '完整根因、例外与唯一下一步见 [CAUSAL_SYNTHESIS.md](CAUSAL_SYNTHESIS.md) 和 [NEXT_STEP_PLAN.md](NEXT_STEP_PLAN.md)。\n')
    offset = body.index('\n## 本轮修复')
    path.write_text(body[:offset] + note + body[offset:], encoding='utf-8')
    print('FINAL_REPORT_GOAL_NOT_ACHIEVED; frozen science/predictions/score unchanged')


if __name__ == '__main__':
    main()
