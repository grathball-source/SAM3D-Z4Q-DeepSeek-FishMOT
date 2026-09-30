"""Append readable QA figures without changing sealed prediction/results."""
import json
from pathlib import Path

import analyze

HERE=Path(__file__).resolve().parent


def main():
    run=HERE/'run'
    original=json.loads((run/'VISUALIZATION_INVENTORY.json').read_text(encoding='utf-8'))
    selected=json.loads((run/'SELECTION.json').read_text(encoding='utf-8'))['first_complete_event']
    name=selected['segment']
    segment=analyze.load_segment(name)
    event=next(x for x in segment['events']['D2_DYNAMIC'] if x['id']==selected['event'])
    out=[]
    for i,record in enumerate(original['private']):
        current=segment if record['segment']==name else analyze.load_segment(record['segment'])
        target=Path(record['path']).with_name(Path(record['path']).stem+'_qa.png')
        assert not target.exists()
        roles=['PRE A; measured independent fragment','PRE B; measured independent fragment',
               'GROUP_VISIBLE_SURFACE only','S0 post unassigned → chosen before first publish'] if i==0 else None
        title=('First complete automatic event MS1-F59: pre / group / q\n'
               'q415 first public n:70→70, n:30→30; no future input') if i==0 else (
               'Maximum candidate-independent core/whole conflict\n'
               'F415 n:62: core12198.4mm, n9, fraction0.18; unusable')
        out.append(analyze.raster_figure(record['segment'],record['local_frames'],record['selected_sources'],
            current,target,title,roles))
    numeric=HERE/'private_visualizations/first_complete_numeric_qa.png'
    assert not numeric.exists()
    analyze.event_plot(name,event,segment,numeric)
    out.append(dict(path=str(numeric),bytes=numeric.stat().st_size,sha256=analyze.score.digest(numeric),
                    data='numeric measurement/forecast plot; matches public SVG'))
    analyze.score.write_new(run/'VISUAL_QA_RECORD.json',dict(status='GENERATED_FOR_ACTUAL_LOCAL_INSPECTION',
        artifacts=out,formal_prediction_seals=json.loads((run/'METRICS.json').read_text(encoding='utf-8'))['seal_sha256'],
        source='raw depth_mm and unchanged saved predicted masks; no GT raster or RGB'))


if __name__=='__main__':
    main()
