"""Frozen observational audit. No new extractor, tracker or model request."""
import gzip
import json
import os
import platform
import socket
import sys
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch

os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DS4 = ROOT/'experiments/ds4_depth_quality_repair'
sys.path.insert(0, str(DS4))
from bootstrap import DATA, SEGMENTS, np, cv2, records, decode, artifact, verify, digest, write_new, dump_line
from score import check_seal, truth_masks, matching
sys.path.insert(0, 'E:/CAU/D-MOT/tools/depth_restoration')
from geometry import Geometry
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
cv2.setNumThreads(1)
CFG = json.loads((HERE/'CONFIG.json').read_text(encoding='utf-8'))
ARMS = ('F2_DS3', 'F6_BG_NOISE')


def shift_counts(selected, matched, all_truth, dx, dy):
    """Translate original sample coordinates; keep original denominator/no wrap."""
    y, x = np.nonzero(selected)
    xx, yy = x+dx, y+dy
    inside = (xx>=0)&(xx<selected.shape[1])&(yy>=0)&(yy<selected.shape[0])
    fish = int(matched[yy[inside], xx[inside]].sum())
    other = int((all_truth[yy[inside], xx[inside]]&~matched[yy[inside], xx[inside]]).sum())
    background = int(inside.sum())-fish-other
    out = dict(n=len(x), fish=fish, other_fish=other, background=background, out_of_view=int((~inside).sum()))
    assert out['n']==sum(out[k] for k in ('fish','other_fish','background','out_of_view'))
    return out


def depth_pieces(depth, selected, gap):
    """8-neighbor edges between measured selected points; no hole filling."""
    y, x = np.nonzero(selected)
    n = len(x)
    if not n:
        return dict(n=0, pieces=[], qualified_pieces=0, largest_median_mm=None,
                    largest_n=0, sorted_max_gap_mm=None, q90_minus_q10_mm=None)
    assert np.all(np.isfinite(depth[selected])&(depth[selected]>0))
    ids = np.full(selected.shape, -1, 'i4'); ids[y,x] = np.arange(n)
    aa, bb = [], []
    for dy, dx in ((0,1),(1,-1),(1,0),(1,1)):
        yy, xx = y+dy, x+dx
        good = (yy>=0)&(yy<selected.shape[0])&(xx>=0)&(xx<selected.shape[1])
        source = np.flatnonzero(good)
        dest = ids[yy[good],xx[good]]
        keep = dest>=0; source, dest = source[keep], dest[keep]
        keep = np.abs(depth[y[source],x[source]]-depth[y[dest],x[dest]])<=gap
        aa.extend(source[keep]); bb.extend(dest[keep])
    graph = coo_matrix((np.ones(len(aa),'u1'), (aa,bb)),shape=(n,n)).tocsr()
    _, labels = connected_components(graph,directed=False)
    values = depth[selected].astype('f8')
    pieces = []
    for label in range(int(labels.max())+1):
        v = values[labels==label]; median = float(np.median(v))
        count = len(v)
        pieces.append(dict(n=count, fraction=count/n, median_mm=median,
                           mad_mm=float(np.median(np.abs(v-median))),
                           qualified=bool(count>=CFG['piece_min_n'] and count/n>=CFG['piece_min_fraction'])))
    pieces.sort(key=lambda p:(-p['n'],p['median_mm']))
    # Ties have no selected winner. This audit never writes a replacement measurement.
    unique = len(pieces)==1 or pieces[0]['n']>pieces[1]['n']
    ordered = np.sort(values)
    return dict(n=n, pieces=pieces, qualified_pieces=sum(p['qualified'] for p in pieces),
                largest_median_mm=pieces[0]['median_mm'] if unique else None, largest_n=pieces[0]['n'],
                sorted_max_gap_mm=float(np.diff(ordered).max()) if n>1 else 0.,
                q90_minus_q10_mm=float(np.quantile(values,.9)-np.quantile(values,.1)))


def jumps(depth, source_index, native):
    valid = np.isfinite(depth)&(depth>0)&(source_index>=0)
    admitted = valid.copy()
    admitted[valid] &= native.ravel()[source_index[valid]]<=CFG['native_suspect_above_mm']
    edge = np.zeros(depth.shape,bool)
    for axis in (0,1):
        a = [slice(None),slice(None)]; b = a.copy()
        a[axis]=slice(None,-1); b[axis]=slice(1,None)
        a,b=tuple(a),tuple(b)
        pair = admitted[a]&admitted[b]&(np.abs(depth[a]-depth[b])>CFG['boundary_jump_mm'])
        edge[a] |= pair; edge[b] |= pair
    return edge


def quantiles(values):
    values = np.asarray(values,'f8')
    return dict(n=int(values.size), min=float(values.min()), median=float(np.median(values)),
                q90=float(np.quantile(values,.9)), max=float(values.max())) if values.size else dict(n=0,min=None,median=None,q90=None,max=None)


def calibration_geometry():
    calibration=json.loads((DATA/'calibration.json').read_text(encoding='utf-8'))
    geom=Geometry(calibration['recorded_profiles'],640,360)
    geom.kc[0,2]+=(640/geom.color['width']-1)/2
    geom.kc[1,2]+=(360/geom.color['height']-1)/2
    u,s,vt=np.linalg.svd(geom.r)
    nearest=u@np.diag([1,1,np.linalg.det(u@vt)])@vt
    return geom,nearest,dict(recorded_matrix=geom.r.tolist(),determinant=float(np.linalg.det(geom.r)),
        max_orthogonality_error=float(np.max(np.abs(geom.r.T@geom.r-np.eye(3)))),
        singular_values=s.tolist(),nearest_SO3=nearest.tolist(),
        interpretation='STRUCTURAL_SENSITIVITY_NOT_CERTIFIED_CORRECTION', physical_calibration='UNKNOWN')


def projection_shadow(geom, nearest, index, native, depth, selected):
    y,x=np.nonzero(selected)
    if not len(x): return dict(status='NO_SELECTED_POINTS',n=0)
    source=index[selected]; assert np.all(source>=0)
    rays=geom.rays.reshape(-1,3)[source]; values=native.ravel()[source]
    xyz=rays@geom.r.T*values[:,None]+geom.t
    assert np.array_equal(xyz[:,2].astype('f4'),depth[selected])
    recorded=geom.project_xyz(xyz)
    altered_xyz=rays@nearest.T*values[:,None]+geom.t
    altered=geom.project_xyz(altered_xyz)
    return dict(status='SAME_NATIVE_POINTS_SHADOW_ONLY',n=len(x),unique_native_n=len(np.unique(source)),
        recorded_raster_rounding_error_px=quantiles(np.linalg.norm(recorded-np.column_stack([x,y]),axis=1)),
        shadow_minus_recorded_dx_px=quantiles(altered[:,0]-recorded[:,0]),
        shadow_minus_recorded_dy_px=quantiles(altered[:,1]-recorded[:,1]),
        shadow_displacement_px=quantiles(np.linalg.norm(altered-recorded,axis=1)),
        shadow_z_delta_mm=quantiles(altered_xyz[:,2]-xyz[:,2]),physical_correctness='UNKNOWN',input_changed=False)


def cohort(rows, facts):
    reasons={}
    def add(r, reason):
        reasons.setdefault((r['segment'],r['frame'],r['token']),[])
        if reason not in reasons[(r['segment'],r['frame'],r['token'])]: reasons[(r['segment'],r['frame'],r['token'])].append(reason)
    for r in rows:
        a,b=(r['methods'][m] for m in ARMS)
        if b['reference_compatible'] is False and a['reference_compatible'] is not False: add(r,'ALL_NEW_REFERENCE_CONFLICTS')
        if r['reference_status']=='SCORABLE' and b['selected_n'] and b['occupancy']['fish']==0: add(r,'ALL_ZERO_MATCHED_SILHOUETTE')
    for name in SEGMENTS:
        low=[r for r in rows if r['segment']==name and r['methods'][ARMS[1]]['selected_n'] and
             facts[(r['frame'],r['token'])]['methods'][ARMS[1]]['selector']['raw_valid_retention']<CFG['low_retention']]
        for r in low[:CFG['low_retention_per_segment']]: add(r,'EARLIEST_LOW_RETENTION')
    for frame,token in CFG['known_cases']:
        r=next(r for r in rows if r['frame']==frame and r['token']==token); add(r,'SEALED_KNOWN_CASE')
    cases=[r for r in rows if (r['segment'],r['frame'],r['token']) in reasons]
    candidates=[r for r in rows if r['reference_status']=='SCORABLE' and all(r['methods'][m]['reference_compatible'] is True for m in ARMS)
                and (r['segment'],r['frame'],r['token']) not in reasons]
    controls={}
    for r in cases:
        area=facts[(r['frame'],r['token'])]['whole']['area']
        pool=[c for c in candidates if c['segment']==r['segment'] and c['reference_status']==r['reference_status']
              and c['reference_usable']==r['reference_usable']]
        if not pool: controls[(r['frame'],r['token'])]=None; continue
        c=min(pool,key=lambda c:(abs(c['frame']-r['frame']),abs(np.log(facts[(c['frame'],c['token'])]['whole']['area']/area)),c['frame'],c['token']))
        controls[(r['frame'],r['token'])]=dict(frame=c['frame'],token=c['token'],frame_delta=c['frame']-r['frame'],
            source_area_ratio=facts[(c['frame'],c['token'])]['whole']['area']/area,
            matched_reference_usable=c['reference_usable']); add(c,'NEAREST_STABLE_DIAGNOSTIC_CONTROL')
    result=[dict(segment=n,frame=f,token=t,reasons=rs,control=controls.get((f,t)),
                 physical_surface_ownership='UNKNOWN') for (n,f,t),rs in sorted(reasons.items())]
    return result


def load_old():
    rows=[r for n in SEGMENTS for r in records(DS4/f'{n}_occupancy.jsonl.gz')]
    facts={(r['frame'],t):o for n in SEGMENTS for r in records(DS4/f'{n}_measurements.jsonl.gz') for t,o in r['objects'].items()}
    assert len(rows)==len(facts)==28382
    return rows,facts


def freeze(rows,facts):
    assert not (HERE/'FREEZE.json').exists(),'refuse overwrite'
    assert json.loads((HERE/'CHECKS.json').read_text())['passed']
    check_seal()
    cases=cohort(rows,facts)
    write_new(HERE/'COHORT.json',dict(cases=cases,selection='DETERMINISTIC_EXPOSED_DIAGNOSTIC_NOT_BLIND',
        old_fixed_S=28382,old_fixed_Q=28088,old_fixed_R=21817,physical_labels_available=False))
    manifest={r['frame']:r for r in map(json.loads,(DATA/'manifest.jsonl').read_text(encoding='utf-8').splitlines())}
    source=[]
    for frame in sorted({c['frame'] for c in cases}):
        m=manifest[frame]
        rgb=DATA/m['rgb_original']; assert digest(rgb)==m['source_rgb_sha256']
        items={k:artifact(DATA/m[k]) for k in ('rgb_original','rgb','label','depth_native','depth_aligned')}
        assert items['depth_native']['sha256']==m['source_depth_sha256']
        source.append(dict(frame=frame,rgb_timestamp_us=m['rgb_timestamp_us'],depth_timestamp_us=m['depth_timestamp_us'],
                           delta_us=m['delta_us'],artifacts=items))
    write_new(HERE/'SOURCE_INVENTORY.json',dict(cohort=source,manifest=artifact(DATA/'manifest.jsonl'),
        calibration=artifact(DATA/'calibration.json'),projection_code=artifact(Path('E:/CAU/D-MOT/tools/depth_restoration/geometry.py'))))
    locks=[artifact(p) for folder in ('ds1_depth_only','ds2_depth_transfer_validation','ds3_depth_foreground_filter','ds4_depth_quality_repair')
        for p in sorted((ROOT/'experiments'/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
    write_new(HERE/'OLD_READONLY_LOCK.json',locks)
    code=[artifact(p) for p in HERE.glob('*.py')]+[artifact(HERE/p) for p in ('PLAN.md','CONFIG.json','CHECKS.json','COHORT.json','SOURCE_INVENTORY.json',
        'SOURCE_REVIEW.json','FAILURE_REVIEW.json','EVALUATION_REVIEW.json')]
    write_new(HERE/'FREEZE.json',dict(status='FROZEN_BEFORE_DS5_AUDIT',base=CFG['base'],code=code,
        old_lock=artifact(HERE/'OLD_READONLY_LOCK.json'),cohort_n=len(cases),census_objects=28382,model_http=0,cost_usd=0))
    return cases


def selected_region(pix,arm,depth):
    item=pix['methods'][arm]; x0,y0,x1,y1=item['crop']
    local=decode(item['regions']['selected'])
    full=np.zeros(depth.shape,bool); full[y0:y1,x0:x1]=local
    return full,local,depth[y0:y1,x0:x1],item


def run():
    rows,facts=load_old(); cases=freeze(rows,facts); started=time.perf_counter()
    keys={(c['frame'],c['token']) for c in cases}; cohort_frames={f for f,t in keys}
    oldrows={(r['frame'],r['token']):r for r in rows}
    geom,nearest,calibration=calibration_geometry(); write_new(HERE/'CALIBRATION_STRUCTURE.json',calibration)
    streams=[gzip.open(HERE/p,'xt',encoding='utf-8') for p in ('CENSUS.jsonl.gz','REGISTRATION.jsonl.gz')]
    count=0; private_inputs=[]
    try:
        for name in SEGMENTS:
            for row in records(DS4/'private'/f'{name}_pixels.jsonl.gz'):
                frame=row['frame']; depth_path=DATA/'depth_rgb_640x360'/f'{frame:06d}.npz'
                with np.load(depth_path,allow_pickle=False) as sensor: depth=sensor['depth_mm'].copy(); index=sensor['source_index'].copy()
                assert frame<=SEGMENTS[name][1]
                if frame in cohort_frames:
                    native=np.load(DATA/'depth_native_mm'/f'{frame:06d}.npy',allow_pickle=False)
                    path=DATA/'labels_640x360'/f'{frame:06d}.json'; truth=truth_masks(path); private_inputs.append(artifact(path))
                    sources={t:decode(o['source_mask']) for t,o in row['objects'].items()}
                    matches=matching(sources,truth); all_truth=np.logical_or.reduce(list(truth.values())) if truth else np.zeros(depth.shape,bool)
                    edge=jumps(depth,index,native)
                    distance=cv2.distanceTransform((~edge).astype('u1'),cv2.DIST_L2,cv2.DIST_MASK_PRECISE) if edge.any() else None
                for token,pix in row['objects'].items():
                    old=oldrows[(frame,token)]; fact=facts[(frame,token)]; outputs={}
                    full_selections={}
                    for arm in ARMS:
                        full,local,crop,item=selected_region(pix,arm,depth); full_selections[arm]=full
                        assert int(local.sum())==old['methods'][arm]['selected_n']
                        spatial_n=cv2.connectedComponents(local.astype('u1'),connectivity=8)[0]-1 if local.any() else 0
                        support=decode(item['regions']['support'])
                        graphs={str(g):depth_pieces(crop,local,g) for g in CFG['depth_edge_gaps_mm']}
                        outputs[arm]=dict(status=old['methods'][arm]['status'],selected_n=int(local.sum()),
                            selected_spatial_components=spatial_n,support_spatial_components=int(cv2.connectedComponents(support.astype('u1'),connectivity=8)[0]-1),
                            graphs=graphs,retention=fact['methods'][arm]['selector']['raw_valid_retention'],
                            old_reference_compatible=old['methods'][arm]['reference_compatible'],
                            source_statistics=fact['methods'][arm]['selector']['selected'],physical_surface_ownership='UNKNOWN')
                    dump_line(streams[0],dict(segment=name,frame=frame,token=token,fact_id=fact['fact_id'],methods=outputs)); count+=1
                    if (frame,token) in keys:
                        match=matches[token]; assert match['status']==old['reference_status']
                        matched=truth[match['identity']] if match['status']=='SCORABLE' else None
                        methods={}
                        for arm in ARMS:
                            selected=full_selections[arm]
                            shifts=[dict(dx=dx,dy=dy,counts=shift_counts(selected,matched,all_truth,dx,dy))
                                for dy in CFG['shift_grid_px'] for dx in CFG['shift_grid_px']] if matched is not None else None
                            if shifts is not None:
                                zero=next(s['counts'] for s in shifts if s['dx']==s['dy']==0)
                                assert {k:zero[k] for k in old['methods'][arm]['occupancy']}==old['methods'][arm]['occupancy']
                            methods[arm]=dict(shifts=shifts,projection_shadow=projection_shadow(geom,nearest,index,native,depth,selected))
                        boundary=matched&~cv2.erode(matched.astype('u1'),np.ones((3,3),'u1')).astype(bool) if matched is not None else None
                        boundary_dist=quantiles(distance[boundary]) if distance is not None and boundary is not None else quantiles([])
                        dump_line(streams[1],dict(segment=name,frame=frame,token=token,reference_status=match['status'],
                            depth_jump_boundary_distance_px=boundary_dist,boundary_diagnostic='RGB_SILHOUETTE_TO_NEAREST_RAW_DEPTH_JUMP_NOT_SURFACE_GT',
                            methods=methods,physical_surface_ownership='UNKNOWN',future_frames_read=False,inputs_changed=False))
                if frame%100==0 or frame==SEGMENTS[name][1]: print(f'DS5 observed {name} F{frame}; objects {count}',flush=True)
    finally:
        for stream in streams: stream.close()
    assert count==28382
    write_new(HERE/'AUDIT_INPUTS.json',private_inputs)
    check_old()
    write_new(HERE/'AUDIT_SEALED.json',dict(status='OBSERVATIONAL_AUDIT_COMPLETE_NO_REPLACEMENT',objects=count,
        cohort_n=len(cases),seconds=time.perf_counter()-started,artifacts=[artifact(HERE/p) for p in ('CENSUS.jsonl.gz','REGISTRATION.jsonl.gz','CALIBRATION_STRUCTURE.json','AUDIT_INPUTS.json')],
        frozen_code=artifact(HERE/'FREEZE.json'),environment=dict(python=platform.python_version(),numpy=np.__version__,opencv=cv2.__version__,cpu_threads=1),
        model_http=0,training=0,sam3=0,tracker_runs=0,cost_usd=0,physical_ownership_labels='UNAVAILABLE_UNKNOWN'))


def check_old():
    freeze=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for item in freeze['code']: verify(item)
    verify(freeze['old_lock'])
    for item in json.loads((HERE/'OLD_READONLY_LOCK.json').read_text(encoding='utf-8')): verify(item)
    inventory=json.loads((HERE/'SOURCE_INVENTORY.json').read_text(encoding='utf-8'))
    for row in inventory['cohort']:
        for item in row['artifacts'].values(): verify(item)
    for key in ('manifest','calibration','projection_code'): verify(inventory[key])


if __name__=='__main__':
    with patch.object(socket.socket,'connect',side_effect=AssertionError('DS5 offline: no network/model')): run()
