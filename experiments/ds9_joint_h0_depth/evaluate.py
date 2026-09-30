"""DS9: six branch seals and semantic publication checks before reference access."""
from common import *
import gzip,hashlib,importlib.util,json,math,sys
spec=importlib.util.spec_from_file_location('ds9_official_helpers',NE1/'score.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
mask_rles,metrics,original_score=legacy.mask_rles,legacy.metrics,legacy.original_score
np,coco=original_score.np,original_score.coco
sys.path.insert(0,str(HERE))
SEALED_FILES={'predictions.jsonl.gz','DEPTH_OBSERVATIONS.jsonl.gz','DEPTH_STATES.jsonl.gz',
 'TRANSACTIONS.jsonl.gz','PUBLISH_LEDGER.jsonl','EVENTS.json','RUN_SUMMARY.json','FREEZE.json',
 'COMMON_STATE_SHADOW.json','PERFORMANCE.json'}
REQUIRED_ACCESS_TOKENS={'labels_640x360','labels_original','labels_source','sealed_test',
 '/rgb_640x360/','/rgb_original/','/color/','/rgb/','depth_restored_rgb_640x360/','restoration/v3/'}
DS8=HERE.parent/'ds8_adaptive_depth_core'

def verify_all_seals(run=RUN):
    run=Path(run)
    manifest=read(run/'ALL_PREDICTIONS_SEALED.json')
    assert manifest['status']=='ALL_SIX_BRANCHES_FOUR_SEGMENTS_SEALED'
    assert manifest['frames']==1471 and tuple(manifest['arms'])==ARMS
    assert set(manifest['seals'])==set(SEGMENTS)
    assert manifest['new_model_http']==manifest['model_cost_usd']==0
    for name,(start,stop) in SEGMENTS.items():
        public=run/name/'public'
        assert sha(public/'PREDICTIONS_SEALED.json')==manifest['seals'][name]
        seal=read(public/'PREDICTIONS_SEALED.json')
        assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
        assert seal['segment']==name and seal['original_frames']==[start,stop]
        assert tuple(seal['arms'])==ARMS and seal['frames']==seal['published_frames']==stop-start+1
        assert seal['new_model_http']==seal['model_cost_usd']==0
        assert SEALED_FILES<=set(seal['artifacts_sha256'])
        for n,h in seal['artifacts_sha256'].items():assert sha(public/n)==h,n
        freeze=read(public/'FREEZE.json')
        assert freeze['status']=='FROZEN_BEFORE_PREDICTION' and freeze['no_gt_before_seal'] is True
        assert freeze['segment']==name and freeze['original_frames']==[start,stop] and freeze['frames']==stop-start+1
        for p in (HERE/'evaluate.py',HERE/'event_audit.py',HERE/'score_checks.py',HERE/'SCORE_CHECKS.json',HERE/'association.py',HERE/'measurement.py',HERE/'runner.py',DS1/'postseal.py',NE1/'score.py',OLD/'score.py'):
            assert str(p.resolve()) in freeze['code_sha256'],p
        for p,h in freeze['code_sha256'].items():assert sha(p)==h,p
        assert len(freeze['native_depth_sources'])==stop-start+1
        for item in list(freeze['derived_inputs'].values())+list(freeze['restored_sources'].values())+list(freeze['current_metadata'].values())+freeze['native_depth_sources']:verify_item(item)
        assert sha(input_dir(name)/'SOURCE_MANIFEST.json')==freeze['source_manifest_sha256']
        assert sha(input_dir(name)/'scan_v4.json')==freeze['scan_sha256']
        assert sha(input_dir(name)/'sources.json')==freeze['source_list_sha256']
        originals=read(input_dir(name)/'sources.json');assert len(originals)==stop-start+1
        for src in originals:
            for prefix in ('prediction','depth'):
                verify_item(dict(path=src[prefix+'_path'],bytes=src[prefix+'_bytes'],sha256=src[prefix+'_sha256']))
    access=read(run/'ACCESS_SEALED.json')
    verify_item(access['artifact']);verify_item(access['prediction_all_seal'])
    assert Path(access['artifact']['path']).resolve()==(run/'PREDICTION_ACCESS_AUDIT.json').resolve()
    assert Path(access['prediction_all_seal']['path']).resolve()==(run/'ALL_PREDICTIONS_SEALED.json').resolve()
    audit=read(run/'PREDICTION_ACCESS_AUDIT.json')
    assert audit['status']=='NO_DIRECT_GT_RGB_V3_OR_NETWORK_DURING_PREDICTION'
    assert audit['new_model_http']==audit['cost_usd']==0
    assert REQUIRED_ACCESS_TOKENS<=set(audit['forbidden_path_tokens'])
    for p in audit['observed_data_paths']:
        assert not any(k in p.replace('\\','/').lower() for k in audit['forbidden_path_tokens'])
    assert all(x['key'] in ('depth_mm','source_index') for x in audit['npz_field_reads'])
    return manifest

def observation_facts(row,arm):
    assert arm in ARMS[1:]
    return row['restored' if arm.startswith('J2_') else 'adaptive_raw']

def check_objects(assignment,prediction):
    assert prediction['variants']['SAM3_NATIVE']==assignment['variants']['N0']
    assert set(prediction['variants'])==set(ARMS)
    masks=[x['mask'] for x in assignment['variants']['N0']]
    for arm in ARMS:
        objs=prediction['variants'][arm]
        assert [x['mask'] for x in objs]==masks
        assert all(type(x['id']) is int for x in objs),arm
        assert len(objs)==len(set(x['id'] for x in objs))
    assert prediction['variants']['J2_DEPTH_ZERO']==prediction['variants']['J0_GEOMETRY']
    return masks

def check_q_binding(e,arm,predictions,publish,transactions,states):
    q=e['q'];pub=publish[q]['event_publish'][arm]
    assert e['evidence_cutoff_frame']==q
    assert all(x['frame']==q for x in e['post_first_observations'].values())
    sources={int(n) for n in e['post_first_observations']};assert len(sources)==2
    assert pub['episode']==e['id'] and pub['q']==q and pub['post_sample_count']==1
    actual={int(x['mask'][2:]):x['id'] for x in predictions[q]['variants'][arm]}
    pair={n:actual[n] for n in sources}
    assert {int(n):v for n,v in pub['first_public_pair'].items()}==pair
    tx=transactions[(q,arm)]
    assert {int(n):v for n,v in tx['actual_published_mapping'].items()}==actual
    assert tx['restore']==e['restore']
    restore=e['restore'];staged=not restore['status'].startswith('LOCAL_FALLBACK')
    if staged:
        assert {int(n):v for n,v in restore['mapping'].items()}==pair
        assert bool(restore['changes'])==(restore['status']=='COMMIT')
        for n in sources:
            live=states[(q,arm)]['live'].get(str(n))
            assert not live or all(f>=q for f in live['sample_frames'])
    preview={int(n):v for n,v in restore['baseline_preview_mapping'].items()}
    assert set(preview)==sources
    if not staged:assert pair==preview
    if staged:
        assert {int(n):v for n,v in restore['changes'].items()}=={n:v for n,v in pair.items() if preview[n]!=v}
    choice=e['numeric']['choice']
    assert choice in ('H0','H1','H2') and restore['selected_choice']==choice
    assert choice!='H0' or (not staged and restore['mapping'] is None and not restore['changes'])
    detail=e['numeric']['detail']
    assert detail['evidence_max_frame']==q
    assert bool(detail['accepted'])==(choice in ('H1','H2'))
    assert intmap(detail['baseline_mapping'])==preview
    if staged:assert intmap(detail['selected_mapping'])==pair
    return pair

def intmap(value):
    assert all(type(v) is int for v in value.values())
    return {int(k):v for k,v in value.items()}

def check_source_extraction(new,old):
    # Values, provenance, timestamps and all object/cohort fields are unchanged.
    assert new==old,'DS9 extraction differs from sealed DS8 facts'

def check_frozen_sample(sample,frozen,arm,segment,measurements,states):
    frame=sample['frame'];row=measurements[frame]
    fact=observation_facts(row,arm)[str(frozen['source'])]
    live=states[(frame,arm)]['live'].get(str(frozen['source']))
    assert live and live['key']==frozen['key'] and frame in live['sample_frames']
    assert frozen['key'][0]==segment and frozen['key'][1]==arm and frozen['key'][3]==frozen['public']
    assert fact['core_usable'] and sample['time']==row['time']
    assert sample['fact_id']==fact['fact_id'] and sample['source']==fact['source']
    assert sample['z_mm']==fact['core']['median'] and sample['mad_mm']==fact['core']['mad']

def check_geometry_history(e,arm,segment,source_rows,transactions,generations):
    for role,history in e['pre_geometry_history'].items():
        index=('A','B').index(role)
        for p in history:
            f,n=p['frame'],p['source'];o=source_rows[f]['observations'][n]
            tx=transactions[(f,arm)];public=intmap(tx['actual_published_mapping'])[n]
            assert 1<=f<e['suspect_frame'] and n==e['member_sources'][index]
            assert p['time']==p['measured_time']==source_rows[f]['time']
            assert p['bbox']==o['box'] and p['center']==[(o['box'][0]+o['box'][2])/2,(o['box'][1]+o['box'][3])/2]
            assert p['area']==o['area'] and p['neighbors']==o.get('neighbors',[]) and p['depth']==o.get('depth')
            assert p['public_id']==public and p['public_epoch']==tx['epochs'][str(n)]
            assert p['source_generation']==generations[(f,n)]
        assert all(b['frame']==a['frame']+1 and b['time']>a['time'] for a,b in zip(history,history[1:]))
    if e['q'] is not None:
        for key,p in e['post_first_observations'].items():
            n=int(key);row=source_rows[e['q']];o=row['observations'][n]
            assert p['source']==n and p['frame']==e['q'] and p['time']==row['time']
            assert p['bbox']==o['box'] and p['center']==[(o['box'][0]+o['box'][2])/2,(o['box'][1]+o['box'][3])/2]

def geometry_mean(histories,role,query):
    # Reuse the old measured-coordinate predictor, with the original paired gate.
    from merge_split_manager import velocity
    fits={r:velocity(histories[r]) for r in ('A','B')}
    last=histories[role][-1];horizon=min(query-last['time'],1.)
    if all(fits[r]['status']!='UNKNOWN' for r in ('A','B')):
        fit=fits[role]
        return [fit['intercept_px'][i]+fit['px_per_second'][i]*(last['time']+horizon-fit['time_origin']) for i in (0,1)]
    return last['center']

def check_association(e,arm,segment,measurements,transactions):
    d=e['numeric']['detail'];q=e['q'];posts=e['post_first_observations']
    sources=[int(n) for n in posts];public=e['public_ids'];cfg=read(HERE/'CONFIG.json')
    assert len(sources)==len(public)==len(set(public))==2
    baseline=intmap(e['restore']['baseline_preview_mapping'])
    maps={'H0':baseline,'H1':dict(zip(sources,public)),'H2':dict(zip(sources,reversed(public)))}
    assert set(d['hypotheses'])==set(maps)
    canonical={};labels={}
    for label,mapping in maps.items():
        key=tuple((n,mapping[n]) for n in sources)
        rep=canonical.setdefault(key,label);labels.setdefault(rep,[]).append(label)
        assert intmap(d['hypotheses'][label]['mapping'])==mapping and d['hypotheses'][label]['canonical']==rep
    assert set(d['candidates'])==set(labels) and d['unique_physical_candidates']==len(labels)
    assert d['geometry_pre_cutoff_frame']==e['suspect_frame']-1
    assert set(d['geometry_forecasts'])==set(d['depth_forecasts'])=={'A','B'}
    assert set(d['edges'])=={f'{r}:{n}' for r in ('A','B') for n in sources}
    def geometry_fact(fact):
        rolefacts=[p for hist in e['pre_geometry_history'].values() for p in hist]
        match=[p for p in rolefacts if p['frame']==fact['frame'] and p['source']==fact['source']]
        assert len(match)==1
        p=match[0]
        assert fact==dict(fact_id=f"{segment}/F{p['frame']}/n:{p['source']}/geometry",
            frame=p['frame'],time=p['time'],source=p['source'],
            version=[p.get(k) for k in ('source','source_generation','public_id','public_epoch')],
            center_px=p['center'],bbox=p['bbox'])
        assert fact['frame']<e['suspect_frame'] and fact['time']<posts[str(sources[0])]['time']
    for role,forecast in d['geometry_forecasts'].items():
        for fact in forecast['pre_facts']:geometry_fact(fact)
        assert forecast['samples']==len(forecast['pre_facts'])
        history=e['pre_geometry_history'][role]
        assert [x['frame'] for x in forecast['pre_facts']]==[x['frame'] for x in history]
        assert forecast['available']==bool(history)
        if history:
            assert forecast['mu_px']==geometry_mean(e['pre_geometry_history'],role,posts[str(sources[0])]['time'])
        for residual in forecast['calibration'].get('residuals',[]):
            geometry_fact(residual['target'])
            for facts in residual['predictor_facts'].values():
                for fact in facts:
                    geometry_fact(fact)
                    assert fact['frame']<residual['target']['frame'] and fact['time']<residual['target']['time']
            assert residual['residual_px']==[residual['target']['center_px'][i]-residual['predicted_center_px'][i] for i in (0,1)]
            target=residual['target'];prefixes={r:[p for p in e['pre_geometry_history'][r] if p['frame']<target['frame'] and p['time']<target['time']][-10:] for r in ('A','B')}
            assert {r:[p['frame'] for p in residual['predictor_facts'][r]] for r in ('A','B')}=={r:[p['frame'] for p in prefixes[r]] for r in ('A','B')}
            assert residual['predicted_center_px']==geometry_mean(prefixes,role,target['time'])
    enabled=arm not in ('J0_GEOMETRY','J2_DEPTH_ZERO')
    assert d['depth_enabled']==enabled
    facts=observation_facts(measurements[q],arm)
    if enabled:
        assert set(d['depth_assignment'])==set(posts)
        assert d['post_pair_usable']==all(bool(facts[str(n)]['core_usable'] and facts[str(n)]['core']['median'] is not None and facts[str(n)]['core']['median']>0 and facts[str(n)]['core']['mad'] is not None and facts[str(n)]['core']['mad']>=0) for n in sources)
        for i,n in enumerate(sources):
            assigned=sources[1-i] if arm=='J2_DEPTH_PERMUTE' else n
            a=d['depth_assignment'][str(n)];m=facts[str(assigned)];original=facts[str(n)]
            assert a==dict(observation_post_source=n,assigned_depth_source=assigned,
                measurement_fact_id=m['fact_id'],original_post_measurement_fact_id=original['fact_id'],
                cohort=m.get('cohort','RAW'),observation_mm=m['core']['median'],observation_mad_mm=m['core']['mad'],
                core_usable=bool(m['core_usable']),original_cohort=original.get('cohort','RAW'),
                actual_state_source=n,actual_state_fact_id=original['fact_id'])
        from depth_state import predict
        for role,forecast in d['depth_forecasts'].items():
            frozen=e['depth_frozen'][role];query=posts[str(sources[0])]['time']
            expected=dict(predict(frozen,query),version_key=frozen['key'],cutoff_frame=frozen['cutoff_frame'],source=frozen['source'],public=frozen['public'])
            assert forecast==expected,'forecast is not from the actual frozen fact sequence'
        full=measurements[q]['restored_full' if arm.startswith('J2_') else 'adaptive_full']
        bg=dict(mu_mm=full['median'],scale_mm=max(60.,1.4826*full['mad'])) if full['n']>0 else None
        assert d['background']['depth']==bg
    else:
        assert not d['depth_assignment'] and not d['post_pair_usable'] and d['used_edges']==0
        assert d['background']['depth'] is None
        assert all(x==dict(status='DEPTH_MODALITY_DISABLED',mu_mm=None,scale_mm=None,samples=0,sample_fact_ids=[]) for x in d['depth_forecasts'].values())
    assert d['used_edges']==sum(x['depth']['used'] for x in d['edges'].values())
    target_roles=dict(zip(public,('A','B')))
    close=lambda a,b:math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12)
    for key,edge in d['edges'].items():
        role,n=edge['role'],edge['source'];assert key==f'{role}:{n}' and edge['associated']
        geo=edge['geometry'];forecast=d['geometry_forecasts'][role]
        assert geo['observed_center_px']==posts[str(n)]['center'] and geo['predicted_center_px']==forecast['mu_px'] and geo['shape_px2']==forecast['shape_px2']
        assert geo['used']==forecast['available']
        dep=edge['depth']
        if enabled:
            a=d['depth_assignment'][str(n)]
            assert dep['measurement_fact_id']==a['measurement_fact_id'] and dep['assigned_depth_source']==a['assigned_depth_source']
        else:assert dep['measurement_fact_id'] is None and dep['assigned_depth_source'] is None and not dep['used'] and dep['log_lr']==0.
        for modality in (geo,dep):
            assert close(modality['mixture_log_density'],modality['background_log_density']+modality['log_lr'])
            if not modality['used']:assert modality['raw_log_density'] is None and modality['log_lr']==0.
    for label,c in d['candidates'].items():
        assert c['labels']==labels[label] and intmap(c['mapping'])==maps[label]
        expected_pairs=[d['edges'][f'{target_roles[maps[label][n]]}:{n}'] if maps[label][n] in target_roles else d['background_edges'][str(n)] for n in sources]
        assert c['pairs']==expected_pairs
        g=sum(p['geometry']['log_lr'] for p in expected_pairs);z=sum(p['depth']['log_lr'] for p in expected_pairs)
        gl=sum(p['geometry']['mixture_log_density'] for p in expected_pairs);zl=sum(p['depth']['mixture_log_density'] for p in expected_pairs)
        assert close(c['log_prior'],-math.log(len(labels))) and close(c['geometry_log_lr'],g) and close(c['depth_log_lr'],z)
        assert close(c['geometry_log_likelihood'],gl) and close(c['depth_log_likelihood'],zl)
        assert close(c['log_joint_density'],c['log_prior']+gl+zl) and close(c['log_score'],c['log_prior']+g+z)
    ranked=sorted(d['candidates'],key=lambda k:(-d['candidates'][k]['log_score'],k!='H0',k))
    best=ranked[0];runner=ranked[1] if len(ranked)>1 else None
    margin=d['candidates'][best]['log_score']-d['candidates'][runner]['log_score'] if runner else None
    assert d['best']==best and d['runner_up']==runner and d['margin']==margin
    assert close(d['minimum_log_odds'],math.log(cfg['minimum_joint_odds']))
    accepted=bool(runner and best!='H0' and margin>=d['minimum_log_odds'])
    choice=best if accepted else 'H0'
    assert d['accepted']==accepted and e['numeric']['choice']==choice and intmap(d['selected_mapping'])==maps[choice]
    maximum=d['candidates'][best]['log_score'];total=sum(math.exp(c['log_score']-maximum) for c in d['candidates'].values())
    assert all(close(c['posterior'],math.exp(c['log_score']-maximum)/total) for c in d['candidates'].values())

def verify_publication(run=RUN):
    run=Path(run);verify_all_seals(run);checks=[];q_checks=history_checks=group_checks=0
    for name,(start,stop) in SEGMENTS.items():
        public=run/name/'public';nframes=stop-start+1
        current=list(rows(public/'predictions.jsonl.gz'))
        old_public=DS8/'run'/name/'public';old_seal=read(old_public/'PREDICTIONS_SEALED.json')
        assert old_seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
        assert old_seal['frames']==old_seal['published_frames']==nframes
        old_all=read(DS8/'run/ALL_PREDICTIONS_SEALED.json')
        assert sha(old_public/'PREDICTIONS_SEALED.json')==old_all['seals'][name]
        for file,h in old_seal['artifacts_sha256'].items():assert sha(old_public/file)==h,file
        old=list(rows(old_public/'predictions.jsonl.gz'))
        state_rows=list(rows(public/'DEPTH_STATES.jsonl.gz'))
        states={(x['frame'],x['arm']):x for x in state_rows}
        tx_rows=list(rows(public/'TRANSACTIONS.jsonl.gz'))
        tx={(x['frame'],x['arm']):x for x in tx_rows}
        expected_keys={(f,a) for f in range(1,nframes+1) for a in ARMS[1:]}
        assert len(state_rows)==len(states)==len(tx_rows)==len(tx)==nframes*(len(ARMS)-1)
        assert set(states)==set(tx)==expected_keys
        source_rows={};generations={};last_source={};source_generation={}
        for source_row in rows(input_dir(name)/'observations.jsonl.gz'):
            f=source_row['frame'];objects={o['id']:o for o in source_row['observations']}
            source_rows[f]=dict(time=source_row['time'],observations=objects)
            for native in objects:
                generation=source_generation.get(native,0)+(last_source.get(native)!=f-1)
                generations[(f,native)]=generation;source_generation[native]=generation;last_source[native]=f
        assert set(source_rows)==set(range(1,nframes+1))
        measure_rows=list(rows(public/'DEPTH_OBSERVATIONS.jsonl.gz'))
        measurements={x['frame']:x for x in measure_rows}
        assert len(measure_rows)==len(measurements)==nframes
        assert set(measurements)==set(range(1,nframes+1))
        old_measure_rows=list(rows(old_public/'DEPTH_OBSERVATIONS.jsonl.gz'))
        assert len(old_measure_rows)==nframes
        for newfact,oldfact in zip(measure_rows,old_measure_rows,strict=True):check_source_extraction(newfact,oldfact)
        events=read(public/'EVENTS.json');assert set(events)==set(ARMS[1:])
        publisher=list(rows(public/'PUBLISH_LEDGER.jsonl'));publish={x['frame']:x for x in publisher}
        assert len(publisher)==len(publish)==nframes
        predictions={x['frame']:x for x in current};assert len(predictions)==nframes
        with gzip.open(public/'predictions.jsonl.gz','rt',encoding='utf-8') as lines:
            for i,(line,pub,assignment,new,previous) in enumerate(zip(lines,publisher,rows(input_dir(name)/'assignments.jsonl.gz'),current,old,strict=True),1):
                assert hashlib.sha256(line.encode()).hexdigest()==pub['prediction_row_sha256']
                assert new['frame']==pub['frame']==assignment['frame']==i
                assert new['global_frame']==pub['global_frame']==assignment['global_frame_id']==start+i-1
                assert all(new[k]==previous[k] for k in ('frame','global_frame','time'))
                assert measurements[i]['frame']==i and measurements[i]['global_frame']==start+i-1 and measurements[i]['time']==new['time']
                check_objects(assignment,new)
                assert new['variants']['SAM3_NATIVE']==previous['variants']['SAM3_NATIVE'],(name,i)
                for arm in ARMS[1:]:
                    actual={int(x['mask'][2:]):x['id'] for x in new['variants'][arm]}
                    assert {int(n):v for n,v in tx[(i,arm)]['actual_published_mapping'].items()}==actual
                    last={int(x['mask'][2:]):x['id'] for x in predictions[i-1]['variants'][arm]} if i>1 else {}
                    assert {int(n):v for n,v in tx[(i,arm)]['previous_mapping'].items()}==last
        assert len(current)==nframes
        for arm in ARMS[1:]:
            for e in events[arm]:
                check_geometry_history(e,arm,name,source_rows,tx,generations)
                for role,frozen in (e['depth_frozen'] or {}).items():
                    assert frozen['cutoff_frame']==e['suspect_frame']-1
                    samples=frozen['samples']
                    assert all(x['frame']<e['suspect_frame'] for x in samples)
                    assert all(b['frame']==a['frame']+1 and b['time']>a['time'] for a,b in zip(samples,samples[1:]))
                    if samples:assert frozen['key'][0]==name and frozen['key'][1]==arm and frozen['key'][3]==frozen['public']
                    for x in samples:
                        check_frozen_sample(x,frozen,arm,name,measurements,states)
                        source=frozen['source'];f=x['frame']
                        assert frozen['key'][2]==generations[(f,source)]
                        assert frozen['key'][3]==intmap(tx[(f,arm)]['actual_published_mapping'])[source]
                        assert frozen['key'][4]==tx[(f,arm)]['epochs'][str(source)]
                        history_checks+=1
                for group in e['group_observations']:
                    live=states[(group['frame'],arm)]['live'].get(str(group['source']))
                    assert not live or group['frame'] not in live['sample_frames'];group_checks+=1
                if e['q'] is not None:
                    check_q_binding(e,arm,predictions,publish,tx,states)
                    check_association(e,arm,name,measurements,tx);q_checks+=1
        checks.append(dict(segment=name,frames=len(current),native_equals_DS8=True,
            depth_zero_equals_geometry=True,source_extraction_equals_DS8=True,
            old_seal_sha256=sha(old_public/'PREDICTIONS_SEALED.json')))
    write_new(run/'VERIFICATION.json',dict(status='PASS_BEFORE_GT_SCORING',checks=checks,
        q_publication_checks=q_checks,frozen_sample_fact_checks=history_checks,group_checks=group_checks,
        zero_deleted_masks=True,all_prediction_seals_verified=True,access_seal_sha256=sha(run/'ACCESS_SEALED.json')))

def support_layers(pooled):
    def exceeds(a,b):
        return all(pooled[a][k]>pooled[b][k] for k in ('IDF1','HOTA','AssA')) and pooled[a]['IDSW']<=pooled[b]['IDSW']
    return dict(geometry_tracking_support=exceeds('J0_GEOMETRY','SAM3_NATIVE'),
        raw_tracking_support=exceeds('J1_RAW_DEPTH','SAM3_NATIVE'),
        restored_tracking_support=exceeds('J2_RESTORED_DEPTH','SAM3_NATIVE'),
        raw_increment_vs_geometry=exceeds('J1_RAW_DEPTH','J0_GEOMETRY'),
        restored_increment_vs_geometry=exceeds('J2_RESTORED_DEPTH','J0_GEOMETRY'),
        restored_increment_vs_depth_zero=exceeds('J2_RESTORED_DEPTH','J2_DEPTH_ZERO'),
        restored_increment_vs_depth_permute=exceeds('J2_RESTORED_DEPTH','J2_DEPTH_PERMUTE'),
        restored_increment_vs_raw=exceeds('J2_RESTORED_DEPTH','J1_RAW_DEPTH'),
        restored_independent_increment_supported=all(exceeds('J2_RESTORED_DEPTH',a) for a in ('J0_GEOMETRY','J2_DEPTH_ZERO','J2_DEPTH_PERMUTE')),
        restored_scope='EXPOSED_OFFLINE_NATIVE_V2_RGB_NEXT_FRAME_SUPPORTED',
        physical_depth_accuracy='UNKNOWN',causal_raw_depth_and_restored_claims_separate=True)
def namespaced(ids, segment_index):
    return [(segment_index, int(identity)) for identity in ids]


def score(run=RUN):
    verify_all_seals(run)
    verification = read(Path(run)/'VERIFICATION.json')
    assert verification['status'] == 'PASS_BEFORE_GT_SCORING'
    combined_truth, combined_sims = [], []
    combined = {arm: [] for arm in ARMS}
    segment_metrics, reference, changed = {}, {}, {}
    pairs = [(arm, 'SAM3_NATIVE') for arm in ARMS[1:]] + [('J1_RAW_DEPTH','J0_GEOMETRY')] + [
        ('J2_RESTORED_DEPTH', arm) for arm in ('J0_GEOMETRY','J1_RAW_DEPTH','J2_DEPTH_ZERO','J2_DEPTH_PERMUTE')]
    for index, (name, (start, stop)) in enumerate(SEGMENTS.items()):
        truth, sims = [], []
        predictions = {arm: [] for arm in ARMS}
        reference_hash = hashlib.sha256()
        changed[name] = {f'{a}_vs_{b}': 0 for a, b in pairs}
        for local, (assignment, prediction) in enumerate(zip(
                rows(input_dir(name)/'assignments.jsonl.gz'),
                rows(Path(run)/name/'public/predictions.jsonl.gz'), strict=True), 1):
            native = check_objects(assignment, prediction)
            assert assignment['frame'] == prediction['frame'] == local
            assert assignment['global_frame_id'] == prediction['global_frame'] == start+local-1
            path = DATA/'labels_640x360'/f'{start+local-1:06d}.json'
            raw = path.read_bytes()
            reference_hash.update(path.name.encode()+b'\0'+raw)
            gt_ids, gt_masks = mask_rles(json.loads(raw)['shapes'])
            masks = [original_score.rle(assignment['masks'][key]) for key in native]
            sim = (np.asarray(coco.iou(gt_masks, masks, [0]*len(masks)), float)
                   if gt_masks and masks else np.zeros((len(gt_ids), len(native))))
            truth.append(gt_ids); sims.append(sim)
            combined_truth.append(namespaced(gt_ids, index)); combined_sims.append(sim)
            for arm in ARMS:
                ids = [int(x['id']) for x in prediction['variants'][arm]]
                predictions[arm].append(ids)
                combined[arm].append(namespaced(ids, index))
            for a, b in pairs:
                changed[name][f'{a}_vs_{b}'] += prediction['variants'][a] != prediction['variants'][b]
        assert len(truth) == stop-start+1
        segment_metrics[name] = {arm: metrics(truth, predictions[arm], sims) for arm in ARMS}
        reference[name] = dict(label_dir=str(DATA/'labels_640x360'), frames=len(truth),
            ordered_file_bytes_sha256=reference_hash.hexdigest(),
            qualification='existing human-edited RGB polygons; not independently certified',
            physical_depth_gt=False, pixel_surface_gt=False)
    pooled = {arm: metrics(combined_truth, combined[arm], combined_sims) for arm in ARMS}
    for arm in ARMS:
        for key in ('IDSW', 'FP', 'FN', 'GT', 'predictions'):
            assert pooled[arm][key] == sum(x[arm][key] for x in segment_metrics.values()), (arm, key)
    delta = {f'{a}_vs_{b}': {key: pooled[a][key]-pooled[b][key]
        for key in ('IDF1', 'HOTA', 'AssA', 'DetA', 'IDSW', 'FP', 'FN')} for a, b in pairs}
    support = {arm: dict(rate_improvements={key: pooled[arm][key] > pooled['SAM3_NATIVE'][key]
                  for key in ('IDF1', 'HOTA', 'AssA')},
                  idsw_not_increased=pooled[arm]['IDSW'] <= pooled['SAM3_NATIVE']['IDSW'])
               for arm in ('J1_RAW_DEPTH','J2_RESTORED_DEPTH')}
    supported = any(all(x['rate_improvements'].values()) and x['idsw_not_increased'] for x in support.values())
    result = dict(status='SCORED_AFTER_ALL_PREDICTION_SEALS', frames=len(combined_truth),
        segment_metrics=segment_metrics, pooled_metrics=pooled, pooled_delta=delta,
        changed_frames=changed, reference=reference,
        seal_sha256={name: sha(Path(run)/name/'public/PREDICTIONS_SEALED.json') for name in SEGMENTS},
        all_seal_sha256=sha(Path(run)/'ALL_PREDICTIONS_SEALED.json'),
        no_negative_id_filtering=True, segment_identity_reset=True,
        pooled_method='direct_TrackEval_on_all_frames_with_tuple_segment_identity_namespaces',
        score_support_layers=support_layers(pooled), frozen_support_rule=support, frozen_support_rule_met=supported,
        interpretation='exposed development-set tracking result; no physical-depth or surface-ownership GT',
        new_model_http=0, model_cost_usd=0)
    assert result['frames'] == 1471
    write_new(Path(run)/'METRICS.json', result)
    write_new(Path(run)/'SCORE_PROVENANCE.json', dict(evaluate_sha256=sha(__file__),
        event_audit_sha256=sha(HERE/'event_audit.py'), legacy_helpers_sha256=sha(NE1/'score.py'), matching_helper_sha256=sha(DS1/'postseal.py'), score_template_sha256=sha(DS8/'evaluate.py'), score_adaptation='DS9_explicit_H0_geometry_raw_restored_zero_post_permute_actual_state_facts',
        scored_after_all_seals=True, trackeval_path=str(original_score.DEPS),
        reference=reference, segment_seal_sha256=result['seal_sha256'],
        all_seal_sha256=result['all_seal_sha256'], verification_sha256=sha(Path(run)/'VERIFICATION.json')))
    return result


def main():
    verify_publication()
    result=score()
    import event_audit
    event_audit.audit(sys.modules[__name__])
    print(json.dumps(dict(pooled=result['pooled_metrics'],delta=result['pooled_delta'],support=result['frozen_support_rule_met'])))
if __name__=='__main__':main()
