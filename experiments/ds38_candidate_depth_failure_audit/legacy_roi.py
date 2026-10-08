"""Exact original profile ROI populations, separately sealed posthoc diagnostics."""
from common import *
import inspect, numpy as np
from audit import distribution_compare
from collections import defaultdict,Counter

def main():
    verified_freeze()
    save('LEGACY_ROI_SUPPLEMENT_FREEZE.json',dict(created_utc=utc(),posthoc=True,labels_already_exposed=True,
        files=[artifact(__file__),artifact(HERE/'LEGACY_ROI_SUPPLEMENT_PLAN.md'),
               artifact(inspect.getsourcefile(SOURCE.exclusive_core)),artifact(HERE/'FEATURES_SEALED.json')],
        source_selection='SAME_235_SEALED_FRAMES_ALL_6289_MASKS',new_tracker=False))
    requested=defaultdict(set)
    for f in rows(HERE/'MEASUREMENTS.jsonl.gz'): requested[f['segment']].add(f['frame'])
    populations={};counts=Counter();private=[];records={}
    with gzip.open(HERE/'LEGACY_ROI_FACTS.jsonl.gz','xt',encoding='utf-8') as output:
        for name in SEGMENTS:
            frames=requested[name];source=input_dir(name)
            assignments={r['frame']:r for r in rows(source/'assignments.jsonl.gz') if r['frame'] in frames}
            profiles={r['frame']:r for r in rows(source/'profiles.jsonl.gz') if r['frame'] in frames}
            measured={r['frame']:r for r in rows(source/'DEPTH_OBSERVATIONS.jsonl.gz') if r['frame'] in frames}
            sensor=SOURCE.RawDepth(name)
            try:
                for frame in sorted(frames):
                    row=measured[frame];depth,index,native,binding=sensor(row['global_frame'],row['time'])
                    assert binding==row['raw_source_binding'];masks=SOURCE.native_masks(assignments[frame])
                    saved={o['id']:o for o in profiles[frame]['observations']};arrays={}
                    occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros(depth.shape,'u2'))
                    for n,mask in sorted(masks.items()):
                        exclusive,core=SOURCE.exclusive_core(mask,occupancy)
                        valid=MEASUREMENT.validate_source(depth,index,native,masks,name,frame,row['global_frame'],row['time'],binding,binding)
                        others=np.zeros(mask.shape,bool)
                        for other,m in masks.items():
                            if other!=n: others|=m
                        other_sources=np.unique(index[others&valid]);views={};pops={}
                        for role,roi in (('whole',mask),('core',core)):
                            stats=SOURCE.stats(depth,roi);assert stats==saved[n][role],(name,frame,n,role,stats,saved[n][role])
                            original=depth[roi&np.isfinite(depth)&(depth>0)].astype('f8')
                            pos,ex=MEASUREMENT._selected(roi,valid,index,other_sources)
                            independent=depth.ravel()[pos].astype('f8');summary=M.summary(independent,int(roi.sum()))
                            views[role]=dict(original_profile=stats,profile_columns_exact=True,
                                original_population_sha256=MEASUREMENT.array_binding(original),
                                original_population_is_pixel_weighted_not_independent=True,
                                independent_summary=summary,independent_exclusions=ex,
                                independent_population_binding=MEASUREMENT._binding(pos,index,depth),
                                roi_binding=MEASUREMENT.array_binding(roi))
                            for mode,value in (('pixels',original),('independent',independent)):
                                pops[f'{role}_{mode}']=value;arrays[f'n{n}_{role}_{mode}']=value
                        k=key(name,frame,n);populations[k]=pops
                        fact=dict(fact_id=k+'/original-profile-roi',segment=name,frame=frame,native=n,views=views,
                            source_binding=binding,profiles_row_sha256=ARCHIVE.row_sha(profiles[frame]),
                            mask_binding=MEASUREMENT.array_binding(mask),GT_used_for_roi=False)
                        records[k]=fact;dump(output,fact);counts['objects']+=1
                    path=HERE/'private'/f'legacy_roi_{name}_F{frame}.npz';np.savez_compressed(path,**arrays);private.append(artifact(path))
                    counts['frames']+=1
            finally:sensor.close()
            print('ORIGINAL_ROI_EXACT',name,dict(counts),flush=True)
    assert counts==dict(objects=6289,frames=235)
    diagnosis=read(HERE/'RESULTS.json');pairs=[];ranking=[]
    for action in diagnosis['actions']:
        a=action['action'];current=key(a['segment'],a['frame'],a['native']);matrix=[]
        for bank in action['bank']:
            if not bank['actual_matrix_column']:continue
            p=bank['distribution'];other=p['reference'] if p else None
            values={mode:distribution_compare(populations[current][mode],populations[other][mode])
                for mode in ('core_pixels','core_independent','whole_pixels','whole_independent')} if other in populations else {}
            pair=dict(action_id=a['action_id'],target=bank['id'],physical=bank['used_depth_reference_physical'],
                selected=bank['selected'],legal=bank['legal_matrix_edge'],current=current,reference=other,comparisons=values)
            pairs.append(pair);matrix.append(pair)
        rank={}
        for mode in ('core_pixels','core_independent','whole_pixels','whole_independent'):
            scores=[(p['comparisons'][mode]['wasserstein_mm'],p['physical']) for p in matrix if p['comparisons'].get(mode,{}).get('wasserstein_mm') is not None]
            if not any(r=='SAME' for _,r in scores): result='NO_CORRECT_COLUMN'
            else:
                minimum=min(d for d,_ in scores);relations=[r for d,r in scores if d==minimum]
                result='CORRECT_MINIMUM' if relations==['SAME'] else 'OTHER_OR_TIED_MINIMUM'
            rank[mode]=result
        selected=next(p for p in matrix if p['selected'])
        ranking.append(dict(action_id=a['action_id'],global_frame=a['global_frame'],physical=action['physical'],
            prefilter_rank=rank,current_original_profiles=records[current]['views'],
            selected_original_profiles=records[selected['reference']]['views'] if selected['reference'] in records else None))
    save('LEGACY_ROI_COMPARISONS.json',dict(pairs=pairs,actions=ranking,summary={p:{mode:dict(Counter(a['prefilter_rank'][mode]
        for a in ranking if a['physical']==p)) for mode in ('core_pixels','core_independent','whole_pixels','whole_independent')}
        for p in ('WRONG','CORRECT','UNSCORABLE')}))
    save('LEGACY_ROI_SUPPLEMENT_SEALED.json',dict(created_utc=utc(),counts=counts,profile_columns_exact=6289,
        freeze=artifact(HERE/'LEGACY_ROI_SUPPLEMENT_FREEZE.json'),files=[artifact(HERE/f) for f in
        ('LEGACY_ROI_FACTS.jsonl.gz','LEGACY_ROI_COMPARISONS.json')],private=private,
        posthoc_diagnostic_not_new_input_or_performance=True,model_http=0,cost_usd=0))
    print('LEGACY_ROI_SUPPLEMENT_SEALED',dict(counts),flush=True)

if __name__=='__main__':main()
