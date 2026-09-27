"""Private RGB contact sheets for actual state commits; never add pixels to Git."""
import gzip
import hashlib
import json
import os
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
RGB = Path(os.environ.get('RGB_ORIGINAL', r'E:/CAU/D-MOT/data/AlignedDataset_v1/rgb_original'))


def sha(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def lines(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        yield from map(json.loads, stream)


def main():
    events = [x for x in json.loads((HERE/'public/EVENTS.json').read_text()) if x['status'] == 'COMMIT']
    wanted = {f for x in events for f in range(x['frame']-2, x['frame']+3)}
    obs = {x['frame']: x for x in lines(Path(r'E:/CAU/D-MOT/tools/sam3_depth_failure_repair_20260917/diagnosis_evidence/diagnosis/observations_validation.jsonl.gz')) if x['frame'] in wanted}
    pred = {x['frame']: x for x in lines(HERE/'public/predictions_validation.jsonl.gz') if x['frame'] in wanted}
    assert wanted == set(obs) == set(pred)
    output = HERE/'private_api/visuals'
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for event in events:
        rows = []
        changed = {int(n) for n in event['changes']}
        source_files = []
        for f in range(event['frame']-2, event['frame']+3):
            r = obs[f]
            source = RGB/f'{r["global_frame"]-1:06d}.jpg'
            image = cv2.imread(str(source))
            assert image is not None and image.shape[:2] == (1080, 1920), source
            image = cv2.resize(image, (640, 360), interpolation=cv2.INTER_AREA)
            source_files.append(dict(path=str(source), bytes=source.stat().st_size, sha256=sha(source)))
            panes = []
            for arm in ('B0', 'B1'):
                pane = image.copy()
                ids = {int(o['mask'].split(':')[1]): o['id'] for o in pred[f]['variants'][arm]}
                for o in r['observations']:
                    n = o['id']
                    if n not in changed:
                        continue
                    x0, y0, x1, y1 = map(int, o['box'])
                    cv2.rectangle(pane, (x0, y0), (x1, y1), (0, 255, 255), 2)
                    cv2.putText(pane, f'ID {ids[n]}', (x0, max(15, y0-4)),
                                cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 255, 255), 2)
                cv2.putText(pane, f'{event["case"]} f{f} {arm}', (8, 22),
                            cv2.FONT_HERSHEY_SIMPLEX, .65, (255, 255, 255), 2)
                panes.append(pane)
            rows.append(cv2.hconcat(panes))
        sheet = cv2.vconcat(rows)
        target = output/f'{event["case"]}_frames_{event["frame"]-2}_{event["frame"]+2}.png'
        assert cv2.imwrite(str(target), sheet)
        records.append(dict(case=event['case'], event_frame=event['frame'],
            display='five consecutive original-RGB frames; left B0, right B1; changed fish boxes and public IDs',
            path=str(target.resolve()), bytes=target.stat().st_size, sha256=sha(target),
            rgb_sources=source_files))
    (HERE/'public/VISUAL_MANIFEST.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print([(x['case'], x['bytes']) for x in records])


if __name__ == '__main__':
    main()
