"""Add the user's later threshold guidance without rewriting sealed evidence."""
from common import *
from datetime import datetime,timezone

check_freeze(); original=(HERE/'FINAL_REVIEW.md').read_text(encoding='utf-8')
old=read(HERE/'REPORT_PROVENANCE.json');verify_item(old['report'])
assert '## 唯一下一步' in original
prefix='''> 最新用户指示已纳入：必要时可以修改门槛。旧冻结结果保留为对照，下一轮允许有依据的门槛/尺度消融；不把固定本轮参数当成永久限制。

'''
before,_=original.rsplit('## 唯一下一步',1)
text=prefix+before+'## 唯一下一步（按最新用户指示更新）\n\n'+(HERE/'NEXT_STEP_PLAN_V2.md').read_text(encoding='utf-8')
with (HERE/'FINAL_REVIEW_V2.md').open('x',encoding='utf-8',newline='\n') as f:f.write(text)
write_new(HERE/'NEXT_STEP_SELECTION_V2.json',dict(status='PLANNED_NOT_STARTED',
    title='允许门槛修正的深度置信消融与完整回放',supersedes_plan_only=artifact(HERE/'NEXT_STEP_PLAN.md'),
    human_instruction='必要的时候要更改门槛，不能一条道走到黑',
    revised_plan=artifact(HERE/'NEXT_STEP_PLAN_V2.md'),old_results_unchanged=True,
    no_new_tracking_or_threshold_trial_started=True,new_model_http=0,cost_usd=0))
write_new(HERE/'REPORT_PROVENANCE_V2.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),
    code=artifact(Path(__file__)),original_report=artifact(HERE/'FINAL_REVIEW.md'),
    original_provenance=artifact(HERE/'REPORT_PROVENANCE.json'),
    new_plan=artifact(HERE/'NEXT_STEP_PLAN_V2.md'),report=artifact(HERE/'FINAL_REVIEW_V2.md'),
    update='PLAN_ONLY_USER_STEERING; ALL_SEALED_RESULTS_AND_NUMERIC_FINDINGS_UNCHANGED',new_model_http=0,cost_usd=0))
print('Later user threshold guidance incorporated; old frozen results/report preserved')
