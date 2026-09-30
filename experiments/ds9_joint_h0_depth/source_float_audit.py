"""Postseal source comparison only; no scoring, decisions, replay or labels."""
from collections import Counter
import math
import struct
from common import HERE, SEGMENTS, read, rows, sha, write_new

TOLERANCE_PX=1e-6
ALLOWED_FIELDS={'dt_max_px','threshold_px'}


def permitted(path,new,old):
    return (len(path)==6 and path[0] in ('adaptive_raw','restored')
        and path[2:4]==['roi_geometry','pieces'] and type(path[4]) is int
        and path[-1] in ALLOWED_FIELDS and type(new) is float and type(old) is float
        and math.isfinite(new) and math.isfinite(old) and abs(new-old)<=TOLERANCE_PX)


def float32_info(new,old):
    values=[struct.unpack('<f',struct.pack('<f',x))[0] for x in (new,old)]
    bits=[struct.unpack('<I',struct.pack('<f',x))[0] for x in (new,old)]
    return dict(both_exact_float32=values==[new,old],float32_ulp_distance=abs(bits[0]-bits[1]))


def audit():
    oldrun=HERE.parent/'ds8_adaptive_depth_core/run';newrun=HERE/'run'
    oldall=read(oldrun/'ALL_PREDICTIONS_SEALED.json');newall=read(newrun/'ALL_PREDICTIONS_SEALED.json')
    assert oldall['frames']==newall['frames']==1471
    assert oldall['status']=='ALL_FIVE_BRANCHES_FOUR_SEGMENTS_SEALED'
    assert newall['status']=='ALL_SIX_BRANCHES_FOUR_SEGMENTS_SEALED'
    assert set(oldall['seals'])==set(newall['seals'])==set(SEGMENTS)
    differences=[];material=[];fields=Counter();leaf_counts=Counter();segments=[];total_frames=total_objects=0
    for name,(start,stop) in SEGMENTS.items():
        paths=[];seals=[]
        for run,manifest in ((oldrun,oldall),(newrun,newall)):
            public=run/name/'public';sealpath=public/'PREDICTIONS_SEALED.json'
            assert sha(sealpath)==manifest['seals'][name]
            seal=read(sealpath)
            assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
            assert seal['segment']==name and seal['frames']==seal['published_frames']==stop-start+1
            path=public/'DEPTH_OBSERVATIONS.jsonl.gz'
            assert sha(path)==seal['artifacts_sha256']['DEPTH_OBSERVATIONS.jsonl.gz']
            paths.append(path);seals.append(sha(sealpath))
        segment_diff_start=len(differences);objects=0;frames=0
        def walk(new,old,path,frame):
            if type(new)!=type(old):kind='TYPE'
            elif isinstance(new,dict):
                if set(new)!=set(old):kind='KEYS'
                else:
                    for key in new:walk(new[key],old[key],path+[key],frame)
                    return
            elif isinstance(new,list):
                if len(new)!=len(old):kind='LENGTH'
                else:
                    for index,(a,b) in enumerate(zip(new,old,strict=True)):walk(a,b,path+[index],frame)
                    return
            else:
                leaf_counts[path[0] if path else '<root>']+=1
                if new==old:return
                kind='VALUE'
            allowed=permitted(path,new,old)
            item=dict(segment=name,local_frame=frame,original_frame=start+frame-1,
                path='/'+'/'.join(map(str,path)),path_tokens=path,new=new,old=old,kind=kind,
                allowed_metadata_difference=allowed)
            if type(new) in (int,float) and type(old) in (int,float):item['absolute_difference']=abs(new-old)
            if allowed:item.update(float32_info(new,old))
            differences.append(item)
            fields['/'.join('*' if type(k) is int or (type(k) is str and k.isdigit()) else k for k in path)]+=1
            if not allowed:material.append(item)
        for index,(old,new) in enumerate(zip(rows(paths[0]),rows(paths[1]),strict=True),1):
            assert old['frame']==new['frame']==index and old['global_frame']==new['global_frame']==start+index-1
            frames+=1;objects+=len(new['objects']);walk(new,old,[],index)
        assert frames==stop-start+1
        total_frames+=frames;total_objects+=objects
        segments.append(dict(segment=name,frames=frames,source_objects=objects,
            differences=len(differences)-segment_diff_start,old_seal_sha256=seals[0],new_seal_sha256=seals[1],
            old_observation_sha256=sha(paths[0]),new_observation_sha256=sha(paths[1])))
    assert total_frames==1471
    result=dict(status='PASS_METADATA_ONLY_FLOAT32_DT_DIFFERENCES' if not material else 'FAIL_MATERIAL_SOURCE_DIFFERENCE',
        frames=total_frames,source_objects=total_objects,segments=segments,difference_count=len(differences),
        difference_fields=dict(fields),material_difference_count=len(material),differences=differences,
        max_absolute_metadata_difference_px=max((x['absolute_difference'] for x in differences if x['allowed_metadata_difference']),default=0.),
        all_changed_metadata_values_exact_float32=all(x.get('both_exact_float32',False) for x in differences),
        max_float32_ulp_distance=max((x.get('float32_ulp_distance',0) for x in differences),default=0),
        allowed_comparison_boundary=dict(fields=sorted(ALLOWED_FIELDS),path='/{adaptive_raw|restored}/{source}/roi_geometry/pieces/{index}/{field}',
            absolute_tolerance_px=TOLERANCE_PX,scope='DT metadata only; no tolerance on measurement facts or any other field'),
        all_other_typed_values_and_structure_exact=not material,examined_scalar_leaves_by_top_field=dict(leaf_counts),
        actual_measurement_facts_exact=not material,
        exact_scope='all n, median, MAD, effective/inferred MAD, cohort, usable/qualification, source/fact identity, provenance, background, threshold, component samples, ROI area and all remaining serialized fields',
        limitations=['The differing metadata are float32 representations; the exact runtime cause is not established.',
            'ROI bitmaps and individual distance fields are not serialized; this comparison certifies serialized ROI counts and measurement facts, not a direct bitwise ROI bitmap comparison.',
            'No physical depth or pixel-surface ground truth is introduced.'],
        old_all_seal_sha256=sha(oldrun/'ALL_PREDICTIONS_SEALED.json'),new_all_seal_sha256=sha(newrun/'ALL_PREDICTIONS_SEALED.json'),
        audit_code_sha256=sha(__file__),decision_or_frozen_code_modified=False,gt_reads=0,new_model_http=0)
    write_new(HERE/'SOURCE_FLOAT_AUDIT.json',result)
    assert not material,'Material source difference: stop scoring'
    print(result['status'],total_frames,total_objects,len(differences),result['max_absolute_metadata_difference_px'])
    return result


if __name__=='__main__':audit()
