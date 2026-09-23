"""SLR-2 causal numeric packets and native-mask contact sheets. No model calls/GT."""
from pathlib import Path
import os, sys, json, gzip, hashlib, time, ctypes, itertools, copy, math
from datetime import datetime
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
ROOT=Path('E:/CAU/D-MOT'); P=Path(__file__).resolve().parent
OLD=ROOT/'tools/sam3_spatial_llm_stage1_20260920/engineering_r3'
DATA=ROOT/'data/AlignedDataset_v1'
OPENED=[]
def guard(event,args):
    if event!='open' or not isinstance(args[0],(str,bytes)):return
    s=os.fsdecode(args[0]).replace('\\','/')
    if any(x in s for x in ['/TRUTH.json','/labels/','/labels_original/','EVENTS_gap','offline_matches_','/TRUTH_SEALED.json']):
        raise PermissionError('Forbidden preparation read: '+s)
    if s.endswith(('.json','.jsonl','.gz','.jpg','.png')):OPENED.append(s)
sys.addaudithook(guard)
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0,str(ROOT/'tools/sam3_depth_only_reconnect_20260916'))
from rle_decode import decode_rle
cv2.setNumThreads(1)
from input_checks import check_packet, canonical_option, check_requests

def now():return datetime.now().astimezone().isoformat(timespec='seconds')
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');temp.replace(p)
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:
        for line in f:yield json.loads(line)
def alias(prefix,key):return prefix+hashlib.sha256(('SLR2:'+str(key)).encode()).hexdigest()[:9]
def limit_cpu():
    k=ctypes.windll.kernel32;k.GetCurrentProcess.restype=ctypes.c_void_p
    k.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
    k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    handle=k.GetCurrentProcess();a=ctypes.c_size_t();s=ctypes.c_size_t()
    assert k.GetProcessAffinityMask(handle,ctypes.byref(a),ctypes.byref(s))
    cpus=[i for i in range(64) if a.value&(1<<i)][:4]
    assert k.SetProcessAffinityMask(handle,sum(1<<i for i in cpus));return cpus

def appearance(im,m):
    yy,xx=np.where(m)
    if len(xx)<16:return None
    xy=np.column_stack([xx,yy]);_,v=np.linalg.eigh(np.cov(xy.T));axis=v[:,-1]
    if axis[0]<0 or (axis[0]==0 and axis[1]<0):axis=-axis
    z=(xy-xy.mean(0))@axis;frac=(z-z.min())/max(1e-6,z.max()-z.min());ii=(frac>=.25)&(frac<=.75)
    body=np.zeros_like(m);body[yy[ii],xx[ii]]=True
    body=cv2.resize(body.astype('u1'),(1920,1080),interpolation=cv2.INTER_NEAREST).astype(bool)
    pixels=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)[body]
    if len(pixels)<16:return None
    h=np.concatenate([np.histogram(pixels[:,i],bins=16,range=(0,180 if i==0 else 256))[0]/len(pixels) for i in range(3)])
    h=np.sqrt(h);h/=np.linalg.norm(h);return h.tolist()

def spaced_references(observations,native,pre,lower):
    actual=[];clean=[]
    for g in range(pre,max(lower,pre-119)-1,-1):
        ob=observations[g]['by_id'].get(native)
        if ob is None:continue
        actual.append(g)
        if ob['area']>=64 and ob.get('presence') is not None and ob['presence']>=.5 and not ob['neighbors']:clean.append(g)
    pool=clean if clean else actual
    if not pool:return [],False
    latest=pool[0];last_time=observations[latest]['time'];chosen=[latest]
    for delta in [.25,.50]:
        candidates=[g for g in pool if observations[g]['time']<=last_time-delta and g not in chosen]
        if candidates:chosen.append(candidates[0])
    return sorted(chosen),bool(clean)

def clean_feature(f):
    return {k:v for k,v in f.items() if k not in {'appearance_hsv_body','mask_sha256'}}

def make_options(packet):
    ts=packet['focal_tracks'];oo=[x['observation'] for x in packet['current'] if x['area_px']>0];out=[]
    for pp in itertools.permutations(oo,len(ts)):
        m=[{'track':t,'observation':o} for t,o in zip(ts,pp)]
        out.append(dict(option_id=alias('H',packet['query_id']+':match:'+json.dumps(m,sort_keys=True)),state='MATCH',matches=m,merged_groups=[],unresolved_tracks=[]))
    for o in oo:
        out.append(dict(option_id=alias('H',packet['query_id']+':merge:'+o),state='POSSIBLE_MERGE',matches=[],
                        merged_groups=[dict(observation=o,possible_members=list(ts))],unresolved_tracks=list(ts)))
    out.append(dict(option_id=alias('H',packet['query_id']+':wait'),state='UNRESOLVED',matches=[],merged_groups=[],unresolved_tracks=list(ts)))
    return out

def permutation(packet):
    tokens=set()
    def find(x):
        if isinstance(x,dict):
            for k,v in x.items():find(k);find(v)
        elif isinstance(x,list):
            for v in x:find(v)
        elif isinstance(x,str) and len(x)==10 and x[0] in 'TOEHL' and all(c in '0123456789abcdef' for c in x[1:]):tokens.add(x)
    find(packet)
    mp={s:alias(s[0],'permuted:'+s) for s in sorted(tokens)}
    def change(x):
        if isinstance(x,str):return mp.get(x,x)
        if isinstance(x,list):return [change(z) for z in x]
        if isinstance(x,dict):return {mp.get(k,k):change(v) for k,v in x.items()}
        return x
    q=change(packet)
    for k in ['focal_tracks','history','current','pairwise','options']:q[k].reverse()
    q['evidence']=dict(reversed(list(q['evidence'].items())))
    for r in q['recent']:r['observations'].reverse()
    for o in q['options']:
        o['matches'].reverse();o['merged_groups'].reverse();o['unresolved_tracks'].reverse()
        for g in o['merged_groups']:g['possible_members'].reverse()
    return q,mp

def font(size):
    return ImageFont.truetype('C:/Windows/Fonts/arial.ttf',size)

def render_sheet(path,packet,specs,pixels):
    # Source RGB pixels at true aspect ratio. Each tile has contextual outline and
    # isolated native mask; no GT, native IDs, global frame numbers or source paths.
    byid={s['label']:s for s in specs}
    ordered=[h['track'] for h in packet['history'] if h['samples']]+[o['observation'] for o in packet['current']]
    tw,th=448,268;cols=2;nr=math.ceil(len(ordered)/cols);canvas=Image.new('RGB',(cols*tw,64+nr*th),(245,247,250));d=ImageDraw.Draw(canvas)
    d.text((12,7),'Native observations: history and current',fill=(20,28,38),font=font(21))
    d.text((12,34),'Left: RGB context + mask outline    Right: pixels inside that mask',fill=(40,50,62),font=font(16))
    for j,label in enumerate(ordered):
        s=byid[label];x0=(j%cols)*tw;y0=64+(j//cols)*th
        d.rectangle((x0+3,y0+3,x0+tw-3,y0+th-3),fill='white',outline=(200,207,218))
        d.text((x0+12,y0+10),s['kind']+' '+label,fill=(10,25,45),font=font(17))
        d.text((x0+12,y0+34),f"t={s['time_s']:.3f}s; measured mask, unverified identity",fill=(65,73,87),font=font(13))
        rgb,mask=pixels[s['source']];yy,xx=np.where(mask)
        if not len(xx):
            d.text((x0+12,y0+100),'EMPTY NATIVE MASK',fill=(160,40,40),font=font(18));continue
        bx0=max(0,int(xx.min())-12);by0=max(0,int(yy.min())-12);bx1=min(640,int(xx.max())+13);by1=min(360,int(yy.max())+13)
        crop=rgb[by0*3:by1*3,bx0*3:bx1*3].copy();cm=cv2.resize(mask[by0:by1,bx0:bx1].astype('u1'),(crop.shape[1],crop.shape[0]),interpolation=cv2.INTER_NEAREST)
        outline=crop.copy();contours,_=cv2.findContours(cm,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(outline,contours,-1,(255,30,200),2)
        isolated=np.full_like(crop,32);isolated[cm.astype(bool)]=crop[cm.astype(bool)]
        for k,img in enumerate([outline,isolated]):
            im=Image.fromarray(img);im.thumbnail((206,195),Image.Resampling.LANCZOS)
            canvas.paste(im,(x0+12+k*218+(206-im.width)//2,y0+62+(195-im.height)//2))
    path.parent.mkdir(exist_ok=True);canvas.save(path,format='PNG')
    return dict(width=canvas.width,height=canvas.height,labels=ordered,sha256=sha(path))

def main():
    start=time.monotonic();cpu=limit_cpu();assert not (P/'PREPARATION_ACCEPTANCE.json').exists(),'sealed preparation exists'
    save(P/'PREPARATION_STATUS.json',dict(stage='BUILDING',at=now(),pid=os.getpid(),cpu=cpu,GT_read=False))
    selectors=read(OLD/'SELECTORS.json');selection=read(OLD/'SELECTION_ACCEPTANCE.json')
    assert sha(OLD/'SELECTORS.json')==selection['selectors_sha256']
    save(P/'SELECTORS.json',selectors)
    oldhash=read(OLD/'INPUT_HASHES.json');sources={str(OLD/'SELECTORS.json'):sha(OLD/'SELECTORS.json')}
    observations={};profiles={};references={};needed={};stable={}
    base=ROOT/'tools/sam3_depth_return_guard_20260918/completion_evidence/experiment'
    frozen=read(base/'PREDICTIONS_FROZEN.json');sources[str(base/'PREDICTIONS_FROZEN.json')]=sha(base/'PREDICTIONS_FROZEN.json')
    for split in ['development','validation']:
        required={g for e in selectors if e['split']==split for g in [e['pre']]+e['query_frames']}
        path=base/f'predictions_{split}.jsonl.gz';h=sha(path);assert h==frozen['hashes'][path.name];sources[str(path)]=h
        stable[split]={}
        for rr in rows(path):
            if rr['global_frame'] not in required:continue
            pp=rr['variants']['Z4Q_STABLE'];assert all(x['mask'].startswith('n:') for x in pp)
            mapping={int(x['mask'][2:]):x['id'] for x in pp};assert len(mapping)==len(pp)
            stable[split][rr['global_frame']]=mapping
        assert set(stable[split])==required
    for split in ['development','validation']:
        op=ROOT/f'tools/sam3_depth_failure_repair_20260917/diagnosis_evidence/diagnosis/observations_{split}.jsonl.gz'
        fp=ROOT/f'tools/sam3_depth_birth_inherit_20260917/completion_evidence/features_r2/features_{split}.jsonl.gz'
        for path in [op,fp]:
            h=sha(path);assert h==oldhash[str(path)];sources[str(path)]=h
        observations[split]={r['global_frame']:r for r in rows(op)}
        profiles[split]={r['global_frame']:{o['id']:o for o in r['observations']} for r in rows(fp)}
        for r in observations[split].values():r['by_id']={o['id']:o for o in r['observations']}
    for e in selectors:
        split=e['split'];obs=observations[split]
        for n in e['historical_native_ids']:
            ff,clean=spaced_references(obs,n,e['pre'],2 if split=='development' else 9301)
            references[(e['key'],n)]=(ff,clean)
            for g in ff:needed.setdefault((split,g),set()).add(n)
        for g in e['query_frames']:needed.setdefault((split,g),set()).update(obs[g]['by_id'])
    assigns={'development':ROOT/'tools/sam3_occlusion_identity_20260915/i3_evidence_20260915_complete/identity_cpu10_20260915/run_8400/assignments.jsonl.gz',
             'validation':ROOT/'tools/sam3_depth_birth_quality_20260918/visual_comparison/native_validation_assignments.jsonl.gz'}
    rles={}
    for split,path in assigns.items():
        h=sha(path);assert h==oldhash[str(path)];sources[str(path)]=h
        for r in rows(path):
            g=r['frame']+(9300 if split=='validation' else 0)
            for n in needed.get((split,g),[]):rles[(split,g,n)]=r['masks'][f'n:{n}']
    manifest={r['frame_id']+1:r for r in map(json.loads,(DATA/'manifest.jsonl').read_text(encoding='utf-8').splitlines())}
    sources[str(DATA/'manifest.jsonl')]=sha(DATA/'manifest.jsonl');features={};pixels={};provenance=[]
    print('Verified native sources; descriptor frame count',len(needed),flush=True)
    for j,((split,g),ids) in enumerate(sorted(needed.items())):
        path=DATA/manifest[g]['rgb_original'];h=sha(path);assert h==manifest[g]['source_rgb_sha256'];sources[str(path)]=h
        image=cv2.imread(str(path));assert image.shape[:2]==(1080,1920);rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
        for n in sorted(ids):
            ob=observations[split][g]['by_id'][n];mask=decode_rle(rles[(split,g,n)]);assert int(mask.sum())==ob['area']
            count,_,stats,_=cv2.connectedComponentsWithStats(mask.astype('u1'),8)
            frac=float(stats[1:,cv2.CC_STAT_AREA].max()/mask.sum()) if count>1 else None
            ctr=np.array(np.where(mask)[::-1]).mean(1).tolist() if mask.any() else None
            f=dict(center_px=ctr,bbox_xyxy_px=ob['box'],area_px=ob['area'],presence=ob['presence'],
                   largest_component_fraction=frac,neighbor_count=len(ob['neighbors']),
                   raw_depth_mm={k:profiles[split][g][n][k] for k in ['whole','core']},
                   appearance_hsv_body=appearance(image,mask),mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest())
            features[(split,g,n)]=f;pixels[(split,g,n)]=(rgb,mask)
            provenance.append(dict(split=split,frame=g,native_id=n,rgb_path=str(path),rgb_sha256=h,mask_sha256=f['mask_sha256'],
                                   appearance_hsv_body=f['appearance_hsv_body'],source_depth_max_frame=profiles[split][g][n].get('source_depth_max_frame')))
        if j%25==0:print('Extracted frames',j+1,'/',len(needed),flush=True)
    oldix={(x['event'],x['stage']):x for x in read(OLD/'PRIVATE_INDEX.json')};packets=[];indexes=[];requests=[];maps={};image_index=[]
    for e in selectors:
        split=e['split'];obs=observations[split];pre=e['pre'];tracks={n:alias('T',e['key']+':'+str(n)) for n in e['historical_native_ids']}
        for k,g in enumerate(e['query_frames']):
            stage=['merge_snapshot','first_split'][k];qid=oldix[(e['key'],stage)]['query_id'];t=obs[g]['time']
            idmap={n:alias('O',qid+':'+str(n)) for n in obs[g]['by_id']};hist=[];evidence={};specs=[]
            prepub=stable[split][pre];currentpub=stable[split][g]
            assert set(currentpub)==set(idmap)
            pre_by_track={tracks[n]:prepub[n] for n in tracks}
            focal_public=set(pre_by_track.values());assert len(focal_public)==2
            other_pre_public=set(prepub.values())-focal_public
            public_to_track={v:k for k,v in pre_by_track.items()}
            for n in e['historical_native_ids']:
                ff,clean=references[(e['key'],n)];ss=[]
                for f in ff:ss.append(dict(time_s=obs[f]['time']-t,lineage=alias('L',e['key']+':'+str(n)),**clean_feature(features[(split,f,n)])))
                age=-ss[-1]['time_s'] if ss else None;span=ss[-1]['time_s']-ss[0]['time_s'] if len(ss)>1 else None
                vel=None
                if span and ss[0]['center_px'] is not None and ss[-1]['center_px'] is not None:vel=((np.array(ss[-1]['center_px'])-ss[0]['center_px'])/span).tolist()
                pred=(np.array(ss[-1]['center_px'])+np.array(vel)*age).tolist() if vel is not None else None
                outside=not (0<=pred[0]<640 and 0<=pred[1]<360) if pred else None
                eid=alias('E',qid+':history:'+str(n))
                hh=dict(track=tracks[n],evidence_id=eid,samples=ss,age_s=age,span_s=span,extrapolation_ratio=age/span if span else None,
                        geometry_independent_reference=clean,ownership='unverified_native_lineage_proxy',
                        velocity_px_s=vel,predicted_center_px=pred,motion_prediction_outside_image=outside,
                        motion_validity='long_term_extrapolation_unvalidated' if vel else 'missing')
                hist.append(hh);evidence[eid]={key:hh[key] for key in ['track','age_s','span_s','extrapolation_ratio','geometry_independent_reference','ownership','motion_prediction_outside_image']}
                evidence[eid]['kind']='historical_reference_quality'
                if ff:specs.append(dict(label=tracks[n],kind='HISTORY',time_s=obs[ff[-1]]['time']-t,source=(split,ff[-1],n)))
            current=[]
            for n in sorted(idmap):
                eid=alias('E',qid+':current:'+str(n));cc=dict(observation=idmap[n],time_s=0.,evidence_id=eid,lineage=alias('L',e['key']+':'+str(n)),
                            native_lineage_focal_track=tracks.get(n),lineage_is_identity_proof=False,
                            stable_owner_focal_track=public_to_track.get(currentpub[n]),
                            stable_owner_other=None if currentpub[n] in focal_public else alias('L',e['key']+':stable:'+str(currentpub[n])),
                            stable_owner_other_status=None if currentpub[n] in focal_public else ('pre_existing_nonfocal' if currentpub[n] in other_pre_public else 'new_since_reference'),
                            stable_ownership='baseline proposal, not identity truth',**clean_feature(features[(split,g,n)]))
                current.append(cc);evidence[eid]=dict(kind='current_observation',observation=idmap[n],area_px=cc['area_px'],center_px=cc['center_px'],
                    largest_component_fraction=cc['largest_component_fraction'],neighbor_count=cc['neighbor_count'],core_depth=cc['raw_depth_mm']['core'],
                    native_lineage_focal_track=tracks.get(n),lineage_is_identity_proof=False,
                    stable_owner_focal_track=cc['stable_owner_focal_track'],stable_owner_other=cc['stable_owner_other'],
                    stable_owner_other_status=cc['stable_owner_other_status'],stable_ownership=cc['stable_ownership'])
                specs.append(dict(label=idmap[n],kind='CURRENT',time_s=0.,source=(split,g,n)))
            pair=[]
            for hh,n in zip(hist,e['historical_native_ids']):
                ff,_=references[(e['key'],n)];refs=[features[(split,f,n)] for f in ff];last=refs[-1] if refs else None
                aa=[r['appearance_hsv_body'] for r in refs if r['appearance_hsv_body'] is not None];av=np.median(aa,axis=0) if aa else None
                if av is not None:av/=np.linalg.norm(av)
                for c in current:
                    native=next(n0 for n0,o0 in idmap.items() if o0==c['observation']);cf=features[(split,g,native)]
                    D=A=M=delta=None;dv=None
                    if last:
                        d=last['raw_depth_mm']['core'];dd=c['raw_depth_mm']['core']
                        if all(z['n']>=16 and z['valid_fraction']>=.2 and z['median'] is not None and z['mad'] is not None for z in [d,dd]):
                            delta=abs(dd['median']-d['median']);D=delta/(15+1.4826*(d['mad']+dd['mad']));dv=min(d['valid_fraction'],dd['valid_fraction'])
                        if av is not None and cf['appearance_hsv_body'] is not None:A=max(0.,float(1-np.dot(av,cf['appearance_hsv_body'])))
                        if hh['predicted_center_px'] is not None and c['center_px'] is not None:
                            box=last['bbox_xyxy_px'];diag=max(1.,float(np.linalg.norm(np.array(box[2:])-box[:2])))
                            M=float(np.linalg.norm(np.array(c['center_px'])-hh['predicted_center_px'])/diag)
                    eid=alias('E',qid+':pair:'+hh['track']+':'+c['observation'])
                    edge=dict(track=hh['track'],observation=c['observation'],evidence_id=eid,D=D,A=A,M=M,depth_difference_mm=delta,
                         history_age_s=hh['age_s'],history_span_s=hh['span_s'],extrapolation_ratio=hh['extrapolation_ratio'],
                         available=dict(D=D is not None,A=A is not None,M=M is not None),quality=dict(depth_valid_fraction_min=dv,
                         history_geometry_independent=hh['geometry_independent_reference'],history_fragmentation=last['largest_component_fraction'] if last else None,
                         current_fragmentation=c['largest_component_fraction'],history_neighbor_count=last['neighbor_count'] if last else None,
                         current_neighbor_count=c['neighbor_count'],motion_prediction_outside_image=hh['motion_prediction_outside_image'],motion_validity=hh['motion_validity']))
                    pair.append(edge);evidence[eid]=dict(kind='pairwise_measurements',**{x:edge[x] for x in ['track','observation','D','A','M','depth_difference_mm','available']})
            frames=sorted(set(int(round(x)) for x in np.linspace(pre,g,5)));recent=[]
            for f in frames:
                rr=obs[f];entry=dict(time_s=rr['time']-t,observations=[dict(lineage=alias('L',e['key']+':'+str(o['id'])),
                    bbox_xyxy_px=o['box'],area_px=o['area'],neighbor_count=len(o['neighbors']),raw_depth_mm=o['depth'],
                    native_lineage_focal_track=tracks.get(o['id']),lineage_is_identity_proof=False,
                    current_observation=idmap.get(o['id']) if f==g else None) for o in rr['observations']])
                eid=alias('E',qid+':recent:'+str(f));entry['evidence_id']=eid
                evidence[eid]=dict(kind='recent_observation_summary',time_s=entry['time_s'],observation_count=len(entry['observations']),
                    focal_lineages=[z['native_lineage_focal_track'] for z in entry['observations'] if z['native_lineage_focal_track'] is not None])
                recent.append(entry)
            p=dict(schema='SLR2.causal.numeric.v1',query_id=qid,focal_tracks=list(tracks.values()),history=hist,current=current,recent=recent,pairwise=pair,evidence=evidence,options=[])
            p['options']=make_options(p)
            baseline_matches={t:[o for o,n in ((o,n) for n,o in idmap.items()) if currentpub[n]==pub] for t,pub in pre_by_track.items()}
            possible_b0=all(len(v)==1 for v in baseline_matches.values()) and len({v[0] for v in baseline_matches.values()})==2
            b0pairs=sorted((t,oo[0]) for t,oo in baseline_matches.items()) if possible_b0 else None
            b0option=next(o for o in p['options'] if (o['state']=='MATCH' and sorted((x['track'],x['observation']) for x in o['matches'])==b0pairs) or (not possible_b0 and o['state']=='UNRESOLVED'))
            p['baseline_option_id']=b0option['option_id']
            evidence[alias('E',qid+':baseline')]=dict(kind='baseline_proposal',option_id=b0option['option_id'],ownership='baseline proposal, not identity truth')
            check_packet(p);packets.append(p)
            ix=dict(query_id=qid,event=e['key'],stage=stage,split=split,frame=g,pre=pre,track_native_map={v:n for n,v in tracks.items()},
                    observation_native_map={v:n for n,v in idmap.items()},source_frames=sorted(set(frames+[f for n in tracks for f in references[(e['key'],n)][0]])),
                    pre_public_by_track=pre_by_track,pre_public_by_native={str(n):pub for n,pub in prepub.items()},
                    current_public_by_observation={o:currentpub[n] for n,o in idmap.items()},
                    current_public_by_native={str(n):pub for n,pub in currentpub.items()},
                    protected_nonfocal_observations=[o for n,o in idmap.items() if currentpub[n] in other_pre_public])
            indexes.append(ix)
            perm,renaming=permutation(p);check_packet(perm)
            for view in (['original','repeat','permuted'] if stage=='first_split' else ['original']):
                vp=perm if view=='permuted' else p;mp=renaming if view=='permuted' else {}
                mapped_specs=[dict(s,label=mp.get(s['label'],s['label'])) for s in specs]
                imgrel=Path('images')/(qid+('_permuted' if view=='permuted' else '_original')+'.png');imagepath=P/imgrel
                if view!='repeat':
                    info=render_sheet(imagepath,vp,mapped_specs,pixels)
                    image_index.append(dict(query_id=qid,view=view,path=imgrel.as_posix(),**info,sources=[dict(label=s['label'],split=s['source'][0],frame=s['source'][1],native_id=s['source'][2],time_s=s['time_s']) for s in mapped_specs]))
                imhash=sha(imagepath)
                tm={mp.get(t,t):n for t,n in ix['track_native_map'].items()};om={mp.get(o,o):n for o,n in ix['observation_native_map'].items()}
                optmap={o['option_id']:canonical_option(o,tm,om) for o in vp['options']}
                for arm in ['T','V']:
                    rid=alias('R',qid+':'+arm+':'+view)
                    requests.append(dict(request_id=rid,query_id=qid,arm=arm,view=view,packet=vp,image_paths=[imgrel.as_posix()] if arm=='V' else [],image_sha256=[imhash] if arm=='V' else []))
                    maps[rid]=dict(query_id=qid,arm=arm,view=view,stage=stage,split=split,frame=g,pre=pre,event=e['key'],
                                   track_native_map=tm,observation_native_map=om,option_map=optmap,
                                   pre_public_by_track={mp.get(t,t):pub for t,pub in pre_by_track.items()},
                                   pre_public_by_native=ix['pre_public_by_native'],current_public_by_native=ix['current_public_by_native'],
                                   current_public_by_observation={mp.get(o,o):pub for o,pub in ix['current_public_by_observation'].items()},
                                   protected_nonfocal_observations=[mp.get(o,o) for o in ix['protected_nonfocal_observations']],
                                   baseline_option_id=vp['baseline_option_id'])
            print('Prepared',qid,stage,len(p['options']),'options',flush=True)
    save(P/'PACKETS.json',packets);save(P/'PRIVATE_INDEX.json',indexes);save(P/'REQUESTS.json',requests);save(P/'REQUEST_MAPS.json',maps)
    save(P/'INPUT_PROVENANCE.json',provenance);save(P/'IMAGE_PROVENANCE.json',image_index);save(P/'INPUT_HASHES.json',sources);save(P/'SOURCE_HASHES.json',sources)
    for source,h in sources.items():assert sha(source)==h
    check=check_requests(P);save(P/'INPUT_CHECKS.json',check)
    outputs=['SELECTORS.json','PACKETS.json','PRIVATE_INDEX.json','REQUESTS.json','REQUEST_MAPS.json','INPUT_PROVENANCE.json','IMAGE_PROVENANCE.json','INPUT_HASHES.json','SOURCE_HASHES.json','INPUT_CHECKS.json']
    hashes={n:sha(P/n) for n in outputs};hashes.update({x['path']:x['sha256'] for x in image_index})
    save(P/'PREPARATION_ACCEPTANCE.json',dict(at=now(),exit_code=0,packets=len(packets),requests=len(requests),images=len(image_index),
         GT_read=False,oracle_conditioned=True,independent_blind_test=False,cpu=cpu,seconds=time.monotonic()-start,
         opened_paths=sorted(set(OPENED)),source_hashes=sources,payload_hashes=hashes,hashes=hashes,
         code_hashes={n:sha(P/n) for n in ['prepare.py','input_checks.py']},input_checks=check))
    save(P/'PREPARATION_STATUS.json',dict(stage='COMPLETE',at=now(),exit_code=0,packets=len(packets),requests=len(requests),images=len(image_index),GT_read=False))
    print('PREPARATION COMPLETE',round(time.monotonic()-start,2),'seconds',flush=True)
if __name__=='__main__':main()
