"""Direct regressions for S0-P's two changed contracts; no GT or API."""
import copy
import itertools
import io
import time
import json
import sys
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'experiments/ms1_s0_development_8400'
sys.path.insert(0,str(OLD))
sys.path.insert(0,str(ROOT/'online/closed_loop_2888/z4q_source'))
from bridge import Bridge,read,rows,stream  # noqa: E402
from merge_split_manager import GroupBridge,MergeSplitManager,choice_mapping,numeric_choice  # noqa: E402
from replay_p import OBS,ASSIGN,PROFILES,ARCHIVED,SCAN,emit  # noqa: E402
from manager_p import GroupBridgeP,MergeSplitManagerP,OutputIdentityPolicy  # noqa: E402
from replay_v7_recovery import publish_once  # noqa: E402


class FakeEngine:
    def __init__(self):
        self.protected={'event':{'generation':1}}
        self.bank={10:dict(value='group-before'),20:dict(value='latent-before'),42:dict(value='outside-corrected')}
        self.view_bank={10:dict(value='group-before'),20:dict(value='latent-before'),42:dict(value='outside-corrected')}
        for field in ('alias','birth','pending','native_seen','native_runs','recent_core',
                      'return_quarantine','empty_quarantine'):
            setattr(self,field,{99:dict(value='outside-corrected')})
        self.alias[99]=dict(target=42,source='earlier_branch_repair')
        self.retired={20}

    def step(self, frame, now, observations, profiles):
        assert not self.protected
        # Causal trial deliberately has an obsolete outside bank. The local
        # write set must keep the already updated branch view's outside bank.
        self.bank[10]=dict(value='group-causal-current')
        self.bank[42]=dict(value='outside-old-candidate')
        self.alias[10]=dict(target=10)
        return {10:10,20:20,99:42},dict(events=[])


class PolicyTests(unittest.TestCase):
    def test_continuous_residual_and_cancellation(self):
        e=dict(q=None,member_sources=[10,20],public_ids=[1,4],group_source=10)
        row=dict(frame=2145,observations=[dict(id=10),dict(id=20)])
        output,why=OutputIdentityPolicy.apply(e,row,{10:1,20:4},{10:2144,20:2144},{10:1,20:-1000000})
        self.assertEqual(output,{10:1,20:4})
        self.assertEqual(len(why),2)
        self.assertEqual(set(output),{10,20})
        # Cancellation on the next frame requires no retroactive rewrite.
        e['group_source']=20
        row['frame']=2146
        output,_=OutputIdentityPolicy.apply(e,row,{10:1,20:4},{10:2145,20:2145},{20:4,10:-1000001})
        self.assertEqual(output,{10:1,20:4})

    def test_one_mask_and_carrier_change(self):
        e=dict(q=None,member_sources=[10,20],public_ids=[1,4],group_source=10)
        row=dict(frame=8,observations=[dict(id=10)])
        output,_=OutputIdentityPolicy.apply(e,row,{10:1},{10:7},{10:1})
        self.assertEqual(output,{10:1})  # The missing member stays latent.
        e['group_source']=20
        row=dict(frame=9,observations=[dict(id=10),dict(id=20)])
        output,_=OutputIdentityPolicy.apply(e,row,{10:1},{10:8,20:5},{20:1,10:-1000000})
        self.assertEqual(output,{10:1,20:4})
        self.assertEqual(len(set(output.values())),len(output))

    def test_first_split_preview_does_not_publish(self):
        e=dict(q=100,member_sources=[10,20],public_ids=[1,4],group_source=10)
        row=dict(frame=100,observations=[dict(id=10),dict(id=20)])
        provisional={10:1,20:4}
        preview,_=OutputIdentityPolicy.apply(e,row,{10:1,20:4},{10:99,20:99},provisional)
        self.assertEqual(preview,provisional)
        output=io.StringIO()
        ledger=io.StringIO()
        published=set()
        pred=dict(frame=100,global_frame=100,variants={'HOLD-P':[
            dict(id=4,mask='n:10'),dict(id=1,mask='n:20')]})  # mock S0 H2
        self.assertEqual(output.getvalue(),'')  # preview has no publisher handle
        publish_once(output,ledger,pred,published,time.monotonic(),dict(decision='H2'))
        self.assertEqual(len(output.getvalue().splitlines()),1)
        self.assertEqual(json.loads(output.getvalue())['variants']['HOLD-P'],pred['variants']['HOLD-P'])
        with self.assertRaises(AssertionError):
            publish_once(output,ledger,pred,published,time.monotonic())
        later=dict(frame=101,observations=[dict(id=10),dict(id=20)])
        self.assertEqual(OutputIdentityPolicy.apply(e,row,{10:1,20:4},{10:99,20:99},provisional)[0],preview)
        self.assertEqual(later['frame'],101)
        self.assertEqual(len(output.getvalue().splitlines()),1)

    def test_failed_group_preserves_outside_branch_state(self):
        bridge=GroupBridgeP.__new__(GroupBridgeP)
        bridge.version=5
        bridge.engine=FakeEngine()
        bridge.previous={10:10,20:20,99:42}
        bridge.epochs={10:1,20:2,99:7}
        bridge.provenance={99:dict(source='earlier_model',target=42)}
        view_engine=copy.deepcopy(bridge.engine)
        view_engine.bank[42]=dict(value='outside-updated-this-frame')
        view_engine.view_bank[42]=dict(value='outside-view-updated')
        view_engine.native_runs[99]=dict(value='outside-run-updated')
        view=dict(version=5,frame=100,now=10.,observations=[dict(id=n) for n in (10,20,99)],
                  profiles={},mapping={10:10,20:20,99:42},trace={},engine=view_engine)
        episode=dict(id='event',q=100,member_sources=[10,20],post_roles={10:[],20:[]},
                     group_source=10,public_ids=[10,20])
        txn,detail=bridge.local_fallback(view,episode)
        self.assertEqual(detail['status'],'LOCAL_FALLBACK_COMMITTED')
        self.assertEqual(txn['engine'].bank[42],dict(value='outside-updated-this-frame'))
        self.assertEqual(txn['engine'].view_bank[42],dict(value='outside-view-updated'))
        self.assertEqual(txn['engine'].native_runs[99],dict(value='outside-run-updated'))
        self.assertEqual(txn['engine'].alias[99],dict(target=42,source='earlier_branch_repair'))
        self.assertEqual(txn['engine'].bank[10],dict(value='group-causal-current'))
        bridge.commit_once(view,txn)
        self.assertEqual(bridge.previous[99],42)
        self.assertEqual(bridge.epochs[99],7)
        self.assertEqual(bridge.provenance[99],dict(source='earlier_model',target=42))
        self.assertEqual(bridge.engine.bank[42],dict(value='outside-updated-this-frame'))
        self.assertNotIn('event',bridge.engine.protected)

    def test_unresolved_q_never_publishes_provisional_h1(self):
        bridge=GroupBridgeP.__new__(GroupBridgeP)
        bridge.version=5
        bridge.engine=FakeEngine()
        bridge.previous={10:10,20:20,99:42}
        view_engine=copy.deepcopy(bridge.engine)
        # A dormant outside alias reserves a group bank, so a state transplant
        # is unsafe even though the two currently visible IDs are legal.
        view_engine.alias[88]=dict(target=10,source='outside_dependency')
        view=dict(version=5,frame=100,now=10.,observations=[dict(id=n) for n in (10,20,99)],
                  profiles={},mapping={10:20,20:10,99:42},trace={},engine=view_engine)
        episode=dict(id='event',q=100,member_sources=[10,20],post_roles={10:[],20:[]},
                     group_source=10,public_ids=[10,20])
        txn,detail=bridge.local_fallback(view,episode)
        self.assertEqual(detail['status'],'LOCAL_FALLBACK_UNRESOLVED')
        self.assertEqual(txn['mapping'],{99:42,10:10,20:20})
        self.assertEqual(txn['engine'].bank[42],dict(value='outside-corrected'))
        self.assertNotIn('event',txn['engine'].protected)


def real_f2145_slice():
    """Replay the actual prefix twice, observing old and repaired first writes."""
    conf=read(OLD/'CONFIG_V7.json')
    assignments={r['frame']:r for r in rows(ASSIGN)}
    suspects={x['frame']:x for x in read(SCAN)['suspects']}
    zconfig=read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json')
    baseline=Bridge(zconfig)
    branches=[(GroupBridge(zconfig),MergeSplitManager),
              (GroupBridgeP(zconfig),MergeSplitManagerP)]
    branches=[(bridge,kind('slice',bridge,suspects,conf,assignments)) for bridge,kind in branches]
    result={}
    for (row,profiles),arch in zip(itertools.islice(stream(OBS,PROFILES,None,1),2147),rows(ARCHIVED)):
        f=row['frame']
        v0=baseline.preview(f,row['time'],row['observations'],profiles)
        base_ids,base_trace=baseline.commit_once(v0)
        assert emit(row,base_ids)==arch['variants']['Z4Q_STABLE']
        for index,(bridge,manager) in enumerate(branches):
            manager.before(row,profiles)
            view=bridge.preview(f,row['time'],row['observations'],profiles)
            e=manager.active
            if e and e['q']==f:
                c,_=numeric_choice(e)
                selected=choice_mapping(e,c) if c in ('H1','H2') else None
                txn,error=bridge.stage_group_restore(view,e,selected) if selected else (None,'unresolved')
                if txn:
                    ids,_=bridge.commit_once(view,txn)
                    status='COMMIT' if txn['changes'] else 'RESOLVE_NO_ID_CHANGE'
                elif index==0:
                    ids,_=bridge.rollback_to_baseline(baseline,view,e,base_trace)
                    status='OLD_ROLLBACK'
                else:
                    txn,_=bridge.local_fallback(view,e)
                    ids,_=bridge.commit_once(view,txn)
                    status='LOCAL_FALLBACK'
                manager.finish(f,status)
            else:
                ids,_=bridge.commit_once(view)
            manager.after(row,profiles)
            if f in (2144,2145,2146,2147):
                result.setdefault('OLD-HOLD' if index==0 else 'HOLD-P',{})[f]=emit(row,ids)
    def target(arm,f,n):
        return next(x['id'] for x in result[arm][f] if x['mask']==f'n:{n}')
    old_2145=result['OLD-HOLD'][2145]
    temporary=[x for x in old_2145 if x['id']<0]
    assert temporary and any(x['mask'] in {y['mask'] for y in result['HOLD-P'][2145]} for x in temporary)
    assert [x['mask'] for x in old_2145]==[x['mask'] for x in result['HOLD-P'][2145]]
    assert any(x['id']==4 for x in result['HOLD-P'][2145])
    return dict(status='PASS',frame_range=[2144,2147],
                old={str(k):v for k,v in result['OLD-HOLD'].items()},
                repaired={str(k):v for k,v in result['HOLD-P'].items()},
                old_temporary_ids=[x['id'] for x in temporary])


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PolicyTests)
    outcome=unittest.TextTestRunner(verbosity=2).run(suite)
    if not outcome.wasSuccessful():
        raise SystemExit(1)
    result=real_f2145_slice()
    path=HERE/'F2145_SLICE.json'
    if path.exists():
        assert json.loads(path.read_text(encoding='utf-8'))==result
    else:
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(tests=outcome.testsRun,real_slice=result['status'],old_temporary_ids=result['old_temporary_ids'])))
