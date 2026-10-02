"""Actual full-run branch action differences; no new prediction or counterfactual."""
from common import *
from collections import Counter

def key(x):return (x['frame'],x['source'],x['target'],x['origin_rule'])
def main():
    assert read(RUN/'SCORE_PROVENANCE.json')['reference_opened_after_all_seals']
    result={}
    for name in SEGMENTS:
        public=RUN/name/'public';auto=read(public/'AUTOMATIC_RECONNECT_AUDIT.json')['arms']
        control={key(x):x for x in auto['ACTIVITY_ORDER']};mixed={key(x):x for x in auto['MIXED_ORDER']}
        need={x[0] for x in set(control)^set(mixed)}
        cert={x['frame']:x for x in rows(public/'MIXED_DEPTH.jsonl.gz') if x['frame'] in need}
        tx={(x['arm'],x['frame']):x for x in rows(public/'TRANSACTIONS.jsonl.gz') if x['frame'] in need and x['arm'] in ('ACTIVITY_ORDER','MIXED_ORDER')}
        removed=[];added=[]
        for keys,source,out in ((set(control)-set(mixed),control,removed),(set(mixed)-set(control),mixed,added)):
            for k in sorted(keys):
                frame,native,target,origin=k;c=cert[frame]['objects'].get(str(native))
                out.append(dict(action=source[k],current_measurement=c,actual_control_state=tx.get(('ACTIVITY_ORDER',frame)),actual_mixed_state=tx.get(('MIXED_ORDER',frame)),attribution='CONDITIONAL_OWN_STATE_PATH_DIFFERENCE; NOT_AN_ISOLATED_EDGE_COUNTERFACTUAL',current_depth_rejected_by_guard={v:not c[v]['eligible_single'] for v in ('whole','core')} if c else None))
        unchanged=sorted(set(control)&set(mixed))
        result[name]=dict(removed=removed,added=added,preserved=unchanged,
            removed_physical_counts=dict(Counter(x['action']['physical'] for x in removed)),added_physical_counts=dict(Counter(x['action']['physical'] for x in added)),
            sources=[artifact(public/'AUTOMATIC_RECONNECT_AUDIT.json'),artifact(public/'MIXED_DEPTH.jsonl.gz'),artifact(public/'TRANSACTIONS.jsonl.gz')])
    write_new(HERE/'ACTION_DEPTH_REVIEW.json',dict(status='POSTSEAL_ACTUAL_BRANCH_ACTION_REVIEW',segments=result,no_new_predictions=True,no_isolated_counterfactual_claim=True,model_http=0,cost_usd=0))
    lines=['# DS17实际自动身份动作与测量审计','','比较ACTIVITY_ORDER与MIXED_ORDER完整独立状态，当前测量保持原源。差异包含累积状态影响，不能把每个消失动作都归因于当前一条边。','','|片段|消失动作|正确|错误|不可评分|新增动作|新增物理判断|','|---|---:|---:|---:|---:|---:|---|']
    for name,r in result.items():
        counts=r['removed_physical_counts'];lines.append(f"|{name}|{len(r['removed'])}|{counts.get('CORRECT',0)}|{counts.get('WRONG',0)}|{counts.get('UNSCORABLE',0)}|{len(r['added'])}|{r['added_physical_counts']}|")
    lines+=['','每项包含实际控制/新分支trace、发布映射、参考anchor、当前whole/core完整层及质量原因，见JSON。缺测、不确定、背景兼容和物理不可评分均保留；UNKNOWN不等于两鱼认证。']
    (HERE/'ACTION_DEPTH_REVIEW.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('ACTUAL_ACTION_DEPTH_REVIEW_COMPLETE')
if __name__=='__main__':main()
