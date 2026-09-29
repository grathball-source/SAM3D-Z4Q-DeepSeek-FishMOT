"""Three-frame geometry sheets from sealed predictions; GT is postseal text."""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / 'experiments/b0_same_source_regression_repair'
CASES = [('SOURCE_OLD', 'feeding_000000_000199', 159, 26),
         ('SOURCE_BASELINE', 'feeding_000351_000555', 372, 28)]


def records(path):
    return {r['original_frame']: r for r in map(json.loads, Path(path).read_text(encoding='utf8').splitlines())}


def sheet(source, segment, frame, native):
    parent = OLD / 'public' / source / segment
    geometry = records(parent / 'B0_ACTION_LEDGER.jsonl')
    onefix = records(parent / 'onefix/ACTION_LEDGER.jsonl')
    pairwise = records(HERE / 'public' / source / segment / 'ACTION_LEDGER.jsonl')
    matches = records(HERE / 'public' / source / 'GT_MATCHED_LEDGER.jsonl')
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="2070" height="565" viewBox="0 0 2070 565">',
             '<rect width="2070" height="565" fill="#111827"/>',
             f'<text x="20" y="34" fill="white" font-size="23" font-family="sans-serif">{source} F{frame} native {native}: before / decision / after</text>',
             '<text x="20" y="57" fill="#9ca3af" font-size="14">Prediction boxes only; no RGB, mask pixels, or GT raster. GT labels were added after all predictions were sealed.</text>']
    for i, f in enumerate((frame-1, frame, frame+1)):
        x0, y0 = 20+690*i, 84
        row, px, fix = geometry[f], pairwise[f], onefix[f]
        parts.append(f'<rect x="{x0}" y="{y0}" width="640" height="360" fill="#1f2937" stroke="#6b7280"/>')
        for obs in row['decision_inputs']:
            x1,y1,x2,y2 = obs['box']
            focus = obs['native_id'] == native
            parts.append(f'<rect x="{x0+x1:.1f}" y="{y0+y1:.1f}" width="{x2-x1:.1f}" height="{y2-y1:.1f}" fill="none" stroke="{("#fb7185" if focus else "#6b7280")}" stroke-width="{3 if focus else 1}" opacity="{1 if focus else .45}"/>')
        b0, px_id, fx = (v.get(str(native), 'absent') for v in (row['published_public'], px['published_public'], fix['published_public']))
        label = f'F{f}  N={native}  B0={b0}  ONEFIX={fx}  PAIRWISE={px_id}'
        parts.append(f'<text x="{x0}" y="{y0+387}" fill="white" font-size="15" font-family="monospace">{html.escape(label)}</text>')
        gt = [m['gt_id'] for m in matches[f]['matches'] if m['native_id'] == native]
        parts.append(f'<text x="{x0}" y="{y0+411}" fill="#9ca3af" font-size="14">Postseal matched GT: {html.escape(str(gt) if gt else "UNKNOWN")}</text>')
        edges = [c for c in px['edge_veto_checks'] if c['native_id'] == native]
        status = ', '.join(f"{c['origin_rule']}→{c['public_id']}: {c['reason']}" for c in edges) or 'no candidate edge'
        parts.append(f'<text x="{x0}" y="{y0+434}" fill="#fbbf24" font-size="12">{html.escape(status[:90])}</text>')
    parts += ['<text x="20" y="548" fill="#9ca3af" font-size="14">Pink = selected native; gray = other prediction boxes. All branches first-publish their own current-frame IDs.</text>', '</svg>']
    return '\n'.join(parts)


def main():
    out = HERE / 'public/cases'
    out.mkdir(exist_ok=True)
    inventory = []
    for source, segment, frame, native in CASES:
        path = out / f'{source}_F{frame}_native{native}.svg'
        assert not path.exists()
        path.write_text(sheet(source, segment, frame, native), encoding='utf8')
        inventory.append(dict(path=str(path.resolve()), bytes=path.stat().st_size))
    (out / 'INVENTORY.json').write_text(json.dumps(inventory, indent=2)+'\n', encoding='utf8')


if __name__ == '__main__':
    main()
