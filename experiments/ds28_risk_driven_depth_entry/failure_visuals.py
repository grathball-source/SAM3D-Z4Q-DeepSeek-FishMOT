"""All old-reference wrong commits, selected only after the new predictions seal."""
from common import *
import visualize as v
import cv2
import numpy as np
import score

def main():
    score.verify_all();selected=[];facts={};transactions={};publications={}
    for name in SEGMENTS:
        public=RUN/name/'public'
        wrong=[a for a in read(public/'ACTION_AUDIT.json')['actions']
            if a['arm']=='Z4Q_FROZEN' and a['actual_reference_physical']=='WRONG']
        if not wrong:continue
        wanted={a['frame'] for a in wrong}
        checkrows={r['frame']:r for r in rows(public/'ORDER_CHECKS.jsonl.gz') if r['frame'] in wanted}
        for a in sorted(wrong,key=lambda a:(a['frame'],a['source'],a['target'])):
            r=checkrows[a['frame']];checks=r['checks']['DEPTH_RISK']
            matches=[(i,c) for i,c in enumerate(checks) if (c['origin_rule'],c['native_id'],c['public_id'])==(a['origin_rule'],a['source'],a['target'])]
            assert len(matches)==1,'An original wrong action has no true legal risk check'
            i,c=matches[0];comparisons=[x for x in c.get('comparisons',[]) if 'pre_pairs' in x]
            comp=next((x for x in comparisons if x['delta_cost']),comparisons[0] if comparisons else None)
            case=v._case(name,'DEPTH_RISK',r,c,i,comp,'ALL_ORIGINAL_WRONG_COMMITS_POSTSCORE_DIAGNOSTIC')
            case['postscore_original_action']=a;selected.append(case)
        for r in rows(public/'MEASUREMENTS.jsonl.gz'):
            f=r['measurement'];facts[name,r['arm'],f['fact_id'],digest(f)]=f
        for tx in rows(public/'TRANSACTIONS.jsonl.gz'):
            if tx['frame'] in wanted and tx['arm']=='DEPTH_RISK':transactions[name,tx['frame']]=tx
        display_frames={f for q in wanted for f in (max(1,q-2),q,min(SEGMENTS[name][1]-SEGMENTS[name][0]+1,q+2))}
        for p in rows(public/'predictions.jsonl.gz'):
            if p['frame'] in display_frames:publications[name,p['frame']]=p
    target=HERE/'private/failures';target.mkdir(parents=True,exist_ok=True)
    records=[];diag=HERE/'FAILURE_DIAGNOSTIC_ENDPOINTS.jsonl.gz'
    with gzip.open(diag,'xt',encoding='utf-8') as h:
        for case in selected:
            name,q=case['segment'],case['q'];tx=transactions[name,q];a=case['postscore_original_action']
            if case['comparison']:
                subset={k[1:]:f for k,f in facts.items() if k[0]==name}
                canvas,detail=v._render(case,subset)
            else:canvas,detail=v._render_diagnostic(case,tx,h)
            header=np.full((62,canvas.shape[1],3),255,'u1')
            label=f"POSTSCORE DIAGNOSIS: original {a['origin_rule']} n{a['source']} -> old{a['target']} is WRONG vs actual saved reference. New branch publishes the same mapping: no correction."
            assert tx['actual_published_mapping'][str(a['source'])]==a['target']
            v._text(header,[label],14,23,header.shape[1]-28,.5,22)
            canvas=np.concatenate((header,canvas),axis=0)
            path=target/f"{name}_F{q:05d}_{a['origin_rule']}_n{a['source']}_to_{a['target']}.png"
            assert not path.exists() and cv2.imwrite(str(path),canvas)
            timeline=[]
            for frame in (max(1,q-2),q,min(SEGMENTS[name][1]-SEGMENTS[name][0]+1,q+2)):
                p=publications[name,frame]
                timeline.append(dict(frame=frame,global_frame=p['global_frame'],variants=p['variants'],
                    display_scope='SEALED_PUBLISH_TIMELINE_ONLY; POST_Q_NOT_ASSOCIATION_INPUT'))
            records.append(dict(segment=name,q=q,original_action=a,actual_risk_check=case['check'],
                true_query_transaction_sha256=digest(tx),actual_published_mapping=tx['actual_published_mapping'],
                figure=artifact(path),display_header_extra_px=62,detail=detail,published_timeline=timeline,
                raw_depth_mask_only=True,GT_pixels=False,no_new_prediction_or_score=True))
    assert len(records)==17
    write_new(HERE/'FAILURE_VISUALS.json',dict(status='ALL_17_ORIGINAL_WRONG_ACTIONS_POSTSCORE_REAL_DEPTH_MASK_DIAGNOSIS',
        cases=records,diagnostic_endpoint_facts=artifact(diag),producer=artifact(__file__),
        case_selection_after_all_predictions_and_scoring=True,used_for_threshold_or_input_selection=False,
        private_pixels_excluded_from_Git=True,new_model_http=0,cost_usd=0))
    print('All17 wrong-action figures and actual publish timelines complete; no GT raster')

if __name__=='__main__':main()
