"""State/evidence contract tests; generated depth and masks, no GT/model calls."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path
import numpy as np

_spec = importlib.util.spec_from_file_location('ds18_unique_test_controller', Path(__file__).with_name('controller.py'))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
M = C._measure
CONFIG = json.loads((C.ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json').read_text())


def inputs(branch, frame, objects=((1, 20, 1000.), (2, 80, 1040.), (9, 140, 1250.)), neighbors=None,
           expose_certificates=False):
    depth = np.full((64, 200), 1500., dtype='f4')
    index = np.arange(depth.size, dtype='i4').reshape(depth.shape)
    masks = {}
    for native, x, z in objects:
        mask = np.zeros(depth.shape, bool)
        mask[20:44, x:x+24] = True
        masks[native] = mask
        depth[mask] = z
    source = dict(frame=frame, global_frame=frame-1, time=frame/30., GT_read=False, RGB_read=False)
    certs = M.measure_mixed(depth, index, masks, 'synthetic', frame, frame-1,
        source_binding=source, native_depth=depth)['objects']
    observations, profiles = [], {}
    for native, x, z in objects:
        whole = copy.deepcopy(certs[native]['whole']['inclusive_summary'])
        fixed = copy.deepcopy(certs[native]['birth_core']['inclusive_summary'])
        observations.append(dict(id=native, mask=f'n:{native}', box=[x,20,x+24,44], area=576,
            presence=.99, score_birth=.99, neighbors=(neighbors or {}).get(native, []), depth=whole))
        profiles[native] = dict(id=native, mask=f'n:{native}', frame=frame, whole=copy.deepcopy(whole), core=fixed)
    row = dict(frame=frame, global_frame=frame-1, time=frame/30., observations=observations)
    sv = {n: ['synthetic', 'TEST', n, 1] for n in masks}
    iv = {n: ['synthetic', 'TEST', 1, branch.previous.get(n), branch.epochs.get(n)] for n in masks}
    row, profiles = M.guard_inputs(row, profiles, certs, source_versions=sv, versions=iv, screen=False)
    branch.configure_evidence(frame, certificates=certs, source_versions=sv, identity_versions=iv, guarded=False)
    return (row, profiles, certs) if expose_certificates else (row, profiles)


def preview(branch, frame, **kwargs):
    row, profiles = inputs(branch, frame, **kwargs)
    return branch.preview(frame, row['time'], row['observations'], profiles)


def warm():
    branch = C.EventBridge(CONFIG)
    for frame in range(1, 11):
        branch.commit_once(preview(branch, frame))
    return branch


def protect(branch, frame=11, suppressed=(1,)):
    snapshot = {k: copy.deepcopy(branch.engine.bank[k]) for k in (1,2)}
    branch.engine.protected['TEST'] = dict(episode='TEST', generation=11,
        member_public=[1,2], member_sources=[1,2], suppressed=list(suppressed), outputs={n:n for n in suppressed})
    branch.engine.event_context = dict(id='TEST', generation=11, q=None, public_ids=[1,2], post_sources=[])
    branch.engine.observation_frame = frame
    branch.engine.observation_classes = {n:'GROUP_MEASUREMENT' for n in suppressed}
    return snapshot


class ControllerContractTests(unittest.TestCase):
    def test_immutable_facts_shared_mutable_branch_state_independent(self):
        branch=warm()
        certificate=branch.engine.certificates[1]
        references=[r for r in branch.engine.reference_bindings.values()
                    if r['anchor']['native_id']==1 and r['anchor']['frame']==10]
        self.assertGreaterEqual(len(references),3)
        self.assertTrue(all(r['certificate'] is certificate for r in references))
        row,profiles,external=inputs(branch,11,expose_certificates=True)
        with self.assertRaises(TypeError):
            external[1]['whole']['inclusive_summary']['median']+=7
        self.assertEqual(branch.engine.certificates[1]['whole']['inclusive_summary']['median'],1000.)
        view=branch.preview(11,row['time'],row['observations'],profiles)
        self.assertEqual(view['mapping'],branch.previous)
        trial=view['engine']
        old_references=[r for r in trial.reference_bindings.values()
                        if r['anchor']['native_id']==1 and r['anchor']['frame']==10]
        self.assertTrue(all(r['certificate'] is old_references[0]['certificate'] for r in old_references))
        self.assertIs(old_references[0]['certificate'],certificate)
        self.assertIs(trial.certificates[1],branch.engine.certificates[1])
        with self.assertRaises(TypeError):
            old_references[0]['certificate']['whole']['inclusive_summary']['median']+=9
        with self.assertRaises(TypeError):
            trial.certificates[1]['whole']['inclusive_summary']['median']+=3
        key=next(k for k,v in trial.reference_bindings.items() if v is old_references[0])
        altered=json.loads(json.dumps(old_references[0]))
        altered['binding']['actual_scalar']['median']+=4
        trial.reference_bindings[key]=altered
        trial.alias[77]=dict(target=1,commit_frame=11)
        trial.pending_birth[88]=dict(original_birth_frame=11,targets={1:dict(frame=10)})
        trial.bank[1]['partners'][9]=11/30.
        self.assertEqual(references[0]['binding']['actual_scalar']['median'],1000.)
        self.assertNotIn(77,branch.engine.alias)
        self.assertNotIn(88,branch.engine.pending_birth)
        self.assertNotIn(9,branch.engine.bank[1]['partners'])
        trial.source_versions[1][-1]=2
        self.assertEqual(branch.engine.source_versions[1][-1],1)
        trial.source_activity[1]=dict(frame=999,identity_measurement_certified=False)
        self.assertEqual(branch.engine.source_activity[1]['frame'],10)
        self.assertEqual(certificate['whole']['inclusive_summary']['median'],1000.)
        self.assertEqual(branch.engine.certificates[1]['whole']['inclusive_summary']['median'],1000.)
        self.assertEqual(external[1]['whole']['inclusive_summary']['median'],1000.)
        untrusted=json.loads(json.dumps(external[1]))
        untrusted['whole']['inclusive_summary']['median']+=7
        self.assertFalse(M.validate_certificate(untrusted))

    def test_real_original_mro_and_no_event_state_equal(self):
        branch = warm()
        original = C.Bridge(CONFIG)
        for frame in range(1,11):
            row, profiles = inputs(C.EventBridge(CONFIG), frame)
            original.commit_once(original.preview(frame, row['time'], row['observations'], profiles))
        mro = type(branch.engine).__mro__
        self.assertEqual(mro[mro.index(C.PendingBirth)-1].__name__, 'NativePrior')
        self.assertEqual(mro[mro.index(C.PendingBirth)+1], C.BirthRefine)
        for name in ('bank','view_bank','alias','birth','pending','first_eligible','native_runs','recent_core'):
            self.assertEqual(getattr(branch.engine,name),getattr(original.engine,name),name)
        self.assertTrue(branch.engine.reference_bindings)
        self.assertEqual(sum(map(len,branch.engine.depth_history_bindings.values())),30)

    def test_anonymous_valid_measurement_activity_and_immutable_references(self):
        branch = warm()
        snapshot = protect(branch)
        before = copy.deepcopy(branch.engine.bank)
        view = preview(branch,11,objects=((1,20,1005.),(9,140,1250.)))
        trial = view['engine']
        self.assertEqual(branch.engine.bank,before)
        for public in (1,2):
            self.assertEqual(C.clean_reference(trial.bank[public]),C.clean_reference(snapshot[public]))
            self.assertEqual(trial.view_bank[public],branch.engine.view_bank[public])
        self.assertEqual(trial.bank[1]['last_frame'],11)
        self.assertEqual(trial.bank[2]['last_frame'],10)
        self.assertEqual(trial.recent_core.get(1),branch.engine.recent_core.get(1))
        self.assertEqual(trial.source_activity[1]['received_association_observation']['depth']['median'],1005.)
        self.assertFalse(trial.source_activity[1]['identity_measurement_certified'])
        self.assertEqual(view['trace']['activity_reference_separation']['anonymous_current_measurement_preserved'],[1])

    def pending_slice(self):
        branch = warm()
        for k, q in ((1,2),(2,1)):
            branch.engine.bank[k]['contact_time'] = 10/30.
            branch.engine.bank[k]['partners'][q] = 10/30.
        snapshot = protect(branch)
        branch.commit_once(preview(branch,11,objects=((1,20,1000.),(9,140,1250.))))
        branch.engine.protected['TEST']['suppressed']=[2,3]
        branch.engine.observation_frame=12
        branch.engine.observation_classes={2:'POST_UNASSIGNED',3:'POST_UNASSIGNED'}
        branch.engine.event_context.update(q=12,post_sources=[2,3])
        view=preview(branch,12,objects=((3,20,1000.),(2,80,1040.),(9,140,1250.)),neighbors={3:[2],2:[3]})
        return branch, snapshot, view

    def test_pending_identity_gate_precedes_any_alias_bank_write(self):
        branch, snapshot, view=self.pending_slice()
        trial=view['engine']
        self.assertNotIn(3,trial.alias)
        self.assertEqual(view['mapping'][3],3)
        self.assertEqual(trial.birth[3],(12,12/30.))
        self.assertIn(3,trial.pending_birth)
        edge=next(e for e in view['trace']['birth_checks'] if e.get('native_id')==3 and e.get('canonical_id')==1)
        self.assertEqual(edge['current_depths']['core']['z'],1000.)
        self.assertIn('WAIT_JOINT_GROUP_TRANSACTION',edge['edge_veto']['reasons'])
        self.assertEqual(C.clean_reference(trial.bank[1]),C.clean_reference(snapshot[1]))
        self.assertNotIn('anchor',trial.bank[3])
        before_targets=copy.deepcopy(trial.pending_birth[3]['targets'])
        trial.remember_birth(13,13/30.,trial._step_observations[3],9,
            dict(edge_veto=dict(veto=True,reason='PENDING_TARGET_ANCHOR_CHANGED')))
        self.assertEqual(trial.pending_birth[3]['targets'],before_targets)
        original_birth=trial.birth[3]
        trial.source_versions[3][-1]=2
        self.assertNotIn(3,[o['id'] for o in trial.birth_candidates(13,13/30.,list(trial._step_observations.values()))])
        self.assertEqual(trial.birth[3],original_birth)
        self.assertEqual(trial.pending_birth[3]['retired_reason'],'SOURCE_GENERATION_CHANGED')

    def test_local_release_keeps_original_birth_clock_and_outside_state(self):
        branch,snapshot,view=self.pending_slice()
        episode=dict(id='TEST',generation=11,q=12,public_ids=[1,2],bank_snapshot=snapshot,
            member_sources=[1,2],group_source=1,post_roles={3:[dict(frame=12,time=.4,center=[32.,32.])],2:[dict(frame=12,time=.4,center=[92.,32.])]})
        fallback,_=branch.local_fallback(view,episode)
        self.assertEqual(fallback['engine'].bank[9],view['engine'].bank[9])
        self.assertEqual(fallback['engine'].pending_birth,view['engine'].pending_birth)
        branch.commit_once(view,fallback)
        branch.engine.observation_classes={}
        branch.engine.event_context=None
        retry=preview(branch,13,objects=((3,20,1000.),(2,80,1040.),(9,140,1250.)),neighbors={3:[2],2:[3]})
        self.assertEqual(retry['engine'].birth[3],(12,.4))
        accepted=[e for e in retry['trace']['events'] if e.get('accepted') and e.get('native_id')==3]
        self.assertEqual(len(accepted),1)
        self.assertEqual(accepted[0]['origin_rule'],'BIRTH_REFINE')
        self.assertEqual(accepted[0]['original_birth_frame'],12)
        self.assertEqual(accepted[0]['evaluation_frame'],13)
        self.assertTrue(accepted[0]['source_previously_published'])
        self.assertEqual(accepted[0]['actual_first_source_publication'],dict(frame=12,public_id=3))
        evidence=accepted[0]['association_evidence_bindings']
        self.assertEqual(evidence['target']['BIRTH_CORE']['anchor']['frame'],10)
        self.assertEqual(evidence['query']['BIRTH_CORE']['frame'],13)
        self.assertEqual(evidence['partners'][0]['current']['BIRTH_WHOLE']['frame'],13)
        self.assertEqual(retry['engine'].birth_counts['births'],1)
        self.assertEqual(retry['engine'].birth_counts['pending_evaluations'],1)

    def test_missing_required_whole_is_unknown_not_candidate_reward(self):
        branch,snapshot,view=self.pending_slice()
        branch.engine.observation_classes={}
        branch.engine.protected.clear()
        branch.engine.view_bank[2].pop('whole')
        candidate=preview(branch,12,objects=((3,20,1000.),(2,80,1040.),(9,140,1250.)),neighbors={3:[2],2:[3]})
        edge=next(e for e in candidate['trace']['birth_checks'] if e.get('native_id')==3 and e.get('canonical_id')==1)
        self.assertEqual(edge['required_whole_evidence']['status'],'UNKNOWN')
        self.assertIn('partner_2_candidate_whole',edge['required_whole_evidence']['unknown'])
        self.assertNotIn(3,candidate['engine'].alias)

    def test_exact_anchor_source_future_and_scalar_tampering_rejected(self):
        branch=warm()
        engine=branch.engine
        history=engine.view_bank[1]['core']
        self.assertIsNotNone(engine.bound_reference(1,'BIRTH_CORE',history,11))
        self.assertIsNone(engine.bound_reference(1,'BIRTH_CORE',history,10))
        for kind in ('source','scalar','anchor'):
            trial=copy.deepcopy(engine)
            h=trial.view_bank[1]['core']
            key=trial.reference_key(1,'BIRTH_CORE',h['anchor'])
            if kind=='source':
                trial.reference_bindings[key]=json.loads(json.dumps(trial.reference_bindings[key]))
                trial.reference_bindings[key]['source_version'][-1]=99
            elif kind=='scalar':h['z']+=1
            else:h['anchor']['native_id']=2
            self.assertIsNone(trial.bound_reference(1,'BIRTH_CORE',h,11),kind)

    def test_unassigned_post_cannot_target_outside_bank_or_be_birth_survivor(self):
        branch,snapshot,view=self.pending_slice()
        trial=view['engine']
        query=trial._step_observations[3]
        check=trial.edge_veto(12,.4,query,9,trial.bank[9]['anchor'],'BIRTH_REFINE')
        self.assertIn('ANONYMOUS_IDENTITY_ROLE_NOT_ASSIGNABLE',check['reasons'])
        # The current post can be measured, but cannot be a single-identity
        # witness for an unrelated query. This must not delete its scalar.
        other=copy.deepcopy(query)
        other['id']=4
        other['mask']='n:4'
        other['neighbors']=[2]
        p=copy.deepcopy(trial._step_profiles[3])
        p.update(id=4,mask='n:4')
        terms=trial.edge(12,.4,other,1,dict(trial._step_profiles,**{}),{2,4,9},
            {2:trial._step_observations[2],4:other,9:trial._step_observations[9]},{4},[1])
        self.assertIn('partner_2_identity_role_unresolved',terms['required_whole_evidence']['unknown'])
        self.assertEqual(trial._step_profiles[2]['whole']['median'],1040.)

    def test_only_atomic_joint_stage_certifies_current_q_and_clears_pending(self):
        branch,snapshot,view=self.pending_slice()
        episode=dict(id='TEST',generation=11,q=12,public_ids=[1,2],bank_snapshot=snapshot,
            member_sources=[1,2],group_source=1,post_roles={3:[dict(frame=12,time=.4,center=[32.,32.])],2:[dict(frame=12,time=.4,center=[92.,32.])]})
        before=copy.deepcopy(branch.engine.bank)
        transaction,error=branch.stage_group_restore(view,episode,{3:1,2:2})
        self.assertIsNone(error)
        self.assertEqual(transaction['mapping'],{3:1,2:2,9:9})
        self.assertNotIn(3,transaction['engine'].pending_birth)
        self.assertEqual(transaction['engine'].bank[9],view['engine'].bank[9])
        self.assertEqual(branch.engine.bank,before)
        ids,trace=branch.commit_once(view,transaction)
        self.assertEqual(ids[3],1)
        with self.assertRaises(AssertionError):
            branch.commit_once(view,transaction)

    def test_d1_exact_histogram_population_and_identity_context(self):
        branch=warm()
        row,ps=inputs(branch,11)
        branch.engine._step_observations={o['id']:o for o in row['observations']}
        branch.engine._step_profiles=ps
        branch.engine._active_anonymous=set()
        query=row['observations'][0]
        check=branch.engine.edge_veto(11,11/30.,query,2,branch.engine.bank[2]['anchor'],'D1_DELAYED')
        self.assertFalse(check['veto'])
        evidence=branch.engine._candidate_bindings['D1_DELAYED',1,2]
        self.assertEqual(len(evidence['whole_history']),10)
        self.assertEqual(evidence['whole_history'][0]['actual_contribution']['binding']['frame'],1)
        self.assertEqual(evidence['ema_last_update']['actual_ema_mm'],1040.)
        time=branch.engine.bank[2]['depth_history'][0][0]
        branch.engine.depth_history_bindings[2][time]=json.loads(json.dumps(branch.engine.depth_history_bindings[2][time]))
        branch.engine.depth_history_bindings[2][time]['median']+=1
        self.assertIn('TARGET_WHOLE_HISTORY_LINEAGE_UNKNOWN',branch.engine.edge_veto(11,11/30.,query,2,branch.engine.bank[2]['anchor'],'D1_DELAYED')['reasons'])
        wrong=copy.deepcopy(query)
        wrong['measurement_bindings']['D1_WHOLE']['version_key'][3]=99
        self.assertIsNone(branch.engine.current_binding(1,'D1_WHOLE',wrong['depth'],wrong))


if __name__=='__main__':
    unittest.main()
