"""Focused numeric and unchanged real-engine contracts; no scientific gate."""
from common import *
import copy, math, traceback
from datetime import datetime, timezone
from predictor import predict, DEPTH
from evidence import DepthEvidence, OLD, ADAPTATION
from adapter import DepthBridge, CONTROL, snapshot, engine_read
from immutable_sources import digest_state,digest_snapshot

prior = readonly_module('ds37_archived_ds32_contracts', OLD32.HERE/'checks.py', evidence=OLD)
prior.C = CONTROL
prior.DepthEvidence = DepthEvidence
prior.DepthBridge = lambda config, namespace, enabled=True, allow_edge=None: _bridge(config, namespace, enabled, allow_edge)

def _bridge(config, namespace, enabled, allow_edge):
    b = DepthBridge(config, namespace, 'LEVEL', enabled)
    b.engine.allow_edge = allow_edge
    return b

def samples(values, times=None):
    times = times or [i/30 for i in range(len(values))]
    return [dict(frame=i+1,time=t,z_mm=z,mad_mm=1.,usable=True,version=['SYNTHETIC',1],fact_id=f'SYNTHETIC:{i+1}')
        for i,(z,t) in enumerate(zip(values,times,strict=True))]

def constant_level_uncertainty_uses_seconds():
    xs = samples([1000.]*10)
    result = predict(xs,xs[-1]['time']+6.)
    assert math.isclose(result['mu_mm'],1000.) and math.isclose(result['scale_mm'],math.sqrt(225+225*6))
    assert result['slope_mm_s'] is None and result['innovation_floor_active']
    assert result['scale_mm']<60.<result['original_wls_diagnostic']['scale_mm']
    assert result['sample_frames']==list(range(1,11))

def innovations_keep_measured_drift_and_actual_dt():
    xs = samples([1000.+2*i for i in range(10)],[i*.1 for i in range(10)])
    result = predict(xs,1.9)
    assert math.isclose(result['original_wls_diagnostic']['slope_mm_s'],20.)
    assert math.isclose(result['raw_innovation_rate_mm2_s'],40.)
    assert result['slope_mm_s'] is None and result['mu_mm']==1009.
    fast = samples([1000.+10*i for i in range(10)],[i*.1 for i in range(10)])
    output = predict(fast,1.9)
    assert math.isclose(output['raw_innovation_rate_mm2_s'],1000.)
    assert math.isclose(output['drift_variance_mm2'],1000.)
    assert math.isclose(output['temporal_variance_mm2'],825.)
    assert math.isclose(output['scale_mm'],math.sqrt(1825.))

def future_version_gap_bad_and_short_are_unknown():
    xs=samples([1000.]*10)
    for altered,now in [(xs[:4],.2),([],1.),(xs,.1)]:
        p=predict(altered,now);assert not p['usable'] and p['mu_mm'] is None
    for change in ('version','frame','time','z_mm','usable'):
        altered=copy.deepcopy(xs)
        altered[3][change]={'version':['DIFFERENT'],'frame':8,'time':.3,'z_mm':float('nan'),'usable':False}[change]
        assert not predict(altered,1.)['usable'],change

def input_target_does_not_change_predictor():
    xs=samples([1000.+i for i in range(10)])
    before=copy.deepcopy(xs);one=predict(xs,1.)
    unrelated_current={'z_mm':2000.};unrelated_current['z_mm']=500.
    assert predict(xs,1.)==one and xs==before
    clone=copy.deepcopy(xs);clone[0]['z_mm']+=10
    assert predict(clone,1.)!=one

def exact_registry_missing_wide_expired_and_rebound():
    bridge=prior.seeded();ev=bridge.engine.evidence;anchor=bridge.engine.bank[1]['anchor'];o=prior.observation(3)
    for now,scale,reason in [(.7,15.,'CURRENT_DEPTH_UNRELIABLE'),(12.4,60.,'TARGET_FORECAST_TOO_BROAD')]:
        ex=prior.extract(o,7,now,1200.,now!=.7)
        if now==12.4:
            # Broad history is synthetic and immutable in this test's clone only.
            key=ev.anchor_key(anchor);record=copy.deepcopy(ev.anchors[key])
            for s in record['samples']:s['mad_mm']=40.
            ev.anchors[key]=record
        r=ev.query(7,now,o,1,anchor,{3:ex});assert not r['veto'] and r['reason']==reason,r['reason']
    r=ev.query(7,13.,o,1,anchor,{3:prior.extract(o,7,13.,1200.)})
    assert r['source_contract']['target_lookup']=='EXPIRED' and not r['veto']
    r=ev.query(7,.7,o,1,dict(anchor,frame=4),{3:prior.extract(o,7,.7,1200.)})
    assert r['source_contract']['target_lookup']=='ANCHOR_CHANGED_OR_REBOUND' and not r['veto']

def frozen_wls_forecast_and_state_path_are_unchanged():
    bridge=DepthBridge(read(CONFIG_PATH),'SYNTHETIC_WLS','WLS')
    oldbridge=CONTROL.DepthBridge(read(CONFIG_PATH),'SYNTHETIC_WLS')
    for frame in range(1,9):
        objects=[prior.observation(1),prior.observation(2,1400.,50.)] if frame<6 else prior.q_objects()
        now=frame/10.;row=dict(frame=frame,time=now,observations=objects,native=[dict(id=o['id'],mask=o['mask']) for o in objects])
        ps={o['id']:prior.profile(o,frame) for o in objects};xs={o['id']:prior.extract(o,frame,now,1200. if frame>=6 else None) for o in objects}
        a=bridge.preview(row,ps,xs);b=oldbridge.preview(row,ps,xs)
        ia,_=bridge.commit_once(a);ib,_=oldbridge.commit_once(b)
        assert ia==ib and digest(CONTROL.engine_state(bridge.engine))==digest(CONTROL.engine_state(oldbridge.engine))
        state=bridge.engine.evidence.state();state.pop('predictor_mode');state.pop('predictor_config')
        assert digest(state)==digest(oldbridge.engine.evidence.state())

def hash_only_snapshot_keeps_exact_full_content_and_detached_public_state():
    bridge=prior.seeded();ev=bridge.engine.evidence
    assert digest(snapshot(bridge))==digest(CONTROL.full_state(bridge))
    assert digest(engine_read(bridge.engine))==digest(CONTROL.engine_state(bridge.engine))
    assert digest(ev._read_state())==digest(ev.state())
    old=digest(snapshot(bridge));returned=ev.state()
    next(iter(returned['sample_pool'].values()))['z_mm']=-100.
    assert digest(snapshot(bridge))==old
    # Direct synthetic mutation is detectable; hashes are not cached.
    key=next(iter(ev.anchors));record=copy.deepcopy(ev.anchors[key])
    record['samples'][0]['z_mm']+=10.;ev.anchors[key]=record
    assert digest(snapshot(bridge))!=old
    assert digest(snapshot(bridge))==digest(CONTROL.full_state(bridge))

def valid_level_history_survives_negative_old_wls_extrapolation():
    xs=samples([740.-4*i for i in range(10)])
    now=xs[-1]['time']+6.
    old=DEPTH.forecast(xs,now)
    assert old['status']=='WLS_LINEAR_TIME' and old['mu_mm']<0 and not old['usable']
    current=predict(xs,now)
    assert current['usable'] and current['mu_mm']>0 and current['scale_mm']<60.
    assert current['original_wls_diagnostic']==old
    changed=copy.deepcopy(xs);changed[3]['version']=['OTHER']
    assert not predict(changed,now)['usable']

def immutable_source_json_bytes_match_complete_stdlib_hash_and_mutations_fail():
    bridge=prior.seeded();ev=bridge.engine.evidence
    assert digest_state(ev._read_state())==digest(ev.state())
    assert digest_snapshot(snapshot(bridge))==digest(CONTROL.full_state(bridge))
    sample=next(iter(ev.anchors.values()))['samples'][0]
    for change in (lambda:sample.__setitem__('z_mm',-1),lambda:sample['version'].append('BAD'),
                   lambda:sample['source_binding']['quality'].__setitem__('physical_surface_identity','BAD')):
        try:change();raise AssertionError('Source mutation was allowed')
        except RuntimeError as error:assert str(error)=='Immutable depth source payload'
    plain=copy.deepcopy(sample);plain['z_mm']+=10.
    assert sample['z_mm']!=plain['z_mm'] and isinstance(plain,dict)

TESTS=[constant_level_uncertainty_uses_seconds,innovations_keep_measured_drift_and_actual_dt,
    future_version_gap_bad_and_short_are_unknown,input_target_does_not_change_predictor,
    exact_registry_missing_wide_expired_and_rebound,frozen_wls_forecast_and_state_path_are_unchanged,
    hash_only_snapshot_keeps_exact_full_content_and_detached_public_state,
    valid_level_history_survives_negative_old_wls_extrapolation,
    immutable_source_json_bytes_match_complete_stdlib_hash_and_mutations_fail]
TESTS += [test for test in prior.TESTS if test.__name__!='missing_wide_expired_and_rebound_are_null']

def main():
    results=[]
    for test in TESTS:
        try:test();results.append(dict(name=test.__name__,status='PASS'))
        except Exception as error:results.append(dict(name=test.__name__,status='FAIL',error=repr(error),traceback=traceback.format_exc()))
    result=dict(status='PASS' if all(x['status']=='PASS' for x in results) else 'FAIL',results=results,
        passed=sum(x['status']=='PASS' for x in results),tests=len(results),query_adapter=ADAPTATION,
        no_real_GT_or_network=True,new_model_http=0,cost_usd=0)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    write_new(HERE/'checks'/f'{stamp}.json',result)
    if result['status']=='PASS':write_new(HERE/'CHECKS_FINAL_V3_COMPLETE.json',result)
    print(json.dumps(result,ensure_ascii=False));assert result['status']=='PASS'

if __name__=='__main__':main()
