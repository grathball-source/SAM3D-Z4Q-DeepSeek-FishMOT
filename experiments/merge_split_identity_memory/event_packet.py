"""Traceable geometry-only M/S inputs from the live episode state."""
import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw

from mask_geometry import mask
from merge_split_manager import velocity

HERE = Path(__file__).resolve().parent
PROMPTS = (HERE/'MS1_MODEL_PROMPTS.md').read_text(encoding='utf-8').split('```text\n')
SYSTEM, MERGE_TEMPLATE, SPLIT_TEMPLATE = [part.split('\n```',1)[0] for part in PROMPTS[1:4]]
COORDINATES = '原预测mask网格640×360；x向右、y向下，位置/框为像素；time为Unix秒，速度px/s；深度中位数和MAD为原传感器mm。'


def token_map(rows):
    out = {}
    for row in rows:
        ranked = sorted(row['observations'], key=lambda o: ((o['box'][0]+o['box'][2])/2,
                                                               (o['box'][1]+o['box'][3])/2,o['id']))
        for rank,o in enumerate(ranked,1):
            out[(row['frame'],o['id'])] = f"F{row['frame']}:O{rank:02d}"
    return out


def public_sample(item, tokens):
    result = {k:v for k,v in item.items() if k not in ('source','neighbors')}
    result['fact_id'] = tokens[(item['frame'],item['source'])]
    result['contact_count'] = len(item['neighbors'])
    return result


def public_fragment(items, tokens):
    shown = [public_sample(x,tokens) for x in items]
    return dict(observations=shown, motion=velocity(items),
                continuity='same source generation only within this clean segment')


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
                   if stage=='S' else [])
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
                          bindings=[dict(role=role,fact_id=tokens[(frame,source)]) for role,source,_ in shown]))
    return index


def fill(template, fields):
    for key,value in fields.items():
        template=template.replace('{{'+key+'}}',value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,separators=(',',':')))
    assert not re.search(r'\{\{[A-Za-z_]+\}\}',template)
    return template


def packet(episode, stage, tokens, images, m_hypothesis=None):
    assert stage in ('M','S')
    pre={role:public_fragment(episode['pre'][role],tokens) for role in ('A','B')}
    group=[public_sample(x,tokens) for x in episode['group']]
    group_anonymous=[dict(public_sample(x,tokens),status='ANONYMOUS_LOW_QUALITY_OR_EMPTY')
                     for x in episode['group_anonymous']]
    public_images=[{k:v for k,v in x.items() if k!='path'} for x in images]
    common=dict(episode_id=episode['id'],coordinate_contract=COORDINATES,
                pre_A=pre['A'],pre_B=pre['B'],image_index=public_images)
    if stage=='M':
        assert episode['confirm_frame'] is not None
        fields=dict(common,evidence_cutoff=episode['confirm_frame'],
            merge_detection_evidence=dict(first_suspect=episode['suspect_frame'],
                confirm=episode['confirm_frame'],source_mask_coverage=list(episode['source_suspect']['coverage'].values()),
                classification='two independent prediction masks to one compatible measured group mask'),
            group_observations_to_now=dict(group_measured=group,other_anonymous=group_anonymous))
        user=fill(MERGE_TEMPLATE,fields)
    else:
        assert episode['q'] is not None and len(episode['post_roles'])==2
        roles=list(episode['post_roles'])
        post={role:public_fragment(episode['post_roles'][source],tokens)
              for role,source in zip(('X','Y'),roles)}
        from merge_split_manager import numeric_choice
        _, comparison=numeric_choice(episode)
        # Show measured pairwise terms, not the selector's aggregate or preference.
        pairwise=[dict(candidate=x['choice'],edges=x['edges']) for x in comparison.get('scores',[])]
        anonymous_risk=[dict(public_sample(x,tokens),status='ANONYMOUS_RISK_OBSERVATION')
                        for role in ('A','B') for x in episode['pre_risk'][role]]
        anonymous_risk.sort(key=lambda x:(x['frame'],x['fact_id']))
        fields=dict(common,evidence_cutoff=episode['q'],
            group_observations=dict(group_measured=group,other_anonymous=group_anonymous),
            visibility_and_contact_intervals=dict(pre_risk_anonymous=anonymous_risk,
                 group_frames=[x['frame'] for x in group],split_start=episode['post_start'],
                 split_confirmation=episode['split_confirm']),
            third_object_context='No third member was admitted by the fixed local mask graph; distant fish are not identity fingerprints.',
            post_X=post['X'],post_Y=post['Y'],pairwise_motion_and_depth_measurements=pairwise,
            merge_model_hypothesis_or_null=dict(type='MODEL_HYPOTHESIS',text=m_hypothesis[:1000]) if m_hypothesis else None,
            candidate_mappings=dict(H1={'A':'X','B':'Y','U':'unchanged'},
                                    H2={'A':'Y','B':'X','U':'unchanged'}))
        user=fill(SPLIT_TEMPLATE,fields)
    # The public body never contains source/native/public/GT identity numbers.
    for forbidden in ('native_id','public_id','gt_grid','file-api-','DEEPSEEK_API_KEY'):
        assert forbidden not in user
    return dict(system=SYSTEM,user=user,images=public_images)
