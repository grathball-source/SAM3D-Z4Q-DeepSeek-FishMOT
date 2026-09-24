"""RQ0 reference-admission experiment on the frozen StableReturn engine.

Only post-association reference writes are vetoed. The original step still owns
birth, alias, last_seen/last_frame, partners, and the current mask output.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "online/closed_loop_2888/z4q_source/source/sam3_depth_return_guard_20260918"
sys.path.insert(0, str(SOURCE))
from controller_return import StableReturn  # noqa: E402

BANK_REFERENCE = ("clean_count", "clean_time", "clean_box", "motion", "areas", "anchor", "depth_history", "ema")
MISSING = object()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class ReferenceAdmission(StableReturn):
    """A veto is keyed by (frame, native), never by GT or public ID."""

    def __init__(self, config, veto=None):
        super().__init__(config)
        self.veto = veto or (lambda frame, obs: False)
        self.write_audit = []
        self.read_audit = []
        self.frame = None

    def _key(self, history):
        return next((k for k, value in self.bank.items() if value is history), None)

    def motion(self, history, obs, now):
        k = self._key(history)
        if k is not None:
            self.read_audit.append(dict(frame=self.frame, reader="motion", public_id=k,
                                        native_id=obs["id"], reference=digest({x: history.get(x) for x in ("clean_box", "clean_time", "motion")})))
        return super().motion(history, obs, now)

    def z(self, history):
        k = self._key(history)
        if k is not None:
            self.read_audit.append(dict(frame=self.frame, reader="z", public_id=k,
                                        reference=digest({x: history.get(x) for x in ("depth_history", "ema")})))
        return super().z(history)

    def history(self, k, view, frame, now):
        value = super().history(k, view, frame, now)
        if value is not None:
            self.read_audit.append(dict(frame=frame, reader="history:" + view, public_id=k,
                                        reference=digest(value), anchor=value.get("anchor")))
        return value

    def step(self, frame, now, observations, profiles=None):
        self.frame = frame
        # Capture one coherent pre-transaction image. A bank may be created by
        # this step; absent fields then return to absent/default after veto.
        before_bank = {k: {name: copy.deepcopy(h[name]) for name in BANK_REFERENCE if name in h}
                       for k, h in self.bank.items()}
        before_views = copy.deepcopy(self.view_bank)
        before_recent = copy.deepcopy(self.recent_core)
        ids, trace = super().step(frame, now, observations, profiles)
        for obs in observations:
            n, k = obs["id"], ids[obs["id"]]
            h = self.bank.get(k)
            if h is None:
                continue
            old = before_bank.get(k, dict(clean_count=0, clean_time=None,
                                          depth_history=[], ema=None, motion=[], areas=[]))
            bank_written = h.get("anchor", {}).get("frame") == frame and h["anchor"].get("native_id") == n
            changed_bank = ([name for name in BANK_REFERENCE if old.get(name, MISSING) != h.get(name, MISSING)]
                            if bank_written else [])
            current_views = self.view_bank.get(k, {})
            changed_views = any(value.get("anchor", {}).get("frame") == frame and
                                value["anchor"].get("native_id") == n and
                                before_views.get(k, {}).get(view) != value
                                for view, value in current_views.items())
            current_recent = self.recent_core.get(k)
            changed_recent = bool(current_recent and current_recent.get("anchor", {}).get("frame") == frame and
                                  current_recent["anchor"].get("native_id") == n and
                                  before_recent.get(k) != current_recent)
            if not (changed_bank or changed_views or changed_recent):
                continue
            veto = bool(self.veto(frame, obs))
            record = dict(frame=frame, native_id=n, public_id=k, observation_key=f"{frame}:n:{n}",
                          veto=veto, bank_fields=changed_bank, view_bank=changed_views,
                          recent_core=changed_recent, before=digest(old),
                          after=digest({name: h.get(name) for name in BANK_REFERENCE}))
            if veto:
                for name in changed_bank:
                    if name not in old:
                        h.pop(name, None)
                    else:
                        h[name] = copy.deepcopy(old[name])
                for target, previous, changed in ((self.view_bank, before_views, changed_views),
                                                  (self.recent_core, before_recent, changed_recent)):
                    if not changed:
                        continue
                    if k in previous:
                        target[k] = copy.deepcopy(previous[k])
                    else:
                        target.pop(k, None)
                record["committed"] = digest({name: h.get(name) for name in BANK_REFERENCE})
            self.write_audit.append(record)
        return ids, trace
