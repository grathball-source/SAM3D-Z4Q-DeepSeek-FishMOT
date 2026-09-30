"""Postseal QA typography only; preserve original frozen render and images."""
import json
import textwrap
from unittest.mock import patch
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import report
from audit import HERE,DS4,SEGMENTS,records,artifact,verify,write_new


def run():
    seal=json.loads((HERE/'REPORT_SEALED.json').read_text(encoding='utf-8'))
    for item in seal['artifacts']: verify(item)
    cases=[c for c in json.loads((HERE/'COHORT.json').read_text(encoding='utf-8'))['cases'] if 'SEALED_KNOWN_CASE' in c['reasons']]
    frames={c['frame'] for c in cases}; facts={}; pixels={}
    for name in SEGMENTS:
        for r in records(DS4/f'{name}_measurements.jsonl.gz'):
            if r['frame'] in frames: facts[r['frame']]=r
        for r in records(DS4/'private'/f'{name}_pixels.jsonl.gz'):
            if r['frame'] in frames: pixels[r['frame']]=r
    title=Axes.set_title; save=Figure.savefig
    def wrapped(ax,label,*a,**kw):
        text='\n'.join(textwrap.fill(line,35) for line in label.splitlines())
        return title(ax,text,*a,**kw)
    def bounded(fig,*a,**kw):
        kw['bbox_inches']='tight'; return save(fig,*a,**kw)
    with patch.object(Axes,'set_title',wrapped),patch.object(Figure,'savefig',bounded),patch.object(report,'HERE',HERE/'private/caption_v2'):
        figures=[report.figure(c,facts[c['frame']],pixels[c['frame']]) for c in cases]
    write_new(HERE/'VISUALIZATION_CAPTION_REPAIR.json',dict(reason='Original left panel titles clip at canvas boundary',
        original_report_seal=artifact(HERE/'REPORT_SEALED.json'),new_figures=figures,
        changed='Title wrapping and tight save bounds only',original_figures_preserved=True,measurement_changed=False))


if __name__=='__main__': run()
