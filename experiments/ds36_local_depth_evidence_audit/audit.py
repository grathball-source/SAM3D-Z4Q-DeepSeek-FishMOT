"""One fixed read-only cohort: local depth distributions and causal forecast diagnostics."""
from common import *
from measurement import measure,compare,components
from collections import defaultdict,Counter
from datetime import datetime,timezone
import copy, math, platform, shutil
import numpy as np

def utc():return datetime.now(timezone.utc).isoformat()
def dump(handle,value):handle.write(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n')
def key(name,frame,native):return f'{name}/F{frame}/n:{native}'

def cohort():
    features=list(rows(DS21/'FEATURES.jsonl.gz'))
    assert len(features)==90 and len({f['action_id'] for f in features})==90
    assert all('physical' not in f for f in features)
    events={name:read(DS35/'run'/name/'public/EVENTS.json')['DEPTH_OVERRIDE'] for name in SEGMENTS}
    requests={};links=[]
    def add(name,frame,native,context,role,cutoff,version=None):
        assert 1<=frame<=SEGMENTS[name][1]-SEGMENTS[name][0]+1 and frame<=cutoff
        k=key(name,frame,native)
        requests.setdefault(k,dict(segment=name,frame=frame,native=native,contexts=[]))['contexts'].append(
            dict(context=context,role=role,evidence_cutoff=cutoff,recorded_version=version))
        return k
    for f in features:
        current=add(f['segment'],f['frame'],f['source'],f['action_id'],'CURRENT',f['frame'])
        anchors={}
        for role,fid in f['anchor_fact_ids'].items():
            _,frame,native,_=fid.split('/');anchors[role]=add(f['segment'],int(frame[1:]),int(native[2:]),f['action_id'],role,f['frame'])
        links.append(dict(action_id=f['action_id'],segment=f['segment'],frame=f['frame'],current=current,
                          anchors=anchors,primary_role='BIRTH_CORE' if f['origin_rule']=='BIRTH_REFINE' else 'D1_WHOLE',
                          original_feature_sha256=digest(f),physical_labels_read=False))
    for name,group in events.items():
        for e in group:
            context=f'{name}/{e["id"]}';cutoff=e['q'] if e['q'] is not None else (e.get('end') or e['suspect_frame'])
            for role,ref in e['joint_pre'].items():
                anchor=ref.get('anchor')
                if anchor:
                    add(name,anchor['frame'],anchor['native_id'],context,'PRE_'+role,cutoff,ref.get('version'))
            add(name,e['suspect_frame'],e['group_source'],context,'SUSPECT_GROUP',cutoff)
            observed=[p['frame'] for p in e.get('group',[]) if p['frame']<=cutoff]
            for f in sorted({observed[0],observed[-1]} if observed else set()):
                add(name,f,e['group_source'],context,'ANONYMOUS_GROUP',cutoff)
            if e['q'] is not None:
                for native,post in e['post_roles'].items():
                    same=[p for p in post if p['frame']==e['q']]
                    if same:add(name,e['q'],int(native),context,'POST_AT_Q',cutoff)
    return features,events,requests,links

def initialize():
    assert git('rev-parse','HEAD').decode().strip()==BASE
    assert not git('diff','--name-only').decode().strip()
    disk=shutil.disk_usage(ROOT);assert disk.free>500*1024**2
    initial=dict(created_utc=utc(),base_commit=BASE,python=sys.executable,python_version=platform.python_version(),
        system=platform.platform(),cpu_jobs=1,library_threads=1,disk_free_bytes=disk.free,
        GPU=False,server=False,model_http=0,cost_usd=0,original_handoff=artifact(ROOT/'research/HANDOFF.md'),
        original_gitignore=artifact(ROOT/'.gitignore'))
    features,events,requests,links=cohort()
    pins={}
    def pin(p):
        p=Path(p).resolve();value=artifact(p)
        if ROOT in p.parents and 'private' not in p.relative_to(ROOT).parts:
            blob=git('show',BASE+':'+p.relative_to(ROOT).as_posix())
            assert hashlib.sha256(blob).hexdigest()==value['sha256']
        pins[str(p)]=value
    for f in ('FEATURES.jsonl.gz','FEATURES_SEALED.json','OBSERVATION_FACTS.jsonl.gz','ACTIONS.json'):
        pin(DS21/f)  # ACTIONS bytes only; labels content stays unopened until feature seal.
    for f in ('PUBLIC_ARTIFACT_MANIFEST.json','RUNTIME_FREEZE.json','CONFIG.json','run/ALL_PREDICTIONS_SEALED.json',
              'run/PREDICTION_PARITY.json','run/METRICS.json'):
        pin(DS35/f)
    all_seal=read(DS35/'run/ALL_PREDICTIONS_SEALED.json')
    assert all_seal['frames']==20098 and set(all_seal['seals'])==set(SEGMENTS)
    for name in SEGMENTS:
        for field in ('seals','access_seals','starts','ends'):
            i=all_seal[field][name];verify_item(i);pin(i['path'])
        public=DS35/'run'/name/'public';seal=read(public/'PREDICTIONS_SEALED.json')
        for filename,expected in seal['artifacts_sha256'].items():
            p=public/filename;assert sha(p)==expected;pin(p)
        source=input_dir(name)/'SOURCE_MANIFEST.json'
        assert artifact(source)==read(public/'FREEZE.json')['source_manifest']
        pin(source);m=read(source)
        assert m['no_GT'] and m['no_RGB'] and m['no_restored_values']
        for i in m['derived_inputs'].values():verify_item(i);pins[i['path']]=i
        for k in ('raw_sources','field_access','scan'):
            verify_item(m[k]);pins[m[k]['path']]=m[k]
    for path,expected in read(DS35/'RUNTIME_FREEZE.json')['code'].items():
        assert sha(path)==expected,path;pins[str(Path(path).resolve())]=artifact(path)
    save('ENVIRONMENT_INITIAL_V2.json',initial)
    save('INPUT_PINS.json',dict(status='OLD_FROZEN_SOURCE_BYTES_VERIFIED',files=list(pins.values()),
                               physical_label_content_opened=False))
    save('COHORT.json',dict(actions=links,requests=list(requests.values()),action_count=len(features),
                           event_count=sum(map(len,events.values())),physical_label_content_opened=False,
                           source_selection='ALL_ORIGINAL_ACTIONS_AND_ALL_DS35_EVENTS; NO_GT_SELECTION'))
    save('CONFIG.json',CFG)
    print('INITIALIZED',len(features),sum(map(len,events.values())),len(requests),flush=True)

def freeze():
    checks=read(HERE/'CHECKS.json');assert checks['status']=='PASS'
    pins=read(HERE/'INPUT_PINS.json')['files']
    pins.extend(artifact(p) for p in HERE.iterdir() if p.is_file() and p.suffix in ('.py','.md','.json')
                and p.name!='FREEZE.json')
    for pin in pins:verify_item(pin)
    save('FREEZE.json',dict(status='FROZEN_BEFORE_FULL_MEASUREMENT_AND_LABEL_JOIN',frozen_utc=utc(),
        files=list({p['path']:p for p in pins}.values()),config=CFG,actions=90,events=75,
        new_predictions=False,new_metrics=False,model_http=0,cost_usd=0))
    print('FROZEN',flush=True)

def risk_ranges(events):
    result=defaultdict(list)
    for e in events:
        natives={*e['member_sources'],e['group_source'],*(int(n) for n in e.get('post_roles',{}))}
        for n in natives:result[n].append((e['suspect_frame'],e.get('end') or e['suspect_frame'],e['id']))
    return result

def temporal(name,events,keep_frames,output):
    """Original state is read, never replayed or mutated. Targets do not enter fits."""
    source=input_dir(name);public=DS35/'run'/name/'public';ranges=risk_ranges(events)
    tx=(v for v in rows(public/'TRANSACTIONS.jsonl.gz') if v['arm']=='Z4Q_FROZEN')
    previous={};fragments=[];live={};counts=Counter();held={};last=0
    streams=zip(rows(source/'observations.jsonl.gz'),rows(public/'FRAME_INPUTS_BINDINGS.jsonl.gz'),tx,strict=True)
    for row,binding,transaction in streams:
        frame,now=row['frame'],row['time'];assert frame==last+1;last=frame
        assert (binding['frame'],transaction['frame'])==(frame,frame)
        assert line_hash(row)==binding['source_row_sha256']==transaction['source_row_sha256']
        if frame in keep_frames:held[frame]=binding
        seen=set()
        for o in row['observations']:
            n=o['id'];seen.add(n);fact=binding['DS18_extracts'][str(n)]
            old_point=previous.get(n);generation=(old_point[1] if old_point and old_point[0]==frame-1 else old_point[1]+1 if old_point else 1)
            public_id=transaction['mapping'][str(n)];epoch=transaction['actual_epochs'].get(str(n));version=[n,generation,public_id,epoch]
            anchor=transaction['bank_anchors'].get(str(public_id));risk=[]
            if public_id<0:risk.append('NONPERSISTENT_PUBLIC')
            if anchor!=dict(frame=frame,native_id=n,canonical_id=public_id,mask=o['mask']):risk.append('NOT_CURRENT_REAL_BANK_ANCHOR')
            if o.get('neighbors'):risk.append('NEIGHBOR_CONTACT')
            if any(a<=frame<=b for a,b,_ in ranges[n]):risk.append('ACTUAL_GROUP_OR_PENDING_EVENT')
            if old_point and old_point[2]!=version:risk.append('SOURCE_OR_IDENTITY_VERSION_BREAK')
            if old_point and old_point[0]!=frame-1:risk.append('SOURCE_VISIBILITY_BREAK')
            if fact['quality'].get('whole_multilayer') or fact['quality'].get('core_multilayer'):risk.append('MEASURED_MIXTURE_RISK')
            if not fact['quality'].get('exclusive_native_sources',False) or fact['quality'].get('unverified_source_n',0):risk.append('MEASUREMENT_SOURCE_OWNERSHIP_RISK')
            point=dict(segment=name,frame=frame,global_frame=row['global_frame'],time=now,native=n,public=public_id,
                       version=version,z_mm=fact['z_mm'],mad_mm=fact['mad_mm'],scale_mm=fact['scale_mm'],
                       usable=fact['usable'],fact_id=fact['fact_id'],certificate_sha256=fact['certificate_sha256'],
                       source_row_sha256=binding['source_row_sha256'],source_risks=risk,
                       depth_reason=fact['reason'],physical_identity='UNKNOWN_SAVED_SOURCE_PROXY')
            dump(output,point);counts['observations']+=1;counts['depth_usable']+=fact['usable']
            counts.update('risk:'+r for r in risk)
            if not fact['usable'] and not risk:counts['ordinary_depth_missing_without_identity_risk']+=1
            if risk:
                if n in live:fragments.append(live.pop(n))
            else:
                if n not in live:live[n]=[]
                live[n].append(point)
            previous[n]=(frame,generation,version)
        for n in list(live):
            if n not in seen:fragments.append(live.pop(n));counts['visibility_end']+=1
    fragments.extend(live.values());assert last==SEGMENTS[name][1]-SEGMENTS[name][0]+1
    counts['clean_proxy_fragments']=len(fragments)
    return fragments,held,dict(counts)

def calibration(name,fragments,output):
    counts=Counter();by_horizon=defaultdict(Counter)
    for number,fragment in enumerate(fragments):
        assert all(not p['source_risks'] for p in fragment)
        assert all(b['frame']==a['frame']+1 and b['version']==a['version'] and b['time']>a['time'] for a,b in zip(fragment,fragment[1:]))
        for end in range(CFG['history_samples']-1,len(fragment),CFG['calibration_anchor_stride']):
            history=fragment[end-9:end+1];anchor=history[-1];counts['fixed_prefix_opportunities']+=1
            if not all(p['usable'] for p in history):
                counts['history_blocked_by_depth_missing']+=1;continue
            times=np.array([p['time'] for p in fragment])
            for horizon in CFG['horizons_seconds']:
                bucket=by_horizon[str(horizon)];bucket['prefix_opportunities']+=1
                target_index=int(np.searchsorted(times,anchor['time']+horizon,side='left'))
                if target_index>=len(fragment):bucket['same_fragment_ended_before_horizon']+=1;continue
                target=fragment[target_index]
                if not target['usable']:bucket['first_target_depth_unusable']+=1;continue
                pred=DEPTH.forecast(history,target['time']);assert pred['usable'] and pred['status']=='WLS_LINEAR_TIME'
                delta=target['time']-anchor['time'];scale=math.hypot(pred['scale_mm'],target['scale_mm'])
                variants={'WLS':pred['mu_mm'],'INTERCEPT_MATCHED_SCALE':pred['beta_intercept_mm'],'LAST_VALUE_MATCHED_SCALE':anchor['z_mm']}
                errors={k:dict(mu_mm=mu,error_mm=target['z_mm']-mu,absolute_error_mm=abs(target['z_mm']-mu),
                        standardized_absolute_error=abs(target['z_mm']-mu)/scale,
                        within_one_scale=abs(target['z_mm']-mu)<=scale,within_two_scales=abs(target['z_mm']-mu)<=2*scale)
                        for k,mu in variants.items()}
                value=dict(segment=name,fragment=f'{name}/fragment:{number}',nominal_horizon_seconds=horizon,
                    anchor_frame=anchor['frame'],target_frame=target['frame'],query_time=target['time'],
                    actual_horizon_seconds=delta,version=anchor['version'],history_frames=[p['frame'] for p in history],
                    history_fact_ids=[p['fact_id'] for p in history],history_sha256=digest(history),target_fact_id=target['fact_id'],
                    target_measurement_mm=target['z_mm'],forecast=pred,combined_scale_mm=scale,errors=errors,
                    scale_components=components(pred,history),future_target_for_diagnostic_only=True,
                    independent_physical_calibration=False,tracker_state_write=False)
                assert max(value['history_frames'])<value['target_frame']
                dump(output,value);bucket['measured_proxy_pairs']+=1;counts['measured_proxy_pairs']+=1
    return dict(counts=dict(counts),horizons={h:dict(v) for h,v in by_horizon.items()})

def gate_components(name,events,held,output):
    count=0
    for e in events:
        d=e.get('joint_decision',{})
        if not d.get('common_weights',{}).get('depth'):continue
        done=set()
        for candidate in d['scores']:
            for edge in candidate['edges']:
                for r in edge['depth_rows']:
                    for pid,p in r['detail']['forecasts'].items():
                        k=(r['frame'],pid)
                        if k in done:continue
                        done.add(k)
                        ref=next(v for v in e['joint_pre'].values() if str(v['public'])==str(pid))
                        samples=[]
                        for f in p['sample_frames']:
                            s=next(x for x in ref['samples'] if x['frame']==f)
                            fact=held[f]['DS18_extracts'][str(s['native'])]
                            samples.append(dict(fact,version=s['version']))
                        pred=DEPTH.forecast(samples,p['query_time'])
                        for field in ('status','mu_mm','slope_mm_s','scale_mm','sample_frames','sample_fact_ids'):
                            assert pred[field]==p[field],(name,e['id'],field)
                        currents=[]
                        for native,post in e['post_roles'].items():
                            fact=held[r['frame']]['DS18_extracts'].get(native)
                            if fact:currents.append(dict(native=int(native),fact_id=fact['fact_id'],usable=fact['usable'],
                                observed_mm=fact['z_mm'],WLS_error_mm=None if fact['z_mm'] is None else fact['z_mm']-pred['mu_mm']))
                        dump(output,dict(segment=name,event=e['id'],q=e['q'],post_frame=r['frame'],public=pid,
                            reason=d['reason'],forecast=pred,scale_components=components(pred,samples),
                            current_anonymous_alternatives=currents,physical_mapping='UNKNOWN_BEFORE_LABEL_JOIN',state_write=False))
                        count+=1
    return count

def measurements():
    verify_freeze();features,events,requests,links=cohort()
    assert read(HERE/'COHORT.json')['requests']==list(requests.values())
    counts={};fragments={};held={}
    with gzip.open(HERE/'TEMPORAL_TRACE.jsonl.gz','xt',encoding='utf-8',newline='\n') as trace, \
         gzip.open(HERE/'CAUSAL_FORECAST_PAIRS.jsonl.gz','xt',encoding='utf-8',newline='\n') as pairs, \
         gzip.open(HERE/'DS35_GATE_SCALE_COMPONENTS.jsonl.gz','xt',encoding='utf-8',newline='\n') as gates:
        for name in SEGMENTS:
            needed={v['frame'] for v in requests.values() if v['segment']==name}
            needed|={s['frame'] for e in events[name] for ref in e['joint_pre'].values() for s in ref['samples']}
            needed|={r['frame'] for e in events[name] for c in e.get('joint_decision',{}).get('scores',[]) for edge in c['edges'] for r in edge['depth_rows']}
            fragments[name],held[name],counts[name]=temporal(name,events[name],needed,trace)
            counts[name]['calibration']=calibration(name,fragments.pop(name),pairs)
            counts[name]['gate_forecasts']=gate_components(name,events[name],held[name],gates)
            print('TEMPORAL',name,json.dumps(counts[name]),flush=True)
    del fragments
    all_results={};populations={};missing=[];pair_results=[];sensor_pins={};frame_count=0
    original_facts={f['fact_id']:f for f in rows(DS21/'OBSERVATION_FACTS.jsonl.gz')}
    with gzip.open(HERE/'LOCAL_MEASUREMENTS.jsonl.gz','xt',encoding='utf-8',newline='\n') as output:
        for name in SEGMENTS:
            wanted=defaultdict(dict)
            for k,r in requests.items():
                if r['segment']==name:wanted[r['frame']][r['native']]=r
            assignments={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame'] in wanted}
            sensor=SOURCE.RawDepth(name)
            try:
                for frame in sorted(wanted):
                    b=held[name][frame];a=assignments[frame]
                    assert line_hash(a)==b['assignment_row_sha256']
                    depth,index,native_depth,binding=sensor(b['global_frame'],b['time'])
                    assert binding==b['raw_source_binding']
                    masks=SOURCE.native_masks(a);selected=set(wanted[frame])&set(masks)
                    for n in wanted[frame]:
                        if n not in masks:missing.append(dict(**wanted[frame][n],reason='REQUESTED_ANONYMOUS_MASK_ABSENT'))
                    for n in tuple(selected):
                        wide=MEASUREMENT._dilate(masks[n],CFG['neighbor_radius_px'])
                        selected.update(other for other,m in masks.items() if other!=n and (wide&m).any())
                    for n in sorted(selected):
                        k=key(name,frame,n)
                        result,pop=measure(depth,index,native_depth,masks,n,name,frame,b['global_frame'],b['time'],binding,b['raw_source_binding'])
                        if k+'/observation' in original_facts:
                            assert result['mask_binding']==original_facts[k+'/observation']['certificate']['mask_binding']
                        assert result['views']['core']['roi_binding']==b['DS18_extracts'][str(n)]['roi_binding']
                        assert result['views']['core']['population_binding']['selected_source_index_binding']==b['DS18_extracts'][str(n)]['selected_source_index_binding']
                        result.update(contexts=requests.get(k,{}).get('contexts',[]),DS35_extract=b['DS18_extracts'][str(n)],
                            assignment_row_sha256=b['assignment_row_sha256'],measurement_sha256=digest(result))
                        dump(output,result);all_results[k]=result;populations[k]=pop['populations']
                    pair_set=set()
                    for n in set(wanted[frame])&set(masks):
                        pair_set.update(tuple(sorted((n,p))) for p in all_results[key(name,frame,n)]['neighbor_natives'])
                    # Both actual q observations are compared even after they move apart.
                    contexts=defaultdict(set)
                    for n,r in wanted[frame].items():
                        for c in r['contexts']:
                            if c['role']=='POST_AT_Q' and n in masks:contexts[c['context']].add(n)
                    for ns in contexts.values():
                        pair_set.update((n,p) for n in sorted(ns) for p in sorted(ns) if n<p)
                    for n,p in sorted(pair_set):
                        aa,bb=key(name,frame,n),key(name,frame,p)
                        values={role:compare(populations[aa][role],populations[bb][role]) for role in ('whole','core')}
                        patches={f'{i}:{j}':compare(populations[aa][f'patch{i}'],populations[bb][f'patch{j}']) for i in range(1,4) for j in range(1,4)}
                        pair_results.append(dict(segment=name,frame=frame,first=aa,second=bb,comparisons=values,
                            all_patch_pairs=patches,first_extract=all_results[aa]['DS35_extract'],second_extract=all_results[bb]['DS35_extract'],
                            both_measured_core_support=all_results[aa]['views']['core']['measurement_support'] and all_results[bb]['views']['core']['measurement_support'],
                            no_identity_assignment=True))
                    for k in ('raw_h5','raw_npz','native_npy','calibration'):
                        if k in binding:sensor_pins[binding[k]['path']]=binding[k]
                    frame_count+=1
                print('LOCAL',name,len(wanted),'frames',len(all_results),'total objects',flush=True)
            finally:sensor.close()
    action_features=[]
    for link in links:
        current=link['current'];assert current in populations
        comparisons={}
        for role,anchor in link['anchors'].items():
            assert anchor in populations
            comparisons[role]={part:compare(populations[current][part],populations[anchor][part]) for part in ('whole','core')}
        neighborhood=[p for p in pair_results if current in (p['first'],p['second'])]
        action_features.append(dict(link,temporal_population_comparisons=comparisons,current_local_pair_count=len(neighborhood),
                                    current_local_pair_keys=[[p['first'],p['second']] for p in neighborhood]))
    save('LOCAL_PAIR_COMPARISONS.json',dict(pairs=pair_results,physical_labels_read=False))
    save('ACTION_FEATURES.json',dict(actions=action_features,physical_labels_read=False))
    save('MEASUREMENT_SUMMARY.json',dict(status='COMPLETE_PRELABEL_DIAGNOSTIC_MEASUREMENT',segments=counts,
        actions=90,events=75,unique_requested_objects=len(requests),measured_objects=len(all_results),raw_frames=frame_count,
        local_pairs=len(pair_results),missing_requested_masks=missing,sensor_files=list(sensor_pins.values()),
        raw_field_reads=SOURCE.FIELD_READS,RGB=False,GT_raster=False,restored=False,tracker_state_write=False,
        new_predictions=False,new_metrics=False,model_http=0,cost_usd=0))
    verify_freeze()
    names=['TEMPORAL_TRACE.jsonl.gz','CAUSAL_FORECAST_PAIRS.jsonl.gz','DS35_GATE_SCALE_COMPONENTS.jsonl.gz',
           'LOCAL_MEASUREMENTS.jsonl.gz','LOCAL_PAIR_COMPARISONS.json','ACTION_FEATURES.json','MEASUREMENT_SUMMARY.json']
    save('FEATURES_SEALED.json',dict(status='ALL_DS36_FEATURES_SEALED_BEFORE_OLD_PHYSICAL_LABEL_JOIN',
        sealed_utc=utc(),files=[artifact(HERE/n) for n in names],freeze=artifact(HERE/'FREEZE.json'),
        physical_labels_read=False,GT_raster=False,RGB=False,model_http=0,cost_usd=0))
    print('FEATURES_SEALED',len(all_results),len(pair_results),frame_count,flush=True)

def join():
    verify_freeze();seal=read(HERE/'FEATURES_SEALED.json')
    for pin in seal['files']:verify_item(pin)
    assert not seal['physical_labels_read']
    actions={a['action_id']:a for a in read(DS21/'ACTIONS.json')['actions']}
    features={a['action_id']:a for a in rows(DS21/'FEATURES.jsonl.gz')}
    assert set(actions)==set(features) and len(actions)==90
    output=[]
    for entry in read(HERE/'ACTION_FEATURES.json')['actions']:
        f=features[entry['action_id']];a=actions[entry['action_id']]
        assert entry['original_feature_sha256']==digest(f) and all(a[k]==v for k,v in f.items())
        output.append(dict(entry,physical=a['physical'],actual_reference_physical=a['actual_reference_physical'],
                           old_physical_label_source=artifact(DS21/'ACTIONS.json')))
    save('LABELED_ACTIONS.json',dict(status='OLD_POSTSEAL_LABELS_JOINED_AFTER_NEW_FEATURE_SEAL',joined_utc=utc(),
        actions=output,physical_counts=dict(Counter(a['physical'] for a in output)),
        feature_seal=artifact(HERE/'FEATURES_SEALED.json'),weak_reference_sources=['L3','LW'],
        diagnostic_only=True,new_metrics=False,new_predictions=False,model_http=0,cost_usd=0))
    print('LABEL_JOIN',dict(Counter(a['physical'] for a in output)),flush=True)

if __name__=='__main__':
    {'initialize':initialize,'freeze':freeze,'measure':measurements,'join':join}[sys.argv[1]]()
