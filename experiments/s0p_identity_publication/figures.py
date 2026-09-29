"""Geometry-only SVGs from actual first-published prediction rows; no pixels/GT."""
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'experiments/ms1_s0_development_8400'
sys.path.insert(0,str(OLD))
sys.path.insert(0,str(ROOT/'online/closed_loop_2888/z4q_source'))
from bridge import read,rows,sha  # noqa: E402
from source_scan import center  # noqa: E402
from replay_p import OBS,SCAN,OUT,write_new  # noqa: E402

PRIOR=OLD/'run_development_v7_recovery/public'
FIG=HERE/'figures'


def get_rows(path,frames):
    return {x['frame']:x for x in rows(path) if x['frame'] in frames}


def render(name,frames,event_id,source,new,old,scan,events):
    event=next(x for x in events if x['id']==event_id)
    suspect=next(x for x in scan['suspects'] if x['frame']==event['suspect_frame'])
    members=set(suspect['sources'])
    roles={x['frame']:x for x in event['publication_policy']}
    all_centers=[center(o) for f in frames for o in source[f]['observations']]
    lo_x=min(x for x,y in all_centers)-20
    hi_x=max(x for x,y in all_centers)+20
    lo_y=min(y for x,y in all_centers)-20
    hi_y=max(y for x,y in all_centers)+20
    panel_w,panel_h=315,260
    margin=22
    width=90+len(frames)*(panel_w+14)
    height=115+3*(panel_h+10)
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="#f8fafc"/>',
           f'<text x="22" y="29" font-size="20" font-family="sans-serif" font-weight="bold">{escape(name)} — actual published IDs</text>',
           '<text x="22" y="49" font-size="12" font-family="sans-serif">Dots are source bbox centers, not image pixels. Internal roles are evidence labels; pub IDs are output.</text>']
    payload=[]
    for col,f in enumerate(frames):
        ro=roles.get(f)
        if f<event['suspect_frame']:
            phase='pre'
        elif f==event['q']:
            phase='first split q'
        elif f>event['end']:
            phase='post'
        elif event['confirm_frame'] and f>=event['confirm_frame']:
            phase='group'
        else:
            phase='suspect / group'
        internal=(f"group n:{ro['internal_group_token']}; residual " +
                  ','.join(f'n:{n}' for n in ro['internal_anonymous_sources']) if ro else
                  'none (before / after event protection)')
        if f==event['q']:
            internal=f"S0 X/Y unassigned until decision; {event['status']}"
        x0=76+col*(panel_w+14)
        parts.append(f'<text x="{x0}" y="70" font-size="14" font-family="sans-serif" font-weight="bold">F{f} {escape(phase)}</text>')
        parts.append(f'<text x="{x0}" y="88" font-size="10" font-family="sans-serif">internal: {escape(internal)}</text>')
        labels={}
        for arm in ('B0','OLD-HOLD','HOLD-P'):
            objects=(new[f]['variants']['B0'] if arm=='B0' else
                     old[f]['variants']['B-HOLD-S0'] if arm=='OLD-HOLD' else
                     new[f]['variants']['HOLD-P'])
            labels[arm]={x['mask']:x['id'] for x in objects}
        payload.append(dict(frame=f,phase=phase,internal=internal,
            observed=[dict(native=o['id'],bbox_center_px=list(center(o)),
                           mask=f"n:{o['id']}") for o in source[f]['observations']],
            first_published=labels))
        for row_index,arm in enumerate(('B0','OLD-HOLD','HOLD-P')):
            y0=104+row_index*(panel_h+10)
            parts.append(f'<text x="12" y="{y0+20}" font-size="13" font-family="sans-serif" font-weight="bold">{arm}</text>')
            parts.append(f'<rect x="{x0}" y="{y0}" width="{panel_w}" height="{panel_h}" rx="8" fill="#fff" stroke="#cbd5e1"/>')
            for o in source[f]['observations']:
                n=o['id']; cx,cy=center(o)
                px=x0+margin+(cx-lo_x)/(hi_x-lo_x)*(panel_w-2*margin)
                py=y0+margin+(cy-lo_y)/(hi_y-lo_y)*(panel_h-2*margin)
                public=labels[arm][f'n:{n}']
                fill='#e11d48' if n in members else '#64748b'
                parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="6" fill="{fill}"/>')
                parts.append(f'<text x="{px+8:.1f}" y="{py-7:.1f}" font-size="11" font-family="sans-serif" fill="#0f172a">n:{n} → {public}</text>')
    parts.append('</svg>')
    path=FIG/f'{name}.svg'
    path.write_text('\n'.join(parts)+'\n',encoding='utf-8')
    return dict(name=name,event=event_id,frames=frames,svg=str(path),svg_sha256=sha(path),
                panels=payload,raw_pixels_included=False,gt_used=False)


def main():
    assert sha(OUT/'predictions_development.jsonl.gz')==read(OUT/'PREDICTIONS_SEALED.json')['predictions_sha256']
    assert sha(PRIOR/'predictions_development.jsonl.gz')==read(PRIOR/'PREDICTIONS_SEALED.json')['predictions_sha256']
    all_frames={2144,2145,2146,1151,1153,1274,1275}
    source=get_rows(OBS,all_frames)
    new=get_rows(OUT/'predictions_development.jsonl.gz',all_frames)
    old=get_rows(PRIOR/'predictions_development.jsonl.gz',all_frames)
    assert set(source)==set(new)==set(old)==all_frames
    FIG.mkdir(exist_ok=False)
    scan=read(SCAN)
    events=read(OUT/'EVENTS.json')['events']
    figures=[render('F2145_cancelled',[2144,2145,2146],'MS1-F2145',source,new,old,scan,events),
             render('F1152_first_confirmed',[1151,1153,1274,1275],'MS1-F1152',source,new,old,scan,events)]
    write_new(OUT/'VISUALIZATION_DATA.json',dict(status='ACTUAL_PUBLISHED_GEOMETRY_ONLY',
        prediction_sha256=sha(OUT/'predictions_development.jsonl.gz'),
        old_prediction_sha256=sha(PRIOR/'predictions_development.jsonl.gz'),figures=figures))
    print('FIGURES',len(figures))


if __name__=='__main__':
    main()
