"""Copy-on-write integration. Only the chosen engine becomes branch state."""
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
P = Path(__file__).resolve().parents[3] / 'online/closed_loop_2888/z4q_source'
sys.path.insert(0, str(P/'source/sam3_depth_return_guard_20260918'))
from controller_return import StableReturn


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def save(p, value):
    p = Path(p)
    tmp = p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    tmp.replace(p)


def rows(p):
    with gzip.open(p, 'rt', encoding='utf-8') as f:
        yield from map(json.loads, f)


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def stream(observations_path, profiles_path, frame_count=None, global_start=None):
    """Read one explicit split without inferring development paths or offsets."""
    count = 0
    for r, p in zip(rows(observations_path), rows(profiles_path), strict=True):
        count += 1
        if frame_count is not None and count > frame_count:
            break
        assert (r['frame'], r['global_frame'], r['time']) == (p['frame'], p['global_frame'], p['time'])
        assert p['evidence_max_global_frame'] <= r['global_frame']
        if global_start is not None:
            assert r['global_frame'] == global_start + count - 1
        profiles = {o['id']: dict(o, frame=r['frame']) for o in p['observations']}
        yield r, profiles
    if frame_count is not None:
        assert count == frame_count


class Bridge:
    def __init__(self, config):
        self.engine = StableReturn(config)
        self.version = 0
        self.provenance = {}
        self.epochs = {}
        self.previous = {}
        self.previous_alias = {}

    @staticmethod
    def alias_signature(engine, native):
        alias = engine.alias.get(native)
        return None if alias is None else (alias['target'], alias.get('commit_frame'), alias.get('transaction_version'))

    def next_epochs(self, ids, engine):
        return {n: self.epochs.get(n, 0) + (n not in self.previous or
                self.previous[n] != k or
                self.previous_alias.get(n) != self.alias_signature(engine, n))
                for n, k in ids.items()}

    def preview(self, frame, now, observations, profiles):
        trial = copy.deepcopy(self.engine)
        ids, trace = trial.step(frame, now, observations, profiles)
        effective_epochs = self.next_epochs(ids, trial)
        return dict(version=self.version, frame=frame, now=now, observations=observations,
                    profiles=profiles, engine=trial, mapping=ids, trace=trace, epochs=effective_epochs)

    def stage(self, view, changes):
        """Validate all edits before running the original lifecycle on a fresh clone.

        A failed plan never mutates the authoritative engine or the native preview.
        Callers enforce model gates, source/claim eligibility and confirmation.
        """
        if view['version'] != self.version:
            return None, 'stale_snapshot'
        before = view['mapping']
        wanted = dict(before, **{})
        wanted.update(changes)
        if not 1 <= len(changes) <= 2 or any(n not in before or k < 0 or before[n] == k for n, k in changes.items()):
            return None, 'invalid_edit'
        if len(set(wanted.values())) != len(wanted):
            return None, 'occupied_target'
        obs = {o['id']: o for o in view['observations']}
        for n, k in changes.items():
            if not self.engine.quality(obs[n]) or obs[n].get('neighbors'):
                return None, 'current_quality_or_contact'
            h = self.engine.bank.get(k)
            if not h or not h.get('anchor') or h['anchor']['frame'] >= view['frame']:
                return None, 'missing_past_anchor'
            # Existing return rule: a qualified original native handle has priority.
            if any(c['qualified'] and c['native_id'] == k and n != k for c in view['trace'].get('native_return_checks', [])):
                return None, 'qualified_native_return'
        trial = copy.deepcopy(self.engine)
        anchors = {n: copy.deepcopy(trial.bank[k]['anchor']) for n, k in changes.items()}
        for n, k in changes.items():
            trial.alias.pop(n, None)
            if n != k:
                trial.alias[n] = dict(target=k, anchor=anchors[n], commit_frame=view['frame'], source='DEEPSEEK_CLOSED_LOOP', transaction_version=self.version+1)
            trial.pending.pop(n, None)
            trial.retired.discard(n)
            trial.native_runs.pop(n, None)
            trial.recent_core.pop(n, None)
        # Keep target banks intact; never blend source and destination histories.
        targets = set(wanted.values()) | {a['target'] for a in trial.alias.values()}
        for n in changes:
            if n not in targets:
                trial.bank.pop(n, None)
                trial.view_bank.pop(n, None)
        ids, trace = trial.step(view['frame'], view['now'], view['observations'], view['profiles'])
        if ids != wanted:
            return None, 'native_lifecycle_veto'
        return dict(engine=trial, mapping=ids, trace=trace, changes=changes, anchors=anchors,
                    epochs=self.next_epochs(ids, trial)), None

    def commit_once(self, view, transaction=None):
        assert view['version'] == self.version, 'already committed or stale'
        selected = view if transaction is None else transaction
        committed_epochs = self.next_epochs(selected['mapping'], selected['engine'])
        assert committed_epochs == selected['epochs'], 'preview_commit_epoch_mismatch'
        self.engine = selected['engine']
        self.version += 1
        ids = selected['mapping']
        self.epochs.update(committed_epochs)
        if transaction is not None:
            for n, k in transaction['changes'].items():
                self.provenance[n] = dict(source='DEEPSEEK_CLOSED_LOOP', target=k, frame=view['frame'],
                    version=self.version, epoch=self.epochs[n], anchor=transaction['anchors'][n])
        for n in list(self.provenance):
            if n in ids and ids[n] != self.provenance[n]['target']:
                self.provenance.pop(n)
        self.previous = dict(ids)
        self.previous_alias = {n: self.alias_signature(self.engine, n) for n in ids}
        return ids, selected['trace']
