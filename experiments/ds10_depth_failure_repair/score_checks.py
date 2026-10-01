"""DS10 small synthetic contracts, including tampering with self-consistent hashes."""
import copy
import tempfile
import unittest
from pathlib import Path
import evaluate as score
import event_audit as audit
from association import choose
from common import HERE, ARMS, read, sha, artifact, verify_item, write_new
import importlib.util
_spec=importlib.util.spec_from_file_location("score_checks_f9",HERE.parent/"ds9_joint_h0_depth/association.py")
_old=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_old)


def fixture(arm='D10_RESTORED'):
    segment='synthetic';history={};frozen={};measurements={}
    for role,n,public,z,x in [('A',1,-7,1000.,20.),('B',2,8,1150.,120.)]:
        history[role]=[dict(frame=f,time=float(f),source=n,center=[x+f,30.],bbox=[x+f-5,25.,x+f+5,35.],
            area=100,neighbors=[],depth=None,observation_class='SOURCE_OBSERVATION',source_generation=1,
            public_id=public,public_epoch=1,measured_time=float(f)) for f in range(1,5)]
        samples=[]
        for f in range(1,5):
            measurements.setdefault(f,dict(time=float(f),adaptive_raw={},restored={}))
            for kind in ('adaptive_raw','restored'):
                measurements[f][kind][str(n)]=dict(core_usable=True,fact_id=f'{segment}/{kind}/{f}/{n}',
                    source=kind,core=dict(median=z+f,mad=5.),cohort='retained')
            fact=score.observation_facts(measurements[f],arm)[str(n)]
            samples.append(dict(frame=f,time=float(f),z_mm=fact['core']['median'],mad_mm=5.,source=fact['source'],fact_id=fact['fact_id']))
        frozen[role]=dict(key=[segment,arm,1,public,1],samples=samples,acquired_interval_seconds=1.,cutoff_frame=4,source=n,public=public)
    posts={n:[dict(frame=7,time=7.,source=n,center=[x,30.],bbox=[x-5,25.,x+5,35.])]
        for n,x in ((11,27.),(12,127.))}
    measurements[7]=dict(time=7.,adaptive_raw={},restored={},adaptive_full=dict(n=100,median=1400.,mad=120.),restored_full=dict(n=100,median=1400.,mad=120.))
    for kind in ('adaptive_raw','restored'):
        for n,z in ((11,1007.),(12,1157.),(13,900.),(14,1250.)):
            measurements[7][kind][str(n)]=dict(core_usable=True,fact_id=f'{segment}/{kind}/7/{n}',
                source=kind,core=dict(median=z,mad=5.),cohort='retained')
    episode=dict(q=7,suspect_frame=5,pre=history,post_roles=posts,public_ids=[-7,8])
    mode='RAW_DEPTH' if arm=='D10_RAW' else 'RESTORED_DEPTH'
    facts={int(n):v for n,v in score.observation_facts(measurements[7],arm).items()}
    selector=_old.choose if arm=='F9_RESTORED' else choose
    choice,detail=selector(episode,frozen,facts,measurements[7]['adaptive_full' if arm=='D10_RAW' else 'restored_full'],{11:-7,12:8},mode,segment)
    event=dict(q=7,suspect_frame=5,public_ids=[-7,8],depth_frozen=frozen,pre_geometry_history=history,
        post_first_observations={str(n):v[0] for n,v in posts.items()},
        restore=dict(baseline_preview_mapping={'11':-7,'12':8}),numeric=dict(choice=choice,detail=detail))
    return event,measurements


class ScoreChecks(unittest.TestCase):
    def test_unique_integer_ids_masks_and_negative_ids(self):
        objects=[dict(mask='n:1',id=-7),dict(mask='n:2',id=8)]
        assignment={'variants':{'N0':objects}}
        prediction={'variants':{a:copy.deepcopy(objects) for a in ARMS}}
        score.check_objects(assignment,prediction)
        for bad in (True,1.2,8):
            changed=copy.deepcopy(prediction);changed['variants']['D10_RAW'][0]['id']=bad
            with self.assertRaises(AssertionError):score.check_objects(assignment,changed)
        changed=copy.deepcopy(prediction);changed['variants']['D10_RESTORED'].reverse()
        with self.assertRaises(AssertionError):score.check_objects(assignment,changed)
        self.assertEqual(score.namespaced([-7],2),[(2,-7)])

    def test_selected_publisher_transaction_and_h0_no_stage(self):
        arm='D10_RAW'
        restore=dict(status='COMMIT',mapping={1:8,2:-7},changes={1:8,2:-7},baseline_preview_mapping={1:-7,2:8},selected_choice='H2')
        event=dict(id='E1',q=2,suspect_frame=1,evidence_cutoff_frame=2,
            post_first_observations={'1':{'frame':2},'2':{'frame':2}},restore=restore,
            numeric=dict(choice='H2',detail=dict(accepted=True,evidence_max_frame=2,baseline_mapping={1:-7,2:8},selected_mapping={1:8,2:-7})))
        predictions={2:{'variants':{arm:[dict(mask='n:1',id=8),dict(mask='n:2',id=-7)]}}}
        publish={2:{'event_publish':{arm:dict(episode='E1',q=2,post_sample_count=1,first_public_pair={'1':8,'2':-7})}}}
        transactions={(2,arm):dict(restore=restore,actual_published_mapping={'1':8,'2':-7})};states={(2,arm):{'live':{}}}
        score.check_q_binding(event,arm,predictions,publish,transactions,states)
        tampered=copy.deepcopy(publish);tampered[2]['event_publish'][arm]['first_public_pair']['1']=-7
        with self.assertRaises(AssertionError):score.check_q_binding(event,arm,predictions,tampered,transactions,states)
        event['numeric']['choice']='H0';restore['selected_choice']='H0';event['numeric']['detail']['accepted']=False
        with self.assertRaises(AssertionError):score.check_q_binding(event,arm,predictions,publish,transactions,states)

    def test_unknown_notstaged_and_nochange_separate(self):
        expected={1:8,2:-7}
        self.assertEqual(audit.mapping_outcome(dict(status='LOCAL_FALLBACK_COMMITTED',mapping=None),expected,expected),({},'NOT_STAGED','CORRECT'))
        self.assertEqual(audit.mapping_outcome(dict(status='RESOLVE_NO_ID_CHANGE',mapping=expected),expected,{}),(expected,'UNSCORABLE_OR_NO_BIJECTION','UNSCORABLE_OR_NO_BIJECTION'))
        e=dict(q=2,depth_frozen={'A':dict(source=1,public=8,key=None,samples=[])})
        def no_reference(*args):raise AssertionError('must not need GT for missing history')
        out=audit.fragment_reference(e,{}, {},{},no_reference,'D10_RAW',3)[0]
        self.assertEqual(out['surface_identity'],'UNKNOWN');self.assertIsNone(out['physical_depth_reference_mm'])
        self.assertIn('NO_FROZEN_HISTORY',out['exclusions'])

    def test_actual_sources_and_selfsealed_semantic_tamper(self):
        for arm in ARMS[1:]:
            e,m=fixture(arm);score.check_association(e,arm,'synthetic',m,{})
            # Every changed body is resealed correctly. Hash integrity is not semantic validity.
            mutations=[lambda d:d['candidates']['H0'].__setitem__('log_score',99.),
                       lambda d:d['hypotheses']['H1'].__setitem__('canonical','H1'),
                       lambda d:d['geometry_forecasts']['A']['pre_facts'][0].__setitem__('frame',7)]
            if arm in ARMS[1:]:
                mutations += [lambda d:d['depth_assignment']['11'].__setitem__('actual_state_fact_id','forged'),
                              lambda d:d['depth_forecasts']['A'].__setitem__('mu_mm',-1.)]
            for mutate in mutations:
                changed=copy.deepcopy(e);mutate(changed['numeric']['detail'])
                with tempfile.TemporaryDirectory(prefix='ds9_score_contract_') as directory:
                    path=Path(directory)/'body.json';write_new(path,changed)
                    sealpath=Path(directory)/'seal.json';write_new(sealpath,artifact(path))
                    verify_item(read(sealpath))
                    with self.assertRaises(AssertionError):score.check_association(read(path),arm,'synthetic',m,{})
    def test_predeclared_inert_float_only_and_native_target(self):
        old={'restored':{'1':{'core':{'median':1000.,'mad':10.},'core_usable':True,
            'roi_geometry':{'pieces':[{'dt_max_px':6.082762241363525,'threshold_px':3.,'samples':20}]}}}}
        new=copy.deepcopy(old);new['restored']['1']['roi_geometry']['pieces'][0]['dt_max_px']=float(score.np.nextafter(score.np.float32(6.082762241363525),score.np.float32(10.)))
        self.assertEqual(len(score.check_source_extraction(new,old)),1)
        for mutation in ('median','threshold','samples','two_ulp'):
            changed=copy.deepcopy(new)
            if mutation=='median':changed['restored']['1']['core']['median']+=1e-10
            elif mutation=='threshold':changed['restored']['1']['roi_geometry']['pieces'][0]['threshold_px']-=1e-10
            elif mutation=='samples':changed['restored']['1']['roi_geometry']['pieces'][0]['samples']+=1
            else:
                piece=changed['restored']['1']['roi_geometry']['pieces'][0]
                piece['dt_max_px']=float(score.np.nextafter(score.np.float32(piece['dt_max_px']),score.np.float32(10.)))
            with self.assertRaises(AssertionError):score.check_source_extraction(changed,old)
        # A nextafter step in the un-clamped interval changes the operative threshold.
        a=copy.deepcopy(old);a['restored']['1']['roi_geometry']['pieces'][0].update(dt_max_px=4.,threshold_px=2.)
        b=copy.deepcopy(a);b['restored']['1']['roi_geometry']['pieces'][0]['dt_max_px']=float(score.np.nextafter(score.np.float32(4.),score.np.float32(10.)))
        with self.assertRaises(AssertionError):score.check_source_extraction(b,a)
        pooled={a:dict(IDF1=80.,HOTA=70.,AssA=60.,IDSW=10) for a in ARMS}
        pooled['D10_RAW']=dict(IDF1=81.,HOTA=71.,AssA=61.,IDSW=10)
        result=score.support_layers(pooled)
        self.assertTrue(result['raw_tracking_support']);self.assertFalse(result['geometry_increment_required'])
        self.assertEqual(result['physical_depth_accuracy'],'UNKNOWN')


def main():
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ScoreChecks))
    assert result.wasSuccessful()
    write_new(HERE/'SCORE_CHECKS.json',dict(status='PASS',tests=result.testsRun,
        scope='five synthetic contracts; self-consistently resealed semantic tampering; no dataset labels or GT scoring',
        failures=len(result.failures),errors=len(result.errors),new_model_http=0,
        code_sha256={n:sha(HERE/n) for n in ('evaluate.py','event_audit.py','score_checks.py','check_real_slice.py')}))


if __name__=='__main__':main()
