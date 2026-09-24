"""Post-score actual-G-pixel and mask-geometry check for every decisive citation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def main(run: Path, scored: Path, out: Path):
    assert (run / 'sender/public/RESPONSES_SEALED.json').exists()
    assert (scored / 'SUMMARY.json').exists()
    assert not out.exists()
    plan = json.loads((run / 'sender/PLAN.json').read_text())
    requests = {x['attempt_id']: x for x in plan['requests']}
    results = [json.loads(row) for row in (scored / 'ATTEMPT_RESULTS.jsonl').read_text().splitlines()]
    records = []
    for result in results:
        if result['decoded_relation'] == 'ABSTAIN':
            continue
        req = requests[result['attempt_id']]
        chosen = ('A-X', 'B-Y') if result['decoded_relation'] == 'STRAIGHT' else ('A-Y', 'B-X')
        frames = {row['image_id']: row for row in json.loads(req['core_text'])['scene_frames']}
        images = {row['image_id']: row for row in req['images'] if row['kind'] == 'G'}
        for edge in chosen:
            detail = result['edges'][edge]
            assert detail['status'] == 'VALID' and detail['relation'] == 'SUPPORT'
            for citation in detail['evidence']:
                image = images[citation['image_id']]
                path = run / 'sender/media' / image['media_file']
                raw = path.read_bytes()
                assert hashlib.sha256(raw).hexdigest() == image['sha256']
                pixels = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
                grayscale = bool(np.array_equal(pixels[:, :, 0], pixels[:, :, 1]) and
                                 np.array_equal(pixels[:, :, 1], pixels[:, :, 2]))
                checks = []
                observed = {x['token']: x for x in frames[citation['image_id']]['observations']}
                for token in citation['observation_tokens']:
                    box = observed[token]['bbox_norm']
                    height, width = pixels.shape[:2]
                    x0, y0 = int(box[0] * width), int(box[1] * height)
                    x1, y1 = min(width, int(np.ceil(box[2] * width))), min(height, int(np.ceil(box[3] * height)))
                    region = pixels[y0:y1, x0:x1]
                    nonwhite = int(np.count_nonzero(region[:, :, 0] < 250))
                    checks.append(dict(token=token, bbox_norm=box, nonwhite_pixels=nonwhite,
                                       geometry_visible=bool(nonwhite > 0)))
                records.append(dict(attempt_id=result['attempt_id'], edge=edge,
                                    image_id=citation['image_id'], relative_seconds=citation['relative_seconds'],
                                    source_file_sha256=image['sha256'], source_file_bytes=len(raw),
                                    actual_grayscale=grayscale, token_pixel_checks=checks,
                                    source_and_pixel_valid=bool(grayscale and all(x['geometry_visible'] for x in checks)),
                                    model_observation=citation['observation'],
                                    semantic_claim='UNKNOWN_NOT_ESTABLISHED_BY_SOURCE_CHECK',
                                    reviewer='Codex_Work_post_score_answer_exposed'))
    out.write_text(''.join(json.dumps(x, ensure_ascii=False, allow_nan=False) + '\n' for x in records), encoding='utf-8')
    print(json.dumps(dict(decisive_citations=len(records),
                          source_and_pixel_valid=sum(x['source_and_pixel_valid'] for x in records),
                          distinct_images=len({(x['attempt_id'], x['image_id']) for x in records}))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--scored', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    options = parser.parse_args()
    main(options.run, options.scored, options.out)
