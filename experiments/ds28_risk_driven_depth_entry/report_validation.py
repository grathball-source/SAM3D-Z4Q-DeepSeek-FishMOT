"""Read final report numbers from actual metrics and pinned postseal evidence."""
from common import *
import math

m=read(RUN/'METRICS.json');a=read(HERE/'MECHANISM_ANALYSIS.json');qa=read(HERE/'POSTSEAL_QA.json')
text=(HERE/'FINAL_REVIEW.md').read_text(encoding='utf-8');fields=('IDF1','HOTA','AssA','IDSW','FP','FN')
tables=[line.split('|')[1:-1] for line in text.splitlines() if line.startswith('|')]
metric_rows=[r for r in tables if len(r)==8 and r[1] in ARMS]
assert len(metric_rows)==36
for r in metric_rows:
    name,arm,*values=r
    expected=m['feeding_pooled']['metrics'][arm] if name=='Feeding pooled 1471' else m['segments'][name]['metrics'][arm]
    assert all(math.isclose(float(value),expected[field],rel_tol=0,abs_tol=5.1e-7) for field,value in zip(fields,values))
assert a['counts']['DEPTH_NEAR']['checks']==495 and a['counts']['DEPTH_RISK']['checks']==1552
assert a['counts']['DEPTH_NEAR']['facts']==172 and a['counts']['DEPTH_RISK']['facts']==420
assert a['comparison_counts']['DEPTH_NEAR']['complete_comparisons']==41 and a['comparison_counts']['DEPTH_RISK']['complete_comparisons']==133
assert a['original_action_coverage']['DEPTH_RISK']['WRONG']==dict(original_actions=17,checked=17,full_pre_q=0,nonzero=0)
for arm in ARMS[1:]:
    assert qa['totals_by_arm'][arm]['proposals_accepted']==90
    assert not qa['totals_by_arm'][arm].get('changed_publication_frames',0)
for arm in ARMS[2:]:
    assert qa['totals_by_arm'][arm]['checks']==a['counts'][arm]['checks']
    assert qa['totals_by_arm'][arm].get('soft_cost_updates',0)==a['counts'][arm].get('nonzero_cost_edges',0)
for x in rows(HERE/'EXECUTION_LOG.jsonl'):
    verify_item(x['stdout']);verify_item(x['stderr'])
for pin in read(HERE/'TECHNICAL_RECOVERY.json')['completed_seven_seals_preserved'].values():verify_item(pin)
for p,pin in read(HERE/'RUNTIME_FREEZE.json')['code'].items():assert sha(p)==pin
write_new(HERE/'REPORT_VALIDATION.json',dict(status='PASS_REPORT_NUMBERS_SEALS_AND_EXECUTION_RECORDS',metric_rows_verified=36,
    report=artifact(HERE/'FINAL_REVIEW.md'),metrics=artifact(RUN/'METRICS.json'),analysis=artifact(HERE/'MECHANISM_ANALYSIS.json'),
    original_7_seals_and_all_frozen_code_unchanged=True,source_and_state_no_GT_audit=artifact(HERE/'POSTSEAL_QA.json'),
    actual_visual_inspection=artifact(HERE/'VISUAL_ACCEPTANCE.json'),not_a_second_independent_expert_review=True,
    new_model_http=0,cost_usd=0))
print('Report36 numeric rows, full actual source/matrix/publication QA and frozen code/logs PASS')
