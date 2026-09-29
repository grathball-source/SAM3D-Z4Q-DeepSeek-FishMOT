"""Focused policy, state-transaction and source-data checks; no GT or HTTP."""
import copy
import gzip
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT/'online/closed_loop_2888/z4q_source'))
from bridge import read, stream  # noqa: E402
from ne_controller import NativeFirstProtectedReturn, NativeFirstGroupBridgeP  # noqa: E402

CONFIG = read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json')
FEED = ROOT/'experiments/feeding_first_two_s0p/private'


def observation(n, x=0):
    return dict(id=n, mask=f'n:{n}', box=[float(x),0.,float(x+20),20.], area=400,
                score_birth=.99, presence=None,
                depth=dict(n=400, valid_fraction=1., median=1000., mad=2.),
                neighbors=[])


def protected_fixture(with_outside=False):
    bridge=NativeFirstGroupBridgeP(CONFIG)
    initial=[observation(7,0),observation(8,100)]
    if with_outside:
        initial.append(observation(9,200))
    bridge.commit_once(bridge.preview(1,1.,initial,{}))
    assert all(bridge.engine.bank[k]['anchor'] for k in (7,8))
    post=[observation(100,3),observation(101,103)]
    if with_outside:
        post.append(observation(9,201))
    snapshot={k:copy.deepcopy(bridge.engine.bank[k]) for k in (7,8)}
    episode=dict(id='TEST',generation=2,q=2,post_roles={100:[dict(frame=2,time=1.1,center=[13.,10.])],
                     101:[dict(frame=2,time=1.1,center=[113.,10.])]},member_sources=[7,8],
                 group_source=7,public_ids=[7,8],bank_snapshot=snapshot)
    bridge.engine.protected['TEST']=dict(episode='TEST',generation=2,
        member_public=[7,8],member_sources=[7,8],suppressed=[100,101],
        outputs={100:7,101:8})
    view=bridge.preview(2,1.1,post,{})
    return bridge,view,episode


class NativeFirstTests(unittest.TestCase):
    def test_source_old_no_event_equals_native_and_no_auto_accept(self):
        checks={'D1_DELAYED':0,'BIRTH_REFINE':0}
        for name,frames in (('feeding_000000_000199',200),
                            ('feeding_000351_000555',205)):
            engine=NativeFirstProtectedReturn(CONFIG)
            private=FEED/name
            for row,profiles in stream(private/'observations.jsonl.gz',
                                       private/'profiles.jsonl.gz',frames):
                ids,trace=engine.step(row['frame'],row['time'],row['observations'],profiles)
                self.assertEqual(ids,{o['id']:o['id'] for o in row['observations']})
                self.assertEqual(len(ids),len(set(ids.values())))
                self.assertFalse(engine.alias)
                for item in trace['native_first_auto_edge_checks']:
                    self.assertTrue(item['veto'])
                    checks[item['origin_rule']]+=1
                self.assertFalse(any(e.get('kind')=='reconnect' and e.get('accepted')
                                     for e in trace['events']))
        self.assertGreater(checks['D1_DELAYED'],0)
        self.assertGreater(checks['BIRTH_REFINE'],0)

    def test_event_stage_persists_as_real_engine_alias(self):
        bridge,view,episode=protected_fixture()
        transaction,error=bridge.stage_group_restore(view,episode,{100:8,101:7})
        self.assertIsNone(error)
        self.assertEqual(transaction['mapping'],{100:8,101:7})
        ids,_=bridge.commit_once(view,transaction)
        self.assertEqual(ids,{100:8,101:7})
        self.assertEqual({n:a['target'] for n,a in bridge.engine.alias.items()},ids)
        next_ids,_=bridge.commit_once(bridge.preview(3,1.2,
            [observation(100,5),observation(101,105)],{}))
        self.assertEqual(next_ids,ids)

    def test_invalid_stage_local_fallback_keeps_outside_state(self):
        bridge,view,episode=protected_fixture(with_outside=True)
        transaction,error=bridge.stage_group_restore(view,episode,{100:8,101:8})
        self.assertIsNone(transaction)
        self.assertEqual(error,'invalid_bijection')
        outside_bank=copy.deepcopy(view['engine'].bank[9])
        outside_epoch=bridge.epochs[9]
        fallback,detail=bridge.local_fallback(view,episode)
        self.assertTrue(detail['outside_mapping_and_ownership_equal'])
        self.assertEqual(fallback['engine'].bank[9],outside_bank)
        ids,_=bridge.commit_once(view,fallback)
        self.assertEqual(ids[9],9)
        self.assertEqual(bridge.epochs[9],outside_epoch)

    def test_preflight_defer_publication_and_causal_cutoff(self):
        root=HERE/'preflight'
        if not root.exists():
            self.skipTest('preflight replay has not been generated')
        q_count=0
        for name,frames in (('feeding_000000_000199',200),
                            ('feeding_000351_000555',205)):
            public=root/name/'public'
            with gzip.open(public/'predictions.jsonl.gz','rt',encoding='utf-8') as handle:
                predictions=[json.loads(line) for line in handle]
            self.assertEqual(len(predictions),frames)
            for row in predictions:
                variants=row['variants']
                self.assertEqual(variants['EVENT_NUM'],variants['EVENT_VLM'])
                masks=[o['mask'] for o in variants['SAM3_NATIVE']]
                for arm in ('Z4Q_FROZEN','EVENT_NUM','EVENT_VLM'):
                    self.assertEqual([o['mask'] for o in variants[arm]],masks)
                    self.assertEqual(len({o['id'] for o in variants[arm]}),len(masks))
            with (public/'PUBLISH_LEDGER.jsonl').open(encoding='utf-8') as handle:
                ledger=[json.loads(line) for line in handle]
            self.assertEqual(len(ledger),frames)
            for item in ledger:
                for arm,event in item['event_publish'].items():
                    q_count+=1
                    self.assertEqual(item['frame'],event['q'])
                    self.assertEqual(event['post_sample_count'],1)
                    self.assertEqual(len(event['first_public_pair']),2)
                    self.assertEqual(len(set(event['first_public_pair'].values())),2)
            requests=public/'requests'
            if requests.exists():
                for path in requests.glob('*-S0.json'):
                    packet=json.loads(path.read_text(encoding='utf-8'))
                    cutoff=int(packet['user'].split('当前证据截止：',1)[1].split('\n',1)[0])
                    self.assertTrue(all(image['frame']<=cutoff for image in packet['images']))
                    self.assertFalse(any(image['frame']>cutoff for image in packet['images']))
                    self.assertEqual(ledger[cutoff-1]['frame'],cutoff)
        self.assertGreater(q_count,0)


if __name__=='__main__':
    unittest.main()
