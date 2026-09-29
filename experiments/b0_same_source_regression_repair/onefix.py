"""One fixed hypothesis: protect certified continuous native IDs from D1 reassignment."""
import copy
import gzip
import hashlib
import json
import time
from pathlib import Path

from source import HERE, ROOT, SEGMENTS, descriptor, save, sha
from trace import BRIDGE, CONFIG, ENGINE_CODE, Bridge, delta, plain, read, rows, state, stream
from controller_return import StableReturn


class CertifiedNativeGuard(StableReturn):
    """Veto D1 birth reconnects after two confirmation windows of native continuity.

    D1's current eligibility expires after three seconds from first eligibility.
    A temporary expired value skips only its candidate path. We restore the
    original value before committing the view, so no artificial expiry enters
    the persistent state. New native IDs can still finish normal confirmation.
    """

    def step(self, frame, now, observations, profiles=None):
        current = {obj['id']: obj for obj in observations}
        protected = []
        previous = {}
        for native, obs in current.items():
            born = self.birth.get(native)
            if (born is None or born[0] == self.first or not 0 <= now-born[1] <= 6
                    or obs.get('neighbors') or not self.depth_valid(obs)):
                continue
            eligible_from = self.first_eligible.get(native, now)
            if now > min(born[1]+6, eligible_from+3):
                continue
            certificate = self.certificate(native, frame, now, current)
            # A newly born source reaches the existing five-frame certificate
            # exactly when its five-frame D1 reconnect may commit. Require one
            # earlier, disjoint confirmation window before protecting its ID.
            if (not certificate['qualified'] or
                    certificate['run']['count'] < 2 * self.cfg['confirm']):
                continue
            previous[native] = self.first_eligible.get(native)
            self.first_eligible[native] = now-4.0
            protected.append(dict(native_id=native, certificate=certificate,
                                  reason='CERTIFIED_CONTINUOUS_NATIVE_BEFORE_D1_RECONNECT'))
        try:
            ids, trace = super().step(frame, now, observations, profiles)
        finally:
            for native, value in previous.items():
                if value is None:
                    self.first_eligible.pop(native, None)
                else:
                    self.first_eligible[native] = value
        assert all(not (event.get('kind') == 'reconnect' and event.get('accepted') and
                        event.get('native_id') == item['native_id'])
                   for item in protected for event in trace['events'])
        trace['onefix_guard'] = protected
        return ids, trace


def line(value):
    return json.dumps(plain(value), ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'


def run_segment(source, name, item):
    target = HERE / 'public' / source / name / 'onefix'
    assert not target.exists(), target
    target.mkdir()
    bridge = Bridge(read(CONFIG))
    bridge.engine = CertifiedNativeGuard(read(CONFIG))
    derived = item['derived']
    for entry in derived.values():
        assert sha(entry['path']) == entry['sha256']
    observations = stream(derived['observations']['path'], derived['profiles']['path'],
                          item['stop']-item['start']+1, global_start=item['start'])
    assignments = rows(derived['assignments']['path'])
    prediction_path = target / 'PREDICTIONS.jsonl.gz'
    action_path = target / 'ACTION_LEDGER.jsonl'
    publication_path = target / 'PUBLISH_LEDGER.jsonl'
    guarded_frames = 0
    reconnects = 0
    count = 0
    with gzip.open(prediction_path, 'wt', encoding='utf-8', compresslevel=3) as predictions, \
         action_path.open('x', encoding='utf-8', newline='\n') as actions, \
         publication_path.open('x', encoding='utf-8', newline='\n') as publications:
        for (row, profiles), assignment in zip(observations, assignments, strict=True):
            received = time.monotonic()
            assert row['frame'] == assignment['frame']
            assert row['global_frame'] == assignment['global_frame_id']
            before = state(bridge)
            view = bridge.preview(row['frame'], row['time'], row['observations'], profiles)
            mapping, trace = bridge.commit_once(view)
            after = state(bridge)
            native = [obj['id'] for obj in assignment['variants']['N0']]
            masks = [obj['mask'] for obj in assignment['variants']['N0']]
            assert set(mapping) == set(native) and len(set(mapping.values())) == len(native)
            guarded_frames += bool(trace['onefix_guard'])
            reconnects += sum(event.get('kind') == 'reconnect' and event.get('accepted')
                              for event in trace['events'])
            raw = line(dict(frame=row['frame'], original_frame=row['global_frame'],
                            masks=masks, public=[dict(native_id=n, public_id=mapping[n], mask=f'n:{n}')
                                                 for n in native]))
            predictions.write(raw)
            actions.write(line(dict(frame=row['frame'], original_frame=row['global_frame'],
                                    previous_public=before['bridge_previous'], published_public=mapping,
                                    guard=trace['onefix_guard'], events=trace['events'],
                                    state_write=delta(before, after))))
            published = time.monotonic()
            publications.write(line(dict(frame=row['frame'], original_frame=row['global_frame'],
                received_monotonic=received, first_publish_monotonic=published,
                prediction_row_sha256=hashlib.sha256(raw.encode()).hexdigest())))
            count += 1
    assert count == item['stop']-item['start']+1
    seal = dict(status='SEALED_BEFORE_GT', source=source, segment=name,
        frames=count, guarded_frames=guarded_frames, accepted_reconnects=reconnects,
        model_http=0, rule='NEW_HYPOTHESIS_CERTIFIED_NATIVE_GUARD',
        source_manifest_sha256=sha(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json'),
        input_derived=derived, prediction=descriptor(prediction_path),
        actions=descriptor(action_path), publication=descriptor(publication_path),
        code={str(path): sha(path) for path in [Path(__file__), HERE / 'source.py',
             HERE / 'trace.py', BRIDGE, CONFIG, *ENGINE_CODE]})
    save(target / 'SEAL.json', seal)
    return seal


def main():
    manifest = read(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json')
    result = {}
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        result[source] = {}
        for name in SEGMENTS:
            seal = run_segment(source, name, manifest['segments'][source][name])
            result[source][name] = dict(seal_sha256=sha(HERE / 'public' / source / name / 'onefix/SEAL.json'),
                                         guarded_frames=seal['guarded_frames'],
                                         accepted_reconnects=seal['accepted_reconnects'])
            print(source, name, result[source][name], flush=True)
    save(HERE / 'public/ONEFIX_RUN_SUMMARY.json', dict(status='ALL_SEALED_BEFORE_GT',
        rule='NEW_HYPOTHESIS_CERTIFIED_NATIVE_GUARD', sources=result, model_http=0))


if __name__ == '__main__':
    main()
