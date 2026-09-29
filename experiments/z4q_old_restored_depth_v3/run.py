"""OLD saved SAM3, restored v3 depth only; two independent real-state replays."""
import copy
import gzip
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PX = ROOT / 'experiments/z4q_pairwise_reconnect_repair'
SOURCE_MANIFEST = ROOT / 'experiments/b0_same_source_regression_repair/public/PREDICTION_SOURCE_MANIFEST.json'
DATA = Path('E:/CAU/D-MOT/data/AlignedFeeding_v1')
DATA_MANIFEST = DATA / 'manifest.jsonl'

spec = importlib.util.spec_from_file_location('frozen_pairwise_replay', PX / 'run.py')
px = importlib.util.module_from_spec(spec)
spec.loader.exec_module(px)
from pycocotools import mask as coco  # noqa: E402
from features import exclusive_core, stats  # noqa: E402

ARMS = ('NATIVE', 'Z4Q_FROZEN_V3', 'Z4Q_PAIRWISE_V3')
CODE = [Path(__file__), HERE / 'score.py', HERE / 'test_depth_input.py',
        PX / 'run.py', *px.SOURCE_FILES, px.BRIDGE, px.CONFIG,
        ROOT / 'experiments/feeding_first_two_s0p/prepare.py',
        Path('E:/CAU/D-MOT/tools/sam3_depth_birth_inherit_20260917/features.py')]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def line(value):
    return json.dumps(px.plain(value), ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'


def files():
    old = read(SOURCE_MANIFEST)
    data = {r['frame']: r for r in map(json.loads, DATA_MANIFEST.read_text(encoding='utf-8').splitlines())}
    assert len(data) == 1471
    for name, (start, stop) in px.SEGMENTS.items():
        item = old['segments']['SOURCE_OLD'][name]
        assert (item['start'], item['stop']) == (start, stop)
        for frame in range(start, stop + 1):
            record = data[frame]
            assert record['frame'] == frame and record['segment'].lower() == name
            path = DATA / record['depth_restored_aligned']
            assert path == DATA / 'depth_restored_rgb_640x360' / f'{frame:06d}.npz'
            yield frame, path


def freeze():
    path = HERE / 'public/FREEZE.json'
    assert not path.exists()
    test = read(HERE / 'public/TEST_REPORT.json')
    assert test['passed']
    manifest = read(SOURCE_MANIFEST)
    derived = {name: manifest['segments']['SOURCE_OLD'][name]['derived'] for name in px.SEGMENTS}
    for segment in derived.values():
        for entry in segment.values():
            assert Path(entry['path']).stat().st_size == entry['bytes']
            assert px.sha(entry['path']) == entry['sha256']
    restored = {str(frame): px.descriptor(p) for frame, p in files()}
    px.save(path, dict(status='FROZEN_BEFORE_REAL_REPLAY_AND_GT', branch='SOURCE_OLD',
        interpretation='ANNOTATION_ASSISTED_V3_DIAGNOSTIC', frames=len(restored),
        segments=px.SEGMENTS, code={str(p): px.sha(p) for p in CODE},
        test_sha256=px.sha(HERE / 'public/TEST_REPORT.json'),
        source_manifest=px.descriptor(SOURCE_MANIFEST),
        data_manifest=px.descriptor(DATA_MANIFEST), derived=derived,
        restored=restored, depth_fields_read_by_controller=['depth_mm'],
        audit_fields=['provenance'], model_http=0))


def prepare_depth(row, profiles, assignment, observations, item, freeze_record):
    frame = row['global_frame']
    meta = item['frames'][row['frame'] - 1]
    assert (frame, meta['original_frame'], assignment['global_frame_id']) == (frame, frame, frame)
    path = Path(freeze_record['restored'][str(frame)]['path'])
    assert path.stat().st_size == freeze_record['restored'][str(frame)]['bytes']
    assert px.sha(path) == freeze_record['restored'][str(frame)]['sha256']
    assert px.sha(meta['depth_path']) == meta['depth_sha256']
    with np.load(path) as source:
        # v3 depth_mm can contain annotation-assisted pixels. No instance/GT planes are read.
        assert {'depth_mm', 'provenance'}.issubset(source.files)
        depth = source['depth_mm']
        provenance = source['provenance']
    with np.load(meta['depth_path']) as source:
        original = source['depth_mm']
    assert depth.shape == original.shape == provenance.shape == (360, 640)
    assert np.all(np.isin(provenance, [0, 1, 2, 3, 4]))
    assert np.all(np.isfinite(depth)) and np.all(depth >= 0)
    ids = [o['id'] for o in observations]
    masks = {n: coco.decode(dict(size=assignment['masks'][f'n:{n}']['size'],
                    counts=assignment['masks'][f'n:{n}']['counts'].encode('ascii'))).astype(bool)
             for n in ids}
    occupancy = np.zeros(depth.shape, np.uint16)
    for mask in masks.values():
        occupancy += mask
    changed, depth_counts = 0, {}
    for observation in observations:
        n = observation['id']
        mask = masks[n]
        _, core = exclusive_core(mask, occupancy)
        old_whole, old_core = stats(original, mask), stats(original, core)
        assert observation['depth'] == {k: old_whole[k] for k in ('n', 'valid_fraction', 'median', 'mad')}
        assert profiles[n]['whole'] == old_whole and profiles[n]['core'] == old_core
        whole, core_stat = stats(depth, mask), stats(depth, core)
        replacement = {k: whole[k] for k in ('n', 'valid_fraction', 'median', 'mad')}
        changed += replacement != observation['depth'] or core_stat != old_core
        observation['depth'] = replacement
        profiles[n]['whole'], profiles[n]['core'] = whole, core_stat
        depth_counts[str(n)] = dict(original_n=old_whole['n'], restored_n=whole['n'],
                                   original_median=old_whole['median'], restored_median=whole['median'])
    union = occupancy > 0
    provenance_counts = {str(k): int(np.count_nonzero((provenance == k) & union)) for k in range(5)}
    return dict(changed_native_count=int(changed), provenance_in_prediction_union=provenance_counts,
                depth_by_native=depth_counts)


def run_segment(name, item, freeze_record):
    target = HERE / 'public' / name
    assert not target.exists(), target
    target.mkdir(parents=True)
    frozen = px.Bridge(px.read(px.CONFIG))
    pairwise = px.new_bridge()
    predicted = target / 'PREDICTIONS.jsonl.gz'
    actions = target / 'ACTIONS.jsonl'
    published = target / 'PUBLISH_LEDGER.jsonl'
    count = 0
    with gzip.open(predicted, 'wt', encoding='utf-8', compresslevel=3) as output, \
         actions.open('x', encoding='utf-8', newline='\n') as action_out, \
         published.open('x', encoding='utf-8', newline='\n') as publish_out:
        for row, profile, assignment, observations in px.feed(item):
            received = time.monotonic()
            depth_audit = prepare_depth(row, profile, assignment, observations, item, freeze_record)
            native = {o['id']: o['id'] for o in observations}
            frozen_map, frozen_trace, frozen_write, ids, masks = px.decision(
                frozen, row, copy.deepcopy(profile), assignment, copy.deepcopy(observations))
            pair_map, pair_trace, pair_write, _, _ = px.decision(
                pairwise, row, profile, assignment, observations)
            assert ids == list(native) and len(set(frozen_map.values())) == len(native)
            assert len(set(pair_map.values())) == len(native)
            payload = line(dict(frame=row['frame'], original_frame=row['global_frame'], masks=masks,
                variants=dict(zip(ARMS, (native, frozen_map, pair_map)))))
            output.write(payload)
            action_out.write(line(dict(frame=row['frame'], original_frame=row['global_frame'],
                depth_audit=depth_audit, frozen_events=frozen_trace['events'],
                pairwise_events=pair_trace['events'], edge_veto_checks=pair_trace['edge_veto_checks'],
                frozen_writes=frozen_write, pairwise_writes=pair_write,
                published={ARMS[1]: frozen_map, ARMS[2]: pair_map})))
            publish_out.write(line(dict(frame=row['frame'], original_frame=row['global_frame'],
                received_monotonic=received, first_publish_monotonic=time.monotonic(),
                prediction_row_sha256=hashlib.sha256(payload.encode()).hexdigest())))
            count += 1
            if count % 50 == 0:
                print(name, count, flush=True)
    assert count == item['stop'] - item['start'] + 1
    seal = dict(status='SEALED_BEFORE_GT', segment=name, source='SOURCE_OLD', frames=count,
        interpretation='ANNOTATION_ASSISTED_V3_DIAGNOSTIC', freeze_sha256=px.sha(HERE / 'public/FREEZE.json'),
        predictions=px.descriptor(predicted), actions=px.descriptor(actions),
        publication=px.descriptor(published), code=freeze_record['code'],
        frozen_final_state=hashlib.sha256(px.line(px.state(frozen)).encode()).hexdigest(),
        pairwise_final_state=px.state_sha(pairwise),
        model_http=0, gt_not_opened=True)
    px.save(target / 'SEAL.json', seal)
    return seal


def run_all():
    freeze_record = read(HERE / 'public/FREEZE.json')
    assert freeze_record['status'] == 'FROZEN_BEFORE_REAL_REPLAY_AND_GT'
    assert freeze_record['test_sha256'] == px.sha(HERE / 'public/TEST_REPORT.json')
    assert all(px.sha(p) == digest for p, digest in freeze_record['code'].items())
    assert px.sha(SOURCE_MANIFEST) == freeze_record['source_manifest']['sha256']
    assert px.sha(DATA_MANIFEST) == freeze_record['data_manifest']['sha256']
    manifest = read(SOURCE_MANIFEST)
    summary = {}
    for name in px.SEGMENTS:
        seal = run_segment(name, manifest['segments']['SOURCE_OLD'][name], freeze_record)
        summary[name] = dict(frames=seal['frames'], seal_sha256=px.sha(HERE / 'public' / name / 'SEAL.json'))
    px.save(HERE / 'public/RUN_SUMMARY.json', dict(status='ALL_SEALED_BEFORE_GT',
        freeze_sha256=px.sha(HERE / 'public/FREEZE.json'), segments=summary, model_http=0))


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('freeze', 'run'):
        raise SystemExit('usage: run.py freeze|run')
    {'freeze': freeze, 'run': run_all}[sys.argv[1]]()
