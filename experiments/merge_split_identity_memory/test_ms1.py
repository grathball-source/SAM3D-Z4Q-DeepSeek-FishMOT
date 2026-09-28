"""Focused source, state, parser and full dry-run checks."""
import copy
import gzip
import json
import re
from pathlib import Path

from mask_geometry import mask
from merge_split_manager import GroupBridge
from provider import parse_split,write_new
from replay import HERE,ROOT,read,rows


def observation(n,x,z=750):
    return dict(id=n,mask=f'n:{n}',box=[x,50,x+20,70],area=400,presence=.99,
                score_birth=.99,neighbors=[],
                depth=dict(n=400,valid_fraction=1.,median=z,mad=2.))


def seeded_bridge():
    bridge=GroupBridge(read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'))
    for frame in range(1,11):
        obs=[observation(1,40),observation(2,100,850),observation(3,200,900)]
        view=bridge.preview(frame,frame/30,obs,{})
        assert bridge.commit_once(view)[0]=={1:1,2:2,3:3}
    return bridge


def protected_pair(bridge):
    snapshot={k:copy.deepcopy(bridge.engine.bank[k]) for k in (1,2)}
    eid='synthetic-group'
    bridge.engine.protected[eid]=dict(episode=eid,generation=11,
        member_public=[1,2],suppressed=[9],outputs={9:1})
    group=[observation(9,65),observation(3,201,900)]
    view=bridge.preview(11,11/30,group,{})
    assert bridge.commit_once(view)[0]=={3:3,9:1}
    assert all(bridge.engine.bank[k]==snapshot[k] for k in (1,2))
    assert bridge.engine.bank[3]['last_frame']==11
    bridge.engine.protected[eid]['suppressed']=[9,10]
    bridge.engine.protected[eid]['outputs']={9:1,10:2}
    current=[observation(9,42),observation(10,102,850),observation(3,202,900)]
    q=bridge.preview(12,12/30,current,{})
    episode=dict(id=eid,generation=11,q=12,public_ids=[1,2],member_sources=[1,2],
                 bank_snapshot=snapshot,post_roles={9:[],10:[]})
    return q,episode


def test():
    checks=[]
    assignment=next(r for r in rows(HERE/'private_source/assignments.jsonl.gz') if r['frame']==2585)
    assert mask(assignment['masks']['n:1']).sum()==890
    assert mask(assignment['masks']['n:4']).sum()==82
    checks.append('COCO_RLE_MATCHES_ACTUAL_AREA')

    scan=read(HERE/'private_source/scan.json')
    assert len(scan['suspects'])==1 and scan['suspects'][0]['frame']==2586
    assert scan['suspects'][0]['prior_mask_iou']<.25
    assert not any(x[0]==2581 for x in scan['transitions'])
    assert scan['counts']['LOST_OR_OUT_OF_SCOPE_TRANSITION']>0
    checks.append('CAUSAL_MASK_GRAPH_CONTACT_LOST_AND_TWO_TO_ONE')

    assert parse_split('{"choice":"H2","version":3,"reason":"short"}','stop')==('H2','OK')
    assert parse_split('{"preferred_hypothesis":"DEFER","type":"answer"}','stop')==('DEFER','OK')
    assert parse_split('{"choice":"H1","selected_hypothesis":"H2"}','stop')[0] is None
    assert parse_split('{"choice":"H1","choice":"H2"}','stop')[0] is None
    assert parse_split('{"choice":"H1","mapping":{"A":"Y","B":"X"}}','stop')[0] is None
    checks.append('EXTRA_FIELDS_ALLOWED_CONFLICTS_REJECTED')

    bridge=seeded_bridge()
    q,episode=protected_pair(bridge)
    frozen=copy.deepcopy(bridge.engine.bank)
    wrong=dict(episode,generation=12)
    assert bridge.stage_group_restore(q,wrong,{9:2,10:1})[1]=='stale_generation'
    assert bridge.engine.bank==frozen
    transaction,error=bridge.stage_group_restore(q,episode,{9:2,10:1})
    assert error is None and transaction['changes']=={9:2,10:1}
    assert bridge.commit_once(q,transaction)[0]=={3:3,9:2,10:1}
    assert not bridge.engine.protected
    next_view=bridge.preview(13,13/30,[observation(9,43),observation(10,103,850),observation(3,203,900)],{})
    assert bridge.commit_once(next_view)[0]=={3:3,9:2,10:1}
    assert bridge.stage_group_restore(q,episode,{9:1,10:2})[1]=='stale_episode'
    checks.append('NEW_NATIVE_ATOMIC_PAIR_RESTORE_AND_NEXT_FRAME_STATE')

    same=seeded_bridge()
    q,episode=protected_pair(same)
    transaction,error=same.stage_group_restore(q,episode,{9:1,10:2})
    assert error is None and transaction['changes']=={}
    same.commit_once(q,transaction)
    assert not same.engine.protected
    checks.append('ZERO_DELTA_RELEASES_PROTECTION')

    dry=HERE/'dry_run/public'
    seal=read(dry/'PREDICTIONS_SEALED.json')
    assert seal['frames']==2888 and seal['http_attempts']==0
    differences=0
    for r in rows(dry/'predictions_validation.jsonl.gz'):
        arms=r['variants']
        assert arms['B-HOLD']==arms['B-VLM']
        assert [x['mask'] for x in arms['B0']]==[x['mask'] for x in arms['B-HOLD']]
        assert all(len({x['id'] for x in arm})==len(arm) for arm in arms.values())
        differences+=arms['B0']!=arms['B-HOLD']
    assert differences>0
    checks.append('FULL_2888_B0_EXACT_AND_ALL_DEFER_EQUALS_HOLD')

    packets=list((dry/'dry_packets').glob('*.json'))
    assert len(packets)==2
    for path in packets:
        body=read(path)
        text=body['user']
        q=2587 if path.stem.endswith('-M') else 2604
        assert max(map(int,re.findall(r'F(\d+):O\d+',text)))<=q
        assert all(x not in text for x in ('native_id','public_id','gt_grid','file-api-'))
        assert len(body['images'])<=12
        assert all(binding['fact_id'] in text for image in body['images'] for binding in image['bindings'])
    checks.append('CAUSAL_PACKET_FACT_BINDINGS_NO_GT_OR_NATIVE')
    report=dict(status='PASS',checks=checks,full_dry_prediction_sha256=seal['predictions_sha256'])
    write_new(HERE/'TEST_REPORT.json',report)
    print(json.dumps(report))


if __name__=='__main__':
    test()
