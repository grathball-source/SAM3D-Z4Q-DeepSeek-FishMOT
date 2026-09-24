"""Actual-input RQ0 transaction isolation checks, prediction-only."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments/vl_assoc_e1/r0_source"))
from bridge import stream  # noqa: E402
from quality_gate import ReferenceAdmission, StableReturn  # noqa: E402

record = json.loads((ROOT / "experiments/vl_assoc_e1c/RUN_RECORD.json").read_text())
source = record["sources"]
canary = json.loads((HERE / "CANARY_DEVELOPMENT.json").read_text())
frame = canary["selected"]["anchor"]["frame"]
native = canary["selected"]["anchor"]["native_id"]
config = json.loads((ROOT / "online/closed_loop_2888/z4q_source/CONFIG.json").read_text())
base = StableReturn(config)
veto = ReferenceAdmission(config, lambda f, o: (f, o["id"]) == (frame, native))
assert base.bank is not veto.bank and base.alias is not veto.alias
for row, profiles in stream(source["development_observations"], source["development_depth"]):
    ids0, _ = base.step(row["frame"], row["time"], row["observations"], profiles)
    ids1, _ = veto.step(row["frame"], row["time"], row["observations"], profiles)
    assert ids0 == ids1
    if row["frame"] == frame:
        target = ids0[native]
        assert base.bank[target] is not veto.bank[target]
        assert all(base.bank[k] == veto.bank[k] for k in base.bank if k != target)
        assert all(base.view_bank.get(k) == veto.view_bank.get(k) for k in base.bank if k != target)
        assert all(base.recent_core.get(k) == veto.recent_core.get(k) for k in base.bank if k != target)
        assert base.alias == veto.alias and base.birth == veto.birth and base.pending == veto.pending
        assert base.native_seen == veto.native_seen and base.native_runs == veto.native_runs
        assert base.bank[target]["last_seen"] == veto.bank[target]["last_seen"]
        assert base.bank[target]["last_frame"] == veto.bank[target]["last_frame"]
        assert base.bank[target]["anchor"]["frame"] == frame
        assert veto.bank[target]["anchor"]["frame"] < frame
        assert len([x for x in veto.write_audit if x["frame"] == frame and x["native_id"] == native and x["veto"]]) == 1
        break
    veto.write_audit.clear(); veto.read_audit.clear()
else:
    raise AssertionError("canary frame not reached")
result = dict(status="PASS_ACTUAL_INPUT_ATOMIC_ISOLATION", frame=frame, native_id=native,
              checks=["independent mutable bank/alias objects", "same current output", "non-target bank/view/recent unchanged",
                      "alias/birth/pending/native lifecycle unchanged", "target last_seen/last_frame unchanged",
                      "target anchor and value jointly retained", "exactly one target veto"], GT_read=False, API_calls=0)
out = HERE / "ATOMIC_TESTS.json"
assert not out.exists()
out.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
