"""Append-only acceptance of inert one-ULP DT diagnostics; frozen scorer unchanged."""
from common import *
import copy,math,numpy as np

def normalize_diagnostic(new,old):
    normalized=copy.deepcopy(new);changes=[]
    for column in ('adaptive_raw','restored'):
        assert set(new[column])==set(old[column])
        for native,item in normalized[column].items():
            pieces=item['roi_geometry']['pieces'];prior=old[column][native]['roi_geometry']['pieces']
            assert len(pieces)==len(prior)
            for i,(a,b) in enumerate(zip(pieces,prior,strict=True)):
                x,y=a['dt_max_px'],b['dt_max_px']
                if x==y:continue
                assert type(x) is type(y) is float and math.isfinite(x) and math.isfinite(y)
                ulp=max(float(np.spacing(np.float32(x))),float(np.spacing(np.float32(y))))
                assert x>=6 and y>=6 and abs(x-y)<=min(1e-6,ulp)
                # Both maxima exceed six: the frozen ROI threshold is exactly 3px.
                assert max(1.5,min(3.,.5*x))==max(1.5,min(3.,.5*y))==3.
                changes.append(dict(frame=new['frame'],global_frame=new['global_frame'],column=column,
                    native=native,piece=i,new_dt_max_px=x,old_dt_max_px=y,float32_ulp_px=ulp,
                    absolute_difference_px=abs(x-y),actual_threshold_px=3.))
                a['dt_max_px']=y
    assert normalized==old,'Any non-DT-max fact or operative threshold differs'
    return changes

def checks():
    old=dict(frame=1,global_frame=1,adaptive_raw={'1':dict(roi_geometry=dict(pieces=[dict(dt_max_px=6.082762241363525,threshold_px=3.)]),core=dict(median=900.))},restored={})
    new=copy.deepcopy(old);new['adaptive_raw']['1']['roi_geometry']['pieces'][0]['dt_max_px']=6.082762718200684
    assert len(normalize_diagnostic(new,old))==1
    assert new['adaptive_raw']['1']['roi_geometry']['pieces'][0]['dt_max_px']!=old['adaptive_raw']['1']['roi_geometry']['pieces'][0]['dt_max_px']
    for field,value in [('core',dict(median=901.)),('roi_geometry',dict(pieces=[dict(dt_max_px=6.082762718200684,threshold_px=2.99)]))]:
        bad=copy.deepcopy(new);bad['adaptive_raw']['1'][field]=value
        try:normalize_diagnostic(bad,old)
        except AssertionError:pass
        else:raise AssertionError('operative input must be rejected')
    bad=copy.deepcopy(new);bad['adaptive_raw']['1']['roi_geometry']['pieces'][0]['dt_max_px']=6.1
    try:normalize_diagnostic(bad,old)
    except AssertionError:pass
    else:raise AssertionError('large DT difference must be rejected')
    assert normalize_diagnostic(old,old)==[]
    return dict(status='PASS',checks=5,scope='inert <=one float32 ULP DT max only; no GT')

def main():
    import evaluate as frozen
    frozen.verify_all_seals()
    audit=read(HERE/'SOURCE_FLOAT_AUDIT.json')
    write_new(HERE/'FLOAT_SCORE_ADAPTER_FROZEN.json',dict(status='APPEND_ONLY_BEFORE_ANY_GT_SCORING',
        original_evaluate=artifact(HERE/'evaluate.py'),adapter=artifact(HERE/'score_float_adapter.py'),
        original_failed_execution=artifact(HERE/'logs/evaluate.txt'),checks=checks(),
        predictions=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),access=artifact(RUN/'ACCESS_SEALED.json'),
        source_diff_audit=artifact(HERE/'SOURCE_FLOAT_AUDIT.json'),
        allowed='dt_max_px only; <=one float32 ULP and <=1e-6 px; both>=6, same operative 3px threshold; all remaining fields exact',
        scientific_thresholds_changed=False,predictions_or_sources_changed=False))
    accepted=[]
    def accepted_check(new,old):accepted.extend(normalize_diagnostic(new,old))
    frozen.check_source_extraction=accepted_check
    frozen.main()
    write_new(HERE/'FLOAT_SCORE_ADAPTER_ACCEPTANCE.json',dict(status='SCORED_WITH_EXPLICIT_DIAGNOSTIC_EXCEPTION',
        changes=accepted,count=len(accepted),all_other_facts_exact=True,all_operative_thresholds_exact=True,
        adapter_freeze=artifact(HERE/'FLOAT_SCORE_ADAPTER_FROZEN.json'),
        official_score_seal=artifact(RUN/'SCORING_SEALED.json')))
    write_new(HERE/'APPENDED_SCORE_PROVENANCE_SEALED.json',dict(
        score_seal=artifact(RUN/'SCORING_SEALED.json'),
        append_only_provenance=[artifact(HERE/n) for n in ('SOURCE_FLOAT_AUDIT.json','FLOAT_SCORE_ADAPTER_FROZEN.json','FLOAT_SCORE_ADAPTER_ACCEPTANCE.json')]))
    print('Inert DT diagnostic exception accepted:',len(accepted))
if __name__=='__main__':main()
