"""Anonymous raw-depth graph pieces, with frozen F6 filtering in isolated globals."""
from __future__ import annotations
import ast
import types
import cv2
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from common import HERE, ROOT, DATA, read, sha
from depth_measurement import statistics

CFG=read(HERE/'CONFIG.json')
FILTER_CFG=read(ROOT/'experiments/ds3_depth_foreground_filter/CONFIG.json')

def frozen_body(path,namespace):
    """Reuse old function bodies without importing or mutating their module globals."""
    tree=ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
    tree.body=[node for node in tree.body if not isinstance(node,(ast.Import,ast.ImportFrom))]
    exec(compile(tree,str(path),'exec'),namespace)
    return types.SimpleNamespace(**namespace)

_fg=frozen_body(ROOT/'experiments/ds3_depth_foreground_filter/foreground.py',
    dict(CFG=FILTER_CFG,cv2=cv2,np=np,statistics=statistics))
_selector=frozen_body(ROOT/'experiments/ds4_depth_quality_repair/selector.py',
    dict(baseline=_fg,cv2=cv2,np=np,statistics=statistics))
f6_measure=_selector.measure

def pieces(depth,selected,fact_id,crop):
    y,x=np.nonzero(selected)
    n=len(x)
    if not n:
        return []
    assert np.all(np.isfinite(depth[selected])&(depth[selected]>0))
    ids=np.full(selected.shape,-1,'i4')
    ids[y,x]=np.arange(n)
    aa,bb=[],[]
    for dy,dx in ((0,1),(1,-1),(1,0),(1,1)):
        yy,xx=y+dy,x+dx
        good=(yy>=0)&(yy<selected.shape[0])&(xx>=0)&(xx<selected.shape[1])
        src=np.flatnonzero(good)
        dst=ids[yy[good],xx[good]]
        keep=dst>=0
        src,dst=src[keep],dst[keep]
        keep=np.abs(depth[y[src],x[src]]-depth[y[dst],x[dst]])<=CFG['depth_edge_gap_mm']
        aa.extend(src[keep]);bb.extend(dst[keep])
    graph=coo_matrix((np.ones(len(aa),'u1'),(aa,bb)),shape=(n,n)).tocsr()
    _,labels=connected_components(graph,directed=False)
    values=np.asarray(depth[selected],dtype='f8')
    result=[]
    for label in range(int(labels.max())+1):
        own=labels==label
        v=values[own]
        median=float(np.median(v))
        mad=float(np.median(np.abs(v-median)))
        scale=max(15.,1.4826*mad)
        count=len(v)
        result.append(dict(piece_id=f'{fact_id}/p{label:03d}',n=count,
            fraction=count/n,median=median,mad=mad,scale_mm=scale,
            centroid_px=[float(x[own].mean()+crop[0]),float(y[own].mean()+crop[1])],
            qualified=bool(count>=CFG['piece_min_n'] and count/n>=CFG['piece_min_fraction']
                           and scale<=CFG['piece_max_scale_mm']),
            identity='UNKNOWN',source='ACTUAL_F6_SELECTED_RAW_POINTS'))
    assert sum(p['n'] for p in result)==n
    return result

def admission(global_frame,depth):
    path=DATA/'depth_rgb_640x360'/f'{global_frame:06d}.npz'
    native_path=DATA/'depth_native_mm'/f'{global_frame:06d}.npy'
    with np.load(path) as sensor:
        index=sensor['source_index']
    native=np.load(native_path)
    valid=np.isfinite(depth)&(depth>0)
    assert np.array_equal(valid,index>=0)
    assert np.all(index[valid]<native.size)
    actual=np.zeros(depth.shape,'f4')
    actual[valid]=native.ravel()[index[valid]]
    assert np.all(np.isfinite(actual[valid])&(actual[valid]>0))
    suspect=valid&(actual>CFG['native_suspect_above_mm'])
    clean=depth.copy()
    clean[suspect]=0
    return clean,dict(native_path=str(native_path),native_sha256=sha(native_path),
        suspect_n=int(suspect.sum()),sensor_valid_range='UNKNOWN',
        source_policy='native>5000mm is SUSPECT; aligned camera-Z retained otherwise')

def measure_frame(depth,masks,occupancy,segment,frame,global_frame):
    clean,quality=admission(global_frame,depth)
    result={}
    for native,region in masks.items():
        fact_id=f'{segment}/F{frame}/n:{native}/F6'
        other=(occupancy-region.astype('u2'))>0
        fact,pixels=f6_measure(clean,region,other,CFG['background_floor_mm'])
        x0,y0,x1,y1=fact['crop']
        graph=pieces(clean[y0:y1,x0:x1],pixels['selected'],fact_id,fact['crop'])
        qualified=[p for p in graph if p['qualified']]
        out=dict(native=native,fact_id=fact_id,source='F6_SELECTED_RAW_GRAPH_PIECE',
            measurement_kind='F6_FOREGROUND_SELECTED',filter=fact,pieces=graph,
            qualified_piece_count=len(qualified),surface_identity='UNKNOWN',
            core=dict(fact['selected']),core_usable=(fact['status']=='AVAILABLE' and bool(qualified)),
            whole=statistics(depth,region))
        # Both new branches use the same unambiguous historical acquisition.
        # A multiple-piece measurement is kept as evidence, never hard-selected.
        out['history_core']=dict(qualified[0]) if len(qualified)==1 else dict(median=None,mad=None)
        out['history_usable']=fact['status']=='AVAILABLE' and len(qualified)==1
        out['history_reason']=('ONE_QUALIFIED_ANONYMOUS_PIECE' if out['history_usable']
                               else 'MULTIPLE_OR_MISSING_PIECES_UNKNOWN')
        result[native]=out
    return result,quality

def history_measurement(measurement):
    """Field adapter only for unchanged DS1 state; raw core remains separately logged."""
    return dict(measurement,core=measurement['history_core'],
                core_usable=measurement['history_usable'],
                measurement_kind='UNAMBIGUOUS_F6_GRAPH_PIECE_FOR_HISTORY')

