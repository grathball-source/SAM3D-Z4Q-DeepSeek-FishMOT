"""Replay native and frozen Z4Q states, seal predictions and the complete B0 trace."""
import copy
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

from source import HERE, ROOT, SEGMENTS, descriptor, save, sha

sys.path.insert(0, str(ROOT / 'online/closed_loop_2888/z4q_source'))
from bridge import Bridge, read, rows, stream  # noqa: E402

CONFIG = ROOT / 'online/closed_loop_2888/z4q_source/CONFIG.json'
BRIDGE = ROOT / 'online/closed_loop_2888/z4q_source/bridge.py'
ENGINE = ROOT / 'online/closed_loop_2888/z4q_source/source'
ENGINE_CODE = [ENGINE / directory / filename for directory, filename in (
    ('sam3_depth_return_guard_20260918', 'controller_return.py'),
    ('sam3_depth_birth_quality_20260918', 'controller_z4.py'),
    ('sam3_depth_birth_native_prior_20260918', 'controller_z3.py'),
    ('sam3_depth_birth_refine_20260918', 'controller_z2.py'),
    ('sam3_depth_failure_repair_20260917', 'repair_controller_r3.py'),
    ('sam3_depth_identity_balance_20260917', 'controller.py'))]
FIELDS = ('bank', 'view_bank', 'alias', 'pending', 'retired', 'birth', 'first_eligible',
          'native_runs', 'return_quarantine', 'empty_quarantine', 'recent_core',
          'native_seen', 'counts', 'first', 'birth_counts')


def plain(value):
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (set, tuple, list)):
        return [plain(item) for item in (sorted(value) if isinstance(value, set) else value)]
    if hasattr(value, 'tolist'):
        return value.tolist()
    if hasattr(value, 'item'):
        return value.item()
    return value


def state(bridge):
    engine = bridge.engine
    return plain({**{field: copy.deepcopy(getattr(engine, field)) for field in FIELDS if hasattr(engine, field)},
                  'bridge_previous': copy.deepcopy(bridge.previous),
                  'bridge_provenance': copy.deepcopy(bridge.provenance),
                  'bridge_epochs': copy.deepcopy(bridge.epochs),
                  'bridge_version': bridge.version})


def delta(before, after):
    changes = {}
    for field in sorted(set(before) | set(after)):
        a, b = before.get(field), after.get(field)
        if a == b:
            continue
        if isinstance(a, dict) and isinstance(b, dict):
            changes[field] = {key: dict(before=a.get(key), after=b.get(key))
                              for key in sorted(set(a) | set(b)) if a.get(key) != b.get(key)}
        else:
            changes[field] = dict(before=a, after=b)
    return changes


def write_line(handle, value):
    handle.write(json.dumps(plain(value), ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')


def run_segment(source, name, item, old_run):
    target = HERE / 'public' / source / name
    assert not target.exists(), target
    target.mkdir(parents=True)
    derived = item['derived']
    for entry in derived.values():
        path = Path(entry['path'])
        assert path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256']
    observations = stream(derived['observations']['path'], derived['profiles']['path'],
                          item['stop'] - item['start'] + 1, global_start=item['start'])
    assignments = rows(derived['assignments']['path'])
    archived = rows(old_run / name / 'public/predictions.jsonl.gz') if source == 'SOURCE_OLD' else None
    bridge = Bridge(read(CONFIG))
    predictions = target / 'PREDICTIONS.jsonl.gz'
    actions = target / 'B0_ACTION_LEDGER.jsonl'
    publications = target / 'PUBLISH_LEDGER.jsonl'
    prior_batch = None
    missing_score_shapes = 0
    all_missing_score_native = 0
    total = 0
    with gzip.open(predictions, 'wt', encoding='utf-8', compresslevel=3) as output, \
         actions.open('x', encoding='utf-8', newline='\n') as action_file, \
         publications.open('x', encoding='utf-8', newline='\n') as publish_file:
        for (row, profiles), assignment in zip(observations, assignments, strict=True):
            received = time.monotonic()
            local, frame = row['frame'], row['global_frame']
            meta = item['frames'][local - 1]
            assert (meta['local_frame'], meta['original_frame']) == (local, frame)
            assert (assignment['frame'], assignment['global_frame_id']) == (local, frame)
            native = {int(obj['id']): int(obj['id']) for obj in row['native']}
            assert set(native) == {obj['id'] for obj in row['observations']}
            masks = {int(obj['id']): obj['mask'] for obj in row['native']}
            raw_shapes = json.loads(Path(meta['prediction_path']).read_text(encoding='utf-8'))['shapes']
            assert sha(meta['prediction_path']) == meta['prediction_sha256']
            score_by_native = {}
            for shape in raw_shapes:
                score_by_native.setdefault(int(shape['group_id']), []).append(shape.get('score'))
                missing_score_shapes += shape.get('score') is None
            all_missing_here = sorted(n for n, values in score_by_native.items() if all(v is None for v in values))
            all_missing_score_native += len(all_missing_here)
            before = state(bridge)
            quality = {str(obs['id']): bridge.engine.quality(obs) for obs in row['observations']}
            view = bridge.preview(local, row['time'], row['observations'], profiles)
            mapped, trace = bridge.commit_once(view)
            after = state(bridge)
            assert set(mapped) == set(native) and len(set(mapped.values())) == len(native)
            passthrough = dict(native)
            assert passthrough == native
            published = dict(frame=local, original_frame=frame,
                             masks=[masks[key] for key in native],
                             variants={'NATIVE': native, 'Z4Q_FROZEN': mapped, 'PASSTHROUGH': passthrough})
            line = json.dumps(plain(published), ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'
            output.write(line)
            if archived is not None:
                old = next(archived)
                assert old['frame'] == local and old['global_frame'] == frame
                assert old['variants']['B0'] == [dict(id=mapped[key], mask=masks[key]) for key in native]
            batch = meta['producer_batch']
            observation_decisions = [dict(native_id=obs['id'], mask=obs['mask'], box=obs['box'],
                                          area=obs['area'], score_birth=obs.get('score_birth'),
                                          presence=obs.get('presence'), neighbors=obs.get('neighbors'),
                                          depth=obs.get('depth'), quality=quality[str(obs['id'])],
                                          whole=profiles[obs['id']].get('whole'),
                                          core=profiles[obs['id']].get('core'))
                                     for obs in row['observations']]
            write_line(action_file, dict(frame=local, original_frame=frame, time=row['time'],
                producer_batch=batch, producer_batch_changed=prior_batch != batch['batch_file'],
                source_json_sha256=meta['prediction_sha256'], native_to_mask=masks,
                missing_score_shapes=sum(shape.get('score') is None for shape in raw_shapes),
                all_missing_score_native=all_missing_here,
                previous_public=before['bridge_previous'], published_public=mapped,
                decision_inputs=observation_decisions, trace=trace, state_write=delta(before, after)))
            prior_batch = batch['batch_file']
            first_publication = time.monotonic()
            write_line(publish_file, dict(frame=local, original_frame=frame,
                received_monotonic=received, first_publish_monotonic=first_publication,
                receive_to_publish_seconds=first_publication - received,
                prediction_row_sha256=hashlib.sha256(line.encode()).hexdigest()))
            total += 1
            if total % 50 == 0:
                print(source, name, total, flush=True)
    assert total == item['stop'] - item['start'] + 1
    if archived is not None:
        assert next(archived, None) is None
    seal = dict(status='SEALED_NO_GT_OPEN', source=source, segment=name, frames=total,
                input_manifest_sha256=sha(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json'),
                input_derived=derived, source_prediction_dir=item['prediction_dir'],
                prediction=descriptor(predictions), actions=descriptor(actions),
                publication=descriptor(publications),
                code={str(path): sha(path) for path in [Path(__file__), HERE / 'source.py', BRIDGE, CONFIG, *ENGINE_CODE]},
                archived_B0_exact=(source == 'SOURCE_OLD'),
                passthrough_equals_native=True,
                missing_score_shapes=missing_score_shapes,
                all_missing_score_native=all_missing_score_native,
                http_attempts=0)
    save(target / 'PREDICTIONS_SEALED.json', seal)
    return seal


def main():
    manifest = json.loads((HERE / 'public/PREDICTION_SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    old_run = ROOT / 'experiments/feeding_first_two_s0p/run'
    seals = {}
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        seals[source] = {}
        for name in SEGMENTS:
            seals[source][name] = run_segment(source, name, manifest['segments'][source][name], old_run)
    save(HERE / 'public/TRACE_RUN_SUMMARY.json', dict(status='ALL_SEALED_BEFORE_GT',
        source_manifest_sha256=sha(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json'),
        seals={source: {name: sha(HERE / 'public' / source / name / 'PREDICTIONS_SEALED.json')
                        for name in SEGMENTS} for source in seals}, http_attempts=0))


if __name__ == '__main__':
    main()
