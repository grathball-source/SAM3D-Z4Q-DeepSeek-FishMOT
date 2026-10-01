"""Source-only exhaustive birth-frame geometry audit; no depth or outcomes.

The name keeps this nondecision audit outside research-code freezes. It may
run before prediction: only SOURCE_OLD observation and assignment files enter.
"""
from __future__ import annotations
import ast
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
observed_paths=set()


def source_guard(event,args):
    if event=='socket.connect':raise RuntimeError('No network in geometry review')
    if event!='open' or not isinstance(args[0],(str,bytes,Path)):return
    path=str(args[0]).replace('\\','/').lower()
    blocked=('/depth_rgb_640x360/','/depth_native_mm/','/full_v2/','/rgb_640x360/',
        '/rgb_original/','/labels_','/restoration/v3/','/run/','/slice/')
    if any(token in path for token in blocked):raise RuntimeError('Forbidden geometry audit input: '+path)
    if path.endswith(('.npz','.npy','.h5','.png','.jpg','.jpeg')):raise RuntimeError('No image/depth array files: '+path)
    if '/private/' in path:observed_paths.add(str(Path(args[0]).resolve()))


sys.addaudithook(source_guard)


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)
    return loaded


def main():
    producer=HERE/'contact_measurement.py'
    tree=ast.parse(producer.read_text(encoding='utf-8'))
    assert any(isinstance(node,ast.FunctionDef) and node.name=='adaptive_core' for node in tree.body), 'Wait for local exact integer-distance core producer'
    from common import SEGMENTS,input_dir,rows,artifact,write_new
    import cv2
    import numpy as np
    from scipy.ndimage import distance_transform_edt
    import scipy
    from depth_measurement import decode
    cv2.setNumThreads(1)
    current=module('ds12_independent_current_geometry',producer)
    old_path=ROOT/'experiments/ds10_depth_failure_repair/adaptive_core.py'
    legacy=module('ds12_independent_legacy_geometry',old_path)
    assert current.adaptive_core.__module__=='ds12_independent_current_geometry'
    summary=Counter();segments={};records=[];sources=[]
    for segment,(start,stop) in SEGMENTS.items():
        base=input_dir(segment);observation_path=base/'observations.jsonl.gz';assignment_path=base/'assignments.jsonl.gz'
        sources.extend([artifact(observation_path),artifact(assignment_path)])
        seen=set();selected={};local=Counter()
        for row in rows(observation_path):
            frame=row['frame'];assert row['global_frame']==start+frame-1
            ids={o['id'] for o in row['observations']}
            assert ids=={int(x['mask'][2:]) for x in row['native']}
            born=ids-seen;seen.update(ids);local['all_source_frames']+=1
            if frame==1:local['initial_native_sources']+=len(born)
            elif born:
                selected[frame]=dict(global_frame=row['global_frame'],born=sorted(born),ids=ids)
                local['first_ever_noninitial_birth_frames']+=1;local['first_ever_noninitial_birth_sources']+=len(born)
        assert local['all_source_frames']==stop-start+1
        for assignment in rows(assignment_path):
            frame=assignment['frame']
            if frame not in selected:continue
            item=selected[frame]
            masks={int(k[2:]):decode(rle) for k,rle in assignment['masks'].items()}
            assert set(masks)==item['ids']
            occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros((360,640),'u2'))
            for native,mask in masks.items():
                old_roi,old_meta=legacy.adaptive_core(mask,occupancy)
                exact_roi,exact_meta=current.adaptive_core(mask,occupancy)
                assert old_roi.shape==exact_roi.shape==(360,640)
                exclusive=mask&(occupancy==1)
                count,labels,stats,_=cv2.connectedComponentsWithStats(exclusive.astype('u1'),connectivity=8)
                assert old_meta['component_count']==exact_meta['component_count']==count-1
                assert old_meta['exclusive_area']==exact_meta['exclusive_area']==int(exclusive.sum())
                difference=old_roi^exact_roi;changed=int(difference.sum())
                local['actual_current_masks_at_birth_frames']+=1;local['changed_masks']+=bool(changed)
                local['different_selected_pixels']+=changed
                local['removed_old_selected_pixels']+=int((old_roi&~exact_roi).sum())
                local['added_exact_selected_pixels']+=int((exact_roi&~old_roi).sum())
                components=[];math_roi=np.zeros(mask.shape,bool)
                for label in range(1,count):
                    x,y,w,h,area=map(int,stats[label]);part=labels[y:y+h,x:x+w]==label
                    padded=np.pad(part,1)
                    closest=distance_transform_edt(padded,return_distances=False,return_indices=True)
                    yy,xx=np.indices(padded.shape,dtype='i8')
                    square=((yy-closest[0])**2+(xx-closest[1])**2)[1:-1,1:-1]
                    maximum=int(square[part].max())
                    if maximum<=9:
                        rule='D2>=2.25; MAX_D2<=9';included=square>=2.25;boundary=np.zeros(part.shape,bool)
                    elif maximum>=36:
                        rule='D2>=9; MAX_D2>=36';included=square>=9;boundary=part&(square==9)
                    else:
                        rule='4*D2>=MAX_D2; 9<MAX_D2<36';included=4*square>=maximum;boundary=part&(4*square==maximum)
                    math_selected=part&included
                    math_roi[y:y+h,x:x+w]|=math_selected
                    delta=difference[y:y+h,x:x+w]&part
                    f32=cv2.distanceTransform(padded.astype('u1'),cv2.DIST_L2,cv2.DIST_MASK_PRECISE)[1:-1,1:-1]
                    float_max=float(f32[part].max());float_threshold=max(1.5,min(3.,.5*float_max))
                    boundary_count=int(boundary.sum());piece_changed=int(delta.sum())
                    local['exclusive_components']+=1;local['changed_components']+=bool(piece_changed)
                    local['true_formula_equality_boundary_pixels']+=boundary_count
                    local['changed_true_equality_boundary_pixels']+=int((delta&boundary).sum())
                    local['changed_nonboundary_pixels']+=int((delta&~boundary).sum())
                    local['float_metadata_max_different_components']+=old_meta['pieces'][label-1]['dt_max_px']!=exact_meta['pieces'][label-1]['dt_max_px']
                    components.append(dict(component_id=label,exclusive_area=area,max_squared_distance_px2=maximum,
                        exact_max_distance_px=float(np.sqrt(maximum)),legacy_float32_max_distance_px=old_meta['pieces'][label-1]['dt_max_px'],
                        legacy_threshold_px=old_meta['pieces'][label-1]['threshold_px'],exact_threshold_px=exact_meta['pieces'][label-1]['threshold_px'],
                        integer_rule=rule,true_formula_equality_boundary_pixels=boundary_count,
                        float32_equality_pixels=int((part&(f32==float_threshold)).sum()),different_selected_pixels=piece_changed,
                        changed_true_equality_boundary_pixels=int((delta&boundary).sum()),changed_nonboundary_pixels=int((delta&~boundary).sum()),
                        old_selected_pixels=int((old_roi[y:y+h,x:x+w]&part).sum()),
                        exact_selected_pixels=int((exact_roi[y:y+h,x:x+w]&part).sum())))
                assert np.array_equal(exact_roi,math_roi),'Current producer is not exact original formula'
                records.append(dict(segment=segment,frame=frame,global_frame=item['global_frame'],native=native,
                    first_ever_born_source=native in item['born'],mask_area=int(mask.sum()),shared_mask_pixels=int((mask&(occupancy>1)).sum()),
                    original_roi_pixels=int(old_roi.sum()),exact_roi_pixels=int(exact_roi.sum()),different_selected_pixels=changed,
                    original_roi_sha256=hashlib.sha256(old_roi.tobytes()).hexdigest(),
                    exact_roi_sha256=hashlib.sha256(exact_roi.tobytes()).hexdigest(),
                    difference_sha256=hashlib.sha256(difference.tobytes()).hexdigest(),components=components))
        segments[segment]=dict(local);summary.update(local)
        print(segment,json.dumps(dict(local)),flush=True)
    assert summary['all_source_frames']==1471 and summary['first_ever_noninitial_birth_sources']==105
    result=dict(status='PASS_EXACT_INTEGER_EDT_ORIGINAL_FORMULA_VALIDATION_WITH_EXHAUSTIVE_BIRTH_FRAME_COMPARISON',
        producer=artifact(producer),legacy_geometry_code=artifact(old_path),audit_code=artifact(Path(__file__)),
        input_sources=sources,actual_private_data_read_paths=sorted(observed_paths),summary=dict(summary),segments=segments,masks=records,
        implementation='SciPy nearest zero pixel indices; int64 coordinate differences squared; zero-padded component crop; fixed original formula as integer inequalities',
        claim='Mathematically equivalent to the original real-valued EDT formula. Finite SOURCE_OLD birth-frame comparison is reported exactly; no claim of legacy floating metadata byte equivalence or all-frame legacy ROI equivalence.',
        pixel_difference_scope='All actual masks on every noninitial true first-ever birth frame in these four segments; not all1471 frame masks.',
        equality_note='Changed equality pixels, if present, are original-formula boundary points affected by floating implementation; no new radius/depth/identity threshold.',
        environment=dict(opencv=cv2.__version__,numpy=np.__version__,scipy=scipy.__version__,opencv_threads=cv2.getNumThreads()),
        depth_reads=0,GT_reads=0,RGB_reads=0,branch_result_reads=0,model_calls=0,network_calls=0)
    destination=HERE/'NUMERICAL_CORE_REVIEW.json';write_new(destination,result)
    print(json.dumps(dict(output=artifact(destination),summary=dict(summary)),ensure_ascii=False))


if __name__=='__main__':
    assert not sys.argv[1:]
    main()
