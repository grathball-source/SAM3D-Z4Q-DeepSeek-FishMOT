"""Postseal failure-case figures only; no extraction/score modification."""
import json
import textwrap
from unittest.mock import patch
from bootstrap import HERE,SEGMENTS,records,write_new,artifact,verify
import report_artifacts as original


def run():
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
    for item in json.loads((HERE/'SCORING_SEALED.json').read_text())['artifacts']: verify(item)
    keys={(1821,'o008'),(1044,'o016'),(1385,'o015')}
    rows=[r for n in SEGMENTS for r in records(HERE/f'{n}_occupancy.jsonl.gz') if (r['frame'],r['token']) in keys]
    facts={}; pixels={}; needed={(r['segment'],r['frame']) for r in rows}
    for name in SEGMENTS:
        for row in records(HERE/f'{name}_measurements.jsonl.gz'):
            if (name,row['frame']) in needed: facts[(name,row['frame'])]=row
        for row in records(HERE/'private'/f'{name}_pixels.jsonl.gz'):
            if (name,row['frame']) in needed: pixels[(name,row['frame'])]=row
    old_title,old_save=Figure.suptitle,Figure.savefig
    def title(figure,text,*args,**kwargs):
        kwargs['fontsize']=10
        return old_title(figure,'\n'.join(textwrap.fill(line,125) for line in text.splitlines()),*args,**kwargs)
    def save(figure,*args,**kwargs):
        kwargs['bbox_inches']='tight'
        return old_save(figure,*args,**kwargs)
    output=[]
    with patch.object(Figure,'suptitle',title),patch.object(Figure,'savefig',save):
        for row in rows:
            case=dict(label='postseal_failure',row=row,selection='POSTSEAL_FAILURE_DIAGNOSIS_NO_RULE_CHANGE')
            key=(row['segment'],row['frame'])
            output.append(original.real_figure(case,facts[key],pixels[key]))
    write_new(HERE/'ADDITIONAL_FAILURE_FIGURES.json',dict(private_figures=output,code=artifact(HERE/'render_additional_failures.py'),
        selection_after_seal=True,inference_http=0,scientific_output_modified=False,manual_pixels_read=False))
    print('Three actual postseal failure figures generated')


if __name__=='__main__': run()
