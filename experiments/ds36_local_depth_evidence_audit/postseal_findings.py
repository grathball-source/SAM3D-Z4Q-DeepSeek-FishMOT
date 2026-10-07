"""Descriptive calculations on sealed results; no new forecast or tracker run."""
from common import *
from report import stats
from audit import key
from datetime import datetime, timezone
import math


def main():
    verify_freeze()
    assert read(HERE/'INDEPENDENT_REVIEW.json')['status']=='PASS'
    result=read(HERE/'RESULTS.json')
    for pin in read(HERE/'FEATURES_SEALED.json')['files']:verify_item(pin)
    grouped={}
    for grade in ('CORRECT','WRONG','UNSCORABLE'):
        actions=[a for a in result['actions'] if a['physical']==grade]
        supported=[a for a in actions if a['current_extract_usable'] and a['anchor_extract_usable']]
        grouped[grade]=dict(actions=len(actions),both_usable=len(supported),
            all_core_gap_mm=stats([a['temporal_comparison']['core']['median_gap_mm'] for a in actions]),
            both_usable_core_gap_mm=stats([a['temporal_comparison']['core']['median_gap_mm'] for a in supported]),
            both_usable_standardized_gap=stats([a['temporal_comparison']['core']['standardized_gap'] for a in supported]),
            segments=sorted({a['segment'] for a in actions}))
    wrong_max=grouped['WRONG']['both_usable_core_gap_mm']['maximum']
    correct_above=[a['action_id'] for a in result['actions'] if a['physical']=='CORRECT'
        and a['current_extract_usable'] and a['anchor_extract_usable']
        and a['temporal_comparison']['core']['median_gap_mm']>wrong_max]
    # A descriptive contrast after the labels were sealed/joined. This value is
    # never a chosen veto threshold, a new prediction or a classification score.
    gates={}
    for entry in result['frozen_DS35_gate_forecasts']:
        k=(entry['segment'],entry['event'],entry['public'])
        if k not in gates or entry['post_frame']<gates[k]['post_frame']:gates[k]=entry
    gate_summary=[]
    for entry in gates.values():
        pred=entry['forecast'];components=entry['scale_components']
        limit=None
        if pred['status']=='WLS_LINEAR_TIME':
            c=pred['covariance_proxy'];t0=pred['time_scale_seconds']
            a=c[1][1]+225/t0**2;b=2*c[0][1];d=c[0][0]+225-60**2
            if d<0:
                limit=2*(-d)/(b+math.sqrt(b*b-4*a*d))
                reconstructed=c[0][0]+2*limit*c[0][1]+limit**2*c[1][1]+225*(1+(limit/t0)**2)
                assert math.isclose(reconstructed,60**2,rel_tol=1e-10)
            else:limit=0.
        gate_summary.append(dict(segment=entry['segment'],event=entry['event'],public=entry['public'],
            q=entry['q'],actual_forecast_query_frame=entry['post_frame'],
            query_frame_offset_from_q=entry['post_frame']-entry['q'],
            prediction_status=pred['status'],history_points=pred['samples'],
            last_history_frame=pred['sample_frames'][-1],history_span_seconds=components.get('fit_span_seconds'),
            mean_mm=pred['mu_mm'],intercept_mm=pred.get('beta_intercept_mm'),slope_mm_s=pred['slope_mm_s'],
            actual_forecast_gap_seconds=pred['delta_seconds'],scale_mm=pred['scale_mm'],
            parameter_variance_fraction=components.get('parameter_fraction'),
            drift_floor_fraction=components.get('drift_floor_fraction'),
            slope_standard_error_proxy_mm_s=components.get('slope_standard_error_proxy_mm_s'),
            frozen_60mm_cap_model_only_max_gap_seconds=limit,
            physical_interval_calibration='UNKNOWN',candidate_selected_by_label=False))
    local={key(v['segment'],v['frame'],v['native']):v for v in rows(HERE/'LOCAL_MEASUREMENTS.jsonl.gz')}
    cases=[]
    visual=read(HERE/'PRIVATE_VISUALS.json')
    for case in visual['cases']:
        verify_item(case['artifact'])
        points=[]
        for binding in case['source_frames']:
            v=local[binding['key']]
            points.append(dict(key=binding['key'],frame=v['frame'],global_frame=v['global_frame'],time=v['time'],
                native=v['native'],DS35_extract=v['DS35_extract'],
                measurements={role:dict(summary=fact['summary'],support=fact['measurement_support'])
                    for role,fact in v['views'].items()},background=v['background']['summary'],
                source_binding=v['source_binding'],mask_binding=v['mask_binding'],physical_surface='UNKNOWN'))
        cases.append(dict(name=case['name'],grade=case['grade'],selection=case['selection'],
            artifact=case['artifact'],points=points))
    save('POSTSEAL_FINDINGS.json',dict(status='READ_ONLY_DESCRIPTIVE_FINDINGS_RECOMPUTED',
        checked_utc=datetime.now(timezone.utc).isoformat(),source_results=artifact(HERE/'RESULTS.json'),
        helper=artifact(Path(__file__)),all_science_inputs_unchanged=True,
        endpoint_gap_by_grade=grouped,
        supported_correct_actions_above_supported_wrong_maximum_gap=correct_above,
        gap_contrast_is_not_a_threshold_or_method_result=True,
        gate_first_actual_query_per_public=gate_summary,all_private_cases=cases,
        query_frames_are_actual_DS35_decision_evidence_not_first_split_q=True,
        new_predictions=False,new_metrics=False,new_tracker_commits=0,model_http=0,cost_usd=0))
    print(json.dumps(dict(status='POSTSEAL_FINDINGS_COMPLETE',gate_first_queries=len(gate_summary),
        wrong_usable=grouped['WRONG']['both_usable'],wrong_gap_max_mm=wrong_max,
        correct_above_wrong_max=len(correct_above),private_cases=len(cases)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
