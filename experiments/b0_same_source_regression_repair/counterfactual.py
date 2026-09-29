"""F159 postscore diagnostic: clone true pre-action state, allow or veto one D1 reconnect."""
import copy
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

from source import DATA, HERE, ROOT, SEGMENTS, descriptor, save, sha
from trace import CONFIG, Bridge, plain, read, rows, state, stream

CASE = dict(source='SOURCE_OLD', segment='feeding_000000_000199',
            original_frame=159, native_id=26, target_id=16)
TARGET = HERE / 'public/counterfactual_F159'


def line(value):
    return json.dumps(plain(value), ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'


def state_sha(bridge):
    return hashlib.sha256(json.dumps(state(bridge), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def veto_preview(bridge, row, profiles):
    """Expire only this event's D1 eligibility for this decision, then restore it."""
    n = CASE['native_id']
    original = bridge.engine.first_eligible.get(n)
    assert original is not None
    now = row['time']
    bridge.engine.first_eligible[n] = now - 4.0  # D1's frozen 3-second eligibility window.
    view = bridge.preview(row['frame'], now, row['observations'], profiles)
    if original is None:
        bridge.engine.first_eligible.pop(n, None)
        view['engine'].first_eligible.pop(n, None)
    else:
        bridge.engine.first_eligible[n] = original
        view['engine'].first_eligible[n] = original
    assert not any(e.get('kind') == 'reconnect' and e.get('accepted') and
                   e.get('native_id') == n and e.get('canonical_id') == CASE['target_id']
                   for e in view['trace']['events'])
    return view


def run():
    assert not TARGET.exists(), TARGET
    manifest = read(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json')
    item = manifest['segments'][CASE['source']][CASE['segment']]
    assert (item['start'], item['stop']) == SEGMENTS[CASE['segment']]
    derived = item['derived']
    for entry in derived.values():
        assert sha(entry['path']) == entry['sha256']
    feed = list(stream(derived['observations']['path'], derived['profiles']['path'],
                       200, global_start=item['start']))
    assignments = list(rows(derived['assignments']['path']))
    assert len(feed) == len(assignments) == 200
    target_local = CASE['original_frame'] - item['start'] + 1
    assert target_local == 160
    prefix_bridge = Bridge(read(CONFIG))
    prefix = []
    for row, profiles in feed[:target_local-1]:
        view = prefix_bridge.preview(row['frame'], row['time'], row['observations'], profiles)
        mapping, _ = prefix_bridge.commit_once(view)
        prefix.append(dict(frame=row['frame'], original_frame=row['global_frame'], mapping=mapping))
    pre = state_sha(prefix_bridge)
    branches = {'ALLOW': copy.deepcopy(prefix_bridge), 'VETO': copy.deepcopy(prefix_bridge)}
    assert state_sha(branches['ALLOW']) == state_sha(branches['VETO']) == pre
    TARGET.mkdir(parents=True)
    for arm, bridge in branches.items():
        output = TARGET / arm
        output.mkdir()
        prediction_path = output / 'PREDICTIONS.jsonl.gz'
        action_path = output / 'ACTION_LEDGER.jsonl'
        publish_path = output / 'PUBLISH_LEDGER.jsonl'
        with gzip.open(prediction_path, 'wt', encoding='utf-8', compresslevel=3) as predictions, \
             action_path.open('x', encoding='utf-8', newline='\n') as actions, \
             publish_path.open('x', encoding='utf-8', newline='\n') as publications:
            for index, ((row, profiles), assignment) in enumerate(zip(feed, assignments, strict=True)):
                received = time.monotonic()
                if index < target_local-1:
                    mapping = prefix[index]['mapping']
                    trace = None
                else:
                    view = (veto_preview(bridge, row, profiles)
                            if arm == 'VETO' and row['global_frame'] == CASE['original_frame']
                            else bridge.preview(row['frame'], row['time'], row['observations'], profiles))
                    mapping, trace = bridge.commit_once(view)
                native = [obj['id'] for obj in assignment['variants']['N0']]
                masks = [obj['mask'] for obj in assignment['variants']['N0']]
                assert set(mapping) == set(native) and len(set(mapping.values())) == len(native)
                pred = dict(frame=row['frame'], original_frame=row['global_frame'], masks=masks,
                            public=[dict(native_id=n, public_id=mapping[n], mask=f'n:{n}') for n in native])
                raw = line(pred)
                predictions.write(raw)
                if trace is not None:
                    actions.write(line(dict(original_frame=row['global_frame'], frame=row['frame'],
                                            events=trace['events'], mapping=mapping,
                                            alias=copy.deepcopy(bridge.engine.alias),
                                            pending=copy.deepcopy(bridge.engine.pending))))
                publication = time.monotonic()
                publications.write(line(dict(original_frame=row['global_frame'], frame=row['frame'],
                    received_monotonic=received, first_publish_monotonic=publication,
                    prediction_row_sha256=hashlib.sha256(raw.encode()).hexdigest())))
        seal = dict(status='SEALED_BEFORE_GT', case=CASE, arm=arm, frames=200,
                    decision_pre_state_sha256=pre,
                    decision_post_state_sha256=state_sha(bridge) if arm == 'ALLOW' else None,
                    prefix_frames=target_local-1, continuation_frames=200-target_local+1,
                    input_source_manifest_sha256=sha(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json'),
                    derived=derived, prediction=descriptor(prediction_path),
                    action=descriptor(action_path), publication=descriptor(publish_path),
                    code={str(path): sha(path) for path in (Path(__file__), HERE / 'trace.py', CONFIG)},
                    diagnostic_only=True, gt_not_opened=True, http_attempts=0)
        save(output / 'SEAL.json', seal)
    save(TARGET / 'PAIR_SEALED.json', dict(status='BOTH_SEALED_BEFORE_GT', case=CASE,
         allow_sha256=sha(TARGET / 'ALLOW/SEAL.json'), veto_sha256=sha(TARGET / 'VETO/SEAL.json')))


def score():
    import importlib.util
    pair = json.loads((TARGET / 'PAIR_SEALED.json').read_text(encoding='utf-8'))
    assert pair['status'] == 'BOTH_SEALED_BEFORE_GT'
    for arm in ('ALLOW', 'VETO'):
        seal = json.loads((TARGET / arm / 'SEAL.json').read_text(encoding='utf-8'))
        assert sha(TARGET / arm / 'SEAL.json') == pair[arm.lower()+'_sha256']
        for entry in (seal['prediction'], seal['action'], seal['publication'], *seal['derived'].values()):
            assert sha(entry['path']) == entry['sha256']
        for path, expected in seal['code'].items():
            assert sha(path) == expected
    spec = importlib.util.spec_from_file_location('feeding_frozen_scorer',
        ROOT / 'experiments/feeding_first_two_s0p/score.py')
    feeding = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(feeding)
    np, coco = feeding.np, feeding.coco
    item = read(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json')['segments']['SOURCE_OLD'][CASE['segment']]
    assignments = list(rows(item['derived']['assignments']['path']))
    archived = list(rows(ROOT / 'experiments/feeding_first_two_s0p/run' / CASE['segment'] / 'public/predictions.jsonl.gz'))
    result = {}
    for arm in ('ALLOW', 'VETO'):
        gt, pred, sims, changed = [], [], [], []
        for assignment, publication, old in zip(assignments, rows(TARGET / arm / 'PREDICTIONS.jsonl.gz'), archived, strict=True):
            frame = publication['original_frame']
            assert old['global_frame'] == frame == assignment['global_frame_id']
            mask_keys = [obj['mask'] for obj in assignment['variants']['N0']]
            assert mask_keys == publication['masks']
            ids = [obj['public_id'] for obj in publication['public']]
            assert ids == [obj['id'] for obj in old['variants']['B0']] or arm == 'VETO'
            if ids != [obj['id'] for obj in old['variants']['B0']]:
                changed.append(frame)
            truth = json.loads((DATA / 'labels_640x360' / f'{frame:06d}.json').read_text(encoding='utf-8'))
            gids, gmasks = feeding.mask_rles(truth['shapes'])
            pmasks = [feeding.original_score.rle(assignment['masks'][key]) for key in mask_keys]
            gt.append(gids)
            pred.append(ids)
            sims.append(np.asarray(coco.iou(gmasks, pmasks, [0]*len(pmasks)), float)
                        if gids and pmasks else np.zeros((len(gids), len(pmasks))))
        result[arm] = dict(metrics=feeding.metrics(gt, pred, sims),
                           changed_vs_archived_frozen_frames=changed)
    assert not result['ALLOW']['changed_vs_archived_frozen_frames']
    save(TARGET / 'POSTSEAL_SCORE.json', dict(status='SCORED_AFTER_PAIR_SEAL', case=CASE,
         branch=result, delta={key: result['VETO']['metrics'][key]-result['ALLOW']['metrics'][key]
                               for key in result['ALLOW']['metrics'] if key not in ('GT', 'predictions')},
         pair_seal_sha256=sha(TARGET / 'PAIR_SEALED.json'), scorer_sha256=sha(Path(__file__))))
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('run', 'score'):
        raise SystemExit('usage: counterfactual.py run|score')
    {'run': run, 'score': score}[sys.argv[1]]()
