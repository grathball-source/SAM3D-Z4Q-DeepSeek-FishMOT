"""Small synthetic contract checks; no source dataset, GT, sensor or API reads."""
from common import *
import copy
import math
import numpy as np
import evidence as E


def fixture(post_end=14):
    pre, packets = {}, {}
    for role,n in (('A',1),('B',2)):
        pre[role]=dict(samples=[],anchor=dict(frame=10,native_id=n,canonical_id=n,mask=f'n:{n}'))
    def center(n,frame): return (12+frame if n in (1,10) else 60-frame, 24.)
    def extract(n,f):
        return dict(usable=True,frame=f,time=f/10.,native=n,fact_id=f'SYNTHETIC:n{n}:f{f}',
            certificate_fact_id=f'SYNTHETIC:cert:n{n}:f{f}',certificate_sha256='synthetic',
            z_mm=1000+f*.5 if n in (1,10) else 1200-f*.25,mad_mm=1.,scale_mm=15.,
            roi_binding=dict(synthetic=True),selected_source_index_binding=dict(synthetic=True),
            quality=dict(core_eligible_single=True,core_quality_usable=True,exclusive_native_sources=True,
                unverified_source_n=0,core_multilayer=False,whole_multilayer=False,
                independent_source_n=100,fraction_of_original_core=1.,physical_surface_identity='UNKNOWN'))
    post={10:[],20:[]}
    for f in list(range(1,11))+list(range(12,post_end+1)):
        ns=(1,2) if f<=10 else (10,20);obs=[];masks={};extracts={}
        for n in ns:
            x,y=center(n,f);box=[x-5,y-5,x+5,y+5]
            o=dict(id=n,mask=f'n:{n}',box=box,area=100,neighbors=[]);obs.append(o)
            m=np.zeros((80,80),bool);m[int(y-5):int(y+5),int(x-5):int(x+5)]=True;masks[n]=m
            extracts[n]=extract(n,f)
            if f<=10:
                pre['A' if n==1 else 'B']['samples'].append(dict(frame=f,time=f/10.,native=n,public=n,
                    version=[n,1,n,0],box=box,area=100,neighbors=[],observation_class='CLEAN_ACTUAL_BANK_ANCHOR'))
            else:
                post[n].append(dict(frame=f,time=f/10.,source=n,center=[x,y],bbox=box,area=100,
                    source_generation=1,public_epoch=None,observation_class='POST_UNASSIGNED'))
        global_frame=1000+f
        native=[dict(id=o['id'],mask=o['mask']) for o in obs]
        row=dict(frame=f,global_frame=global_frame,time=f/10.,observations=obs,native=native)
        assignment=dict(frame=f,global_frame_id=global_frame,time=f/10.,variants={'N0':native})
        packets[f]=dict(row=row,assignment=assignment,masks=masks,extracts=extracts,
            measured=dict(adaptive_full=dict(n=1000,median=1500.,mad=80.)),
            sensor=dict(binding=dict(global_frame=global_frame,time=f/10.,synthetic=True)))
    episode=dict(q=12,suspect_frame=11,member_sources=[1,2],public_ids=[1,2],post_roles=post)
    return episode,pre,packets


class Pair:
    """Known pixel translation mock, labelled synthetic and never a formal flow."""
    def __init__(self,a,b,packets,broken=False):
        self.delta=b-a;self.broken=broken
        self.numeric_summary=dict(schema='SYNTHETIC_ONLY',method='MOCK_NOT_FORMAL_DIS',rgb_status='AVAILABLE',
            previous_frame=packets[a]['row']['global_frame'],current_frame=packets[b]['row']['global_frame'],
            maximum_read_global_frame=packets[b]['row']['global_frame'],
            previous_source_binding=packets[a]['sensor']['binding'],current_source_binding=packets[b]['sensor']['binding'])
    def warp_forward(self,mask,quality=False):
        if quality and self.broken:return np.zeros_like(mask)
        xs=np.nonzero(mask)[1];direction=1 if len(xs) and xs.mean()<40 else -1
        return np.roll(mask,direction*self.delta,axis=1)
    def warp_backward(self,mask,quality=False):
        if quality and self.broken:return np.zeros_like(mask)
        xs=np.nonzero(mask)[1];direction=1 if len(xs) and xs.mean()<40 else -1
        return np.roll(mask,-direction*self.delta,axis=1)


def provider(packets, broken=None):
    return lambda a,b:Pair(a,b,packets,broken==(a,b))


def run():
    checks=[]
    def passed(name):checks.append(name)
    def rejected(name, action):
        try:action()
        except AssertionError:passed(name)
        else:raise AssertionError(name+' was accepted')
    e,pre,packets=fixture()
    baseline=E.choose(e,pre,packets,True,provider(packets))
    assert baseline['status']=='CHOOSE' and baseline['mapping']=={10:1,20:2}
    assert baseline['common_weights']==dict(motion=.25,contour=.25,depth=.25)
    assert sum(len(edge['contour_samples']) for edge in baseline['scores'][0]['edges'])==18
    assert all(not d['used_for_identity_score'] for d in baseline['post_backward_to_q'].values())
    passed('full_joint_three_by_three_symmetric_contours_and_depth_with_post_backtrace_diagnostic_only')
    reordered=copy.deepcopy(e);reordered['post_roles']=dict(reversed(list(e['post_roles'].items())))
    result=E.choose(reordered,pre,packets,True,provider(packets))
    assert result['choice']=='H2' and result['mapping']==baseline['mapping']
    passed('candidate_permutation_preserves_physical_mapping_not_unpermuted_H_label')
    noisy=[dict(frame=i+1,time=t,box=[x-1,0,x+1,2]) for i,(t,x) in enumerate(((0.,0.),(.1,3.),(.4,6.),(1.,10.)))]
    fitted=E.fit(noisy);times=[s['time'] for s in noisy];xs=[E._center(s)[0] for s in noisy]
    mt=sum(times)/4;mx=sum(xs)/4;expected=sum((t-mt)*(x-mx) for t,x in zip(times,xs))/sum((t-mt)**2 for t in times)
    assert math.isclose(fitted['velocity_px_s'][0],expected,abs_tol=1e-12)
    assert not math.isclose(expected,10.) and fitted['residual_rms_px']>0
    passed('real_time_OLS_uses_all_points_and_reports_residual_not_first_last_secant')
    short=copy.deepcopy(pre);short['A']['samples']=short['A']['samples'][-2:]
    result=E.choose(e,short,packets,False,provider(packets))
    assert result['pre_fits']['A']['velocity_px_s'] is None and result['common_weights']['motion']==result['common_weights']['contour']==0.
    passed('two_point_pre_retains_last_position_and_unknown_motion_common_contour_off')
    empty=copy.deepcopy(pre);empty['A']['samples']=[]
    assert E.choose(e,empty,packets,True)['choice']=='DEFER'
    passed('missing_pre_DEFER_preserved')
    bad=copy.deepcopy(packets);bad[8]['extracts'][1]['quality'].pop('whole_multilayer')
    result=E.choose(e,pre,bad,True,provider(bad))
    rgb=E.choose(e,pre,bad,False,provider(bad))
    assert result['common_weights']['depth']==0. and result['scores']==rgb['scores']
    forecast=result['scores'][0]['edges'][0]['depth_rows'][0]['detail']['forecasts'][1]
    assert forecast['samples']==10 and forecast['sample_frames']==list(range(1,11)) and not forecast['usable']
    passed('middle_missing_pre_depth_retained_no_filter_stitch_entire_component_shared_null')
    bad=copy.deepcopy(packets);bad[12]['extracts'][20]['quality']['whole_multilayer']=True
    result=E.choose(e,pre,bad,True,provider(bad));rgb=E.choose(e,pre,bad,False,provider(bad))
    assert result['common_weights']['depth']==0. and result['scores']==rgb['scores']
    passed('one_bad_post_endpoint_depth_disables_all_edges_no_missing_candidate_discount')
    result=E.choose(e,pre,packets,False,provider(packets,broken=(8,12)))
    assert result['common_weights']['contour']==0.
    passed('one_unreliable_cross_endpoint_contour_disables_modality_for_entire_joint_matrix')
    extra=copy.deepcopy(packets);extra[99]=dict(masks={'future':'never_read'})
    extra_e=copy.deepcopy(e)
    for n in extra_e['post_roles']:extra_e['post_roles'][n].append(dict(frame=99,never_read=True))
    assert E.choose(extra_e,pre,extra,True,provider(extra))==baseline
    passed('extra_q_future_packets_and_later_post_samples_do_not_change_fixed_inputs')
    future=copy.deepcopy(e)
    for n in future['post_roles']:future['post_roles'][n][1]['frame']=43
    rejected('selected_post_after_q_plus_30_rejected',lambda:E.choose(future,pre,packets,True))
    risk_e,risk_pre,risk_packets=fixture(post_end=15)
    for o in risk_packets[12]['row']['observations']:o['neighbors']=[999]
    risk_e['confirmed_post_roles']={n:values[1:4] for n,values in risk_e['post_roles'].items()}
    result=E.choose(risk_e,risk_pre,risk_packets,True,provider(risk_packets))
    assert result['post_frames']=={'10':[13,14,15],'20':[13,14,15]} and result['q']==12 and result['causal_max_frame']==15
    passed('first_ready_three_raw_clean_post_after_risky_q_keeps_q_and_anonymous_risk')
    alias_e=copy.deepcopy(e);alias_e['member_sources']=[101,202]
    result=E.choose(alias_e,pre,packets,True,provider(packets))
    assert result['mapping']==baseline['mapping'] and result['actual_reference_anchors']['A']['native_id']==1
    passed('historical_exact_bank_anchor_native_different_from_current_member_not_falsely_stitched')
    changed=copy.deepcopy(risk_e)
    for values in changed['confirmed_post_roles'].values():
        for s in values:s['source_generation']=2
    assert E.choose(changed,risk_pre,risk_packets,True)['reason']=='POST_SOURCE_GENERATION_CHANGED_SINCE_FIRST_SPLIT_Q'
    passed('post_source_generation_break_since_q_DEFER_not_crash_or_authentication')
    wrong=copy.deepcopy(packets);wrong[12]['extracts'][10]['time']=9.
    rejected('wrong_or_future_depth_fact_time_rejected',lambda:E.choose(e,pre,wrong,True))
    def future_provider(a,b):
        pair=Pair(a,b,packets);pair.numeric_summary['maximum_read_global_frame']+=1;return pair
    rejected('motion_provider_future_source_binding_rejected',lambda:E.choose(e,pre,packets,True,future_provider))
    print(json.dumps(dict(status='PASS_SCOPED_SYNTHETIC_EVIDENCE_CONTRACT',checks=checks,
        actual_active_CONFIG=CFG,evidence=artifact(HERE/'evidence.py'),tests=artifact(__file__),
        source_dataset_reads=0,GT_reads=0,new_model_http=0,cost_usd=0,synthetic_checks_not_performance_evidence=True),indent=2))


if __name__=='__main__':run()
