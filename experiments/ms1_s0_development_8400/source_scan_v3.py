"""Prediction-only local 2→1 suspects, including persistent small residual masks.

This scanner emits first-suspect opportunities. The live manager still has to
confirm a two-frame group and find the first two-candidate split before any
episode becomes a completed S0 trial. No GT or future frame selects a suspect.
"""
import json
import statistics
from collections import Counter, defaultdict, deque
from pathlib import Path

from mask_geometry import mask, shifted_coverage
from source_scan import ASSIGN, OBS, rows

HERE=Path(__file__).resolve().parent
HISTORY=30
MAX_EPISODE_FRAMES=300
AREA_RATIO=.5
GROUP_RATIO=.95
PAIR_MASS_RATIO=.65
SOFT_SUPPORT=.15
DIRECT_SUPPORT=.15


def scan(observations=OBS, assignments=ASSIGN, output=None):
    areas=defaultdict(lambda:deque(maxlen=HISTORY))
    previous=None
    last_contact={}
    cooldown={}
    counts=Counter()
    suspects=[]
    diagnostics=[]
    for row,assignment in zip(rows(observations),rows(assignments),strict=True):
        frame=row['frame']
        assert assignment['frame']==frame
        assert assignment.get('global_frame_id',frame)==row['global_frame']
        current={x['id']:x for x in row['observations']}
        native={int(key[2:]):value for key,value in assignment['masks'].items()
                if key.startswith('n:')}
        assert set(current)==set(native)
        contenders=defaultdict(list)
        if previous is not None:
            prior,prior_masks,prior_frame=previous
            for donor,x in current.items():
                history=areas[donor]
                if donor not in prior or len(history)<10 or x['area']<64:
                    continue
                reference=max(history)
                if reference<256 or x['area']/reference>=AREA_RATIO:
                    continue
                prior_mask=None
                for group in x.get('neighbors',[]):
                    if (group not in current or group not in prior or
                            current[group]['area']<64 or len(areas[group])<10):
                        continue
                    pair=tuple(sorted((donor,group)))
                    if last_contact.get(pair)!=prior_frame or frame<cooldown.get(pair,0):
                        continue
                    group_reference=statistics.median(areas[group])
                    group_ratio=current[group]['area']/max(1,group_reference)
                    pair_mass=(x['area']+current[group]['area'])/(reference+group_reference)
                    if group_ratio<GROUP_RATIO or pair_mass<PAIR_MASS_RATIO:
                        continue
                    if prior_mask is None:
                        prior_mask=mask(prior_masks[donor])
                    group_mask=mask(native[group])
                    direct=float((prior_mask&group_mask).sum()/max(1,prior_mask.sum()))
                    soft=shifted_coverage(prior_mask,group_mask,0,0,8)
                    if soft<SOFT_SUPPORT:
                        continue
                    # Proximity alone is common in the crowded tank. Accept a
                    # real pixel transfer, or require both tighter proximity
                    # and growth of the proposed surviving group mask.
                    if direct<DIRECT_SUPPORT and not (soft>=.25 and group_ratio>=1.05):
                        counts['proximity_without_transfer_rejected']+=1
                        continue
                    other=mask(prior_masks[group])
                    prior_iou=float((prior_mask&other).sum()/max(1,(prior_mask|other).sum()))
                    if prior_iou>=.25:
                        counts['duplicate_overlap_rejected']+=1
                        continue
                    contenders[donor].append(dict(frame=frame,time=row['time'],sources=list(pair),
                        group=group,donor=donor,coverage={str(donor):round(direct,4),
                            str(group):round(float((other&group_mask).sum()/max(1,other.sum())),4)},
                        soft_support=round(soft,4),donor_area=x['area'],
                        donor_reference_area=reference,group_area=current[group]['area'],
                        group_reference_area=group_reference,group_ratio=round(group_ratio,4),
                        pair_mass_ratio=round(pair_mass,4),prior_mask_iou=prior_iou,
                        previous_count=sum(o['area']>=64 for o in prior.values()),
                        current_count=sum(o['area']>=64 for o in current.values()),
                        selection_route=('DIRECT_MASK_TRANSFER' if direct>=DIRECT_SUPPORT
                                         else 'CONTACT_AREA_COLLAPSE'),
                        third_contact_count=len(x.get('neighbors',[]))))
            for donor,options in contenders.items():
                options.sort(key=lambda x:(x['coverage'][str(donor)]+x['soft_support']+
                                           max(0,x['group_ratio']-1)),reverse=True)
                if len(options)>1 and options[0]['soft_support']-options[1]['soft_support']<.15:
                    counts['ambiguous_multi_group']+=1
                    diagnostics.append(dict(frame=frame,kind='AMBIGUOUS_MULTI_GROUP',donor=donor,
                                            possible_groups=[x['group'] for x in options]))
                    continue
                candidate=options[0]
                pair=tuple(candidate['sources'])
                if frame<cooldown.get(pair,0):
                    continue
                suspects.append(candidate)
                cooldown[pair]=frame+MAX_EPISODE_FRAMES
                counts['suspect_'+candidate['selection_route']]+=1
        for x in current.values():
            areas[x['id']].append(x['area'])
            for group in x.get('neighbors',[]):
                last_contact[tuple(sorted((x['id'],group)))]=frame
        previous=(current,native,frame)
        if frame%1000==0:
            print('FRAME',frame,'suspects',len(suspects),flush=True)
    result=dict(scanner='LOCAL_AREA_AND_MASK_V3',frames=frame,window_frames=HISTORY,
        max_episode_frames=MAX_EPISODE_FRAMES,thresholds=dict(area_ratio=AREA_RATIO,
            group_ratio=GROUP_RATIO,pair_mass_ratio=PAIR_MASS_RATIO,
            soft_support=SOFT_SUPPORT,direct_support=DIRECT_SUPPORT),
        counts=dict(counts),suspects=suspects,diagnostics=diagnostics,
        qualification='SUSPECT_ONLY: requires live two-frame confirmation and first-split q; no GT')
    target=Path(output) if output is not None else HERE/'private_source/scan_v3.json'
    assert not target.exists(),target
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('SUSPECTS',len(suspects),'FRAMES',[x['frame'] for x in suspects])
    return result


if __name__=='__main__':
    scan()
