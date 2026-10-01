"""Current raw sensor adapters. No restored value, RGB, reference or instance_id."""
from common import *
import copy
from functools import lru_cache
import numpy as np, cv2, h5py
from pycocotools import mask as coco
from geometry import Geometry
from build_aligned_dataset import rasterize
from features import stats,exclusive_core
from contact_measurement import array_binding
cv2.setNumThreads(1)
KERNEL=np.ones((7,7),'u1')
FIELD_READS=[]

def native_masks(assignment):
    # Old collection files also contain unpublished rescue/proposal RLEs.
    # N0, not the superset archive, is the saved SAM3 observation contract.
    keys=[x['mask'] for x in assignment['variants']['N0']]
    return {int(k[2:]):coco.decode(dict(size=assignment['masks'][k]['size'],counts=assignment['masks'][k]['counts'].encode('ascii'))).astype(bool) for k in keys}

@lru_cache(maxsize=None)
def file_binding(path):return artifact(path)

def feature_observations(masks,scores,presence,frame,global_frame,now,depth):
    occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros((360,640),'u2'))
    neighbors={n:[] for n in masks};keys=sorted(masks)
    for i,n in enumerate(keys):
        dilated=cv2.dilate(masks[n].astype('u1'),KERNEL).astype(bool)
        for other in keys[i+1:]:
            if np.any(dilated&masks[other]):neighbors[n].append(other);neighbors[other].append(n)
    observations=[];profiles=[];encoded={}
    for n in keys:
        mask=masks[n];y,x=np.where(mask);assert len(x)
        bbox=[float(x.min()),float(y.min()),float(x.max()+1),float(y.max()+1)]
        whole=stats(depth,mask);exclusive,core=exclusive_core(mask,occupancy);cs=stats(depth,core)
        token=f'n:{n}'
        observations.append(dict(id=n,mask=token,box=bbox,area=int(mask.sum()),score_birth=scores[n],
            presence=presence[n],depth={k:whole[k] for k in ('n','valid_fraction','median','mad')},neighbors=neighbors[n]))
        profiles.append(dict(id=n,mask=token,area=int(mask.sum()),box=bbox,neighbors=neighbors[n],
            score_birth=scores[n],presence=presence[n],whole=whole,core=cs,
            overlap_pixels=int((mask&(occupancy>1)).sum()),exclusive_area=int(exclusive.sum()),core_area=int(core.sum())))
        rle=coco.encode(np.asfortranarray(mask.astype('u1')))
        encoded[token]=dict(size=list(rle['size']),counts=rle['counts'].decode('ascii'))
    native=[dict(id=n,mask=f'n:{n}') for n in keys]
    common=dict(frame=frame,global_frame=global_frame,time=now)
    return (dict(common,observations=observations,native=native),
            dict(common,evidence_max_global_frame=global_frame,observations=profiles),
            dict(frame=frame,global_frame_id=global_frame,time=now,masks=encoded,variants={'N0':native}))

def polygon_masks(shapes):
    masks={};scores={}
    for s in shapes:
        assert s['shape_type']=='polygon'
        n=int(s['group_id']);region=masks.setdefault(n,np.zeros((360,640),'u1'))
        points=np.rint((np.asarray(s['points'],float)+.5)/3-.5).astype('i4')
        cv2.fillPoly(region,[points],1);scores[n]=max(scores.get(n,0.),float(s.get('score') or 0.))
    return {n:m.astype(bool) for n,m in masks.items()},scores

class RawDepth:
    def __init__(self,segment):
        self.segment=segment;self.files={};self.previous_frame=None
        if segment.startswith('feeding_'):
            self.kind='FEEDING';self.metadata={r['frame']:r for r in rows(DATA/'manifest.jsonl')}
        elif segment.startswith('fishsa_'):
            self.kind='FISHSA';self.base=WORK/'data/AlignedDataset_v1'
            self.metadata={r['source_color_index']+1:r for r in rows(self.base/'manifest.jsonl')}
        else:
            self.kind='CAMERA';self.base=WORK/'data/AnnotationNewBags_20260919'/segment
            self.metadata={r['frame']:r for r in read(self.base/'manifest.json')['frames']}
            self.geo=Geometry(read(self.base/'calibration.json'),640,360)
            self.geo.kc[0,2]+=(640/self.geo.color['width']-1)/2
            self.geo.kc[1,2]+=(360/self.geo.color['height']-1)/2

    def __call__(self,global_frame,now):
        g=int(global_frame);assert g==global_frame
        # The caller may read the same current frame twice, never an older/future requested row.
        assert self.previous_frame is None or g>=self.previous_frame
        self.previous_frame=g
        if self.kind=='FEEDING':
            row=self.metadata[g];assert abs(row['rgb_timestamp_us']/1e6-now)<1e-6
            path=DATA/row['depth_aligned'];native_path=DATA/'depth_native_mm'/f'{g:06d}.npy'
            with np.load(path,allow_pickle=False) as f:
                depth=f['depth_mm'];index=f['source_index'];FIELD_READS.append(dict(segment=self.segment,frame=g,fields=['depth_mm','source_index']))
            native=np.load(native_path,allow_pickle=False)
            binding=dict(raw_npz=file_binding(path),native_npy=file_binding(native_path),actual_fields_read=['depth_mm','source_index'],
                native_fields_read=['current_native_depth_mm'],delta_us=row['delta_us'],sensor_available=True)
        elif self.kind=='FISHSA':
            row=self.metadata.get(g)
            if row is None:
                assert g==1 # Source RGB index0 is the original unpaired first frame.
                depth=np.zeros((360,640),'f4');index=np.full((360,640),-1,'i4');native=np.zeros((576,640),'f4')
                binding=dict(sensor_available=False,missing_reason='ORIGINAL_UNPAIRED_FIRST_RGB',actual_fields_read=[])
            else:
                assert row['source_color_index']+1==g and abs(row['color_timestamp_us']/1e6-now)<1e-6
                path=self.base/row['h5'];position=row['h5_row']
                if path not in self.files:self.files[path]=h5py.File(path,'r')
                f=self.files[path]
                assert int(f['frame_id'][position])==row['frame_id']
                depth=f['aligned/raw_depth_mm'][position];index=f['aligned/raw_source_index'][position]
                native=f['native/original_depth_mm'][position]
                fields=['frame_id','aligned/raw_depth_mm','aligned/raw_source_index','native/original_depth_mm']
                FIELD_READS.append(dict(segment=self.segment,frame=g,h5_row=position,fields=fields))
                binding=dict(raw_h5=file_binding(path),h5_row=position,aligned_frame_id=row['frame_id'],
                    source_color_index=row['source_color_index'],source_depth_index=row['source_depth_index'],
                    actual_fields_read=fields,delta_us=row['delta_us'],sensor_available=True)
        else:
            row=self.metadata[g];assert abs(row['rgb_timestamp_us']/1e6-now)<1e-6
            path=Path(row['depth_source'])
            native=np.load(path,allow_pickle=False)
            if row['depth_usable']:
                values=native.ravel();source=np.flatnonzero(np.isfinite(values)&(values>0))
                xyz=self.geo.rc.reshape(-1,3)[source]*values[source,None]+self.geo.t
                depth,index=rasterize(self.geo.project_xyz(xyz),xyz[:,2],source,360,640)
            else:
                depth=np.zeros((360,640),'f4');index=np.full((360,640),-1,'i4')
            binding=dict(native_npy=file_binding(path),actual_fields_read=['current_native_depth_mm'],
                delta_us=row['delta_us'],sensor_available=bool(row['depth_usable']),
                missing_reason=None if row['depth_usable'] else 'TIMESTAMP_MISMATCH_OVER_5_MS',
                calibration=file_binding(self.base/'calibration.json'),projection='FROZEN_GEOMETRY_NEAREST_Z_NATIVE_INDEX_TIE')
        assert depth.shape==index.shape==(360,640) and native.shape==(576,640)
        valid=np.isfinite(depth)&(depth>0)
        assert np.array_equal(valid,index>=0) and np.all(index[valid]<native.size)
        assert np.all(np.isfinite(native.ravel()[index[valid]])&(native.ravel()[index[valid]]>0))
        binding.update(global_frame=g,time=now,aligned_depth=array_binding(depth),aligned_source_index=array_binding(index),
            native_depth=array_binding(native),aligned_coordinates='RECORDED_RGB_CAMERA_Z_MM',
            native_coordinates='RECORDED_NATIVE_SENSOR_Z_MM',RGB_read=False,GT_read=False,restored_read=False,
            sensor_valid_range='UNKNOWN',physical_accuracy_mm='UNKNOWN')
        return depth,index,native,binding

    def close(self):
        for f in self.files.values():f.close()
        self.files.clear()

def original_sources(segment):
    if segment.startswith('feeding_'):
        owner=FEED if SEGMENTS[segment][0]<701 else DS2
        p=owner/'private'/segment
        return dict(observations=p/'observations.jsonl.gz',profiles=p/'profiles.jsonl.gz',assignments=p/'assignments.jsonl.gz',
            raw_measurements=ROOT/'experiments/ds10_depth_failure_repair/run'/segment/'public/DEPTH_OBSERVATIONS.jsonl.gz')
    if segment.startswith('fishsa_'):
        split='development' if 'development' in segment else 'validation'
        assignment=(WORK/'tools/sam3_occlusion_identity_20260915/i3_evidence_20260915_complete/identity_cpu10_20260915/run_8400/assignments.jsonl.gz'
                    if split=='development' else WORK/'tools/sam3_depth_birth_quality_20260918/visual_comparison/native_validation_assignments.jsonl.gz')
        return dict(observations=WORK/f'tools/sam3_depth_failure_repair_20260917/diagnosis_evidence/diagnosis/observations_{split}.jsonl.gz',
            profiles=WORK/f'tools/sam3_depth_birth_inherit_20260917/completion_evidence/features_r2/features_{split}.jsonl.gz',assignments=assignment)
    return dict(manifest=WORK/'data/AnnotationNewBags_20260919'/segment/'manifest.json',
                calibration=WORK/'data/AnnotationNewBags_20260919'/segment/'calibration.json')
