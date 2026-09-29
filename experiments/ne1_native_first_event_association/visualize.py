"""Geometry-only sheets from actual first-published identities, no RGB or mask pixels."""
import hashlib
import html
import json
from pathlib import Path

from verify import HERE, FEED, SEGMENTS, gzlines, digest


def color(public):
    palette=('#f97316','#22d3ee','#a3e635','#c084fc','#f472b6','#facc15','#60a5fa')
    h=int(hashlib.sha256(str(public).encode()).hexdigest()[:8],16)
    return palette[h%len(palette)]


def sheet(name,start,arm,event,rows,predictions):
    suspect=event['suspect_frame']
    confirm=event['confirm_frame']
    q=event['q']
    last=q if q is not None else event['end'] or confirm
    frames=[max(1,suspect-1),confirm,last]
    roles=['BEFORE SUSPECT','CONFIRMED GROUP','FIRST SPLIT q' if q is not None else 'NO LEGAL SPLIT']
    focus=set(event['member_sources'] or [])|{event['group_source']}
    focus|={int(n) for n in event['post_first_observations']}
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="2010" height="525" viewBox="0 0 2010 525">',
           '<rect width="2010" height="525" fill="#111827"/>',
           f'<text x="20" y="31" fill="white" font-family="sans-serif" font-size="22">{html.escape(name)} {html.escape(arm)} {html.escape(event["id"])} status {html.escape(event["status"])}</text>',
           '<text x="20" y="55" fill="#9ca3af" font-family="sans-serif" font-size="13">Actual saved prediction boxes and first-published public IDs; schematic only, no RGB/mask pixels or visual physical identity claim.</text>']
    for index,(frame,role) in enumerate(zip(frames,roles)):
        x0=20+665*index
        y0=91
        parts.append(f'<rect x="{x0}" y="{y0}" width="640" height="360" fill="#1f2937" stroke="#6b7280"/>')
        row=rows[frame]
        prediction=predictions[frame]
        mapping={int(obj['mask'][2:]):obj['id'] for obj in prediction['variants'][arm]}
        for obj in row['observations']:
            native=obj['id']
            public=mapping[native]
            x1,y1,x2,y2=obj['box']
            stroke=color(public) if native in focus else '#6b7280'
            opacity='1' if native in focus else '.32'
            parts.append(f'<rect x="{x0+x1:.1f}" y="{y0+y1:.1f}" width="{x2-x1:.1f}" height="{y2-y1:.1f}" fill="none" stroke="{stroke}" stroke-width="{2 if native in focus else 1}" opacity="{opacity}"/>')
            if native in focus:
                parts.append(f'<text x="{x0+x1:.1f}" y="{y0+max(12.,y1-3):.1f}" fill="{stroke}" font-family="monospace" font-size="12">{native}→{public}</text>')
        parts.append(f'<text x="{x0}" y="480" fill="white" font-family="monospace" font-size="15">{html.escape(role)}  F{start+frame-1}  local {frame}</text>')
    parts.append('</svg>')
    return '\n'.join(parts)+'\n'


def main():
    run=HERE/'run'
    assert (run/'METRICS.json').is_file() and (run/'EVENT_AUDIT.json').is_file()
    output=run/'visualizations'
    output.mkdir(exist_ok=False)
    inventory=[]
    for name,(start,stop) in SEGMENTS.items():
        rows={row['frame']:row for row in gzlines(FEED/'private'/name/'observations.jsonl.gz')}
        public=run/name/'public'
        predictions={row['frame']:row for row in gzlines(public/'predictions.jsonl.gz')}
        events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8'))
        for arm in ('EVENT_NUM','EVENT_VLM'):
            for event in events[arm]:
                if event['confirm_frame'] is None:
                    continue
                path=output/f'{name}_{arm}_{event["id"]}.svg'
                path.write_text(sheet(name,start,arm,event,rows,predictions),encoding='utf-8')
                inventory.append(dict(path=str(path.resolve()),bytes=path.stat().st_size,
                                      sha256=digest(path),kind='ACTUAL_PUBLISHED_BOX_GEOMETRY_NOT_RGB'))
    (output/'INVENTORY.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(visualizations=len(inventory))))


if __name__=='__main__':
    main()
