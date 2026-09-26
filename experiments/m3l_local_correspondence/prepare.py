"""Freeze the B01 two-frame inputs. This program never opens GT or old responses."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

FRAMES = [1300, 1308, 1315, 1321, 1323, 1331, 1338, 1346, 1353, 1361, 1369, 1376, 1384]
OLD_MEDIA = Path('/home/xiongxiong/m2t_motion_first_20260924/full_run/sender/media')
OLD_LEDGER = Path('/home/xiongxiong/m2t_motion_first_20260924/full_run/private/TOKEN_LEDGER.json')
OLD_SOURCE = Path('/home/xiongxiong/m2t_motion_first_20260924/full_run/public/SOURCE_MANIFEST.json')
OUT = Path('/home/xiongxiong/m3l_local_correspondence_20260926')


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def write(path, obj):
    assert not path.exists(), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(out=OUT):
    source = json.loads(OLD_SOURCE.read_text(encoding='utf-8'))
    case = next(x for x in source['cases'] if x['case_alias'] == 'B01')
    ledger = json.loads(OLD_LEDGER.read_text(encoding='utf-8'))['B01']
    images = case['g_images'][5:18]
    assert len(images) == len(FRAMES) == len(ledger[5:18])
    frames = []
    for i, (image, private, frame) in enumerate(zip(images, ledger[5:18], FRAMES, strict=True), 6):
        assert image['image_id'] == f'G{i:03d}' and private['frame'] == frame
        assert image['sha256'] == private['image_sha256']
        assert image['observation_tokens'] == [x['token'] for x in private['observations']]
        path = OLD_MEDIA / image['media_file']
        assert path.is_file() and sha(path) == image['sha256'] and path.stat().st_size == image['bytes']
        target = out / 'sender/media' / image['media_file']
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists(), target
        shutil.copyfile(path, target)
        assert sha(target) == image['sha256']
        frames.append(dict(image_id=image['image_id'], frame=frame, time=private['source_time'],
                           image_sha256=image['sha256'], media_file=image['media_file'],
                           image_bytes=image['bytes'], width=image['width'], height=image['height'],
                           observations=[{k: obs[k] for k in ('token', 'center_norm', 'bbox_norm')}
                                         for obs in private['observations']]))
    assert frames[0]['frame'] == 1300 and frames[1]['frame'] == 1308
    write(out / 'public/SLICE_AUDIT.json', dict(status='REAL_TWO_FRAME_VERIFIED',
          image_ids=['G006', 'G007'], frames=[1300, 1308],
          images=[dict(sha256=x['image_sha256'], bytes=x['image_bytes']) for x in frames[:2]],
          source_observations=len(frames[0]['observations']), target_observations=len(frames[1]['observations'])))
    requests = []
    for i, (src, dst) in enumerate(zip(frames[:-1], frames[1:], strict=True), 1):
        core = dict(request_id=f'M3L-P{i:02d}', source=dict(image_id=src['image_id'],
                    relative_seconds=round(src['time'] - dst['time'], 3), observations=src['observations']),
                    target=dict(image_id=dst['image_id'], relative_seconds=0, observations=dst['observations']),
                    note='Two actual sampled moments only. Tokens are frame-local, not persistent identities. '
                         'All ROI objects are listed. Do not invent intermediate observations.')
        assert core['source']['relative_seconds'] < 0
        requests.append(dict(pair=f'P{i:02d}', core_text=json.dumps(core, separators=(',', ':')),
                             images=[{k: x[k] for k in ('image_id', 'media_file', 'image_sha256', 'image_bytes')}
                                     for x in (src, dst)]))
    # P01 first, P02 first, P01 repeat, P03 first, P02 repeat, ...
    schedule = []
    for i in range(12):
        schedule.append(f'P{i+1:02d}-FIRST')
        if i:
            schedule.append(f'P{i:02d}-REPEAT')
    schedule.append('P12-REPEAT')
    assert len(schedule) == 24
    plan = dict(model='deepseek-flash', max_tokens=65536, schedule=schedule, requests=requests,
                reserve_each_usd=.11, smoke_max=1, cost_cap_usd=3.0)
    assert (len(schedule) + 1) * plan['reserve_each_usd'] <= plan['cost_cap_usd']
    write(out / 'sender/PLAN.json', plan)
    write(out / 'public/SOURCE_MANIFEST.json', dict(status='FROZEN_PRE_MODEL', review_base='8ec0d3b8bd2e7c75dd2d6b3d15b1b0bb6341e16b',
          old_source_sha256=sha(OLD_SOURCE), old_token_ledger_sha256=sha(OLD_LEDGER),
          frames=frames, old_media_root=str(OLD_MEDIA)))
    write(out / 'public/REQUEST_MANIFEST.json', dict(status='FROZEN_LOGICAL_REQUESTS', schedule=schedule,
          requests=[dict(pair=x['pair'], core_sha256=hashlib.sha256(x['core_text'].encode()).hexdigest(),
                         image_ids=[y['image_id'] for y in x['images']],
                         image_sha256=[y['image_sha256'] for y in x['images']]) for x in requests]))
    write(out / 'public/PREFLIGHT.json', dict(status='PASS', formal_requests=24, smoke_max=1,
          max_inference=25, peak_price_input_per_million=.30, peak_price_output_per_million=1.20,
          reserve_usd=2.75, cap_usd=3.0, no_GT_read=True, no_model_calls=True))
    print(json.dumps(dict(frames=len(frames), pairs=len(requests), attempts=len(schedule), reserve_usd=2.75)))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, default=OUT)
    run(p.parse_args().out)
