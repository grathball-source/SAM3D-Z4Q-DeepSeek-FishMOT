"""Quantify the reported ID 1/7 interaction from sealed prediction sources."""
import json
from pathlib import Path

from mask_geometry import mask
from source_scan import ASSIGN, OBS, rows

HERE=Path(__file__).resolve().parent
FRAMES={5926,5927,5932,5933,5939}


def main():
    observed={r['frame']:r for r in rows(OBS) if r['frame'] in FRAMES}
    assigned={r['frame']:r for r in rows(ASSIGN) if r['frame'] in FRAMES}
    assert set(observed)==set(assigned)==FRAMES
    timeline=[]
    for frame in sorted(FRAMES):
        obs={x['id']:x for x in observed[frame]['observations']}
        area={str(n):obs[n]['area'] for n in (1,7)}
        pixel={str(n):int(mask(assigned[frame]['masks'][f'n:{n}']).sum()) for n in (1,7)}
        assert area==pixel
        timeline.append(dict(frame=frame,source_area_px=area,
                             source_neighbor_ids={str(n):obs[n].get('neighbors',[]) for n in (1,7)}))
    carrier=mask(assigned[5933]['masks']['n:1'])
    transferred={str(n):round(float((mask(assigned[5932]['masks'][f'n:{n}'])&carrier).sum()/
                                     max(1,mask(assigned[5932]['masks'][f'n:{n}']).sum())),6)
                 for n in (1,7)}
    report=dict(status='PREDICTION_MASK_GEOMETRY_ONLY',timeline=timeline,
                fraction_of_f5932_masks_inside_f5933_source_1=transferred,
                scanner_suspect=5927,merge_confirm=5928,first_two_full_candidates=5939,
                note='source IDs and mask geometry are observations; physical identity and correctness require separate postseal scoring')
    output=HERE/'dry_run_v6/public/F5927_GEOMETRY_AUDIT.json'
    with output.open('x',encoding='utf-8') as handle:
        json.dump(report,handle,ensure_ascii=False,indent=2)
        handle.write('\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    main()
