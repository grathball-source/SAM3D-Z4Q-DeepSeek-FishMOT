"""Geometry-only case sheets from sealed action logs; never render private pixels."""
import html
import json
from pathlib import Path

from source import HERE, save, sha


CASES = (
    ('SOURCE_OLD', 'feeding_000000_000199', 159, 26, 'D1 maps mature native 26 to old public 16'),
    ('SOURCE_OLD', 'feeding_000000_000199', 190, 30, 'D1 maps mature native 30 to old public 8'),
    ('SOURCE_BASELINE', 'feeding_000351_000555', 372, 28, 'One-fix vetoes a physically same-GT reconnect'),
    ('SOURCE_BASELINE', 'feeding_000351_000555', 409, 30, 'Short birth reconnection remains in one-fix'),
)


def lines(path):
    return {row['original_frame']: row for row in map(json.loads, path.read_text(encoding='utf-8').splitlines())}


def svg_case(source, segment, frame, native, title, match):
    root = HERE / 'public' / source / segment
    frozen = lines(root / 'B0_ACTION_LEDGER.jsonl')
    fixed = lines(root / 'onefix/ACTION_LEDGER.jsonl')
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="2070" height="560" viewBox="0 0 2070 560">',
             '<rect width="2070" height="560" fill="#111827"/>',
             f'<text x="20" y="34" fill="#f9fafb" font-size="24" font-family="sans-serif">{html.escape(title)}</text>',
             f'<text x="20" y="59" fill="#9ca3af" font-size="15" font-family="sans-serif">{source} · original F{frame} · native {native} · prediction boxes only, no RGB or masks</text>']
    for i, f in enumerate((frame-1, frame, frame+1)):
        x0, y0 = 20+690*i, 85
        row = frozen[f]
        one = fixed[f]
        parts.append(f'<rect x="{x0}" y="{y0}" width="640" height="360" fill="#1f2937" stroke="#6b7280"/>')
        for obs in row['decision_inputs']:
            n = obs['native_id']
            x1,y1,x2,y2 = obs['box']
            if n == native:
                stroke, width, opacity = '#fb7185', 3, 1
            else:
                stroke, width, opacity = '#6b7280', 1, .45
            parts.append(f'<rect x="{x0+x1:.1f}" y="{y0+y1:.1f}" width="{x2-x1:.1f}" height="{y2-y1:.1f}" fill="none" stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"/>')
        b0 = row['published_public'].get(str(native), 'absent')
        onefix = one['published_public'].get(str(native), 'absent')
        gt = match.get(f, [])
        label = f'F{f}  mask n:{native}: N={native if b0 != "absent" else "absent"}  B0={b0}  FIX={onefix}'
        parts.append(f'<text x="{x0}" y="{y0+385}" fill="#f9fafb" font-size="16" font-family="monospace">{html.escape(label)}</text>')
        parts.append(f'<text x="{x0}" y="{y0+407}" fill="#9ca3af" font-size="14" font-family="sans-serif">Postseal GT match: {html.escape(str(gt) if gt else "UNKNOWN")}</text>')
        b0_actions = [f"reconnect→{event['canonical_id']}" for event in row['trace']['events']
                      if event.get('native_id') == native and event.get('kind') == 'reconnect'
                      and event.get('accepted')]
        fixed_guard = any(item['native_id'] == native for item in one['guard'])
        fixed_actions = [f"reconnect→{event['canonical_id']}" for event in one['events']
                         if event.get('native_id') == native and event.get('kind') == 'reconnect'
                         and event.get('accepted')]
        action = f"B0: {','.join(b0_actions) or 'none'} · FIX: {'guard' if fixed_guard else ','.join(fixed_actions) or 'none'}"
        parts.append(f'<text x="{x0}" y="{y0+429}" fill="#fbbf24" font-size="14" font-family="sans-serif">{html.escape(action)}</text>')
    parts.append('<text x="20" y="545" fill="#9ca3af" font-size="14" font-family="sans-serif">Gray outlines: all prediction boxes · pink: affected native · boxes come from the frozen source, GT IDs are postseal annotations.</text>')
    parts.append('</svg>')
    return '\n'.join(parts)


def main():
    target = HERE / 'public/cases'
    target.mkdir(exist_ok=True)
    inventory = []
    for source, segment, frame, native, title in CASES:
        ledger = lines(HERE / 'public' / source / 'GT_MATCHED_LEDGER.jsonl')
        # GT_MATCHED_LEDGER uses original frame numbers, so keys are already global.
        match = {f: [entry['gt_id'] for entry in row['matches']['NATIVE'] if entry['native_id'] == native]
                 for f, row in ledger.items() if frame-1 <= f <= frame+1}
        output = target / f'{source}_{frame}_native{native}.svg'
        assert not output.exists()
        output.write_bytes(svg_case(source, segment, frame, native, title, match).encode('utf-8'))
        inventory.append(dict(path=str(output), bytes=output.stat().st_size, sha256=sha(output),
                              source=source, original_frame=frame, native_id=native))
    save(HERE / 'public/CASE_VISUALIZATIONS.json', dict(status='POSTSEAL_GEOMETRY_ONLY', cases=inventory,
        no_private_pixels=True, gt_ids_postseal_only=True, model_http=0))
    print(json.dumps(inventory, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
