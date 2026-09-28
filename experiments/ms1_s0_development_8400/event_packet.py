"""Traceable geometry-only M/S inputs from the live episode state."""
import hashlib
import json
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw
import numpy as np
from scipy.ndimage import label

from mask_geometry import mask
from merge_split_manager import velocity

HERE = Path(__file__).resolve().parent
PROMPTS = (HERE/'MS1_MODEL_PROMPTS.md').read_text(encoding='utf-8').split('```text\n')
SYSTEM, MERGE_TEMPLATE, SPLIT_TEMPLATE = [part.split('\n```',1)[0] for part in PROMPTS[1:4]]
COORDINATES = ('原预测mask网格640×360；x向右、y向下，位置/框为像素；time为Unix秒，速度px/s；'
               '深度中位数和MAD为未校准管线mm，非距水面深度。无邻居、非零面积、同source只是预测观测属性，'
               '不保证完整鱼体或跨时身份。传感器同步/外部epoch证明未提供。')


def token_map(rows):
    out = {}
    for row in rows:
        ranked = sorted(row['observations'], key=lambda o: ((o['box'][0]+o['box'][2])/2,
                                                               (o['box'][1]+o['box'][3])/2,o['id']))
        for rank,o in enumerate(ranked,1):
            out[(row['frame'],o['id'])] = f"F{row['frame']}:O{rank:02d}"
    return out


def geometry_diagnostic(rle,bbox):
    actual=mask(rle)
    ys,xs=np.nonzero(actual)
    count=int(len(xs))
    labeled,components=label(actual,np.ones((3,3),dtype=np.uint8))
    sizes=np.bincount(labeled[actual]) if count else np.array([])
    centroid=[float(xs.mean()),float(ys.mean())] if count else None
    box_center=[(bbox[0]+bbox[2])/2,(bbox[1]+bbox[3])/2]
    return dict(mask_pixels=count,connected_components_8=int(components),
        largest_component_fraction=float(sizes.max()/count) if count else None,
        mask_centroid_px=centroid,bbox_center_px=box_center,
        centroid_bbox_center_offset_px=(math.dist(centroid,box_center) if centroid else None))


def depth_quality(d):
    if not isinstance(d,dict):
        return dict(status='UNKNOWN',n=0,valid_fraction=None,mad=None,
                    mixture_status='UNKNOWN_FROM_AGGREGATES')
    n=d.get('n') or 0
    fraction=d.get('valid_fraction')
    mad=d.get('mad')
    usable=(n>=16 and isinstance(fraction,(int,float)) and fraction>=.2 and
            isinstance(mad,(int,float)) and math.isfinite(mad) and mad>=0 and
            isinstance(d.get('median'),(int,float)) and math.isfinite(d['median']) and d['median']>0 and
            max(15.,1.4826*mad)<=60.)
    return dict(status='SAMPLE_RULE_PASS_NOT_IDENTITY_CERT' if usable else 'INSUFFICIENT_OR_INVALID',
                n=n,valid_fraction=fraction,mad=mad,
                mixture_status='UNKNOWN_FROM_AGGREGATES',rule='Z4Q_CORE_MIN16_FRACTION0.2_RISK60')


def public_sample(item, tokens, assignments):
    result = {k:v for k,v in item.items() if k not in ('source','neighbors','public_id')}
    result['fact_id'] = tokens[(item['frame'],item['source'])]
    result['contact_count'] = len(item['neighbors'])
    result['mask_diagnostic']=geometry_diagnostic(
        assignments[item['frame']]['masks'][f'n:{item["source"]}'],item['bbox'])
    result['depth_quality']={key:depth_quality(item.get(key)) for key in ('depth','core','whole')}
    return result


def public_fragment(items, tokens, assignments):
    shown = [public_sample(x,tokens,assignments) for x in items]
    return dict(observations=shown, motion=velocity(items),
                continuity='source-and-public-version-contiguous prediction observations; identity not independently certified')


def select_frames(values, limit):
    frames = sorted(set(values))
    if len(frames) <= limit:
        return frames
    return [frames[round(i*(len(frames)-1)/(limit-1))] for i in range(limit)]


def render_images(episode, stage, assignments, tokens, output):
    """Draw true prediction masks in one fixed tank coordinate system."""
    pre_frames = select_frames([x['frame'] for role in ('A','B') for x in episode['pre'][role]],3)
    group_frames = select_frames([x['frame'] for x in episode['group']],6)
    post_frames = (select_frames([x['frame'] for xs in episode['post_roles'].values() for x in xs],3)
                   if stage=='S0' else [])
    chosen = [(f,'PRE') for f in pre_frames]+[(f,'GROUP') for f in group_frames]+[(f,'POST') for f in post_frames]
    assert len(chosen)<=12
    output.mkdir(parents=True,exist_ok=True)
    index=[]
    roles = {'A':episode['member_sources'][0],'B':episode['member_sources'][1]}
    for frame,phase in chosen:
        assignment=assignments[frame]
        assert frame <= (episode['confirm_frame'] if stage=='M' else episode['q'])
        image=Image.new('RGB',(640,360),'#101820')
        labels=[]
        shown=[]
        if phase=='PRE':
            for role,source in roles.items():
                if any(x['frame']==frame and x['source']==source for x in episode['pre'][role]):
                    shown.append((role,source, '#1671b9' if role=='A' else '#e98c25'))
        elif phase=='GROUP':
            item=next(x for x in episode['group'] if x['frame']==frame)
            shown.append(('GROUP',item['source'],'#9254bd'))
        else:
            for role,source in zip(('X','Y'),episode['post_roles']):
                shown.append((role,source,'#24a878' if role=='X' else '#39b4d0'))
        centers=[]
        for role,source,_ in shown:
            series=(episode['pre'].get(role,[]) if phase=='PRE' else episode['group'] if phase=='GROUP'
                    else episode['post_roles'][source])
            point=next((x['center'] for x in series if x['frame']==frame and x['source']==source),None)
            if point:
                centers.append(point)
        member_sources={source for _,source,_ in shown}
        context=[]
        for key,rle in assignment['masks'].items():
            if not key.startswith('n:'):
                continue
            source=int(key.split(':')[1])
            if source in member_sources or (frame,source) not in tokens:
                continue
            actual=mask(rle)
            ys,xs=np.nonzero(actual)
            if not len(xs):
                continue
            centroid=[float(xs.mean()),float(ys.mean())]
            residual=any(x['frame']==frame and x['source']==source for x in episode['group_anonymous'])
            if residual or any(math.dist(centroid,c)<=120 for c in centers):
                image.paste('#68737b',mask=Image.fromarray((actual*255).astype('uint8')))
                context.append(dict(fact_id=tokens[(frame,source)],mask_pixels=int(len(xs)),
                                    mask_centroid_px=centroid,role='ANONYMOUS_CONTEXT'))
                labels.append((min(515,centroid[0]+6),max(22,centroid[1]-13),
                               f'ANON {tokens[(frame,source)]}'))
        for role,source,color in shown:
            key=f'n:{source}'
            if key not in assignment['masks']:
                continue
            image.paste(color,mask=Image.fromarray((mask(assignment['masks'][key])*255).astype('uint8')))
            sample=next((x for seq in ([episode['pre'].get(role,[])] if phase=='PRE' else
                                          [episode['group']] if phase=='GROUP' else
                                          [episode['post_roles'][source]])
                         for x in seq if x['frame']==frame and x['source']==source),None)
            if sample:
                cx,cy=sample['center']
                labels.append((min(515,cx+6),max(22,cy-13),f'{role} {tokens[(frame,source)]}'))
        draw=ImageDraw.Draw(image)
        for x,y,label in labels:
            draw.rectangle((x-2,y-1,x+len(label)*7+2,y+12),fill='#101820')
            draw.text((x,y),label,fill='white')
        draw.text((8,6),f'{phase} F{frame} 640x360 measured masks',fill='white')
        path=output/f'{episode["id"]}_{stage}_{phase}_{frame}.png'
        image.save(path)
        raw=path.read_bytes()
        index.append(dict(frame=frame,phase=phase,path=str(path),bytes=len(raw),
                          sha256=hashlib.sha256(raw).hexdigest(),
                          bindings=[dict(role=role,fact_id=tokens[(frame,source)]) for role,source,_ in shown]+
                                   [dict(role='ANONYMOUS_CONTEXT',fact_id=x['fact_id']) for x in context],
                          anonymous_context=context))
    return index


def fill(template, fields):
    for key,value in fields.items():
        template=template.replace('{{'+key+'}}',value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,separators=(',',':')))
    assert not re.search(r'\{\{[A-Za-z_]+\}\}',template)
    return template


def project_merge(raw):
    """Pass ordinary JSON intact; bound only oversized fields, never raw-prefix truncation."""
    if not isinstance(raw,str):
        return None
    try:
        value=json.loads(raw)
    except (ValueError,TypeError):
        return None
    if not isinstance(value,dict):
        return None
    keys=('merge_assessment','possible_continuations','watch_for_after_split','uncertainty')
    if len(raw)<=12000:
        return dict(type='MODEL_HYPOTHESIS',fields=value,projection='FULL_PARSED_JSON')
    def clip(value,limit=4000):
        if isinstance(value,str):
            return value if len(value)<=limit else value[:limit]+f' [FIELD_TRUNCATED_AFTER_{limit}_CHARS]'
        if isinstance(value,list):
            return [clip(x,800) for x in value[:8]]+(['[LIST_TRUNCATED_AFTER_8_ITEMS]'] if len(value)>8 else [])
        return value if value is None or isinstance(value,(int,float,bool)) else str(value)[:limit]
    return dict(type='MODEL_HYPOTHESIS',fields={key:clip(value.get(key)) for key in keys},
                projection='FOUR_FIXED_FIELDS_TOP_STRING4000_LIST8_ITEM800; UNCERTAINTY_RETAINED')


def packet(episode, stage, tokens, images, assignments, m_hypothesis=None):
    assert stage in ('M','S0')
    pre={role:public_fragment(episode['pre'][role],tokens,assignments) for role in ('A','B')}
    group=[public_sample(x,tokens,assignments) for x in episode['group']]
    group_anonymous=[dict(public_sample(x,tokens,assignments),status='ANONYMOUS_LOW_QUALITY_OR_EMPTY')
                     for x in episode['group_anonymous']]
    anonymous_risk=[dict(public_sample(x,tokens,assignments),status='ANONYMOUS_RISK_OBSERVATION')
                    for role in ('A','B') for x in episode['pre_risk'][role]]
    anonymous_risk.sort(key=lambda x:(x['frame'],x['fact_id']))
    public_images=[{k:v for k,v in x.items() if k!='path'} for x in images]
    common=dict(episode_id=episode['id'],coordinate_contract=COORDINATES,
                pre_A=pre['A'],pre_B=pre['B'],image_index=public_images)
    if stage=='M':
        assert episode['confirm_frame'] is not None
        fields=dict(common,evidence_cutoff=episode['confirm_frame'],
            merge_detection_evidence=dict(first_suspect=episode['suspect_frame'],
                confirm=episode['confirm_frame'],source_mask_coverage=list(episode['source_suspect']['coverage'].values()),
                classification='two independent prediction masks to one compatible measured group mask',
                raw_mask_policy='small residual masks remain in raw set; group is not an individual'),
            group_observations_to_now=dict(pre_risk_anonymous=anonymous_risk,
                group_measured=group,other_anonymous=group_anonymous,
                image_local_anonymous_context=[dict(frame=x['frame'],facts=x['anonymous_context']) for x in public_images]))
        user=fill(MERGE_TEMPLATE,fields)
    else:
        assert episode['q'] == episode['split_first_frame'] == episode['evidence_cutoff_frame']
        assert len(episode['post_roles'])==2
        assert all(len(xs)==1 and xs[0]['frame']==episode['q'] for xs in episode['post_roles'].values())
        assert all(x['frame']<=episode['q'] for x in episode['group'])
        roles=list(episode['post_roles'])
        post={role:public_fragment(episode['post_roles'][source],tokens,assignments)
              for role,source in zip(('X','Y'),roles)}
        from merge_split_manager import numeric_choice
        _, comparison=numeric_choice(episode)
        # Show measured pairwise terms, not the selector's aggregate or preference.
        pairwise=[dict(candidate=x['choice'],edges=x['edges']) for x in comparison.get('scores',[])]
        fields=dict(common,evidence_cutoff=episode['q'],
            group_observations=dict(group_measured=group,other_anonymous=group_anonymous),
            visibility_and_contact_intervals=dict(pre_risk_anonymous=anonymous_risk,
                 group_frames=[x['frame'] for x in group],
                 split_first_frame=episode['q'],post_sample_count=1),
            third_object_context=dict(statement='Fixed local graph selected a two-member opportunity; third involvement remains unverified.',
                image_local_anonymous_context=[dict(frame=x['frame'],facts=x['anonymous_context']) for x in public_images]),
            post_X=post['X'],post_Y=post['Y'],pairwise_motion_and_depth_measurements=pairwise,
            merge_model_hypothesis_or_null=project_merge(m_hypothesis),
            candidate_mappings=dict(H1={'A':'X','B':'Y','U':'unchanged'},
                                    H2={'A':'Y','B':'X','U':'unchanged'}))
        user=fill(SPLIT_TEMPLATE,fields)
        user += ('\n现在是本事件第一次出现两个分离候选的当前帧。请利用完整的合并前历史、合并过程和当前两个观测，'
                 '联合选择H1/H2/DEFER。当前X/Y各只有一个观测，重现后速度UNKNOWN；不要编造后续方向，'
                 '也不要仅因post速度未知就忽略实际存在的pre运动。两条历史轨迹到当前的位置预测是带误差的估计，'
                 '不是实测身份链。不能从群组中心的变化推出两条成员都作了同样运动。禁止使用当前帧之后的信息。'
                 '只有choice必填，reason/evidence_refs可选，额外无关字段忽略。\n')
    # The public body never contains source/native/public/GT identity numbers.
    for forbidden in ('native_id','public_id','gt_grid','file-api-','DEEPSEEK_API_KEY'):
        assert forbidden not in user
    return dict(system=SYSTEM,user=user,images=public_images)
