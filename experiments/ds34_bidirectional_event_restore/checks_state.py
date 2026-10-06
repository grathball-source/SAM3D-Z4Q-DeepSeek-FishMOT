"""Focused actual Z4Q state transactions on synthetic observations; no GT or API."""
import copy
import json
import unittest
from unittest.mock import patch

from common import CONFIG_PATH, CFG, read, digest
from transaction import GroupBridge, Bridge, StableReturn, engine_state, bridge_hash, outside_state
from manager import EventManager
import numpy as np
from pycocotools import mask as coco


def observation(n, x=5, z=1000., neighbors=(), width=10, area=None):
    return dict(id=n, mask=f'n:{n}', box=[x,10,x+width,20], area=width*10 if area is None else area,
                score_birth=.9, presence=.9, neighbors=list(neighbors),
                depth=dict(n=100,valid_fraction=1.,median=z,mad=1.))


def packet(frame, objects, now=None):
    row = dict(frame=frame, global_frame=frame, time=frame/10 if now is None else now,
               observations=objects, native=[dict(id=o['id'],mask=o['mask']) for o in objects])
    profiles = {o['id']:dict(id=o['id'],mask=o['mask'],frame=frame,
                  core=copy.deepcopy(o['depth']),whole=copy.deepcopy(o['depth'])) for o in objects}
    masks = {}
    for o in objects:
        m = np.zeros((32,96),dtype=np.uint8)
        if o['area']:
            x,y,a,b=map(int,o['box']);m[y:b,x:a]=1
        rle=coco.encode(np.asfortranarray(m));rle['counts']=rle['counts'].decode('ascii')
        masks[o['mask']]=rle
    return row,profiles,dict(masks=masks)


def hit(frame=8):
    return dict(frame=frame,sources=[1,2],group=1,donor=2,
                donor_reference_area=100,group_reference_area=100)


def prepare(suspects=None):
    branch=GroupBridge(read(CONFIG_PATH));assignments={}
    manager=EventManager('CHECK',branch,[hit()] if suspects is None else suspects,CFG,assignments)
    for f in range(1,8):
        objects=[observation(1),observation(2,25,1400.,(7,) if f==6 else (8,) if f==7 else ())]
        objects += [observation(7 if f<=6 else 8,70,1700.,(2,) if f>=6 else ())]
        row,profiles,assignment=packet(f,objects);assignments[f]=assignment
        manager.before(row,profiles);branch.commit_once(branch.preview(f,row['time'],objects,profiles));manager.after(row,profiles)
    assert branch.previous[8]==7 and branch.engine.alias[8]['target']==7
    return branch,manager,assignments


def advance(branch,manager,assignments,frame,objects=None,now=None):
    objects=objects if objects is not None else ([observation(1,width=30),observation(2,25,1400.,area=0),
        observation(8,70,1700.)] if frame<=9 else [observation(1),observation(3,25,1400.),observation(8,70,1700.)])
    row,profiles,assignment=packet(frame,objects,now);assignments[frame]=assignment
    signal=manager.before(row,profiles);view=branch.preview(frame,row['time'],objects,profiles)
    branch.commit_once(view);manager.after(row,profiles)
    return row,profiles,view,signal


class StateChecks(unittest.TestCase):
    def test_no_event_exact_original_full_state(self):
        branch=GroupBridge(read(CONFIG_PATH));baseline=Bridge(read(CONFIG_PATH))
        for f in range(1,15):
            objects=[observation(1),observation(2,25,1400.)]
            row,profiles,_=packet(f,objects)
            ids,_=branch.commit_once(branch.preview(f,row['time'],objects,profiles))
            old,_=baseline.commit_once(baseline.preview(f,row['time'],objects,profiles))
            self.assertEqual(ids,old);self.assertEqual(engine_state(branch.engine),vars(baseline.engine))
            self.assertEqual((branch.previous,branch.epochs,branch.provenance),(baseline.previous,baseline.epochs,baseline.provenance))

    def test_group_post_anonymous_and_readiness(self):
        b,m,a=prepare();advance(b,m,a,8);frozen=copy.deepcopy(m.active['bank_snapshot'])
        for f in (9,10,11,12):
            advance(b,m,a,f)
            self.assertEqual({k:b.engine.bank[k] for k in (1,2)},frozen)
            for n in m.frame_class:self.assertFalse(m.clean.get(n))
        e=m.active
        self.assertEqual(e['q'],10);self.assertTrue(e['ready'])
        self.assertEqual({n:[p['frame'] for p in v] for n,v in e['confirmed_post_roles'].items()},{1:[10,11,12],3:[10,11,12]})
        self.assertEqual(b.engine.alias[8]['target'],7)

    def test_real_joint_alias_commit_q_only_and_ongoing_state(self):
        b,m,a=prepare();advance(b,m,a,8);advance(b,m,a,9);checkpoint=copy.deepcopy(b)
        window=[]
        for f in (10,11,12):
            r,p,_,_=advance(b,m,a,f);window.append((r,p))
            if f==10:qspec=copy.deepcopy(b.engine.protected[m.active['id']])
        e=copy.deepcopy(m.active);selected=checkpoint;selected.engine.protected={e['id']:qspec}
        r,p=window[0];view=selected.preview(10,r['time'],r['observations'],p);before=bridge_hash(selected)
        tx,error=selected.stage_group_restore(view,e,{1:2,3:1})
        self.assertIsNone(error);self.assertIsNotNone(tx);self.assertEqual(bridge_hash(selected),before)
        self.assertEqual(outside_state(tx['engine'],{1,2,3},{1,2}),outside_state(view['engine'],{1,2,3},{1,2}))
        ids,_=selected.commit_once(view,tx);self.assertEqual(ids,{1:2,3:1,8:7})
        self.assertEqual(selected.engine.alias[1]['target'],2);self.assertEqual(selected.engine.alias[3]['target'],1)
        for k in (1,2):
            self.assertTrue(all(t<=1.0 for t,_ in selected.engine.bank[k]['motion']))
            self.assertEqual(selected.engine.bank[k]['anchor']['frame'],10)
        for r,p in window[1:]:
            ids,_=selected.commit_once(selected.preview(r['frame'],r['time'],r['observations'],p))
            self.assertEqual(ids,{1:2,3:1,8:7})
        self.assertEqual(selected.provenance[1]['source'],'DS34_EVENT_NUMERIC')
        self.assertEqual(selected.engine.alias[8]['target'],7)

    def test_invalid_bijection_stale_generation_and_occupation_atomic(self):
        b,m,a=prepare();advance(b,m,a,8);advance(b,m,a,9)
        row,profiles,assignment=packet(10,[observation(1),observation(3,25,1400.),observation(8,70,1700.)]);a[10]=assignment
        m.before(row,profiles);view=b.preview(10,1.,row['observations'],profiles);before=bridge_hash(b)
        for mapping,error in (({1:1,3:1},'invalid_bijection'),):
            tx,why=b.stage_group_restore(view,m.active,mapping);self.assertIsNone(tx);self.assertEqual(why,error)
        bad=copy.deepcopy(m.active);bad['generation']+=1
        self.assertEqual(b.stage_group_restore(view,bad,{1:2,3:1})[1],'stale_generation')
        stale=copy.deepcopy(view);stale['version']+=1
        self.assertEqual(b.stage_group_restore(stale,m.active,{1:2,3:1})[1],'stale_episode')
        later=copy.deepcopy(m.active);later['post_roles'][1][-1]['time']+=.1
        self.assertEqual(b.stage_group_restore(view,later,{1:2,3:1})[1],'q_observation_time_source_or_generation_mismatch')
        changed_generation=copy.deepcopy(m.active);changed_generation['post_generations'][1]+=1
        self.assertEqual(b.stage_group_restore(view,changed_generation,{1:2,3:1})[1],'q_observation_time_source_or_generation_mismatch')
        occupied=copy.deepcopy(view);occupied['mapping'][8]=2
        self.assertEqual(b.stage_group_restore(occupied,m.active,{1:2,3:1})[1],'occupied_target')
        changed=copy.deepcopy(view);changed['engine'].bank[1]['clean_time']+=1
        self.assertEqual(b.stage_group_restore(changed,m.active,{1:2,3:1})[1],'protected_reference_changed')
        self.assertEqual(bridge_hash(b),before)

    def test_protected_exception_restores_reference_fields(self):
        b,m,a=prepare();advance(b,m,a,8);before=bridge_hash(b);engine=copy.deepcopy(b.engine)
        row,p,_=packet(9,[observation(1,width=30),observation(2,25,1400.,area=0),observation(8,70,1700.)])
        frozen={k:copy.deepcopy(engine.bank[k]) for k in (1,2)}
        with patch.object(StableReturn,'step',side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):engine.step(9,.9,row['observations'],p)
            with self.assertRaises(RuntimeError):b.preview(9,.9,row['observations'],p)
        self.assertEqual({k:engine.bank[k] for k in (1,2)},frozen);self.assertEqual(bridge_hash(b),before)

    def test_all_scan_records_retained(self):
        first=hit();second=dict(hit(),group=2,donor=1)
        b,m,a=prepare([first,second,hit(9)])
        advance(b,m,a,8);advance(b,m,a,9)
        self.assertEqual([x['status'] for x in m.scan_records],['FIRST_RECORD_ATTEMPT','SAME_FRAME_OVERLAP','ACTIVE_EPISODE_OVERLAP'])
        self.assertEqual(len(m.events),1)

    def test_post_generation_break_keeps_q_and_protection(self):
        b,m,a=prepare();advance(b,m,a,8);advance(b,m,a,9);advance(b,m,a,10)
        advance(b,m,a,11,[observation(1),observation(8,70,1700.)])
        self.assertEqual(m.active['q'],10);self.assertFalse(m.active['ready']);self.assertTrue(m.active['post_broken'])
        self.assertEqual(m.close_reason,'UNKNOWN_POST_SOURCE_BREAK');self.assertIn(m.active['id'],b.engine.protected)

    def test_dirty_q_later_first_clean_three_and_timeout(self):
        b,m,a=prepare();advance(b,m,a,8);advance(b,m,a,9)
        advance(b,m,a,10,[observation(1,neighbors=(3,)),observation(3,25,1400.,(1,)),observation(8,70,1700.)])
        self.assertEqual(m.active['q'],10);self.assertFalse(m.active['ready'])
        for f in (11,12,13):advance(b,m,a,f)
        self.assertTrue(m.active['ready']);self.assertEqual([p['frame'] for p in m.active['confirmed_post_roles'][1]],[11,12,13])
        self.assertEqual([p['frame'] for p in m.active['post_roles'][1]],[10,11,12,13])
        advance(b,m,a,14,now=12.)
        self.assertEqual(m.close_reason,'UNKNOWN_EPISODE_TIMEOUT');self.assertEqual(m.active['q'],10)

    def test_local_fallback_preserves_outside_existing_fix(self):
        b,m,a=prepare();advance(b,m,a,8);advance(b,m,a,9)
        row,p,assignment=packet(10,[observation(1),observation(3,25,1400.),observation(8,70,1700.)]);a[10]=assignment
        m.before(row,p);view=b.preview(10,1.,row['observations'],p);before=bridge_hash(b)
        tx,detail=b.local_fallback(view,m.active)
        self.assertEqual(outside_state(tx['engine'],{1,2,3},{1,2,3}),outside_state(view['engine'],{1,2,3},{1,2,3}))
        self.assertEqual(tx['mapping'][8],7);self.assertEqual(tx['engine'].alias[8]['target'],7)
        self.assertEqual(bridge_hash(b),before)

    def test_pre_split_cancel_local_release_real_continuity(self):
        b,m,a=prepare();advance(b,m,a,8);reserved=copy.deepcopy(m.active['bank_snapshot'])
        row,p,assignment=packet(9,[observation(1,width=30),observation(2,25,1400.),observation(8,70,1700.)]);a[9]=assignment
        m.before(row,p);self.assertIsNotNone(m.release_episode)
        view=b.preview(9,.9,row['observations'],p);before=bridge_hash(b)
        tx,detail=b.local_release(view,m.release_episode)
        self.assertEqual(bridge_hash(b),before);self.assertEqual(tx['mapping'][8],7)
        ids,_=b.commit_once(view,tx);m.after(row,p);m.finish(9,'CANCELLED_NO_PERSISTENT_COLLAPSE')
        self.assertEqual(ids,{1:1,2:2,8:7});self.assertEqual(b.engine.alias[8]['target'],7)
        self.assertEqual({k:b.engine.bank[k] for k in (1,2)},reserved);self.assertFalse(b.engine.protected)

    def test_unresolved_fallback_does_not_publish_nonexistent_bank_identity(self):
        b,m,a=prepare();advance(b,m,a,8)
        advance(b,m,a,9,[observation(3,width=30),observation(1,area=0),observation(2,25,1400.,area=0),observation(8,70,1700.)])
        b.engine.alias[99]=dict(target=2,anchor=copy.deepcopy(b.engine.bank[2]['anchor']),commit_frame=9)
        row,p,assignment=packet(10,[observation(3),observation(4,25,1400.),observation(8,70,1700.)]);a[10]=assignment
        m.before(row,p);view=b.preview(10,1.,row['observations'],p);before=bridge_hash(b)
        tx,detail=b.local_fallback(view,m.active)
        self.assertEqual(detail['status'],'LOCAL_FALLBACK_UNRESOLVED');self.assertEqual(bridge_hash(b),before)
        self.assertNotIn(0,tx['engine'].bank);self.assertEqual(tx['mapping'],{8:7,3:3,4:4})
        self.assertEqual(tx['engine'].alias[99],b.engine.alias[99])
        b.commit_once(view,tx)
        row,p,_=packet(11,[observation(3),observation(4,25,1400.),observation(8,70,1700.)])
        ids,_=b.commit_once(b.preview(11,1.1,row['observations'],p))
        self.assertEqual(ids,{3:3,4:4,8:7});self.assertEqual(b.engine.alias[99]['target'],2)

    def test_unselected_member_residual_rejects_alias_return_cascade(self):
        b,m,a=prepare();advance(b,m,a,8);advance(b,m,a,9)
        row,p,assignment=packet(10,[observation(1),observation(3,25,1400.),observation(2,25,1400.,area=0),observation(8,70,1700.)]);a[10]=assignment
        m.before(row,p);view=b.preview(10,1.,row['observations'],p)
        tx,error=b.stage_group_restore(view,m.active,{1:2,3:1})
        self.assertIsNone(tx);self.assertEqual(error,'UNSELECTED_MEMBER_OWNERSHIP')
        fallback,_=b.local_fallback(view,m.active);b.commit_once(view,fallback)
        row,p,_=packet(11,[observation(1),observation(3,25,1400.),observation(2,25,1400.),observation(8,70,1700.)])
        ids,_=b.commit_once(b.preview(11,1.1,row['observations'],p))
        self.assertEqual(len(ids),len(set(ids.values())));self.assertEqual(ids[8],7)

    def test_qualified_and_unqualified_event_alias_return_current_frame_only(self):
        for returned_at in (13,41):
            b,m,a=prepare();advance(b,m,a,8);advance(b,m,a,9)
            row,p,assignment=packet(10,[observation(1),observation(3,25,1400.),observation(8,70,1700.)]);a[10]=assignment
            m.before(row,p);view=b.preview(10,1.,row['observations'],p)
            tx,error=b.stage_group_restore(view,m.active,{1:2,3:1});self.assertIsNone(error);b.commit_once(view,tx)
            for f in range(11,returned_at):
                row,p,_=packet(f,[observation(1),observation(3,25,1400.),observation(8,70,1700.)]);b.commit_once(b.preview(f,row['time'],row['observations'],p))
            prior=bridge_hash(b);oldbank=copy.deepcopy(b.engine.bank)
            row,p,_=packet(returned_at,[observation(1),observation(2,25,1400.,area=0),observation(3,25,1400.),observation(8,70,1700.)])
            unqualified=b.preview(returned_at,row['time'],row['observations'],p)
            self.assertEqual(unqualified['mapping'],{1:2,2:-3,3:1,8:7})
            self.assertNotIn('ds34_event_return_cascade',unqualified['trace']);self.assertEqual(bridge_hash(b),prior)
            row,p,_=packet(returned_at,[observation(1),observation(2,25,1400.),observation(3,25,1400.),observation(8,70,1700.)])
            qualified=b.preview(returned_at,row['time'],row['observations'],p)
            self.assertEqual(qualified['mapping'],{1:1,2:2,3:3,8:7});self.assertEqual(bridge_hash(b),prior)
            self.assertEqual(qualified['engine'].alias[8],b.engine.alias[8]);self.assertEqual(qualified['trace']['ds34_event_return_cascade']['event_aliases_revoked'],[3])
            self.assertFalse(qualified['trace']['ds34_event_return_cascade']['bank_copied'])
            self.assertTrue({1,3}<=qualified['engine'].retired);self.assertEqual(b.engine.bank,oldbank)
            b.commit_once(qualified);self.assertEqual(b.previous,{1:1,2:2,3:3,8:7})

    def test_outside_alias_component_cannot_be_changed_by_group_restore(self):
        b,m,a=prepare();advance(b,m,a,8);advance(b,m,a,9)
        b.engine.alias[99]=dict(target=3,anchor=copy.deepcopy(b.engine.bank[1]['anchor']),commit_frame=9)
        row,p,assignment=packet(10,[observation(1),observation(3,25,1400.),observation(8,70,1700.)]);a[10]=assignment
        m.before(row,p);view=b.preview(10,1.,row['observations'],p);before=bridge_hash(b)
        tx,error=b.stage_group_restore(view,m.active,{1:2,3:1})
        self.assertIsNone(tx);self.assertEqual(error,'OUTSIDE_ALIAS_OWNERSHIP');self.assertEqual(bridge_hash(b),before)

    def test_actual_original_d1_alias_competition_without_canonical_return(self):
        b,m,a=prepare();advance(b,m,a,8);advance(b,m,a,9)
        row,p,assignment=packet(10,[observation(1),observation(3,25,1400.),observation(8,70,1700.)]);a[10]=assignment
        m.before(row,p);view=b.preview(10,1.,row['observations'],p)
        tx,error=b.stage_group_restore(view,m.active,{1:2,3:1});self.assertIsNone(error);b.commit_once(view,tx)
        for f in (11,12):
            row,p,_=packet(f,[observation(1),observation(3,25,1400.),observation(8,70,1700.)]);b.commit_once(b.preview(f,row['time'],row['observations'],p))
        accepted=[]
        for f in range(13,18):
            row,p,_=packet(f,[observation(4,z=1000.),observation(3,25,1400.),observation(8,70,1700.)])
            _,trace=b.commit_once(b.preview(f,row['time'],row['observations'],p))
            accepted.extend(e for e in trace.get('events',[]) if e.get('kind')=='reconnect' and e.get('accepted'))
        self.assertTrue(any(e['native_id']==4 and e['canonical_id']==2 for e in accepted))
        self.assertEqual(b.engine.alias[4]['target'],2)
        row,p,_=packet(18,[observation(1),observation(4,z=1000.),observation(3,25,1400.),observation(8,70,1700.)])
        before=bridge_hash(b);view=b.preview(18,1.8,row['observations'],p)
        self.assertEqual(bridge_hash(b),before);self.assertEqual(view['mapping'],{1:1,3:3,4:2,8:7})
        self.assertEqual(view['trace']['ds34_event_return_cascade']['actual_qualified_returns'],[])
        self.assertEqual(view['trace']['ds34_event_return_cascade']['event_aliases_revoked'],[3])
        self.assertEqual(view['engine'].alias[4],b.engine.alias[4]);self.assertEqual(view['engine'].alias[8],b.engine.alias[8])


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(StateChecks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps(dict(status='PASS' if result.wasSuccessful() else 'FAIL',checks=result.testsRun,
        no_GT=True,model_http=0,cost_usd=0,actual_original_engine=True)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
