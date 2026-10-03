"""Event-local state semantics using real measurement/binding code; no GT or API."""
import copy
import unittest
from unittest.mock import patch

import numpy as np

from common import HERE, DS18, module

C = module('ds19_contract_controller', HERE/'controller.py')
T = module('ds19_contract_old_fixtures', DS18/'test_controller.py')
M = T.M
CONFIG = T.CONFIG
from pycocotools import mask as coco


def plain(value):
    if isinstance(value,dict):return {repr(k):plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [plain(v) for v in value]
    if isinstance(value,set):return sorted(map(repr,value))
    if isinstance(value,np.ndarray):return value.tolist()
    return value


def state(branch):
    return plain(dict(engine=vars(branch.engine), previous=branch.previous,
        epochs=branch.epochs, provenance=branch.provenance, version=branch.version))


def actual_input(branch, frame, objects, *, now=None, neighbors=None,
                 manager=None, guarded=False, source_generation=1, shared_source=None):
    """All changes occur before measuring; no certificate/eligibility is fabricated."""
    now = frame/30. if now is None else now
    depth = np.full((64, 200), 1500., dtype='f4')
    index = np.arange(depth.size, dtype='i4').reshape(depth.shape)
    masks = {}
    for native, x, z in objects:
        mask = np.zeros(depth.shape, bool)
        mask[20:44, x:x+24] = True
        masks[native] = mask
        depth[mask] = z
    if shared_source is not None:
        donor,receiver=shared_source
        index[masks[receiver]]=index[masks[donor]]
    certificates = M.measure_mixed(depth, index, masks, 'synthetic', frame, frame-1,
        source_binding=dict(frame=frame, global_frame=frame-1, time=now,
                            GT_read=False, RGB_read=False), native_depth=depth)['objects']
    observations, profiles = [], {}
    for native, x, z in objects:
        whole = copy.deepcopy(certificates[native]['whole']['inclusive_summary'])
        profiles[native] = dict(id=native, mask=f'n:{native}', frame=frame,
            whole=copy.deepcopy(whole), core=copy.deepcopy(
                certificates[native]['birth_core']['inclusive_summary']))
        observations.append(dict(id=native, mask=f'n:{native}', box=[x,20,x+24,44],
            area=576, presence=.99, score_birth=.99,
            neighbors=(neighbors or {}).get(native, []), depth=whole))
    row = dict(frame=frame, global_frame=frame-1, time=now, observations=observations)
    if manager is not None:
        rles = {}
        for native, mask in masks.items():
            rle = coco.encode(np.asfortranarray(mask.astype('u1')))
            rle['counts'] = rle['counts'].decode('ascii')
            rles[f'n:{native}'] = rle
        manager.assignments[frame] = dict(masks=rles)
        manager.before(row, profiles)
    versions = {n:['synthetic','TEST',source_generation,
        branch.previous.get(n),branch.epochs.get(n)] for n in masks}
    classes = manager.frame_class if manager else branch.engine.observation_classes
    for native, cls in classes.items():
        if native in versions and cls in T.C.ANONYMOUS_CLASSES:
            versions[native][3:] = [None,None]
    sources = {n:['synthetic','TEST',n,source_generation] for n in masks}
    bound, bound_profiles = M.guard_inputs(row, profiles, certificates,
        source_versions=sources, versions=versions, screen=guarded)
    branch.configure_evidence(frame, certificates=certificates, source_versions=sources,
        identity_versions=versions, guarded=guarded)
    return bound, bound_profiles, certificates


class Slice:
    """An isolated D1 return with a genuinely anonymous other member.

    A real synthetic clock gap ages the other member's clean reference beyond
    D1's six-second reservation range, while the target's actual contact and
    last_seen are recent and its original twelve-second clean window remains.
    Birth's no_verified_local_survivor gate is retained. Original D1 needs five
    consecutive accepted proposals; neither qualified nor accepted is set here.
    """
    def __init__(self, enabled=True, guarded=False, legacy=False, outside_fix=False):
        self.branch = T.C.EventBridge(CONFIG) if legacy else C.EventBridge(CONFIG, local_return=enabled)
        manager_class = T.C.EventManager if legacy else C.EventManager
        self.manager = manager_class('MIXED_RETURN' if guarded else 'ACTIVITY_RETURN',
            self.branch, {}, dict(max_episode_seconds=10.), {})
        self.guarded = guarded
        self.outside = 19 if outside_fix else 9
        self.published = []
        for frame in range(1,11):
            neighbors = {1:[2],2:[1]} if frame==10 else None
            outside = self.outside if frame==10 else 9
            self.advance(frame, ((1,20,1000.),(2,80,1040.),(outside,140,1250.)),
                neighbors=neighbors, associate=False,
                outside_changes={19:9} if outside_fix and frame==10 else None)
        self.entry = {k:copy.deepcopy(self.branch.engine.bank[k]) for k in (1,2)}
        pre = {role:copy.deepcopy(list(self.manager.clean.get(native) or
                    self.manager.last_clean.get(native, [])))
               for role,native in zip(('A','B'),(1,2))}
        self.episode = dict(id='TEST', generation=11, q=None,
            member_sources=[1,2], group_source=2, public_ids=[1,2],
            minimum_restored_area=300., bank_snapshot=copy.deepcopy(self.entry),
            pre=pre, pre_risk={'A':[],'B':[]}, suspect_frame=11, suspect_time=8.,
            source_suspect=dict(donor=1,donor_reference_area=576.,
                               group_reference_area=576.),
            confirm_frame=None, group=[], group_anonymous=[], post_roles={},
            post_start=None, split_confirm=None, split_first_frame=None,
            evidence_cutoff_frame=None, end=None, status='SUSPECT',
            temporary_choice='H1', numeric=None, temporary_ids={},
            depth_rule=copy.deepcopy(CONFIG))
        self.manager.active = self.episode
        self.manager.events.append(self.episode)
        self.advance(11, ((1,20,1000.),(2,80,1040.),(self.outside,140,1250.)),
            now=8., neighbors={1:[2],2:[1]}, associate=False)

    def view(self, frame, objects=None, **kwargs):
        objects = objects or ((3,20,1000.),(2,80,1040.),(self.outside,140,1250.))
        kwargs.setdefault('now', 8.+(frame-11)/30.)
        row, profiles, certs = actual_input(self.branch,frame,objects,
            manager=self.manager,guarded=self.guarded,**kwargs)
        return self.branch.preview(frame,row['time'],row['observations'],profiles), row, profiles, certs

    def advance(self, frame, objects=None, associate=True, outside_changes=None, **kwargs):
        if not hasattr(self,'episode'):
            row, profiles, certs = actual_input(self.branch,frame,objects,
                manager=self.manager,guarded=self.guarded,**kwargs)
            view=self.branch.preview(frame,row['time'],row['observations'],profiles)
        else:
            view,row,profiles,certs=self.view(frame,objects,**kwargs)
        tx,error=(self.branch.stage_event_return(view,self.episode)
                  if associate and self.manager.active and hasattr(self.branch,'stage_event_return')
                  else (None,None))
        if outside_changes is not None:
            tx,error=self.branch.stage(view,outside_changes)
            assert tx is not None and error is None,(outside_changes,error)
        ids,trace=self.branch.commit_once(view,tx)
        if tx is not None and tx.get('return_record'):
            self.manager.record_event_return(frame,tx)
        self.manager.after(row,profiles)
        self.published.append(dict(frame=frame,mapping=copy.deepcopy(ids)))
        return view,tx,error,trace,certs

    def restore(self):
        actions=[]
        for frame in range(12,17):
            actions.append(self.advance(frame))
        return actions


class EventReturnTests(unittest.TestCase):
    def restored(self, **kwargs):
        case=Slice(**kwargs)
        actions=case.restore()
        self.assertEqual(case.branch.previous.get(3),1,
            'The original five-confirmation D1 fixture must have a legal event return')
        self.assertEqual(case.episode['q'],None)
        self.assertTrue(any(tx and tx.get('changes') for _,tx,_,_,_ in actions))
        return case,actions

    def test_original_d1_confirmation_and_commit_before_single_publication(self):
        case,actions=self.restored()
        accepted=[]
        for view,tx,error,trace,certs in actions:
            if tx:
                accepted.extend(e for e in tx['trace'].get('events',[])
                    if e.get('kind')=='reconnect' and e.get('accepted') and e.get('native_id')==3)
            self.assertEqual(len(case.published),len({p['frame'] for p in case.published}))
            self.assertTrue(all(M.validate_certificate(c) for c in certs.values()))
        self.assertTrue(accepted)
        self.assertEqual(accepted[-1]['origin_rule'],'D1_DELAYED')
        self.assertIn('association_evidence_bindings',accepted[-1])
        self.assertEqual(accepted[-1]['association_evidence_sha256'],
                         M._digest(accepted[-1]['association_evidence_bindings']))
        self.assertGreaterEqual(accepted[-1]['confirmations'],case.branch.engine.cfg['confirm'])
        self.assertEqual(case.branch.engine.birth[3],(12,8.+1/30.))
        self.assertEqual(case.branch.engine.source_first_publication[3],dict(frame=12,public_id=3))
        self.assertEqual(case.published[-1]['mapping'][3],1)
        self.assertEqual(len(case.branch.previous),len(set(case.branch.previous.values())))

    def test_partial_live_update_keeps_other_reference_and_entry_registry(self):
        case,_=self.restored()
        entry=copy.deepcopy(case.episode['bank_snapshot'])
        other=T.C.clean_reference(case.branch.engine.bank[2])
        other_views=copy.deepcopy(case.branch.engine.view_bank[2])
        registry=copy.deepcopy(case.branch.engine.identity_reference_registry)
        anchor=copy.deepcopy(case.branch.engine.bank[1].get('anchor'))
        case.advance(17,objects=((3,20,1003.),(2,80,1040.),(9,140,1250.)))
        self.assertEqual(case.branch.previous[3],1)
        self.assertEqual(case.branch.engine.bank[1]['anchor']['frame'],17)
        self.assertNotEqual(case.branch.engine.bank[1]['anchor'],anchor)
        self.assertEqual(T.C.clean_reference(case.branch.engine.bank[2]),other)
        self.assertEqual(case.branch.engine.view_bank[2],other_views)
        self.assertEqual(case.branch.engine.identity_reference_registry,registry)
        self.assertEqual(case.episode['bank_snapshot'],entry)

    def test_timeout_retains_return_and_outside_fix(self):
        case,_=self.restored()
        before=copy.deepcopy(case.branch.engine.alias[3])
        case.advance(18,now=18.1)
        self.assertIsNone(case.manager.active)
        self.assertEqual(case.episode['status'],'TIMEOUT')
        self.assertEqual(case.branch.engine.alias[3],before)
        self.assertEqual(case.branch.previous[3],1)
        self.assertEqual(case.branch.previous[9],9)
        self.assertFalse(case.branch.engine.protected)

    def test_late_real_q_does_not_reject_returned_live_reference(self):
        case,_=self.restored()
        view,row,profiles,certs=case.view(17,
            objects=((3,67,1000.),(2,93,1040.),(9,140,1250.)))
        self.assertEqual(case.episode['q'],17,'The original two-mask coverage rule must create q')
        self.assertTrue(all(len(v)==1 and v[0]['frame']==17
                            for v in case.episode['post_roles'].values()))
        tx,error=case.branch.stage_group_restore(view,case.episode,{3:1,2:2})
        self.assertIsNone(error)
        self.assertIsNotNone(tx)
        ids,_=case.branch.commit_once(view,tx)
        self.assertEqual(ids[3],1)
        self.assertEqual(ids[2],2)
        self.assertEqual(ids[9],9)

    def test_conflicting_late_q_cannot_undo_return(self):
        case,_=self.restored()
        view,_,_,_=case.view(17,objects=((3,67,1000.),(2,93,1040.),(9,140,1250.)))
        before=state(case.branch)
        tx,error=case.branch.stage_group_restore(view,case.episode,{3:2,2:1})
        self.assertIsNone(tx)
        self.assertTrue(error)
        self.assertEqual(state(case.branch),before)
        fallback,_=case.branch.local_fallback(view,case.episode)
        ids,_=case.branch.commit_once(view,fallback)
        self.assertEqual(ids[3],1)

    def test_disabled_matches_frozen_ds18_publication_and_state(self):
        case=Slice(enabled=False)
        case.restore()
        other=Slice(legacy=True)
        other.restore()
        self.assertEqual(case.published,other.published)
        for name in ('bank','view_bank','alias','birth','pending','first_eligible',
                     'native_runs','recent_core','identity_reference_registry',
                     'reference_bindings','depth_history_bindings','source_activity',
                     'pending_birth','source_first_publication'):
            self.assertEqual(plain(getattr(case.branch.engine,name)),
                             plain(getattr(other.branch.engine,name)),name)
        for name in ('previous','epochs','provenance','version'):
            self.assertEqual(getattr(case.branch,name),getattr(other.branch,name),name)
        self.assertEqual(case.branch.previous[3],3)

    def test_partial_preserves_actual_prior_outside_transaction(self):
        case=Slice(outside_fix=True)
        provenance=copy.deepcopy(case.branch.provenance[19])
        epoch=case.branch.epochs[19]
        outside_alias=copy.deepcopy(case.branch.engine.alias[19])
        actions=case.restore()
        self.assertEqual(case.branch.previous[3],1)
        self.assertEqual(case.branch.previous[19],9)
        self.assertEqual(case.branch.engine.alias[19],outside_alias)
        self.assertEqual(case.branch.provenance[19],provenance)
        self.assertEqual(case.branch.epochs[19],epoch)
        for view,tx,_,_,_ in actions:
            if tx:
                for name in ('bank','view_bank','alias','source_activity'):
                    key=19 if name in ('alias','source_activity') else 9
                    self.assertEqual(getattr(tx['engine'],name)[key],
                                     getattr(view['engine'],name)[key])

    def accepted_view(self):
        case=Slice()
        for frame in range(12,16):case.advance(frame)
        view,row,profiles,certs=case.view(16)
        proposal=view.get('event_return_proposal',{})
        self.assertTrue(proposal.get('trace',{}).get('ds19_natural_event_returns'),
                        'Failure tests must begin with a genuinely accepted original candidate')
        return case,view,row,profiles,certs

    def test_preview_and_stage_do_not_write_authoritative_state(self):
        case,view,_,_,_=self.accepted_view()
        before=state(case.branch)
        tx,error=case.branch.stage_event_return(view,case.episode)
        self.assertIsNone(error)
        self.assertIsNotNone(tx)
        self.assertEqual(state(case.branch),before)
        case.branch.commit_once(view,tx)
        with self.assertRaises(AssertionError):case.branch.commit_once(view,tx)

    def test_exception_in_proposal_and_stage_has_no_state_leak(self):
        case=Slice()
        row,profiles,_=actual_input(case.branch,12,
            ((3,20,1000.),(2,80,1040.),(9,140,1250.)),now=8.+1/30.,manager=case.manager)
        before=state(case.branch)
        original=C.EventReturn.step
        def exploding(trial,*args,**kwargs):
            result=original(trial,*args,**kwargs)
            if trial.return_proposal:raise RuntimeError('synthetic proposal exception after clone writes')
            return result
        with patch.object(C.EventReturn,'step',exploding):
            with self.assertRaises(RuntimeError):
                case.branch.preview(12,row['time'],row['observations'],profiles)
        self.assertEqual(state(case.branch),before)
        case,view,_,_,_=self.accepted_view()
        before=state(case.branch)
        with patch.object(C.EventBridge,'_outside_equal',side_effect=RuntimeError('synthetic stage exception')):
            with self.assertRaises(RuntimeError):case.branch.stage_event_return(view,case.episode)
        self.assertEqual(state(case.branch),before)

    def test_occupied_target_and_changed_entry_reject_without_pollution(self):
        for kind in ('occupied','anchor'):
            case,view,_,_,_=self.accepted_view()
            if kind=='occupied':
                # An actual observed outside owner is added to the same semantic
                # snapshot. No candidate hash/measurement is changed.
                view['mapping'][9]=1
            else:
                # This is another genuinely generated bank reference, but it is
                # not the target against which this original candidate was made.
                case.episode['bank_snapshot'][1]=copy.deepcopy(case.entry[2])
            before=state(case.branch)
            tx,error=case.branch.stage_event_return(view,case.episode)
            self.assertIsNone(tx,kind)
            self.assertTrue(error,kind)
            self.assertEqual(state(case.branch),before,kind)

    def test_consistently_rebound_current_generation_rejects_old_proposal(self):
        case,view,_,_,_=self.accepted_view()
        row,profiles,_=actual_input(case.branch,16,
            ((3,20,1000.),(2,80,1040.),(9,140,1250.)),now=8.+5/30.,
            source_generation=2)
        engine=view['engine']
        engine.configure_evidence(16,case.branch.engine.certificates,
            case.branch.engine.source_versions,case.branch.engine.identity_versions,False)
        engine._step_observations={o['id']:o for o in row['observations']}
        engine._step_profiles=profiles
        self.assertIsNotNone(engine.current_binding(3,'D1_WHOLE',
            engine._step_observations[3]['depth'],engine._step_observations[3]),
            'The new source chain is internally valid; rejection must be semantic')
        before=state(case.branch)
        tx,error=case.branch.stage_event_return(view,case.episode)
        self.assertIsNone(tx)
        self.assertIn('version',error)
        self.assertEqual(state(case.branch),before)

    def test_shared_mask_and_native_source_do_not_certify_return(self):
        for duplicate_mask in (False,True):
            case=Slice()
            objects=((3,80 if duplicate_mask else 20,1000.),(2,80,1000.),(9,140,1250.))
            row,profiles,certs=actual_input(case.branch,12,objects,now=8.+1/30.,
                shared_source=None if duplicate_mask else (2,3))
            self.assertTrue(M.validate_certificate(certs[3]))
            self.assertFalse(certs[3]['whole']['source_ownership_exclusive'])
            view=case.branch.preview(12,row['time'],row['observations'],profiles)
            self.assertTrue(any('CURRENT_SOURCE_OWNERSHIP_UNKNOWN_OR_SHARED' in c['reasons']
                for c in view['trace']['ds19_event_return_proposals']['checks']))
            before=state(case.branch)
            tx,error=case.branch.stage_event_return(view,case.episode)
            self.assertIsNone(tx)
            self.assertTrue(error)
            self.assertEqual(state(case.branch),before)

    def test_unknown_is_measured_missing_and_all_rejected_equals_frozen_fallback(self):
        repaired,old=Slice(),Slice(legacy=True)
        for frame in range(12,17):
            objects=((3,20,0.),(2,80,1040.),(9,140,1250.))
            view,tx,error,trace,certs=repaired.advance(frame,objects)
            old.advance(frame,objects)
            self.assertEqual(certs[3]['whole']['inclusive_summary']['n'],0)
            self.assertIsNone(tx)
            self.assertTrue(error)
        self.assertEqual(repaired.published,old.published)
        for name in ('bank','view_bank','alias','birth','pending','first_eligible',
                     'native_runs','recent_core','pending_birth'):
            self.assertEqual(plain(getattr(repaired.branch.engine,name)),
                             plain(getattr(old.branch.engine,name)),name)

    def test_first_eligible_deadline_is_not_restarted(self):
        case=Slice()
        case.advance(12)
        birth=case.branch.engine.birth[3]
        first=case.branch.engine.first_eligible[3]
        view,tx,error,_,_=case.advance(13,now=first+3.01)
        self.assertIsNone(tx)
        self.assertTrue(error)
        self.assertEqual(case.branch.engine.birth[3],birth)
        self.assertEqual(case.branch.engine.first_eligible[3],first)
        self.assertLess(view['now'],birth[1]+6)
        self.assertEqual(view['trace']['eligible_new'],0)

    def test_generation_change_cuts_real_confirmation_without_restarting_birth(self):
        case=Slice()
        case.advance(12)
        birth=case.branch.engine.birth[3]
        first=case.branch.engine.first_eligible[3]
        self.assertEqual(case.branch.engine.pending[3]['count'],1)
        for frame in range(13,17):
            view,tx,error,_,_=case.advance(frame,source_generation=2)
            self.assertIsNone(tx,'Changed-generation observations must not inherit old confirmation')
            self.assertEqual(case.branch.engine.pending[3]['count'],frame-12)
            self.assertEqual(case.branch.engine.birth[3],birth)
            self.assertEqual(case.branch.engine.first_eligible[3],first)
        case.advance(17,source_generation=2)
        self.assertEqual(case.branch.previous[3],1)
        self.assertEqual(case.branch.engine.birth[3],birth)

    def test_anonymous_query_cannot_become_a_clean_return(self):
        case=Slice()
        row,profiles,certs=actual_input(case.branch,12,
            ((3,20,1000.),(2,80,1040.),(9,140,1250.)),now=8.+1/30.)
        case.branch.engine.observation_classes[3]='ANONYMOUS_RESIDUAL'
        view=case.branch.preview(12,row['time'],row['observations'],profiles)
        self.assertTrue(any('ANONYMOUS_IDENTITY_ROLE_NOT_ASSIGNABLE' in c['reasons']
            for c in view['trace']['ds19_event_return_proposals']['checks']))
        tx,error=case.branch.stage_event_return(view,case.episode)
        self.assertIsNone(tx)
        self.assertTrue(error)
        self.assertEqual(view['mapping'][3],3)
        self.assertEqual(view['engine'].bank[1]['anchor'],case.entry[1]['anchor'])

    def test_contact_birth_route_rejected_and_original_birth_window_expires(self):
        case=Slice()
        view,tx,error,_,_=case.advance(12,neighbors={3:[2],2:[3]})
        self.assertIsNone(tx)
        self.assertTrue(error)
        checks=view['trace']['ds19_event_return_proposals']['checks']
        self.assertTrue(any(c['origin_rule']=='BIRTH_REFINE' and
            'CURRENT_QUALITY_OR_CONTACT_RISK' in c['reasons'] for c in checks))
        birth=case.branch.engine.birth[3]
        self.assertNotIn(3,case.branch.engine.first_eligible)
        view,tx,error,_,_=case.advance(13,now=birth[1]+6.01)
        self.assertIsNone(tx)
        self.assertEqual(case.branch.engine.birth[3],birth)
        self.assertEqual(case.branch.engine.pending_birth[3]['retired_reason'],
                         'ORIGINAL_BIRTH_WINDOW_EXPIRED')

    def test_returned_source_becoming_group_again_stays_anonymous_through_timeout(self):
        case,_=self.restored()
        clean=T.C.clean_reference(case.branch.engine.bank[1])
        alias=copy.deepcopy(case.branch.engine.alias[3])
        case.advance(17,objects=((3,80,1100.),(9,140,1250.)))
        self.assertEqual(case.manager.frame_class[3],'GROUP_MEASUREMENT')
        self.assertEqual(T.C.clean_reference(case.branch.engine.bank[1]),clean)
        self.assertFalse(case.branch.engine.source_activity[3]['identity_measurement_certified'])
        self.assertEqual(case.branch.engine.source_activity[3][
            'received_association_observation']['depth']['median'],1100.)
        case.advance(18,objects=((3,80,1100.),(9,140,1250.)),now=18.1)
        self.assertEqual(case.episode['status'],'TIMEOUT')
        self.assertEqual(T.C.clean_reference(case.branch.engine.bank[1]),clean)
        self.assertEqual(case.branch.engine.alias[3],alias)
        self.assertEqual(case.branch.previous[3],1)
        self.assertFalse(case.branch.engine.source_activity[3]['identity_measurement_certified'])

    def test_future_observations_do_not_change_prior_publication_or_candidate(self):
        left,_=self.restored()
        right=copy.deepcopy(left)
        prefix=copy.deepcopy(left.published)
        entry=copy.deepcopy(left.episode['bank_snapshot'])
        left.advance(17,objects=((3,20,1001.),(2,80,1040.),(9,140,1250.)))
        right.advance(17,objects=((3,20,1100.),(2,80,0.),(9,140,1250.)))
        self.assertEqual(left.published[:-1],prefix)
        self.assertEqual(right.published[:-1],prefix)
        self.assertEqual(left.episode['bank_snapshot'],entry)
        self.assertEqual(right.episode['bank_snapshot'],entry)


if __name__=='__main__':unittest.main(verbosity=2)
