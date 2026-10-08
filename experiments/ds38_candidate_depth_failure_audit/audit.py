"""Passive candidate census, raw distributions, then an independent postseal label join."""
from common import *
from collections import Counter, defaultdict
import copy, inspect, time, shutil, platform, traceback
import numpy as np
from scipy.stats import wasserstein_distance

def initialize():
    assert git('rev-parse','HEAD').decode().strip()==BASE
    actions=[v for v in read(DS37/'run/ORIGINAL_ACTION_FOLLOWUP.json')['actions'] if v['segment'] in SEGMENTS]
    assert len(actions)==27 and Counter(v['physical'] for v in actions)==dict(WRONG=17,CORRECT=8,UNSCORABLE=2)
    cohort=[]
    for a in actions:
        e=a['event'];n=e['native_id'];k=e['canonical_id']
        cohort.append(dict(action_id=f'{a["segment"]}/F{a["frame"]}/n{n}-p{k}',segment=a['segment'],
            frame=a['frame'],global_frame=a['global_frame'],native=n,target=k,
            phase='BIRTH_REFINE' if e.get('phase')=='birth' else 'D1_DELAYED',
            actual_reference=a['actual_reference'],event_sha256=digest(e),
            event=e))
    save('COHORT.json',dict(actions=cohort,selection='ALL_27_ORIGINAL_FEEDING_COMMITTED_ACTIONS',
        exposure='POSTHOC: 17 WRONG / 8 CORRECT / 2 UNSCORABLE labels already exposed; not blind validation'))
    pins={}
    def pin(p):
        v=artifact(p);pins[v['path']]=v
    pin(DS37/'run/ORIGINAL_ACTION_FOLLOWUP.json')
    pin(CONFIG_PATH)
    for name in SEGMENTS:
        ARCHIVE.verify_seal(name)
        public=DS37/'run'/name/'public'
        for filename in ('PREDICTIONS_SEALED.json','TRANSACTIONS.jsonl.gz','predictions.jsonl.gz',
                         'REFERENCE_MATCHES.json','FREEZE.json'):
            pin(public/filename)
        manifest=read(input_dir(name)/'SOURCE_MANIFEST.json')
        assert manifest['no_GT'] and manifest['no_RGB'] and manifest['no_restored_values']
        pin(input_dir(name)/'SOURCE_MANIFEST.json')
        for p in manifest['derived_inputs'].values(): verify_item(p);pins[p['path']]=p
    for file,h in read(DS37/'RUNTIME_FREEZE.json')['code'].items():
        assert sha(file)==h;pin(file)
    for file in (LEGACY.__file__, M.__file__, MEASUREMENT.__file__, SOURCE.__file__): pin(file)
    save('INPUT_PINS.json',dict(files=list(pins.values()),old_archives_read_only=True))
    save('ENVIRONMENT.json',dict(created_utc=utc(),base=BASE,python=sys.executable,
        python_version=platform.python_version(),platform=platform.platform(),CPU_jobs=1,library_threads=1,
        output_free_bytes=shutil.disk_usage(ROOT).free,input_free_bytes=shutil.disk_usage(ORIGINAL).free,
        server=False,GPU=False,RGB=False,GT_raster=False,model_http=0,cost_usd=0))
    print('INITIALIZED',len(cohort),flush=True)

def bank_eligibility(engine, occupied, now, phase):
    result=[]
    for k,h in sorted(engine.bank.items()):
        failures=[]
        if k in occupied: failures.append('occupied')
        if k in engine.alias: failures.append('alias_source')
        if h['clean_count']<5: failures.append('insufficient_D1_history')
        if h['clean_time'] is None: failures.append('no_D1_clean_anchor')
        elif now-h['clean_time']>12: failures.append('D1_history_expired')
        if not 0<now-h['last_seen']<=6: failures.append('not_recently_missing')
        if h['contact_time'] is None or h['last_seen']-h['contact_time']>1: failures.append('no_recent_interaction')
        if (phase=='BIRTH_REFINE' or engine.cfg['use_depth']) and not h['depth_history']:
            failures.append('no_D1_depth_history')
        result.append(dict(id=k,eligible=not failures,failures=failures,anchor=copy.deepcopy(h.get('anchor')),
            last_seen_age_s=now-h['last_seen'],clean_age_s=None if h['clean_time'] is None else now-h['clean_time'],
            clean_count=h['clean_count'],contact_time=h['contact_time'],
            partners=copy.deepcopy(h['partners']),view_anchors=copy.deepcopy(engine.view_bank.get(k,{}))))
    return result

def trace_sites(engine):
    sites={}
    for cls in type(engine).__mro__:
        if cls.__name__ not in ('DepthRepair','BirthRefine'): continue
        function=cls.step;lines,start=inspect.getsourcelines(function)
        phase='D1_DELAYED' if cls.__name__=='DepthRepair' else 'BIRTH_REFINE'
        before='if new and old:' if phase=='D1_DELAYED' else 'matrix=np.full((len(born),len(old)+len(born)),1e6);terms={}'
        after='rr,cc=linear_sum_assignment(matrix);total=float(matrix[rr,cc].sum())'
        for marker,role in ((before,'before'),(after,'matrix')):
            found=[start+i for i,line in enumerate(lines) if line.strip().startswith(marker)]
            assert len(found)==1,(phase,marker,found)
            sites[(function.__code__,found[0])]=(phase,role)
    assert len(sites)==4
    return sites

def passive_preview(branch, row, profiles, enabled):
    """Only detached state is retained. The observer restores Python's old tracer."""
    captured={};sites=trace_sites(branch.engine) if enabled else {}
    def tracer(frame,event,arg):
        if event=='line' and (frame.f_code,frame.f_lineno) in sites:
            phase,role=sites[frame.f_code,frame.f_lineno];local=frame.f_locals;engine=local['self']
            if role=='before':
                occupied=set(local['occupied']);old=list(local['old']);observations=local['new' if phase=='D1_DELAYED' else 'born']
                census=bank_eligibility(engine,occupied,row['time'],phase)
                assert old==[c['id'] for c in census if c['eligible']]
                if phase=='BIRTH_REFINE':
                    assert [(c['id'],c['failures']) for c in census]==[(c['id'],c['failures']) for c in local['eligibility']]
                captured[phase]=dict(phase=phase,rows=[o['id'] for o in observations],columns=old,
                    bank=census,aliases=copy.deepcopy(engine.alias),occupied=sorted(occupied),
                    current_public={str(o['id']):engine.alias.get(o['id'],{}).get('target',o['id']) for o in local['obs']},
                    pre_phase_engine_sha256=digest(vars(engine)),matrix=None,terms=[])
            else:
                c=captured[phase];c['matrix']=local['matrix'].tolist()
                c['terms']=[dict(row=i,column=j,terms=copy.deepcopy(t)) for (i,j),t in sorted(local['terms'].items())]
                assert len(c['matrix'])==len(c['rows'])
        return tracer if frame.f_code in {s[0] for s in sites} else None
    before=digest(vars(branch.engine));previous=sys.gettrace()
    try:
        if enabled: sys.settrace(tracer)
        view=branch.preview(row['frame'],row['time'],row['observations'],profiles)
    finally: sys.settrace(previous)
    assert digest(vars(branch.engine))==before and sys.gettrace() is previous
    return view,captured

def replay(output, only=None, stop=None, require_freeze=True):
    if require_freeze: verified_freeze()
    output=HERE/output;output.mkdir(parents=True,exist_ok=True)
    cohort=read(HERE/'COHORT.json')['actions'];stats={};began=time.perf_counter()
    with gzip.open(output/'CANDIDATES.jsonl.gz','xt',encoding='utf-8') as candidates, \
         gzip.open(output/'SOURCE_STATE.jsonl.gz','xt',encoding='utf-8') as states:
        for name in ([only] if only else SEGMENTS):
            wanted=defaultdict(list)
            for a in cohort:
                if a['segment']==name: wanted[a['frame']].append(a)
            source=input_dir(name);branch=Bridge(read(CONFIG_PATH));last={};generation={};count=0
            archive=(t for t in rows(DS37/'run'/name/'public/TRANSACTIONS.jsonl.gz') if t['arm']=='Z4Q_FROZEN')
            wls={t['frame']:t['controller_trace']['depth_checks'] for t in rows(DS37/'run'/name/'public/TRANSACTIONS.jsonl.gz')
                 if t['arm']=='Z4Q_WLS_VETO' and t['frame'] in wanted}
            for row,profiles in stream(source/'observations.jsonl.gz',source/'profiles.jsonl.gz'):
                count=row['frame'];expected=next(archive)
                for o in row['observations']:
                    n=o['id'];generation[n]=generation.get(n,0)+(last.get(n)!=count-1);last[n]=count
                view,captured=passive_preview(branch,row,profiles,count in wanted)
                mapping,trace=branch.commit_once(view)
                assert {str(k):v for k,v in mapping.items()}==expected['mapping']
                assert digest(trace)==digest(expected['controller_trace'])
                assert digest(vars(branch.engine))==expected['engine_state_sha256']
                assert branch.version==expected['version']==count
                assert len(set(mapping.values()))==len(row['native'])
                dump(states,dict(segment=name,frame=count,global_frame=row['global_frame'],time=row['time'],
                    source_row_sha256=ARCHIVE.row_sha(row),engine_state_sha256=expected['engine_state_sha256'],
                    source={str(o['id']):dict(generation=generation[o['id']],epoch=branch.epochs.get(o['id'],0),
                        public=mapping[o['id']],neighbors=o.get('neighbors',[]),quality=branch.engine.quality(o),
                        depth_valid=branch.engine.depth_valid(o)) for o in row['observations']}))
                for action in wanted.get(count,[]):
                    phase=action['phase'];c=copy.deepcopy(captured[phase]);n=action['native'];k=action['target']
                    assert c['matrix'] is not None and n in c['rows'] and k in c['columns']
                    checks=[x for x in wls[count] if x['native_id']==n and x['phase']==phase]
                    chosen=[x for x in checks if x['canonical_id']==k];assert len(chosen)==1
                    dump(candidates,dict(action=action,phase_snapshot=c,original_depth_queries=checks,
                        current_source_versions=copy.deepcopy(generation),archived_transaction_sha256=ARCHIVE.row_sha(expected),
                        state_trace_mapping_version_exact=True,observer_writes=0,actual_GT_content_read=False))
                if count%200==0: print('REPLAY',name,count,flush=True)
                if stop==count: break
            if stop is None: assert count==SEGMENTS[name][1]-SEGMENTS[name][0]+1 and next(archive,None) is None
            stats[name]=dict(frames=count,full_engine_trace_mapping_version_exact=True)
    save(str(output.relative_to(HERE)/'REPLAY_SEALED.json'),dict(created_utc=utc(),segments=stats,
        files=[artifact(output/f) for f in ('CANDIDATES.jsonl.gz','SOURCE_STATE.jsonl.gz')],
        elapsed_seconds=time.perf_counter()-began,new_tracking_policy=False,model_http=0,cost_usd=0))
    print('REPLAY_SEALED',stats,flush=True)

def freeze():
    assert read(HERE/'CHECKS.json')['status']=='PASS'
    pins=read(HERE/'INPUT_PINS.json')['files']
    pins.extend(artifact(p) for p in HERE.iterdir() if p.is_file() and p.suffix in ('.py','.md','.json') and p.name!='FREEZE.json')
    for pin in pins: verify_item(pin)
    save('FREEZE.json',dict(created_utc=utc(),base=BASE,files=list({p['path']:p for p in pins}.values()),
        actions=27,frames=1471,physical_labels_already_exposed=True,GT_join_after_feature_seal=True,
        old_parameters_unchanged=LEGACY.CFG,new_tracking_policy=False,model_http=0,cost_usd=0))

def requests_for(candidates):
    requested=defaultdict(lambda:defaultdict(set))
    def add(name,anchor,cutoff):
        if not anchor: return
        f,n=anchor['frame'],anchor['native_id'];assert 1<=f<=cutoff
        requested[name][f].add(n)
    for c in candidates:
        a=c['action'];name=a['segment'];q=a['frame']
        add(name,dict(frame=q,native_id=a['native']),q)
        add(name,a['actual_reference'],q)
        for b in c['phase_snapshot']['bank']:
            add(name,b['anchor'],q)
            for v in b['view_anchors'].values(): add(name,v.get('anchor'),q)
        for query in c['original_depth_queries']:
            add(name,query.get('anchor'),q)
            for h in query['terms'].get('depth_anchors',{}).values():
                if h: add(name,h.get('anchor'),q)
    return requested

def distribution_compare(a,b):
    result=M.compare(a,b)
    result['wasserstein_mm']=float(wasserstein_distance(a,b)) if len(a) and len(b) else None
    return result

def measurements():
    verified_freeze();candidates=list(rows(HERE/'run/CANDIDATES.jsonl.gz'));assert len(candidates)==27
    requests=requests_for(candidates);facts={};populations={};pairs=[];private=[];missing=[]
    private_dir=HERE/'private';private_dir.mkdir(exist_ok=True)
    measured_count=0
    with gzip.open(HERE/'MEASUREMENTS.jsonl.gz','xt',encoding='utf-8') as output:
        for name in SEGMENTS:
            frames=set(requests[name]);source=input_dir(name)
            assignment={r['frame']:r for r in rows(source/'assignments.jsonl.gz') if r['frame'] in frames}
            observed={r['frame']:r for r in rows(source/'DEPTH_OBSERVATIONS.jsonl.gz') if r['frame'] in frames}
            sensor=SOURCE.RawDepth(name)
            try:
                for frame in sorted(frames):
                    row=observed[frame];depth,index,native_depth,binding=sensor(row['global_frame'],row['time'])
                    expected=row['raw_source_binding'];assert binding==expected
                    masks=SOURCE.native_masks(assignment[frame]);arrays={}
                    missing.extend(dict(segment=name,frame=frame,native=n,reason='MASK_ABSENT') for n in requests[name][frame]-masks.keys())
                    # All current neighbors are measured; no candidate/GT selects a favorable depth layer.
                    for n in sorted(masks):
                        fact,pop=M.measure(depth,index,native_depth,masks,n,name,frame,row['global_frame'],row['time'],binding,expected)
                        fact['depth_quantiles_mm']={role:(np.quantile(values,np.linspace(.05,.95,19)).tolist() if len(values) else [])
                            for role,values in pop['populations'].items()}
                        fact['background_quantiles_mm']=np.quantile(pop['background'],np.linspace(.05,.95,19)).tolist() if len(pop['background']) else []
                        fact['assignment_row_sha256']=ARCHIVE.row_sha(assignment[frame])
                        fact['identity']='UNKNOWN_BEFORE_POSTSEAL_JOIN';fact['measurement_sha256']=digest(fact)
                        k=key(name,frame,n);facts[k]=fact
                        populations[k]=dict(pop['populations'],background=pop['background'])
                        for role,values in populations[k].items(): arrays[f'n{n}_{role}']=values
                        dump(output,fact);measured_count+=1
                    path=private_dir/f'{name}_F{frame}_populations.npz'
                    np.savez_compressed(path,**arrays);private.append(artifact(path))
                    if frame in {a['action']['frame'] for a in candidates if a['action']['segment']==name}:
                        # Actual depth and mask view is restricted and never enters Git.
                        render_pixels(depth,masks,name,frame)
                print('MEASURED',name,len(frames),'frames',measured_count,'objects',flush=True)
            finally: sensor.close()
    for c in candidates:
        a=c['action'];name=a['segment'];q=a['frame'];current=key(name,q,a['native'])
        for bank in c['phase_snapshot']['bank']:
            refs={'bank':bank['anchor']}
            refs.update({role:v.get('anchor') for role,v in bank['view_anchors'].items()})
            for role,anchor in refs.items():
                if not anchor: continue
                other=key(name,anchor['frame'],anchor['native_id'])
                if current not in populations or other not in populations:
                    pairs.append(dict(action_id=a['action_id'],target=bank['id'],reference_role=role,
                        current=current,reference=other,status='UNKNOWN_MISSING_MASK'));continue
                views={r:distribution_compare(populations[current][r],populations[other][r]) for r in ROLES}
                pairs.append(dict(action_id=a['action_id'],target=bank['id'],reference_role=role,
                    current=current,reference=other,anchor=anchor,comparisons=views,
                    both_core_supported=facts[current]['views']['core']['measurement_support'] and facts[other]['views']['core']['measurement_support'],
                    physical='UNKNOWN_BEFORE_POSTSEAL_JOIN'))
    save('DISTRIBUTION_PAIRS.json',dict(pairs=pairs,method='EMPIRICAL_WASSERSTEIN_1_MM_AND_TIED_RANK_AUC; NOT_IDENTITY_ACCURACY'))
    order=relative_order(candidates,facts,populations)
    save('RELATIVE_ORDER_FEATURES.json',dict(witnesses=order,physical='UNKNOWN_BEFORE_POSTSEAL_JOIN'))
    save('MEASUREMENT_SUMMARY.json',dict(requested_frames=sum(map(len,requests.values())),measured_objects=measured_count,
        distribution_pairs=len(pairs),relative_order_witnesses=len(order),missing=missing,
        selections='ALL_BANK_AND_VIEW_ANCHORS_AND_ALL_MASKS_IN_THEIR_FRAMES',model_http=0,cost_usd=0))
    private.extend(artifact(p) for p in sorted(private_dir.glob('*.png')))
    save('PRIVATE_INVENTORY.json',dict(files=private,usage='Local raw depth/masks and independent-source populations; no RGB/GT raster',
        reproduce='audit.py measurements after verified full replay; same raw depth and saved SAM3 inputs required'))
    save('FEATURES_SEALED.json',dict(created_utc=utc(),files=[artifact(HERE/f) for f in
        ('MEASUREMENTS.jsonl.gz','DISTRIBUTION_PAIRS.json','RELATIVE_ORDER_FEATURES.json','MEASUREMENT_SUMMARY.json','PRIVATE_INVENTORY.json')],
        replay_seal=artifact(HERE/'run/REPLAY_SEALED.json'),new_GT_raster_reads=0,
        cohort_labels_already_exposed=True,reference_match_join_started=False))
    print('FEATURES_SEALED',measured_count,len(pairs),len(order),flush=True)

def render_pixels(depth,masks,name,frame):
    from PIL import Image,ImageDraw
    valid=depth[np.isfinite(depth)&(depth>0)]
    low,high=np.quantile(valid,[.02,.98]) if len(valid) else (0,1)
    value=np.clip((np.nan_to_num(depth)-low)/max(1,high-low),0,1)
    grey=(255*value).astype('u1');rgb=np.repeat(grey[:,:,None],3,axis=2);rgb[depth<=0]=0
    palette=((255,70,70),(70,255,70),(70,130,255),(255,200,50))
    import cv2
    for i,(n,m) in enumerate(sorted(masks.items())):
        contours,_=cv2.findContours(m.astype('u1'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(rgb,contours,-1,palette[i%4],1)
    image=Image.fromarray(rgb).resize((1280,720))
    draw=ImageDraw.Draw(image)
    for n,m in sorted(masks.items()):
        yy,xx=np.nonzero(m)
        if len(xx): draw.text((2*float(xx.mean()),2*float(yy.mean())),f'n{n}',fill='white',stroke_width=1,stroke_fill='black')
    draw.text((8,8),f'{name} local F{frame}; original aligned depth; n=anonymous native mask',fill='white',stroke_width=1,stroke_fill='black')
    image.save(HERE/'private'/f'{name}_F{frame}_raw_depth_masks.png')

def relative_order(candidates,facts,populations):
    states={(r['segment'],r['frame']):r for r in rows(HERE/'run/SOURCE_STATE.jsonl.gz')};result=[]
    for c in candidates:
        a=c['action'];name=a['segment'];q=a['frame'];cur=key(name,q,a['native']);snapshot=c['phase_snapshot']
        qstate=states[name,q]['source']
        for bank in snapshot['bank']:
            ref=bank['anchor']
            if not ref: continue
            f=ref['frame'];old=key(name,f,ref['native_id']);past=states[name,f]['source']
            if old not in facts or cur not in facts: continue
            for witness in facts[old]['neighbor_natives']:
                wk=key(name,f,witness);wq=key(name,q,witness)
                if wk not in populations or wq not in populations: continue
                versions=[states[name,t]['source'].get(str(witness)) for t in range(f,q+1)]
                reasons=[]
                if any(v is None for v in versions): reasons.append('VISIBILITY_BREAK')
                elif len({(v['generation'],v['epoch'],v['public']) for v in versions})!=1: reasons.append('SOURCE_OR_PUBLIC_VERSION_BREAK')
                elif any(v['neighbors'] or not v['quality'] or not v['depth_valid'] for v in versions): reasons.append('WITNESS_CONTACT_OR_QUALITY_RISK')
                if witness==a['native'] or witness==ref['native_id']: reasons.append('NOT_INDEPENDENT_WITNESS')
                before=distribution_compare(populations[old]['core'],populations[wk]['core'])
                now=distribution_compare(populations[cur]['core'],populations[wq]['core'])
                support=all(facts[k]['views']['core']['measurement_support'] for k in (old,wk,cur,wq))
                if not support: reasons.append('WEAK_MEASUREMENT')
                sign=lambda d: None if d.get('signed_median_gap_mm') is None else int(np.sign(d['signed_median_gap_mm']))
                result.append(dict(action_id=a['action_id'],target=bank['id'],witness_native=witness,reference=old,current=cur,
                    witness_before=wk,witness_current=wq,before=before,current_comparison=now,
                    status='UNKNOWN' if reasons else 'SAME_VERSION_MEASURED_PROXY_ORDER',reasons=reasons,
                    raw_order_reversed=None if sign(before) is None or sign(now) is None else sign(before)*sign(now)<0,
                    physical_identity='UNKNOWN',physical_order_invariance='ASSUMPTION_NOT_ESTABLISHED'))
    return result

def join():
    verified_freeze();seal=read(HERE/'FEATURES_SEALED.json')
    for pin in seal['files']: verify_item(pin)
    for pin in read(HERE/'run/REPLAY_SEALED.json')['files']: verify_item(pin)
    labels={name:read(DS37/'run'/name/'public/REFERENCE_MATCHES.json') for name in SEGMENTS}
    candidates=list(rows(HERE/'run/CANDIDATES.jsonl.gz'));pairs=read(HERE/'DISTRIBUTION_PAIRS.json')['pairs']
    byaction=defaultdict(list)
    for p in pairs: byaction[p['action_id']].append(p)
    old_actions={f'{a["segment"]}/F{a["frame"]}/n{a["event"]["native_id"]}-p{a["event"]["canonical_id"]}':a
                 for a in read(DS37/'run/ORIGINAL_ACTION_FOLLOWUP.json')['actions'] if a['segment'] in SEGMENTS}
    results=[]
    for c in candidates:
        a=c['action'];snap=c['phase_snapshot'];name=a['segment'];q=a['frame'];n=a['native']
        current=labels[name][str(q)].get(str(n),{})
        def rel(anchor):
            return relation(current,labels[name][str(anchor['frame'])].get(str(anchor['native_id']),{})) if anchor else 'UNKNOWN'
        i=snap['rows'].index(n);row=snap['matrix'][i];bank=[]
        for b in snap['bank']:
            identity=rel(b['anchor']);column=b['id'] in snap['columns']
            cost=row[snap['columns'].index(b['id'])] if column else None
            selected=b['id']==a['target']
            distribution=next((p for p in byaction[a['action_id']] if p['target']==b['id'] and p['reference_role']=='bank'),None)
            used=next((p for p in byaction[a['action_id']] if p['target']==b['id'] and p['reference_role']=='core'),None) if a['phase']=='BIRTH_REFINE' else distribution
            used=used or distribution
            query=next((x for x in c['original_depth_queries'] if x['canonical_id']==b['id']),None)
            failures=b['failures'] if not column else (
                query['terms'].get('failures',[]) if query and a['phase']=='BIRTH_REFINE' else
                [query['terms']['rejection']] if query and query['terms'].get('rejection') else [])
            bank.append(dict(**b,physical_reference=identity,actual_matrix_column=column,matrix_cost=cost,
                legal_matrix_edge=column and cost<1e6,can_beat_own_dummy=column and cost<1,
                selected=selected,entry_or_edge_failures=failures,distribution=used,
                used_depth_reference_physical=rel(used['anchor']) if used and 'anchor' in used else 'UNKNOWN',
                original_depth_query=query))
        actual=rel(a['actual_reference']);physical='CORRECT' if actual=='SAME' else 'WRONG' if actual=='DIFFERENT' else 'UNSCORABLE'
        assert physical==old_actions[a['action_id']]['physical']
        same=[b for b in bank if b['physical_reference']=='SAME']
        stages=dict(in_bank=bool(same),matrix_column=any(b['actual_matrix_column'] for b in same),
            legal_edge=any(b['legal_matrix_edge'] for b in same),below_dummy=any(b['can_beat_own_dummy'] for b in same))
        ranks={}
        for role in ('whole','core'):
            pool=[b for b in bank if b['legal_matrix_edge'] and b['distribution'] and 'comparisons' in b['distribution']]
            scores={b['id']:b['distribution']['comparisons'][role]['wasserstein_mm'] for b in pool}
            scores={k:v for k,v in scores.items() if v is not None}
            best=min(scores.values()) if scores else None
            winners=[k for k,v in scores.items() if v==best]
            ranks[role]=dict(pool='ACTUAL_LEGAL_MATRIX_EDGES',scores_mm=scores,minima=winners,
                best_physical=[next(b['physical_reference'] for b in bank if b['id']==k) for k in winners],
                selected_distance_mm=scores.get(a['target']),not_a_new_assignment=True)
        latest=[]
        if current.get('status')=='UNIQUE_IOU_MATCH':
            for f in range(1,q):
                for native,match in labels[name][str(f)].items():
                    if relation(current,match)=='SAME': latest.append(dict(frame=f,native=int(native),iou=match['iou']))
        results.append(dict(action=a,physical=physical,bank=bank,correct_reference_availability=stages,
            distribution_ranking=ranks,latest_same_physical_observations_before_q=latest[-5:],
            historical_GT_lookup='POSTSEAL_DIAGNOSIS_ONLY; NOT_NEW_CANDIDATE_OR_ANCHOR',
            actual_reference_relation=actual,original_action_physically_wrong=physical=='WRONG'))
    order=read(HERE/'RELATIVE_ORDER_FEATURES.json')['witnesses']
    for o in order:
        a=next(v['action'] for v in results if v['action']['action_id']==o['action_id']);name=a['segment'];q=a['frame']
        f=int(o['reference'].split('/F')[1].split('/')[0]);native=int(o['reference'].split('/n:')[1])
        o['reference_physical']=relation(labels[name][str(q)].get(str(a['native']),{}),labels[name][str(f)].get(str(native),{}))
    save('POSTSEAL_DIAGNOSIS.json',dict(actions=results,order=order,feature_seal=artifact(HERE/'FEATURES_SEALED.json'),
        labels=[artifact(DS37/'run'/name/'public/REFERENCE_MATCHES.json') for name in SEGMENTS],
        model_http=0,cost_usd=0,new_tracker_performance=False))
    print('POSTSEAL_DIAGNOSIS',dict(Counter(v['physical'] for v in results)),flush=True)

if __name__=='__main__':
    command=sys.argv[1]
    try:
        if command=='initialize': initialize()
        elif command=='freeze': freeze()
        elif command=='slice': replay('slice_f159',only='feeding_000000_000199',stop=160,require_freeze=False)
        elif command=='replay': replay('run')
        elif command=='measurements': measurements()
        elif command=='join': join()
        else: raise ValueError(command)
    except Exception:
        name=f'FAILURE_{command}_{time.time_ns()}.json'
        save(name,dict(created_utc=utc(),command=command,traceback=traceback.format_exc(),status='FAILED_PRESERVED'))
        raise
