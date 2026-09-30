"""Reuse frozen DS3 sources and helpers without modifying their globals."""
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DS3=ROOT/'experiments/ds3_depth_foreground_filter'
sys.path.insert(0,str(DS3))
import common as legacy
import foreground as baseline
sys.path.insert(0,str(HERE))

np,cv2,coco=legacy.np,legacy.cv2,legacy.coco
DATA,OLD,SEGMENTS=legacy.DATA,legacy.OLD,legacy.SEGMENTS
artifact,verify,digest=legacy.artifact,legacy.verify,legacy.digest
records,encoded,decode=legacy.records,legacy.encoded,legacy.decode
write_new,dump_line=legacy.write_new,legacy.dump_line
extract_frame,statistics,KERNEL=legacy.extract_frame,legacy.statistics,legacy.KERNEL
CONFIG=json.loads((HERE/'CONFIG.json').read_text(encoding='utf-8'))
ARMS={
    'F2_DS3':(False,False,15.),
    'F3_RANGE':(True,False,15.),
    'F4_MAIN':(False,True,15.),
    'F5_RANGE_MAIN':(True,True,15.),
    'F6_BG_NOISE':(True,False,1.),
}


def source_depth(frame):
    with np.load(DATA/'depth_rgb_640x360'/f'{frame:06d}.npz') as sensor:
        depth=sensor['depth_mm'].copy()
        index=sensor['source_index'].copy()
    native=np.load(DATA/'depth_native_mm'/f'{frame:06d}.npy')
    assert depth.shape==index.shape==(360,640) and native.shape==(576,640)
    valid=np.isfinite(depth)&(depth>0)
    assert np.array_equal(valid,index>=0)
    assert np.all(index[valid]<native.size)
    source=np.zeros(depth.shape,'f4')
    source[valid]=native.ravel()[index[valid]]
    assert np.all(np.isfinite(source[valid])&(source[valid]>0))
    suspect=valid & (source>CONFIG['native_suspect_above_mm'])
    clean=depth.copy(); clean[suspect]=0
    return depth,clean,suspect,dict(native_path=str(DATA/'depth_native_mm'/f'{frame:06d}.npy'),
        native_sha256=digest(DATA/'depth_native_mm'/f'{frame:06d}.npy'),native_suspect_n=int(suspect.sum()),
        original_valid_n=int(valid.sum()),status='RAW_SOURCE_VERIFIED_SUSPECT_RANGE_POLICY',
        sensor_valid_range='UNKNOWN')


def main_region(region):
    count,labels,stats,_=cv2.connectedComponentsWithStats(region.astype('u1'),connectivity=8)
    areas=stats[1:,cv2.CC_STAT_AREA]
    biggest=int(areas.max())
    winners=np.flatnonzero(areas==biggest)+1
    main=(labels==int(winners[0])) if len(winners)==1 else np.zeros(region.shape,bool)
    return main,dict(components=count-1,areas_descending=sorted(map(int,areas),reverse=True),
                    main_unique=len(winners)==1,main_area=int(main.sum()),
                    minor_area=int(region.sum()-main.sum()))
