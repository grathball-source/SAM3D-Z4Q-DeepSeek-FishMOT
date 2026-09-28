"""Direct state, measurement, parser and full all-DEFER replay checks."""
import copy
import gzip
import json
import math
import re
from pathlib import Path

from event_packet import depth_quality, project_merge
from mask_geometry import mask
from merge_split_manager import GroupBridge, MergeSplitManager, numeric_choice, sample, velocity
from provider import parse_split, write_new
from replay import HERE, ROOT, read, rows


def observation(n,x,z=750,neighbors=None):
    return dict(id=n,mask=f'n:{n}',box=[x,50,x+20,70],area=400,presence=.99,
                score_birth=.99,neighbors=[] if neighbors is None else neighbors,
                depth=dict(n=400,valid_fraction=1.,median=z,mad=2.))


def seeded_bridge():
    bridge=GroupBridge(read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'))
    for frame in range(1,11):
        view=bridge.preview(frame,frame/30,[observation(1,40),observation(2,100,850),
                                            observation(3,200,900)],{})
        assert bridge.commit_once(view)[0]=={1:1,2:2,3:3}
    return bridge


def protected_view(bridge, sources, outputs, member_sources=(10,20)):
    snapshot={k:copy.deepcopy(bridge.engine.bank[k]) for k in (1,2)}
    eid='SYNTHETIC_GROUP'
    bridge.engine.protected[eid]=dict(episode=eid,generation=11,member_public=[1,2],
        member_sources=list(member_sources),suppressed=[9],outputs={9:1})
    bridge.engine.alias[77]=dict(target=3,anchor=copy.deepcopy(bridge.engine.bank[3]['anchor']),
        commit_frame=9,source='OUTSIDE',transaction_version=1)
    bridge.engine.alias[1]=dict(target=3,anchor=copy.deepcopy(bridge.engine.bank[3]['anchor']),
        commit_frame=9,source='DORMANT_COLLISION',transaction_version=1)
    group=bridge.preview(11,11/30,[observation(9,65),observation(3,201,900)],{})
    assert bridge.commit_once(group)[0]=={3:3,9:1}
    assert 1 in bridge.engine.alias and 77 in bridge.engine.alias
    assert all(bridge.engine.bank[k]==snapshot[k] for k in (1,2))
    bridge.engine.protected[eid]['suppressed']=list(sources)
    bridge.engine.protected[eid]['outputs']=dict(outputs)
    current=[observation(n,42+i*60) for i,n in enumerate(sources)]+[observation(3,202,900)]
    q=bridge.preview(12,12/30,current,{})
    episode=dict(id=eid,generation=11,q=12,suspect_frame=11,public_ids=[1,2],
                 member_sources=list(member_sources),bank_snapshot=snapshot,
                 post_roles={n:[] for n in sources})
    return q,episode


def synthetic_sample(frame,x,core_n=20):
    o=observation(9,x)
    p=dict(core=dict(n=core_n,valid_fraction=1.,median=800.,mad=2.),
           whole=dict(n=core_n,valid_fraction=1.,median=800.,mad=2.))
    return sample(dict(o,frame=frame,time=frame/30),p,generation=1,public_epoch=1)


def test_units():
    checks=[]
    bridge=seeded_bridge()
    manager=MergeSplitManager('TEST',bridge,{},dict(max_episode_seconds=10),{})
    manager._history_update(dict(frame=10,time=10/30,observations=[observation(1,41)]),{})
    frozen=list(manager.clean[1])
    manager.frame_class={1:'GROUP_MEASUREMENT'}
    manager._history_update(dict(frame=11,time=11/30,observations=[observation(1,42,neighbors=[])]),{})
    assert not manager.clean[1] and manager.risk[1][-1]['observation_class']=='GROUP_MEASUREMENT'
    assert frozen[0]['frame']==10 and manager.last_clean[1]==frozen
    manager.frame_class={1:'POST_UNASSIGNED'}
    manager._history_update(dict(frame=12,time=12/30,observations=[observation(1,43)]),{})
    assert not manager.clean[1] and manager.risk[1][-1]['observation_class']=='POST_UNASSIGNED'
    manager.pending_clear.add(1)
    manager.frame_class={1:'POST_UNASSIGNED'}
    manager._history_update(dict(frame=13,time=13/30,observations=[observation(1,44)]),{})
    assert 1 not in manager.clean and 1 not in manager.last_clean and 1 not in manager.risk
    manager.frame_class={}
    manager._history_update(dict(frame=14,time=14/30,observations=[observation(1,45)]),{})
    assert [x['frame'] for x in manager.clean[1]]==[14]
    checks.append('GROUP_AND_SPLIT_NOT_CLEAN_EVEN_WITH_EMPTY_NEIGHBORS_AND_NEXT_EPISODE_RESET')

    bridge.epochs[1]+=1
    manager._history_update(dict(frame=15,time=15/30,observations=[observation(1,46)]),{})
    assert [x['frame'] for x in manager.clean[1]]==[15]
    manager._history_update(dict(frame=17,time=17/30,observations=[observation(1,47)]),{})
    assert [x['frame'] for x in manager.clean[1]]==[17]
    assert manager.clean[1][-1]['source_generation']>frozen[0]['source_generation']
    manager.suspects={18:dict(frame=18,sources=[1,2],group=1,coverage={'1':1.,'2':1.})}
    manager.before(dict(frame=18,time=18/30,observations=[observation(1,48),observation(2,101)]),{})
    assert [x['frame'] for x in manager.active['pre']['A']]==[17]
    assert all(x['observation_class']=='SOURCE_OBSERVATION' for x in manager.active['pre']['A'])
    checks.append('PUBLIC_EPOCH_AND_SOURCE_GENERATION_BREAK_LOCAL_HISTORY')

    for sources,outputs,selected in [([1,2],{1:1,2:2},{1:1,2:2}),
                                     ([9,10],{9:1,10:2},{9:2,10:1}),
                                     ([1,10],{1:1,10:2},{1:1,10:2})]:
        b=seeded_bridge()
        q,e=protected_view(b,sources,outputs)
        before=copy.deepcopy(b.engine.bank)
        assert b.stage_group_restore(q,dict(e,generation=12),selected)[1]=='stale_generation'
        assert b.engine.bank==before
        transaction,error=b.stage_group_restore(q,e,selected)
        assert error is None
        assert all(k in transaction['engine'].bank and transaction['engine'].bank[k]['anchor'] for k in (1,2))
        assert 77 in transaction['engine'].alias
        ids,_=b.commit_once(q,transaction)
        assert {n:ids[n] for n in sources}==selected and not b.engine.protected
        assert b.stage_group_restore(q,e,selected)[1]=='stale_episode'
    checks.append('PUBLIC_BANK_NATIVE_KEY_COLLISION_NEW_NATIVE_ONE_NEW_AND_ZERO_DELTA_ATOMICITY')

    straight=[synthetic_sample(i,float(i)) for i in range(1,11)]
    middle=[synthetic_sample(i,float(i)+(12 if 2<=i<=5 else -8 if 6<=i<=9 else 0)) for i in range(1,11)]
    a,b=velocity(straight),velocity(middle)
    assert a['samples']==b['samples']==10 and a['span_seconds']==b['span_seconds']
    assert a['residual_rms_2d_px']<b['residual_rms_2d_px']
    assert a['model']==b['model']=='OLS_INTERCEPT_LINEAR_TIME'
    assert velocity(straight[:2])['status']=='UNKNOWN'
    checks.append('TEN_POINT_OLS_MIDDLE_POINTS_CHANGE_RESIDUAL')

    assert depth_quality(dict(n=1,valid_fraction=1.,median=800.,mad=0.))['status']=='INSUFFICIENT_OR_INVALID'
    pre_a=[synthetic_sample(i,i,core_n=1) for i in (1,2,3)]
    pre_b=[synthetic_sample(i,20+i) for i in (1,2,3)]
    post_x=[synthetic_sample(i,i) for i in (10,11,12)]
    post_y=[synthetic_sample(i,20+i) for i in (10,11,12)]
    _,detail=numeric_choice(dict(pre={'A':pre_a,'B':pre_b},post_roles={9:post_x,10:post_y},
                                 temporary_choice='H1'))
    assert not detail['core_depth_used_for_both']
    assert all(edge['core_depth'] is None for candidate in detail['scores'] for edge in candidate['edges'])
    checks.append('SINGLE_PIXEL_DEPTH_REJECTED_AND_PAIRWISE_MODALITY_FAIR')

    long=dict(merge_assessment='m'*2500,possible_continuations=['c'*300],
              watch_for_after_split=['w'*300],uncertainty='uncertainty_tail_'+('u'*1800))
    projected=project_merge(json.dumps(long,ensure_ascii=False))
    assert projected['fields']['uncertainty']==long['uncertainty']
    oversized=dict(long,possible_continuations=['path'*3000]*20)
    bounded=project_merge(json.dumps(oversized,ensure_ascii=False))
    assert bounded['fields']['uncertainty']==long['uncertainty']
    assert len(json.dumps(bounded))<25000
    assert project_merge('{broken') is None
    assert parse_split('{"choice":"H2","extra":1}','stop')==('H2','OK')
    checks.append('LONG_PARSED_M_RETAINS_UNCERTAINTY_AND_S_EXTRA_FIELDS')
    return checks


def test_dry():
    dry=HERE/'dry_run_ms1r/public'
    seal=read(dry/'PREDICTIONS_SEALED.json')
    assert seal['frames']==2888 and seal['http_attempts']==0
    changed=0
    for row in rows(dry/'predictions_validation.jsonl.gz'):
        arms=row['variants']
        assert arms['B-HOLD-R']==arms['B-VLM-R']
        assert [x['mask'] for x in arms['B0']]==[x['mask'] for x in arms['B-HOLD-R']]
        assert all(len({x['id'] for x in arm})==len(arm) for arm in arms.values())
        changed+=arms['B0']!=arms['B-HOLD-R']
    assert changed>0
    packets=list((dry/'dry_packets').glob('*.json'))
    assert len(packets)==2
    for path in packets:
        body=read(path)
        assert 'native_id' not in body['user'] and 'public_id' not in body['user']
        assert all(x['bindings'] for x in body['images'])
        assert any(x['anonymous_context'] for x in body['images'])
    assignments={r['frame']:r for r in rows(HERE.parent/'merge_split_identity_memory/private_source/assignments.jsonl.gz')}
    for path in (HERE/'dry_run_ms1r/private_api').glob('*.bindings.json'):
        binding=read(path)['token_to_actual_source']
        for token,actual in binding.items():
            frame,rank=map(int,re.fullmatch(r'F(\d+):O(\d+)',token).groups())
            ranked=[]
            for key,rle in assignments[frame]['masks'].items():
                ys,xs=mask(rle).nonzero()
                if len(xs):
                    ranked.append(((xs.min()+xs.max()+1)/2,(ys.min()+ys.max()+1)/2,int(key.split(':')[1])))
                else:
                    ranked.append((0.,0.,int(key.split(':')[1])))
            ranked.sort()
            assert ranked[rank-1][2]==actual['source'],(token,actual,ranked)
    return ['FULL_2888_B0_EXACT_AND_ALL_DEFER_PROTECTION_EQUAL',
            'RAW_MASK_SET_UNCHANGED_NEUTRAL_CONTEXT_AND_PRIVATE_TOKEN_BINDINGS']


if __name__=='__main__':
    import sys
    checks=test_units()
    if sys.argv[1:]==['with-dry']:
        checks+=test_dry()
        report=dict(status='PASS',checks=checks,full_dry_prediction_sha256=read(
            HERE/'dry_run_ms1r/public/PREDICTIONS_SEALED.json')['predictions_sha256'])
        write_new(HERE/'TEST_REPORT.json',report)
    elif sys.argv[1:]:
        raise SystemExit('usage: test_ms1r.py [with-dry]')
    else:
        report=dict(status='PASS',checks=checks)
    print(json.dumps(report))
