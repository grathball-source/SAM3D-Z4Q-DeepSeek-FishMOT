"""Real measured fixtures for confirmation isolation; no GT, API or fake gates."""
import copy
import unittest
from unittest.mock import patch

from common import ROOT, module

T = module('ds20_readonly_ds19_measured_fixtures',
    ROOT/'experiments/ds19_protected_event_return/test_event_return.py')
C, M = T.C, T.M


def event_rows(engine):
    return list(engine.event_return_confirmations.values())


class Competition:
    """A protected target competes with a genuinely measured ordinary target."""
    def __init__(self, source=38, protected=16, ordinary=7, enabled=True):
        self.source, self.target, self.ordinary = source, protected, ordinary
        self.branch = C.EventBridge(T.CONFIG, local_return=enabled)
        self.manager = C.EventManager('ACTIVITY_RETURN', self.branch, {},
            dict(max_episode_seconds=10.), {})
        self.published = []
        for frame in range(1, 11):
            neighbors = ({protected:[2], 2:[protected], ordinary:[9], 9:[ordinary]}
                         if frame == 10 else None)
            self.advance(frame, ((protected,20,1000.), (ordinary,50,1010.),
                                (2,85,1040.), (9,145,1250.)),
                         neighbors=neighbors, associate=False,
                         now=8. if frame==10 else frame/30.)
        entry = {k:copy.deepcopy(self.branch.engine.bank[k]) for k in (protected,2)}
        pre = {role:copy.deepcopy(list(self.manager.clean.get(native) or
                self.manager.last_clean.get(native, [])))
                for role,native in zip(('A','B'),(protected,2))}
        self.episode = copy.deepcopy(T.Slice().episode)
        self.episode.update(member_sources=[protected,2], public_ids=[protected,2],
                            bank_snapshot=entry, pre=pre,
                            source_suspect=dict(donor=protected, donor_reference_area=576.,
                                                group_reference_area=576.))
        self.manager.active = self.episode
        self.manager.events.append(self.episode)
        self.advance(11, ((protected,20,1000.), (ordinary,50,1010.),
                          (2,85,1040.), (9,145,1250.)), now=8.+1/30.,
            neighbors={protected:[2],2:[protected]}, associate=False)

    def advance(self, frame, objects=None, associate=True, **kwargs):
        objects = objects or ((self.source,20,1010. if frame<14 else 1000.),
                              (2,85,1040.), (9,145,1250.))
        kwargs.setdefault('now', frame/30. if frame<=10 else 8.+(frame-10)/30.)
        row, profiles, _ = T.actual_input(self.branch, frame, objects,
            manager=self.manager, **kwargs)
        view = self.branch.preview(frame,row['time'],row['observations'],profiles)
        tx,error = (self.branch.stage_event_return(view,self.episode)
                    if associate and hasattr(self,'episode') else (None,None))
        ids,trace = self.branch.commit_once(view,tx)
        if tx and tx.get('return_record'):
            self.manager.record_event_return(frame,tx)
        self.manager.after(row,profiles)
        self.published.append(dict(frame=frame,mapping=copy.deepcopy(ids)))
        return view,tx,error,trace


class PendingIsolationTests(unittest.TestCase):
    def assert_audit(self, view):
        audit = view['trace']['ds20_pending_isolation']
        self.assertEqual(audit['ordinary_pending_after'], audit['ordinary_pending_after_proposal'])
        self.assertEqual(audit['ordinary_pending_after_proposal'], view['engine'].pending)
        self.assertTrue(audit['ordinary_pending_not_overwritten'])
        for record in audit['event_confirmations_after']:
            self.assertEqual(record['key'], M._digest(record['identity']))
            self.assertEqual(record['identity']['public'], record['pending']['target'])
        return audit

    def accepted_view(self, outside_fix=False):
        case=T.Slice(outside_fix=outside_fix)
        for frame in range(12,17):case.advance(frame)
        view,row,profiles,certs=case.view(17)
        self.assertTrue(view['event_return_proposal']['trace']['ds19_natural_event_returns'])
        return case,view,row,profiles,certs

    def restored(self, **kwargs):
        case=T.Slice(**kwargs)
        actions=[case.advance(frame) for frame in range(12,18)]
        self.assertEqual(case.branch.previous[3],1)
        self.assertEqual(case.episode['q'],None)
        self.assertEqual(len([1 for _,tx,_,_,_ in actions if tx]),1)
        self.assertFalse(case.branch.engine.event_return_confirmations)
        return case,actions

    def test_five_natural_confirmations_and_atomic_single_publication(self):
        case,actions=self.restored()
        accepted=[]
        for view,tx,error,trace,certs in actions:
            self.assert_audit(view)
            self.assertTrue(all(M.validate_certificate(c) for c in certs.values()))
            if tx:
                accepted.extend(tx['return_record']['original_proposal_trace_events'])
                self.assertEqual(tx['return_record']['confirmation_policy'],
                                 trace['ds19_event_local_return']['confirmation_policy'])
        self.assertEqual(accepted[-1]['confirmations'],case.branch.engine.cfg['confirm'])
        self.assertEqual(accepted[-1]['origin_rule'],'D1_DELAYED')
        self.assertEqual(len(case.published),len({x['frame'] for x in case.published}))
        self.assertEqual(case.branch.engine.source_first_publication[3],dict(frame=12,public_id=3))
        self.assertEqual(case.published[-1]['mapping'][3],1)

    def test_feeding_and_lw_competition_keeps_ordinary_matrix_confirmation(self):
        for source,target,ordinary in ((38,16,7),(32,7,24)):
            with self.subTest(source=source):
                repaired=Competition(source,target,ordinary)
                control=Competition(source,target,ordinary,enabled=False)
                competing=False
                for frame in range(12,18):
                    view,tx,error,trace=repaired.advance(frame)
                    old_view,_,_,_=control.advance(frame)
                    audit=self.assert_audit(view)
                    self.assertEqual(view['engine'].pending,old_view['engine'].pending)
                    self.assertEqual(view['mapping'],old_view['mapping'])
                    ordinary_pending=view['engine'].pending.get(source)
                    protected_rows=[r for r in event_rows(view['engine'])
                        if r['identity']['native']==source]
                    if ordinary_pending and protected_rows:
                        self.assertEqual(ordinary_pending['target'],ordinary)
                        self.assertEqual(protected_rows[0]['pending']['target'],target)
                        competing=True
                    self.assertIsNone(tx,'A naturally accepted ordinary edge owns its source')
                    if source in audit['ordinary_accepted_sources']:
                        self.assertFalse(any(r['identity']['native']==source for r in
                                             audit['event_confirmations_after']))
                self.assertTrue(competing,'The measured fixture must actually exercise both targets')
                if source==32:
                    # In this measured fixture the ordinary edge really reaches
                    # five confirmations. Feeding's actual five-count timing is
                    # verified separately on the immutable real source slice.
                    self.assertEqual(repaired.branch.previous[source],ordinary)
                self.assertEqual(repaired.published,control.published)

    def test_event_key_changes_cut_confirmation_without_restarting_birth(self):
        for kind in ('source','identity','event','anchor'):
            with self.subTest(kind=kind):
                case=T.Slice()
                for frame in range(12,15):case.advance(frame)
                birth=case.branch.engine.birth[3]
                first=case.branch.engine.first_eligible[3]
                row,profiles,_=T.actual_input(case.branch,15,
                    ((3,20,1000.),(2,80,1040.),(9,140,1250.)),
                    now=8.+4/30.,source_generation=2 if kind=='source' else 1)
                if kind=='identity':
                    case.branch.engine.identity_versions[3][-1]+=1
                elif kind=='event':
                    case.branch.engine.protected['TEST']['generation']+=1
                elif kind=='anchor':
                    case.branch.engine.bank[1]['anchor']=copy.deepcopy(case.branch.engine.bank[9]['anchor'])
                    record=event_rows(case.branch.engine)[0]
                    diagnostic=dict(engine=case.branch.engine,mapping=case.branch.previous,
                                    frame=15,now=row['time'])
                    self.assertEqual(case.branch._invalid_reason(record,diagnostic,
                        case.branch.engine.protected['TEST']),'EXACT_OLD_ANCHOR_CHANGED')
                    before=T.state(case.branch)
                    with self.assertRaisesRegex(AssertionError,'certified event reference changed'):
                        case.branch.preview(15,row['time'],row['observations'],profiles)
                    self.assertEqual(T.state(case.branch),before)
                    continue
                view=case.branch.preview(15,row['time'],row['observations'],profiles)
                audit=self.assert_audit(view)
                self.assertTrue(audit['invalidated'])
                self.assertTrue(any('CHANGED' in r['reason'] for r in audit['invalidated']))
                self.assertEqual(view['engine'].birth[3],birth)
                self.assertEqual(view['engine'].first_eligible[3],first)
                self.assertTrue(all(r['pending']['count']<=1 for r in event_rows(view['engine'])))

    def test_new_event_does_not_borrow_four_real_ordinary_confirmations(self):
        case=T.Slice()
        case.branch.engine.protected.clear()
        case.branch.engine.event_context=None
        case.branch.engine.observation_classes={}
        case.manager.active=None
        for frame in range(12,16):
            view,tx,_,_,_=case.advance(frame,associate=False)
            self.assertEqual(view['engine'].pending[3]['target'],1)
            self.assertEqual(view['engine'].pending[3]['count'],frame-11)
            self.assertIsNone(tx)
        birth=case.branch.engine.birth[3]
        first=case.branch.engine.first_eligible[3]
        self.assertFalse(case.branch.engine.event_return_confirmations)
        case.manager.active=case.episode
        view,_,_,_=case.view(16)
        audit=self.assert_audit(view)
        self.assertEqual(audit['ordinary_pending_before'][3]['count'],4)
        self.assertEqual(audit['ordinary_protected_confirmations_not_imported'],
            [dict(native=3,pending=audit['ordinary_pending_before'][3])])
        self.assertFalse(view['event_return_proposal']['trace']['ds19_natural_event_returns'])
        self.assertEqual(event_rows(view['engine'])[0]['pending']['count'],1)
        self.assertEqual(view['engine'].birth[3],birth)
        self.assertEqual(view['engine'].first_eligible[3],first)

    def test_target_occupation_and_original_time_window_invalidate(self):
        for kind in ('occupied','window'):
            case=T.Slice()
            for frame in range(12,15):case.advance(frame)
            now=8.+4/30. if kind=='occupied' else 8.+.8
            objects=((3,20,1000.),(2,80,1040.),(9,140,1250.))
            if kind=='occupied':objects=objects+((1,170,1000.),)
            view,tx,error,_,_=case.advance(15,objects=objects,now=now)
            audit=self.assert_audit(view)
            self.assertTrue(audit['invalidated'])
            self.assertIsNone(tx)
            self.assertNotEqual(case.branch.previous[3],1)

    def test_preview_exception_and_failed_stage_do_not_mutate_authoritative_state(self):
        case=T.Slice()
        row,profiles,_=T.actual_input(case.branch,12,
            ((3,20,1000.),(2,80,1040.),(9,140,1250.)),
            now=8.+1/30.,manager=case.manager)
        before=T.state(case.branch)
        original=C.EventReturn.step
        def exploding(engine,*args,**kwargs):
            result=original(engine,*args,**kwargs)
            if engine.return_proposal:raise RuntimeError('proposal clone failure')
            return result
        with patch.object(C.EventReturn,'step',exploding):
            with self.assertRaises(RuntimeError):
                case.branch.preview(12,row['time'],row['observations'],profiles)
        self.assertEqual(T.state(case.branch),before)
        case,view,_,_,_=self.accepted_view(outside_fix=True)
        before=T.state(case.branch)
        view['mapping'][19]=1
        tx,error=case.branch.stage_event_return(view,case.episode)
        self.assertIsNone(tx)
        self.assertTrue(error)
        self.assertEqual(T.state(case.branch),before)
        self.assertEqual(case.branch.previous[19],9)

    def test_success_preserves_prior_group_outside_transaction(self):
        case,actions=self.restored(outside_fix=True)
        self.assertEqual(case.branch.previous[19],9)
        self.assertEqual(case.branch.provenance[19]['frame'],10)
        for view,tx,_,_,_ in actions:
            if tx:
                for store,key in (('bank',9),('view_bank',9),('alias',19),('source_activity',19)):
                    self.assertEqual(getattr(tx['engine'],store)[key],getattr(view['engine'],store)[key])

    def test_timeout_releases_confirmation_but_preserves_committed_return(self):
        case,_=self.restored()
        alias=copy.deepcopy(case.branch.engine.alias[3])
        _,tx,_,trace,_=case.advance(18,now=18.1)
        self.assertIsNone(tx)
        self.assertEqual(case.episode['status'],'TIMEOUT')
        self.assertFalse(case.branch.engine.protected)
        self.assertFalse(case.branch.engine.event_return_confirmations)
        self.assertEqual(case.branch.engine.alias[3],alias)
        self.assertEqual(case.branch.previous[3],1)

    def test_q_fallback_and_joint_trace_keep_actual_isolation_audit(self):
        for joint in (False,True):
            case,_=self.restored()
            view,row,profiles,_=case.view(18,
                objects=((3,67,1000.),(2,93,1040.),(9,140,1250.)))
            self.assertEqual(case.episode['q'],18)
            if joint:
                tx,error=case.branch.stage_group_restore(view,case.episode,{3:1,2:2})
                self.assertIsNone(error)
            else:
                tx,_=case.branch.local_fallback(view,case.episode)
            ids,trace=case.branch.commit_once(view,tx)
            self.assertEqual(trace['ds20_pending_isolation'],view['trace']['ds20_pending_isolation'])
            self.assertFalse(case.branch.engine.event_return_confirmations)
            self.assertEqual(ids[3],1)

    def test_disabled_unknown_and_deadline_reuse_old_real_semantic_checks(self):
        old_checks=T.EventReturnTests()
        for name in ('test_disabled_matches_frozen_ds18_publication_and_state',
                     'test_unknown_is_measured_missing_and_all_rejected_equals_frozen_fallback',
                     'test_first_eligible_deadline_is_not_restarted',
                     'test_anonymous_query_cannot_become_a_clean_return',
                     'test_contact_birth_route_rejected_and_original_birth_window_expires',
                     'test_shared_mask_and_native_source_do_not_certify_return'):
            with self.subTest(check=name):getattr(old_checks,name)()


if __name__=='__main__':unittest.main(verbosity=2)
