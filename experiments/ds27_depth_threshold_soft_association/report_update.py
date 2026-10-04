"""Append a reporting correction; frozen science and v1 report stay unchanged."""
from common import *

previous=read(HERE/'REPORT_PROVENANCE.json')
verify_item(previous['report'])
old=(HERE/'FINAL_REVIEW.md').read_bytes()
text=old.decode('utf-8')
assert 'birth真实竞争也没有覆盖' in text
text=text.replace('birth真实竞争也没有覆盖','birth实际有3次近竞争候选检查（均在LW、当前source风险），但没有进入正式pre/q测量')
text += ('\n## 报告v2纠正与实际阶段覆盖\n\n'
    '第一次报告、其producer和provenance原件保留。封存检查实际每策略495次：D1_DELAYED492、BIRTH_REFINE3；'
    '预检从旧决策后trace估算birth0不等于真实入矩阵前覆盖，不能当正式计数。实际birth3次均CURRENT_SOURCE_RISK，'
    '因此可以说birth测量输入覆盖0，不能说birth候选检查0。正式source/成本/状态/预测/评分未改变。'
    '本v2只更正文案，全文指标、688正式事实、41完整比较及其zero-cost原因沿用封存证据。\n')
with (HERE/'FINAL_REVIEW_V2.md').open('x',encoding='utf-8') as h:h.write(text)
assert (HERE/'FINAL_REVIEW.md').read_bytes()==old
write_new(HERE/'REPORT_PROVENANCE_V2.json',dict(producer=artifact(__file__),previous=artifact(HERE/'REPORT_PROVENANCE.json'),
    old_report=artifact(HERE/'FINAL_REVIEW.md'),report=artifact(HERE/'FINAL_REVIEW_V2.md'),results=artifact(HERE/'RESULTS.json'),
    metrics=artifact(RUN/'METRICS.json'),qa=artifact(HERE/'POSTSEAL_QA.json'),visuals=artifact(HERE/'PRIVATE_VISUALS_V2.json'),
    reason='Actual birth candidate-check coverage3 differs from preflight estimate0; its formal measurement-input coverage remains0.',
    scientific_predictions_scoring_thresholds_unchanged=True,old_report_bytes_preserved=True,new_model_http=0,cost_usd=0))
print('v2 report correction appended; all science/old report unchanged')
