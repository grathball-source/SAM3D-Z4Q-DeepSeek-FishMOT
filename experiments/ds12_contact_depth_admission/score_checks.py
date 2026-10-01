"""DS12 small synthetic contracts, including tampering with self-consistent hashes."""
import copy
import tempfile
import unittest
from pathlib import Path
import evaluate as score
import event_audit as audit
from common import HERE, ARMS, read, sha, artifact, verify_item, write_new
import importlib.util
_spec=importlib.util.spec_from_file_location("score_checks_f9",HERE.parent/"ds9_joint_h0_depth/association.py")
_old=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_old)


def fixture(arm=ARMS[3]):
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
    mode='RAW_DEPTH' if arm==ARMS[2] else 'RESTORED_DEPTH'
    facts={int(n):v for n,v in score.observation_facts(measurements[7],arm).items()}
    selector=_old.choose
    choice,detail=selector(episode,frozen,facts,measurements[7]['adaptive_full' if arm==ARMS[2] else 'restored_full'],{11:-7,12:8},mode,segment)
    event=dict(q=7,suspect_frame=5,public_ids=[-7,8],depth_frozen=frozen,pre_geometry_history=history,
        post_first_observations={str(n):v[0] for n,v in posts.items()},
        restore=dict(baseline_preview_mapping={'11':-7,'12':8}),numeric=dict(choice=choice,detail=detail))
    return event,measurements

def birth_fixture():
    import reconnect
    segment='BIRTH_SYNTHETIC';arm=ARMS[2];key=[segment,arm+'_RAW_SENSOR_SUPPORT',1,7,1]
    history=[];samples=[];measurements={};sources={};transactions={};states={};generations={}
    for f in range(1,11):
        t=(f-1)*.1
        p=dict(frame=f,time=t,measured_time=t,source=7,source_generation=1,public_id=7,public_epoch=1,
            center=[10.,10.],bbox=[0.,0.,20.,20.],area=400,neighbors=[],depth=None,observation_class='SOURCE_OBSERVATION')
        m=dict(source='RAW_SENSOR_ADAPTIVE',fact_id=f'{segment}/F{f}/n:7/adaptive/raw',
            core_usable=True,core=dict(median=1000.,mad=2.))
        history.append(p);samples.append(dict(frame=f,time=t,z_mm=1000.,mad_mm=2.,source=m['source'],fact_id=m['fact_id'],version_key=key,source_native=7))
        sources[f]=dict(time=t,observations={7:dict(box=p['bbox'],area=400,neighbors=[],depth=None)})
        measurements[f]=dict(time=t,adaptive_raw={'7':m})
        transactions[(f,arm)]=dict(actual_published_mapping={'7':7},epochs={'7':1})
        states[(f,arm)]=dict(birth_raw_arm=key[1],birth_raw_live={'7':dict(key=key,sample_frames=list(range(1,f+1)))})
        generations[(f,7)]=1
    candidate=dict(public=7,source=7,eligible=True,reasons=[],bank_anchor_version=key,last_seen_frame=10,
        anchor=dict(frame=10,native_id=7,canonical_id=7),
        reference_anchor=dict(frame=10,time=.9,native_id=7,canonical_id=7,source_generation=1,public_epoch=1),
        risk_interval=dict(reference_frame=10,reference_time=.9,last_appearance_frame=10,disappearance_frame=11,
            query_frame=11,query_time=1.,full_gap_seconds=1.-.9,observed_risk_frames=[],missing_interval_frames=[11,10],
            identity_continuity='UNKNOWN',path_between_reference_and_query='UNOBSERVED_NOT_INTERPOLATED'),
        anonymous_risk_observations=[],geometry_history=history,
        frozen_depth=dict(key=key,samples=samples,source=7,public=7,cutoff_frame=10,acquired_interval_seconds=.1))
    q=dict(source=100,frame=11,time=1.,center=[10.,10.],bbox=[0.,0.,20.,20.],area=400,neighbors=[],quality=True,observation_class='BIRTH_UNASSIGNED')
    facts={n:dict(native=n,source='RAW_SENSOR_ADAPTIVE',fact_id=f'{segment}/F11/n:{n}/adaptive/raw',cohort='RAW',
        core_usable=True,core=dict(n=40,valid_fraction=1.,median=z,mad=2.)) for n,z in ((100,1000.),(200,1700.),(201,2200.))}
    full=dict(n=230400,median=2500.,mad=100.)
    target,detail=reconnect.choose(q,[candidate],facts,full,'RAW_DEPTH',segment)
    query=dict(source=100,first_source_frame=11,query_observation=q,current_measurement_fact_id=facts[100]['fact_id'],
        candidates=[candidate],selection=score.json.loads(score.json.dumps(detail)),selected_target=target,
        selected_candidate=candidate if target is not None else None,selected_anchor=candidate['anchor'] if target is not None else None,
        selected_reference_anchor=candidate['reference_anchor'] if target is not None else None)
    measurements[11]=dict(time=1.,adaptive_raw={str(n):m for n,m in facts.items()},adaptive_full=full)
    return query,segment,arm,measurements,sources,transactions,states,generations

def initial_birth_fixture():
    source=99;segment='INITIAL_SYNTHETIC';o=dict(id=source,box=[0.,0.,20.,20.],area=400,neighbors=[],depth=None,presence=1.)
    sample=dict(source=source,frame=1,time=0.,bbox=o['box'],center=[10.,10.],area=400,neighbors=[],depth=None,
        quality=True,observation_class='BIRTH_UNASSIGNED',source_generation=1,public_id=source,public_epoch=1)
    m=dict(source='RAW_SENSOR_ADAPTIVE',fact_id='raw/99',core_usable=False,core=dict(median=None,mad=None))
    measurement={1:dict(time=0.,adaptive_raw={'99':m},restored={'99':dict(m,source='RESTORED_V2_UNKNOWN',fact_id='rest/99')})}
    sources={1:dict(time=0.,observations={source:o})};pred={1:dict(global_frame=100,variants={a:[dict(mask='n:99',id=99)] for a in ARMS})}
    pub={1:dict(prediction_row_sha256='bound',birth_publish={})};tx={};states={};births=[]
    for arm in ARMS[1:]:
        query=dict(source=source,first_source_frame=1,post_sample_count=1,query_observation=sample,
            current_measurement_fact_id=score.observation_facts(measurement[1],arm)['99']['fact_id'],candidates=[],selection=None,
            selected_target=None,selected_anchor=None,selected_candidate=None,status='INITIAL_FRAME_NOT_ASSOCIATED',
            actual_first_public_id=99,transaction_version=1,stage_error=None)
        births.append(dict(frame=1,global_frame=100,time=0.,arm=arm,prediction_row_sha256='bound',
            actual_mapping={'99':99},baseline_before={'99':99},changes={},status='NO_BIRTH_COMMIT',queries=[query],
            group_blocked=False,preframe_version=0,transaction_version=1,
            preframe=dict(birth_raw_arm=arm+'_SENSOR_SUPPORT',previous_mapping={},bank_anchors={},alias_targets={},group_reserved_targets=[])))
        tx[(1,arm)]=dict(actual_published_mapping={'99':99},previous_mapping={},active_event=None,
            birth_restore=dict(status='NO_BIRTH_COMMIT',changes={}),epochs={'99':1})
        states[(1,arm)]=dict(birth_raw_arm=arm+'_SENSOR_SUPPORT')
        pub[1]['birth_publish'][arm]=dict(transaction_version=1,changes={},post_sample_count=1,first_public_ids={'99':99})
    return births,segment,sources,measurement,pred,pub,tx,states,{(1,99):1}

def contact_fixture():
    import reconnect
    from contact_measurement import measure_contact
    query,segment,arm,measurements,*_=birth_fixture()
    sample=query['query_observation'];sample['neighbors']=[200]
    shape=(64,96);depth=score.np.full(shape,1000.,'f4');index=score.np.arange(depth.size,dtype='i4').reshape(shape)
    masks={n:score.np.zeros(shape,bool) for n in (100,200,201)}
    masks[100][0:20,0:20]=True;masks[200][0:20,20:40]=True;masks[201][30:50,50:70]=True
    depth[masks[200]]=1700.;depth[masks[201]]=2200.
    binding=dict(frame=11,global_frame=100,time=1.,measurement_fact_ids={n:m['fact_id'] for n,m in measurements[11]['adaptive_raw'].items()})
    certs=measure_contact(depth,index,masks,segment,11,100,source_binding=binding,native_depth=score.np.full(shape,1400.,'f4'))
    facts={int(n):m for n,m in measurements[11]['adaptive_raw'].items()}
    target,detail=reconnect.choose(sample,query['candidates'],facts,measurements[11]['adaptive_full'],'RAW_DEPTH',segment,certs)
    query.update(selection=score.json.loads(score.json.dumps(detail)),selected_target=target,
        contact_certificate=certs[100],admission_body_sha256=detail['admission_body_sha256'])
    return query,segment,arm,measurements,{str(n):c for n,c in certs.items()},depth,index,masks,binding


class ScoreChecks(unittest.TestCase):
    def test_unique_integer_ids_masks_and_negative_ids(self):
        objects=[dict(mask='n:1',id=-7),dict(mask='n:2',id=8)]
        assignment={'variants':{'N0':objects}}
        prediction={'variants':{a:copy.deepcopy(objects) for a in ARMS}}
        score.check_objects(assignment,prediction)
        for bad in (True,1.2,8):
            changed=copy.deepcopy(prediction);changed['variants'][ARMS[2]][0]['id']=bad
            with self.assertRaises(AssertionError):score.check_objects(assignment,changed)
        changed=copy.deepcopy(prediction);changed['variants'][ARMS[3]].reverse()
        with self.assertRaises(AssertionError):score.check_objects(assignment,changed)
        self.assertEqual(score.namespaced([-7],2),[(2,-7)])
        args=initial_birth_fixture();checked=score.check_birth_rows(*args)
        self.assertEqual(checked['birth_first_publication_queries'],3);self.assertEqual(checked['birth_true_commits'],0)
        bad=copy.deepcopy(args);bad[0][0]['queries']=[]
        with self.assertRaises(AssertionError):score.check_birth_rows(*bad)

    def test_selected_publisher_transaction_and_h0_no_stage(self):
        arm=ARMS[2]
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
        birth,segment,arm,m,s,tx,st,g=birth_fixture()
        self.assertEqual(score.check_birth_selection(birth,arm,segment,m[11]),7)
        self.assertEqual(score.check_birth_past(birth['candidates'][0],birth['query_observation'],arm,segment,s,tx,st,m,g),20)
        bad=copy.deepcopy(birth);bad['candidates'][0]['frozen_depth']['samples'][0]['fact_id']='forged'
        with self.assertRaises(AssertionError):score.check_birth_past(bad['candidates'][0],bad['query_observation'],arm,segment,s,tx,st,m,g)
        contact,segment,arm,m,certificates,*_=contact_fixture()
        self.assertEqual(score.check_birth_selection(contact,arm,segment,m[11],certificates),7)
        # Even a shared mask's internally valid missing certificate cannot admit a fish.
        from contact_measurement import measure_contact
        q,seg,arm,m,certs,depth,index,masks,binding=contact_fixture()
        masks[200]=masks[100].copy()
        duplicated=measure_contact(depth,index,masks,seg,11,100,source_binding=binding)
        self.assertFalse(duplicated[100]['eligible']);self.assertFalse(duplicated[200]['eligible'])
        bad=copy.deepcopy(birth);bad['candidates'][0]['geometry_history'][0]['center'][0]+=1.
        with self.assertRaises(AssertionError):score.check_birth_past(bad['candidates'][0],bad['query_observation'],arm,segment,s,tx,st,m,g)

    def test_unknown_notstaged_and_nochange_separate(self):
        expected={1:8,2:-7}
        self.assertEqual(audit.mapping_outcome(dict(status='LOCAL_FALLBACK_COMMITTED',mapping=None),expected,expected),({},'NOT_STAGED','CORRECT'))
        self.assertEqual(audit.mapping_outcome(dict(status='RESOLVE_NO_ID_CHANGE',mapping=expected),expected,{}),(expected,'UNSCORABLE_OR_NO_BIJECTION','UNSCORABLE_OR_NO_BIJECTION'))
        e=dict(q=2,depth_frozen={'A':dict(source=1,public=8,key=None,samples=[])})
        def no_reference(*args):raise AssertionError('must not need GT for missing history')
        out=audit.fragment_reference(e,{}, {},{},no_reference,ARMS[2],3)[0]
        self.assertEqual(out['surface_identity'],'UNKNOWN');self.assertIsNone(out['physical_depth_reference_mm'])
        self.assertIn('NO_FROZEN_HISTORY',out['exclusions'])
        same=dict(status='UNIQUE_IOU_MATCH',gt_id=9)
        other=dict(status='UNIQUE_IOU_MATCH',gt_id=10)
        query=dict(status='COMMIT',selected_target=8,actual_first_public_id=8)
        self.assertEqual(audit.birth_outcome(query,same,same),('CORRECT','CORRECT','SAME'))
        self.assertEqual(audit.birth_outcome(query,other,same),('WRONG','WRONG','DIFFERENT'))
        self.assertEqual(audit.birth_outcome(query,dict(status='AMBIGUOUS'),same),('UNSCORABLE','UNSCORABLE','UNKNOWN'))
        query.update(status='REJECTED',actual_first_public_id=11)
        self.assertEqual(audit.birth_outcome(query,same,same),('NOT_STAGED','NOT_RECONNECTED','SAME'))
        self.assertEqual(audit.physical_restore_qualification('COMMIT','SAME','SAME','SAME'),'SAME_QUERY_CLEAN_BANK_AND_SOURCE_ORIGIN_RGB_REFERENCE')
        self.assertEqual(audit.physical_restore_qualification('COMMIT','SAME','DIFFERENT','SAME'),'DIFFERENT_RGB_IDENTITY_REFERENCE')
        self.assertEqual(audit.physical_restore_qualification('COMMIT','SAME','UNKNOWN','SAME'),'UNKNOWN_RGB_IDENTITY_REFERENCE')
        self.assertEqual(audit.physical_restore_qualification('KEEP_NATIVE','SAME','SAME','SAME'),'NOT_COMMITTED')


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
        birth,segment,arm,m,*_=birth_fixture()
        for mutate in (lambda d:d['selection']['candidates']['OLD:7'].__setitem__('log_score',99.),
                       lambda d:d['selection']['depth_assignment'].__setitem__('measurement_fact_id','forged'),
                       lambda d:d['selection']['candidates']['OLD:7']['depth_forecast'].__setitem__('mu_mm',1001.)):
            bad=copy.deepcopy(birth);mutate(bad)
            with tempfile.TemporaryDirectory(prefix='ds12_birth_score_contract_') as directory:
                path=Path(directory)/'body.json';write_new(path,bad);seal=Path(directory)/'seal.json';write_new(seal,artifact(path));verify_item(read(seal))
                with self.assertRaises(AssertionError):score.check_birth_selection(read(path),arm,segment,m[11])
        contact,segment,arm,m,certs,*_=contact_fixture()
        from contact_measurement import _digest,validate_contact_certificate
        from reconnect import admission_hash
        for field in ('future_raw','pixel_fact','body','erase_neighbors'):
            bad=copy.deepcopy(contact);badcerts=copy.deepcopy(certs)
            if field in ('future_raw','pixel_fact'):
                c=badcerts['100']
                if field=='future_raw':
                    c['source_binding']['global_frame']+=1;c['global_frame']+=1
                else:
                    c['components'][0]['selected_depth_binding']['sha256']='0'*64
                    c['qualified_components'][0]['selected_depth_binding']['sha256']='0'*64
                c['certificate_sha256']=_digest(c)
                self.assertTrue(validate_contact_certificate(c))
                bad['contact_certificate']=copy.deepcopy(c)
                # Resealing bytes never makes either pixel certificate equal to the actual one.
                with self.assertRaises(AssertionError):score.check_contact_equality(badcerts,certs)
            elif field=='body':
                body=bad['selection']['admission_body'];body['query']['neighbors']=[]
                body['body_sha256']=admission_hash(body)
                bad['selection']['admission_body_sha256']=bad['admission_body_sha256']=body['body_sha256']
            else:bad['query_observation']['neighbors']=[]
            with tempfile.TemporaryDirectory(prefix='ds12_contact_score_contract_') as directory:
                path=Path(directory)/'body.json';write_new(path,bad);seal=Path(directory)/'seal.json';write_new(seal,artifact(path));verify_item(read(seal))
                with self.assertRaises(AssertionError):score.check_birth_selection(read(path),arm,segment,m[11],certs)
    def test_exact_cache_and_native_target(self):
        old={'restored':{'1':{'core':{'median':1000.,'mad':10.},'core_usable':True,
            'roi_geometry':{'pieces':[{'dt_max_px':6.082762241363525,'threshold_px':3.,'samples':20}]}}}}
        new=copy.deepcopy(old);new['restored']['1']['roi_geometry']['pieces'][0]['dt_max_px']=float(score.np.nextafter(score.np.float32(6.082762241363525),score.np.float32(10.)))
        self.assertEqual(score.check_source_extraction(copy.deepcopy(old),old),[])
        with self.assertRaises(AssertionError):score.check_source_extraction(new,old)
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
        pooled[ARMS[2]]=dict(IDF1=81.,HOTA=71.,AssA=61.,IDSW=10)
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
