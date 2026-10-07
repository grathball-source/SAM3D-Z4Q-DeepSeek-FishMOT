"""Postseal independent consistency checks; no criteria changes or new fits."""
from common import *
from audit import key
from datetime import datetime,timezone
import math

def main():
    verify_freeze();seal=read(HERE/'FEATURES_SEALED.json')
    for pin in seal['files']:verify_item(pin)
    pairs=list(rows(HERE/'CAUSAL_FORECAST_PAIRS.jsonl.gz'))
    wanted=set()
    for p in pairs:
        n=int(p['target_fact_id'].split('/')[2][2:]);name=p['segment']
        wanted.update(key(name,f,n) for f in p['history_frames']+[p['target_frame']])
    points={key(p['segment'],p['frame'],p['native']):p for p in rows(HERE/'TEMPORAL_TRACE.jsonl.gz') if key(p['segment'],p['frame'],p['native']) in wanted}
    for p in pairs:
        name=p['segment'];n=int(p['target_fact_id'].split('/')[2][2:])
        history=[points[key(name,f,n)] for f in p['history_frames']];target=points[key(name,p['target_frame'],n)]
        assert all(s['usable'] and not s['source_risks'] and s['version']==p['version'] for s in history+[target])
        assert all(b['frame']==a['frame']+1 for a,b in zip(history,history[1:]))
        assert digest(history)==p['history_sha256'] and target['fact_id']==p['target_fact_id']
        assert max(s['frame'] for s in history)<target['frame'] and max(s['time'] for s in history)<p['query_time']
        assert target['z_mm']==p['target_measurement_mm'] and target['time']==p['query_time']
        pred=DEPTH.forecast(history,target['time'])
        for field in ('status','mu_mm','slope_mm_s','scale_mm','sample_frames','sample_fact_ids','beta_intercept_mm'):
            assert pred[field]==p['forecast'][field]
        assert math.isclose(p['combined_scale_mm'],math.hypot(pred['scale_mm'],target['scale_mm']),rel_tol=1e-12)
        for variant,mu in [('WLS',pred['mu_mm']),('INTERCEPT_MATCHED_SCALE',pred['beta_intercept_mm']),('LAST_VALUE_MATCHED_SCALE',history[-1]['z_mm'])]:
            assert p['errors'][variant]['mu_mm']==mu
            assert p['errors'][variant]['absolute_error_mm']==abs(target['z_mm']-mu)
    local=list(rows(HERE/'LOCAL_MEASUREMENTS.jsonl.gz'));lookup={key(m['segment'],m['frame'],m['native']):m for m in local}
    requests={key(r['segment'],r['frame'],r['native']):r for r in read(HERE/'COHORT.json')['requests']}
    missing=read(HERE/'MEASUREMENT_SUMMARY.json')['missing_requested_masks']
    missing_keys={key(m['segment'],m['frame'],m['native']) for m in missing}
    assert set(requests)<=set(lookup)|missing_keys
    for k,r in requests.items():
        assert all(r['frame']<=c['evidence_cutoff'] for c in r['contexts'])
    for m in local:
        original={k:v for k,v in m.items() if k not in ('contexts','DS35_extract','assignment_row_sha256','measurement_sha256')}
        assert digest(original)==m['measurement_sha256']
        assert not any(m['source_binding'].get(k) for k in ('GT_read','RGB_read','restored_read'))
        assert m['views']['core']['roi_binding']==m['DS35_extract']['roi_binding']
        assert m['views']['core']['population_binding']['selected_source_index_binding']==m['DS35_extract']['selected_source_index_binding']
        for v in m['views'].values():
            assert v['summary']['n']==v['population_binding']['selected_source_index_binding']['shape'][0]
            assert v['source_exclusions']['selected_independent_native_source_n']==v['summary']['n']
    labeled=read(HERE/'LABELED_ACTIONS.json');source={a['action_id']:a for a in read(DS21/'ACTIONS.json')['actions']}
    assert len(labeled['actions'])==len(source)==90
    assert labeled['joined_utc']>seal['sealed_utc']
    for a in labeled['actions']:
        assert a['physical']==source[a['action_id']]['physical'] and a['actual_reference_physical']==source[a['action_id']]['actual_reference_physical']
    verify_freeze()
    save('INDEPENDENT_REVIEW.json',dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),
        causal_forecast_pairs=len(pairs),local_measurements=len(local),actions=90,events=75,
        all_actual_targets_bound=True,all_forecasts_recomputed=True,source_risk_and_version_breaks_respected=True,
        future_targets_excluded_from_history=True,missing_requests_retained=True,all_population_bindings_consistent=True,
        old_labels_joined_only_after_seal=True,old_frozen_inputs_unchanged=True,new_predictions=False,new_metrics=False,
        helper=artifact(__file__),model_http=0,cost_usd=0))
    print('INDEPENDENT_REVIEW_PASS',len(pairs),len(local),flush=True)

if __name__=='__main__':main()
