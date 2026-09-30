"""Append readable-caption rerenders; preserve frozen code and original figures."""
import json
import textwrap
from unittest.mock import patch

from bootstrap import HERE,SEGMENTS,records,write_new,artifact,verify
import report_artifacts as original


def run():
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
    old_title,old_save=Figure.suptitle,Figure.savefig
    def title(figure,text,*args,**kwargs):
        wrapped='\n'.join(textwrap.fill(line,width=125) for line in text.splitlines())
        kwargs['fontsize']=10
        return old_title(figure,wrapped,*args,**kwargs)
    def save(figure,*args,**kwargs):
        kwargs.setdefault('bbox_inches','tight')
        return old_save(figure,*args,**kwargs)
    for item in json.loads((HERE/'SCORING_SEALED.json').read_text())['artifacts']: verify(item)
    rows=[r for name in SEGMENTS for r in records(HERE/f'{name}_occupancy.jsonl.gz')]
    cases,_=original.choose_cases(rows)
    required={(c['row']['segment'],c['row']['frame']) for c in cases}; facts={}; pixels={}
    for name in SEGMENTS:
        for row in records(HERE/f'{name}_measurements.jsonl.gz'):
            if (name,row['frame']) in required: facts[(name,row['frame'])]=row
        for row in records(HERE/'private'/f'{name}_pixels.jsonl.gz'):
            if (name,row['frame']) in required: pixels[(name,row['frame'])]=row
    output=[]
    with patch.object(Figure,'suptitle',title),patch.object(Figure,'savefig',save):
        for case in cases:
            case=dict(case,label=case['label']+'_caption_v2'); key=(case['row']['segment'],case['row']['frame'])
            output.append(original.real_figure(case,facts[key],pixels[key]))
    write_new(HERE/'VISUALIZATION_CAPTION_REPAIR.json',dict(reason='original long legend clipped at figure width',
        intervention='wrap caption and tight layout only; same source/facts/pixels/colors/full depth range',
        code=artifact(HERE/'repair_figure_captions.py'),original_figures=artifact(HERE/'VISUALIZATION_FILES.json'),
        repaired_private_figures=output,originals_preserved=True,scientific_output_modified=False,
        manual_pixels_read=False,inference_http=0,cost_usd=0))
    print('Five captions rerendered; original images and frozen results preserved')


if __name__=='__main__': run()
