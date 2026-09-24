"""Check whether excluded non-B0 vetoes affected frozen Q-rule outputs."""
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def rows(path):
    with gzip.open(path, "rt") as handle:
        yield from map(json.loads, handle)


result = {}
for split in ("development", "validation"):
    changed = []
    count = 0
    for old, fixed in zip(rows(HERE / f"PREDICTIONS_{split}.jsonl.gz"),
                          rows(HERE / f"PREDICTIONS_QRULE_SCOPEFIX_{split}.jsonl.gz"), strict=True):
        assert old["frame"] == fixed["frame"]
        assert old["variants"]["B0"] == fixed["B0"]
        if old["variants"]["Q-rule"] != fixed["Q_rule_scopefix"]:
            changed.append(old["frame"])
        count += 1
    result[split] = dict(frames=count, old_vs_scopefix_changed_output_frames=len(changed),
                         first_changed_frames=changed[:20])
out = HERE / "SCOPEFIX_OUTPUT_PARITY.json"
assert not out.exists()
out.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
