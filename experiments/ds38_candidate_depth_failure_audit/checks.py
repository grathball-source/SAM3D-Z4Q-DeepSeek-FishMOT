"""Source ownership, missing populations, causality, and exact real replay checks."""
from common import *
from audit import distribution_compare,requests_for,passive_preview,replay
import numpy as np

def run():
    results=[]
    # Duplicate projection pixels are one sensor sample; another mask's sample is excluded.
    roi=np.ones((2,3),bool);index=np.array([[0,0,1],[2,3,3]],dtype='i8')
    pos,excluded=MEASUREMENT._selected(roi,roi,index,np.array([2],dtype='i8'))
    assert set(index.ravel()[pos])=={0,1,3} and len(pos)==3
    results.append('INDEPENDENT_SENSOR_DEDUP_AND_OTHER_MASK_EXCLUSION')
    a=np.array([100.,100.,200.,200.]);b=np.array([100.,200.])
    identical=distribution_compare(a,b)
    assert identical['wasserstein_mm']==0 and identical['auc_nearer_a']==.5
    assert distribution_compare(a,b+50)['wasserstein_mm']==50
    assert distribution_compare(a[::-1],b)['wasserstein_mm']==0
    assert distribution_compare([],b)['wasserstein_mm'] is None
    # Both layers remain present. No minimum-distance peak selects the identity.
    assert distribution_compare(a,[100.,100.])['wasserstein_mm']==50
    results.append('TIES_PERMUTATION_MISSING_AND_MIXTURE_FULL_DISTRIBUTION')
    sample=dict(action=dict(segment='feeding_000000_000199',frame=10,native=1,actual_reference=dict(frame=8,native_id=3)),
        phase_snapshot=dict(bank=[dict(anchor=dict(frame=7,native_id=2),view_anchors={})]),original_depth_queries=[])
    r=requests_for([sample]);assert r['feeding_000000_000199'][7]=={2}
    sample['phase_snapshot']['bank'][0]['anchor']['frame']=11
    try: requests_for([sample])
    except AssertionError: pass
    else: raise AssertionError('future anchor accepted')
    results.append('EXACT_REFERENCE_BINDING_AND_Q_PLUS_ONE_REJECTED')
    bridge=Bridge(read(CONFIG_PATH));before=digest(vars(bridge.engine));previous=sys.gettrace()
    def failing(*args): raise RuntimeError('synthetic preview failure')
    bridge.preview=failing
    try: passive_preview(bridge,dict(frame=1,time=0,observations=[]),{},True)
    except RuntimeError: pass
    else: raise AssertionError('preview failure not surfaced')
    assert digest(vars(bridge.engine))==before and sys.gettrace() is previous
    results.append('EXCEPTION_RESTORES_OBSERVER_AND_AUTHORITATIVE_STATE')
    output=f'slice_f159_checks_{len(list(HERE.glob("slice_f159_checks_*")))+1}'
    replay(output,only='feeding_000000_000199',stop=160,require_freeze=False)
    c=list(rows(HERE/output/'CANDIDATES.jsonl.gz'));assert len(c)==1
    assert c[0]['action']['global_frame']==159 and c[0]['phase_snapshot']['matrix'] is not None
    assert c[0]['state_trace_mapping_version_exact']
    results.append('REAL_F159_160_FRAMES_EXACT_FULL_STATE_TRACE_MAPPING_VERSION')
    save('CHECKS.json',dict(status='PASS',checks=results,real_slice_seal=artifact(HERE/output/'REPLAY_SEALED.json'),
        synthetic_checks_are_not_research_results=True,model_http=0,cost_usd=0))
    print('CHECKS PASS',len(results),flush=True)

if __name__=='__main__': run()
