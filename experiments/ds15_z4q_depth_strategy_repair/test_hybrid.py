"""Candidate veto, UNKNOWN retention and causal preview state checks."""
import copy
from types import SimpleNamespace
from common import HERE,ROOT,read,input_dir,module
from hybrid import HybridBridge,EventDepthState
from bridge import stream
from group_association import predict as group_predict
automatic_adoption=module('ds15_runner_test',HERE/'runner.py').automatic_adoption


def main():
    config=read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json')
    bridge=HybridBridge(config,True)
    anchor=dict(native_id=1,canonical_id=1,frame=5)
    key=['synthetic','support',0,1,0]
    samples=[dict(frame=f,time=f/30,z_mm=500.,mad_mm=1.,source='RAW_SENSOR_ADAPTIVE',
                  fact_id=f'F{f}',version_key=key) for f in range(1,6)]
    bridge.engine.depth_context=dict(frame=6,time=.2,
        past={1:dict(anchor=anchor,frozen=dict(key=key,samples=samples,cutoff_frame=5))},
        current={2:dict(qualified=True,fact_id='F6/n2',core=dict(median=1500.,mad=1.))},
        background=dict(method='FULL_SENSOR_DEPTH_T4',mu_mm=1500.,scale_mm=60.))
    a=bridge.engine.edge_veto(6,.2,dict(id=2),1,anchor,'BIRTH_REFINE')
    assert a['veto'] and a['reason']=='STRONG_DEPTH_CONTRADICTION_EDGE_VETO'
    assert not bridge.engine.edge_veto(6,.2,dict(id=2),3,anchor,'D1_DELAYED')['veto']
    assert not bridge.engine.edge_veto(6,.2,dict(id=2),1,dict(anchor,frame=4),'D1_DELAYED')['veto']
    bridge.engine.depth_context['current'][2]['qualified']=False
    assert not bridge.engine.edge_veto(6,.2,dict(id=2),1,anchor,'BIRTH_REFINE')['veto']
    shared=HybridBridge(config,False);shared.engine.depth_context=copy.deepcopy(bridge.engine.depth_context)
    assert not shared.engine.edge_veto(6,.2,dict(id=2),1,anchor,'BIRTH_REFINE')['veto']
    synthetic=dict(frame=6,time=.2,observations=[dict(id=2,area=200,presence=None,score_birth=1.,neighbors=[])])
    query=dict(core_usable=True,core=dict(median=1500.,mad=1.),fact_id='F6/n2')
    bridge.engine.bank={1:dict(anchor=anchor)}
    rawstate=SimpleNamespace(live={1:dict(key=tuple(key))})
    for count in (3,4,5):
        selected=samples[-count:]
        memory=SimpleNamespace(live={1:dict(key=key,samples=selected,
            geometry_history=[dict(frame=s['frame'],time=s['time']) for s in selected])},
            anchor_versions={(1,1,5):key})
        bridge.bind_depth(synthetic,{2:query},dict(n=100,median=1500.,mad=1.),memory,rawstate)
        assert (1 in bridge.engine.depth_context['past'])==(count==5)
    base=input_dir('fishsa_development_8400')
    row,profiles=next(stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz',1))
    pristine=HybridBridge(config,True);before=copy.deepcopy(vars(pristine.engine))
    view=pristine.preview(row['frame'],row['time'],row['observations'],profiles)
    assert vars(pristine.engine)==before and pristine.version==0
    ids,_=pristine.commit_once(view,None)
    assert len(ids)==len(set(ids.values()))==len(row['observations'])
    assert pristine.version==1
    state=EventDepthState('synthetic','support')
    measurement=dict(core_usable=True,core=dict(median=500.,mad=1.),source='RAW_SENSOR_ADAPTIVE',fact_id='known')
    for f in range(1,6):state.update(1,measurement,f,f/30,1,0,0,'SOURCE_OBSERVATION')
    for f in range(6,40):state.update(1,measurement,f,f/30,1,0,0,'QUALITY_OR_CONTACT_RISK')
    event=dict(member_sources=[1,2],public_ids=[1,2])
    frozen=state.freeze(event,40,{1:0},{1:0})['A']
    assert [x['frame'] for x in frozen['samples']]==list(range(1,6))
    assert len(state.live[1]['cache'])==30 and not state.live[1]['samples']
    assert group_predict(frozen,40/30)['history_eligible']
    assert not group_predict(frozen,13.)['history_eligible']
    assert not state.freeze(event,40,{1:1},{1:0})['A']['samples']
    trace=dict(events=[dict(kind='reconnect',accepted=True,native_id=7,canonical_id=0)])
    adopted=SimpleNamespace(engine=SimpleNamespace(alias={7:dict(target=0)}))
    assert len(automatic_adoption(adopted,{7:0},trace)['durable_automatic_commits'])==1
    assert not automatic_adoption(adopted,{7:7},trace)['durable_automatic_commits']
    assert not automatic_adoption(adopted,{7:0},trace,dict(changes={7:0}))['durable_automatic_commits']
    print('PASS: edge UNKNOWN retention; strong depth veto; preview pure; bijective commit; intact frozen history beyond live30; expiry/version break.')

if __name__=='__main__':main()
