"""Geometry-only three-frame decision sheets from sealed public traces."""
import html
import json
from pathlib import Path

from run import HERE, OLD, save, sha


def records(path):
    return {r['original_frame']: r for r in map(json.loads, Path(path).read_text(encoding='utf8').splitlines())}


def sheet(source, segment, frame, native, target):
    parent = OLD/'public'/source/segment
    geometry = records(parent/'B0_ACTION_LEDGER.jsonl')
    oldpx = records(HERE.parent/'z4q_pairwise_reconnect_repair/public'/source/segment/'ACTION_LEDGER.jsonl')
    pxa = records(HERE/'public'/source/segment/'ACTION_LEDGER.jsonl')
    selected = next((c for c in pxa[frame]['edge_veto_checks']
                     if (c['native_id'], c['public_id']) == (native, target)), None)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="2070" height="665" viewBox="0 0 2070 665">',
             '<rect width="2070" height="665" fill="#111827"/>',
             f'<text x="20" y="33" fill="white" font-size="23" font-family="sans-serif">{html.escape(source)} F{frame}: native {native} to historical public {target}</text>',
             '<text x="20" y="57" fill="#9ca3af" font-size="14">Geometry schematic from actual prediction boxes, not RGB or mask pixels; no visual identity claim.</text>']
    for i, f in enumerate((frame-1, frame, frame+1)):
        x0, y0 = 20+690*i, 82
        row, old, new = geometry[f], oldpx[f], pxa[f]
        parts.append(f'<rect x="{x0}" y="{y0}" width="640" height="360" fill="#1f2937" stroke="#6b7280"/>')
        for obs in row['decision_inputs']:
            x1, y1, x2, y2 = obs['box']
            focus = obs['native_id'] == native
            parts.append(f'<rect x="{x0+x1:.1f}" y="{y0+y1:.1f}" width="{x2-x1:.1f}" height="{y2-y1:.1f}" fill="none" stroke="{("#fb7185" if focus else "#6b7280")}" stroke-width="{3 if focus else 1}" opacity="{1 if focus else .45}"/>')
        native_key = str(native)
        label = (f'F{f}  N={native}  B0={row["published_public"].get(native_key,"absent")}'
                 f'  PX={old["published_public"].get(native_key,"absent")}'
                 f'  PX-A={new["published_public"].get(native_key,"absent")}')
        parts.append(f'<text x="{x0}" y="{y0+387}" fill="white" font-size="15" font-family="monospace">{html.escape(label)}</text>')
        edges = [c for c in new['edge_veto_checks'] if c['native_id'] == native]
        status = ', '.join(f'{c["origin_rule"]} to {c["public_id"]}: {c["reason"]}' for c in edges) or 'no candidate edge'
        parts.append(f'<text x="{x0}" y="{y0+414}" fill="#fbbf24" font-size="12">{html.escape(status[:94])}</text>')
    if selected:
        info = [f'At F{frame}, source live version: {selected["source_version"] or "UNKNOWN"}',
                f'Target anchor key: {selected["anchor_key"]}; version: {selected["target_version"] or "UNKNOWN"}',
                f'Pair evidence: {selected["pair_status"]}; observed frames {selected["evidence_frames"]}; time {selected.get("evidence_time","UNKNOWN")}',
                f'Lookup: {selected["target_lookup"]}; veto: {selected["veto"]}; actual public: {pxa[frame]["published_public"].get(str(native),"absent")}']
    else:
        info = [f'No checked edge for native {native} to public {target} at F{frame}']
    for i, message in enumerate(info):
        parts.append(f'<text x="20" y="{540+i*26}" fill="#d1d5db" font-size="13" font-family="monospace">{html.escape(message)}</text>')
    parts.append('</svg>')
    return '\n'.join(parts)


def main():
    audit = json.loads((HERE/'public/SOURCE_AUDIT.json').read_text(encoding='utf8'))
    gain = audit['first_lookup_gain']
    cases = [('SOURCE_OLD', 'feeding_000000_000199', 159, 26, 16)]
    if gain:
        cases.append((gain['source'], gain['segment'], gain['original_frame'],
                      gain['native_id'], gain['public_id']))
    out = HERE/'public/cases'
    out.mkdir(exist_ok=True)
    inventory = []
    for source, segment, frame, native, target in cases:
        path = out/f'{source}_F{frame}_native{native}_target{target}.svg'
        assert not path.exists()
        path.write_text(sheet(source, segment, frame, native, target), encoding='utf8')
        inventory.append(dict(path=str(path.resolve()), bytes=path.stat().st_size,
                              sha256=sha(path), kind='GEOMETRY_SCHEMATIC_NOT_RGB'))
    save(out/'INVENTORY.json', inventory)


if __name__ == '__main__':
    main()
