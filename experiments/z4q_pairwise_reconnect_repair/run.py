"""Causal pairwise replay on the two immutable, same-source FEEDING inputs."""
import copy
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / 'experiments/b0_same_source_regression_repair'
sys.path.insert(0, str(OLD))
sys.path.insert(0, str(HERE / 'source'))

from source import SEGMENTS, descriptor, save, sha  # noqa: E402
from trace import BRIDGE, CONFIG, Bridge, delta, plain, read, rows, state, stream  # noqa: E402
from px_controller import PairwiseStableReturn  # noqa: E402

MANIFEST = OLD / 'public/PREDICTION_SOURCE_MANIFEST.json'
SOURCE_FILES = sorted((HERE / 'source').glob('*.py'))
CODE = [Path(__file__), *SOURCE_FILES, BRIDGE, CONFIG]


def line(value):
    return json.dumps(plain(value), ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'


def full_state(bridge):
    result = state(bridge)
    result['co_visibility'] = plain(copy.deepcopy(vars(bridge.engine.co_visibility)))
    return result


def state_sha(bridge):
    return hashlib.sha256(line(full_state(bridge)).encode()).hexdigest()


def feed(item, verify=True):
    derived = item['derived']
    if verify:
        for entry in derived.values():
            assert Path(entry['path']).stat().st_size == entry['bytes']
            assert sha(entry['path']) == entry['sha256']
    observations = stream(derived['observations']['path'], derived['profiles']['path'],
                          item['stop']-item['start']+1, global_start=item['start'])
    assignments = rows(derived['assignments']['path'])
    for (row, profiles), assignment in zip(observations, assignments, strict=True):
        assert row['frame'] == assignment['frame'] and row['global_frame'] == assignment['global_frame_id']
        meta = item['frames'][row['frame']-1]
        assert meta['original_frame'] == row['global_frame']
        generation = hashlib.sha256(meta['producer_batch']['batch_file'].encode()).hexdigest()[:16]
        obs = copy.deepcopy(row['observations'])
        for o in obs:
            o['pairwise_rle'] = assignment['masks'][o['mask']]
            o['pairwise_generation'] = generation
        yield row, profiles, assignment, obs


def new_bridge():
    bridge = Bridge(read(CONFIG))
    bridge.engine = PairwiseStableReturn(read(CONFIG))
    return bridge


def decision(bridge, row, profiles, assignment, observations):
    before = state(bridge)
    view = bridge.preview(row['frame'], row['time'], observations, profiles)
    mapping, trace = bridge.commit_once(view)
    after = state(bridge)
    native = [obj['id'] for obj in assignment['variants']['N0']]
    masks = [obj['mask'] for obj in assignment['variants']['N0']]
    assert set(mapping) == set(native) and len(set(mapping.values())) == len(native)
    return mapping, trace, delta(before, after), native, masks


def slice_f159():
    target = HERE / 'public/SLICE_F159.json'
    assert not target.exists()
    manifest = read(MANIFEST)
    item = manifest['segments']['SOURCE_OLD']['feeding_000000_000199']
    bridge = new_bridge()
    archived = rows(OLD / 'public/SOURCE_OLD/feeding_000000_000199/PREDICTIONS.jsonl.gz')
    for row, profiles, assignment, observations in feed(item):
        if row['global_frame'] > 159:
            break
        pre = state_sha(bridge) if row['global_frame'] == 159 else None
        mapping, trace, writes, native, masks = decision(bridge, row, profiles, assignment, observations)
        old = next(archived)
        assert old['original_frame'] == row['global_frame'] and old['masks'] == masks
        if row['global_frame'] == 159:
            result = dict(status='REAL_SOURCE_TO_F159_NO_GT', source='SOURCE_OLD',
                          original_frame=159, source_manifest_sha256=sha(MANIFEST),
                          decision_pre_state=pre, decision_post_state=state_sha(bridge),
                          frozen_mapping=old['variants']['Z4Q_FROZEN'], pairwise_mapping=mapping,
                          events=trace['events'], edge_veto_checks=trace['edge_veto_checks'],
                          state_write=writes, cache_versions=len(bridge.engine.co_visibility.runs),
                          code={str(path): sha(path) for path in CODE})
            save(target, result)
            return result
    raise AssertionError('F159 missing')


def run_segment(source, name, item):
    target = HERE / 'public' / source / name
    assert not target.exists(), target
    target.mkdir(parents=True)
    bridge = new_bridge()
    pred_path = target / 'PREDICTIONS.jsonl.gz'
    action_path = target / 'ACTION_LEDGER.jsonl'
    pub_path = target / 'PUBLISH_LEDGER.jsonl'
    first, last = item['start'], item['stop']
    count, vetoes, accepted = 0, [], []
    decision_post = None
    with gzip.open(pred_path, 'wt', encoding='utf-8', compresslevel=3) as predictions, \
         action_path.open('x', encoding='utf-8', newline='\n') as actions, \
         pub_path.open('x', encoding='utf-8', newline='\n') as publications:
        for row, profiles, assignment, observations in feed(item):
            received = time.monotonic()
            mapping, trace, writes, native, masks = decision(bridge, row, profiles, assignment, observations)
            frame = row['global_frame']
            raw = line(dict(frame=row['frame'], original_frame=frame, masks=masks,
                            public=[dict(native_id=n, public_id=mapping[n], mask=f'n:{n}') for n in native]))
            predictions.write(raw)
            checks = trace['edge_veto_checks']
            vetoes.extend(dict(original_frame=frame, **check) for check in checks if check['veto'])
            accepted.extend(dict(original_frame=frame, **event) for event in trace['events']
                            if event.get('kind') == 'reconnect' and event.get('accepted'))
            actions.write(line(dict(frame=row['frame'], original_frame=frame,
                                    published_public=mapping, edge_veto_checks=checks,
                                    events=trace['events'], state_write=writes,
                                    co_visibility_version_count=trace['co_visibility_version_count'])))
            published = time.monotonic()
            publications.write(line(dict(frame=row['frame'], original_frame=frame,
                received_monotonic=received, first_publish_monotonic=published,
                prediction_row_sha256=hashlib.sha256(raw.encode()).hexdigest())))
            count += 1
            if source == 'SOURCE_OLD' and frame == 159:
                decision_post = state_sha(bridge)
            if count % 50 == 0:
                print(source, name, count, flush=True)
    assert count == last-first+1
    seal = dict(status='SEALED_BEFORE_GT', source=source, segment=name, frames=count,
                hypothesis='VERSIONED_QUALIFIED_PAIRWISE_EXCLUSION',
                source_manifest_sha256=sha(MANIFEST), input_derived=item['derived'],
                prediction=descriptor(pred_path), actions=descriptor(action_path),
                publication=descriptor(pub_path), code={str(path): sha(path) for path in CODE},
                vetoes=vetoes, accepted_reconnects=accepted,
                decision_post_state=decision_post, final_state=state_sha(bridge),
                model_http=0, gt_not_opened=True)
    save(target / 'SEAL.json', seal)
    return seal


def run_all():
    assert (HERE / 'public/SLICE_F159.json').exists()
    manifest = read(MANIFEST)
    summary = {}
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        summary[source] = {}
        for name in SEGMENTS:
            seal = run_segment(source, name, manifest['segments'][source][name])
            summary[source][name] = dict(seal_sha256=sha(HERE / 'public' / source / name / 'SEAL.json'),
                                         frames=seal['frames'], vetoes=len(seal['vetoes']),
                                         accepted=len(seal['accepted_reconnects']))
    save(HERE / 'public/RUN_SUMMARY.json', dict(status='ALL_SEALED_BEFORE_GT',
         source_manifest_sha256=sha(MANIFEST), slice_sha256=sha(HERE / 'public/SLICE_F159.json'),
         source=summary, model_http=0))


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('slice', 'run'):
        raise SystemExit('usage: run.py slice|run')
    {'slice': slice_f159, 'run': run_all}[sys.argv[1]]()
