"""Focused DS32 contracts on synthetic observations; no data/GT/network access."""
from common import *
from bridge import Bridge
import copy, traceback
from datetime import datetime, timezone
C = module('ds32_unique_contract_checks_controller', HERE/'controller.py')
DepthBridge, engine_state, full_state = C.DepthBridge, C.engine_state, C.full_state
DepthEvidence = module('ds32_unique_contract_checks_evidence', HERE/'evidence.py').DepthEvidence


def observation(native, z=1000., x=10., neighbors=()):
    return dict(id=native, mask=f'n:{native}', box=[x,10.,x+10.,20.], area=100,
        score_birth=.9, presence=.9, neighbors=list(neighbors),
        depth=dict(n=100,valid_fraction=1.,median=z,mad=1.))


def profile(o, frame, core_z=None):
    z=o['depth']['median']
    stats=dict(n=100,area=100,valid_fraction=1.,median=z,mad=1.,q25=z-1,q75=z+1)
    return dict(id=o['id'],mask=o['mask'],frame=frame,whole=dict(stats),
        core=dict(stats,median=z if core_z is None else core_z))


def extract(o, frame, now, z=None, usable=True):
    native=o['id']
    return dict(usable=usable,frame=frame,time=now,native=native,
        z_mm=o['depth']['median'] if z is None else z,mad_mm=1.,scale_mm=15.,
        fact_id=f'SYNTHETIC:{frame}:{native}:core',certificate_fact_id=f'SYNTHETIC:{frame}:{native}',
        certificate_sha256='SYNTHETIC_NO_REAL_SOURCE_CERTIFICATE',
        roi_binding=dict(synthetic=True),selected_source_index_binding=dict(synthetic=True),
        quality=dict(physical_surface_identity='UNKNOWN'))


def tick(bridge, frame, objects, *, actual_z=None, core_z=None, anonymous=()):
    now=frame/10.
    row=dict(frame=frame,time=now,observations=objects,
        native=[dict(id=o['id'],mask=o['mask']) for o in objects])
    profiles={o['id']:profile(o,frame,(core_z or {}).get(o['id'])) for o in objects}
    extracts={o['id']:extract(o,frame,now,(actual_z or {}).get(o['id'])) for o in objects}
    before=digest(full_state(bridge))
    view=bridge.preview(row,profiles,extracts,anonymous)
    assert before==digest(full_state(bridge))
    ids,trace=bridge.commit_once(view)
    assert bridge.engine.query_context is None
    return view,ids,trace


def seeded(*, birth=True, extra=False, enabled=True, allow_edge=None):
    bridge=DepthBridge(read(CONFIG_PATH),'SYNTHETIC_CONTRACT',enabled,allow_edge)
    bridge.engine.birth_enabled=birth
    for frame in range(1,6):
        obs=[observation(1),observation(2,1400.,50.)]
        if extra:obs.append(observation(4,1010.,15.))
        tick(bridge,frame,obs,actual_z={4:1200.} if extra else None)
    obs=[observation(1,neighbors=(2,)),observation(2,1400.,50.,(1,4) if extra else (1,))]
    if extra:obs.append(observation(4,1010.,15.,(2,)))
    tick(bridge,6,obs,actual_z={4:1200.} if extra else None)
    return bridge


def q_objects(*, bad=False):
    return [observation(3,1200. if bad else 1000.),observation(2,1400.,50.)]


def d1_legal_veto_keeps_dummy():
    bridge=seeded(birth=False)
    view,ids,trace=tick(bridge,7,q_objects(),actual_z={3:1200.})
    selected=[c for c in trace['depth_checks'] if c['phase']=='D1_DELAYED' and c['canonical_id']==1]
    assert len(selected)==1 and selected[0]['original_eligible'] and selected[0]['conflict'] and selected[0]['veto']
    assert ids[3]==3 and 3 not in bridge.engine.pending and not view['actual_commits']
    assert len(ids)==len(set(ids.values()))==2


def d1_partial_edge_preserves_other_candidate():
    bridge=seeded(birth=False,extra=True)
    view,ids,trace=tick(bridge,7,q_objects(),actual_z={3:1200.})
    checks={c['canonical_id']:c for c in trace['depth_checks'] if c['phase']=='D1_DELAYED'}
    assert checks[1]['veto'] and checks[4]['original_eligible'] and not checks[4]['veto']
    assert bridge.engine.pending[3]['target']==4 and bridge.engine.pending[3]['count']==1
    assert ids[3]==3 and not view['actual_commits']


def birth_objects():
    return [observation(3,neighbors=(2,)),observation(2,1400.,50.,(3,))]


def birth_legal_veto_before_first_publication():
    bridge=seeded();objects=birth_objects();evidence=bridge.engine.evidence
    real=evidence.query(7,.7,objects[0],1,bridge.engine.bank[1]['anchor'],
        {o['id']:extract(o,7,.7,1200. if o['id']==3 else None) for o in objects})
    assert real['veto'] and real['conflict'] and real['reason']=='RELIABLE_DEPTH_CONFLICT'
    bad={o['id']:extract(o,7,.7,1200. if o['id']==3 else None,False if o['id']==3 else True) for o in objects}
    unknown=evidence.query(7,.7,objects[0],1,bridge.engine.bank[1]['anchor'],bad)
    assert not unknown['veto'] and unknown['reason']=='CURRENT_DEPTH_UNRELIABLE'
    view,ids,trace=tick(bridge,7,objects,actual_z={3:1200.})
    birth=[c for c in trace['depth_checks'] if c['phase']=='BIRTH_REFINE' and c['canonical_id']==1]
    assert len(birth)==1 and birth[0]['original_eligible'] and birth[0]['veto']
    assert view['original_mapping'][3]==1 and ids[3]==3 and not view['actual_commits']
    assert view['actual_matrix_deletions']==1


def originally_invalid_conflicts_do_not_change_original_state():
    bridge=seeded()
    view,ids,trace=tick(bridge,7,q_objects(bad=True),actual_z={3:1200.})
    conflicts=[c for c in trace['depth_checks'] if c['conflict']]
    assert {c['phase'] for c in conflicts}=={'BIRTH_REFINE','D1_DELAYED'}
    assert all(not c['original_eligible'] and not c['veto'] for c in conflicts)
    assert view['actual_matrix_deletions']==0 and trace['null_original_state_exact']
    assert view['actual_engine_state_sha256']==view['original_engine_state_sha256'] and ids==view['original_mapping']


def counterfactual_allow_is_one_exact_edge():
    bridge=seeded(allow_edge=(7,'BIRTH_REFINE',3,1))
    view,ids,trace=tick(bridge,7,birth_objects(),actual_z={3:1200.})
    check=next(c for c in trace['depth_checks'] if c['phase']=='BIRTH_REFINE' and c['canonical_id']==1)
    assert check['conflict'] and check['counterfactual_allowed'] and not check['veto']
    assert ids[3]==1 and view['actual_commits']==view['original_commits'] and len(view['actual_commits'])==1
    # The fixed key does not suppress another phase, frame or source.
    engine=bridge.engine
    current=observation(9)
    engine.query_context=dict(row=dict(frame=8,time=.8),
        extracts={9:extract(current,8,.8,1200.)})
    try:
        other=engine.edge_veto(8,.8,current,1,engine.bank[1]['anchor'],
            'D1_DELAYED',dict(cost=.2),True)
        assert other['conflict'] and other['veto'] and not other['counterfactual_allowed']
    finally:engine.query_context=None


def disabled_replays_full_original_state():
    new=DepthBridge(read(CONFIG_PATH),'SYNTHETIC_DISABLED',False)
    old=Bridge(read(CONFIG_PATH))
    for frame in range(1,9):
        obs=[observation(1),observation(2,1400.,50.)] if frame<6 else q_objects()
        _,ids,trace=tick(new,frame,obs,actual_z={o['id']:1200. for o in obs})
        now=frame/10.;profiles={o['id']:profile(o,frame) for o in obs}
        old_ids,_=old.commit_once(old.preview(frame,now,obs,profiles))
        assert ids==old_ids and digest(engine_state(new.engine))==digest(vars(old.engine))
        assert new.previous==old.previous and new.epochs==old.epochs and new.provenance==old.provenance
        assert trace['null_original_state_exact']


def preview_and_exception_keep_authoritative_state():
    bridge=seeded()
    before=digest(full_state(bridge));captured=[]
    def broken(trial,*args,**kwargs):
        captured.append(trial)
        raise RuntimeError('TEST_ONLY_PREVIEW_EXCEPTION')
    owner=C.DepthVetoEngine
    assert 'step' not in owner.__dict__
    owner.step=broken
    try:
        try:
            tick(bridge,7,q_objects(),actual_z={3:1200.})
            raise AssertionError('Exception was swallowed')
        except RuntimeError as error:assert str(error)=='TEST_ONLY_PREVIEW_EXCEPTION'
    finally:del owner.step
    assert len(captured)==1 and captured[0].query_context is None
    assert digest(full_state(bridge))==before and bridge.engine.query_context is None


def observer_preserves_real_bank_and_frozen_anchor_after_risk():
    bridge=seeded()
    evidence=bridge.engine.evidence;anchor=copy.deepcopy(bridge.engine.bank[1]['anchor'])
    assert anchor['frame']==5 and 1 not in evidence.live
    before=digest(engine_state(bridge.engine));old=digest(evidence.state())
    objects=q_objects();extracts={o['id']:extract(o,7,.7,1200. if o['id']==3 else None) for o in objects}
    check=evidence.query(7,.7,objects[0],1,anchor,extracts)
    assert check['conflict'] and check['veto'] and check['source_contract']['target_lookup']=='REGISTERED'
    assert check['samples'][-1]['frame']==5 and len(check['samples'])==5
    assert digest(engine_state(bridge.engine))==before and digest(evidence.state())==old


def source_generation_epoch_and_risk_break_history():
    bridge=DepthBridge(read(CONFIG_PATH),'SYNTHETIC_BREAKS')
    for frame in range(1,6):tick(bridge,frame,[observation(1)])
    first=copy.deepcopy(bridge.engine.evidence.live[1]['identity'])
    tick(bridge,6,[]);tick(bridge,7,[observation(1)])
    record=bridge.engine.evidence.live[1]
    assert record['identity'][2]==first[2]+1 and len(record['samples'])==1
    bridge.epochs[1]+=1
    tick(bridge,8,[observation(1)])
    record=bridge.engine.evidence.live[1]
    assert record['identity'][4]==bridge.epochs[1] and len(record['samples'])==1
    tick(bridge,9,[observation(1)],anonymous=(1,))
    assert 1 not in bridge.engine.evidence.live
    tick(bridge,10,[observation(1)])
    assert len(bridge.engine.evidence.live[1]['samples'])==1 and bridge.engine.evidence.live[1]['fragment_start']==10


def missing_wide_expired_and_rebound_are_null():
    bridge=seeded();evidence=bridge.engine.evidence;anchor=bridge.engine.bank[1]['anchor']
    o=observation(3);xs={3:extract(o,7,.7,1200.,False)}
    missing=evidence.query(7,.7,o,1,anchor,xs)
    assert not missing['veto'] and missing['reason']=='CURRENT_DEPTH_UNRELIABLE'
    wide=evidence.query(7,3.,o,1,anchor,{3:extract(o,7,3.,1200.)})
    assert not wide['veto'] and wide['reason']=='TARGET_FORECAST_TOO_BROAD'
    expired=evidence.query(7,13.,o,1,anchor,{3:extract(o,7,13.,1200.)})
    assert not expired['veto'] and expired['source_contract']['target_lookup']=='EXPIRED'
    rebound=evidence.query(7,.7,o,1,dict(anchor,frame=4),{3:extract(o,7,.7,1200.)})
    assert not rebound['veto'] and rebound['source_contract']['target_lookup']=='ANCHOR_CHANGED_OR_REBOUND'


def future_current_and_q_in_pre_are_rejected():
    bridge=seeded();evidence=bridge.engine.evidence;o=observation(3);anchor=bridge.engine.bank[1]['anchor']
    for frame,now,extracts in [(7,.7,{3:extract(o,8,.8,1200.)}),(6,.6,{3:extract(o,6,.6,1200.)})]:
        try:
            evidence.query(frame,now,o,1,anchor,extracts)
            raise RuntimeError('Invalid causal payload accepted')
        except AssertionError:pass


def immutable_evidence_clone_and_exact_source_adaptation():
    bridge=seeded();evidence=bridge.engine.evidence;before=digest(evidence.state())
    sibling=copy.deepcopy(evidence)
    o=observation(3);check=sibling.query(7,.7,o,1,bridge.engine.bank[1]['anchor'],{3:extract(o,7,.7,1200.)})
    check['samples'][0]['z_mm']=-1
    assert digest(evidence.state())==before and digest(sibling.state())==before
    twin=copy.deepcopy(bridge);tick(twin,7,q_objects(),actual_z={3:1200.})
    assert digest(evidence.state())==before
    receipt=read(HERE/'source/ADAPTATION.json')
    for record in receipt['records']:
        assert sha(record['original_path'])==record['original_sha256']
        assert sha(record['adapted_path'])==record['adapted_sha256']
    assert len(receipt['records'])==5


TESTS=[d1_legal_veto_keeps_dummy,d1_partial_edge_preserves_other_candidate,
    birth_legal_veto_before_first_publication,originally_invalid_conflicts_do_not_change_original_state,
    counterfactual_allow_is_one_exact_edge,disabled_replays_full_original_state,
    preview_and_exception_keep_authoritative_state,observer_preserves_real_bank_and_frozen_anchor_after_risk,
    source_generation_epoch_and_risk_break_history,missing_wide_expired_and_rebound_are_null,
    future_current_and_q_in_pre_are_rejected,immutable_evidence_clone_and_exact_source_adaptation]


def main():
    results=[]
    for check in TESTS:
        try:check();results.append(dict(name=check.__name__,status='PASS'))
        except Exception as error:
            results.append(dict(name=check.__name__,status='FAIL',error=repr(error),traceback=traceback.format_exc()))
    result=dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL',
        tests=len(results),passed=sum(r['status']=='PASS' for r in results),results=results,
        synthetic_only=True,GT_data_network_opened=False,new_model_http=0,cost_usd=0,
        birth_legal_hook_test_uses_real_WLS_and_reliable_exclusive_query=True,
        current_contact_with_unusable_depth_retains_UNKNOWN=True,
        code={str(p.resolve()):sha(p) for p in [HERE/'checks.py',HERE/'controller.py',HERE/'evidence.py',*sorted((HERE/'source').glob('*.py'))]},
        code_artifacts=[artifact(p) for p in [HERE/'checks.py',HERE/'controller.py',HERE/'evidence.py',*sorted((HERE/'source').glob('*.py'))]])
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    write_new(HERE/'checks'/f'{stamp}.json',result)
    if result['status']=='PASS' and not (HERE/'CHECKS_FINAL.json').exists():write_new(HERE/'CHECKS_FINAL.json',result)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    assert result['status']=='PASS',f"{result['passed']}/{result['tests']} checks passed"


if __name__=='__main__':main()
