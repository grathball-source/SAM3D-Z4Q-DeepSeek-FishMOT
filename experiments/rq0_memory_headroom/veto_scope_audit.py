"""Post-run audit of the frozen B0-allowed-write restriction."""
import gzip
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def rows(path):
    with gzip.open(path, "rt") as handle:
        yield from map(json.loads, handle)


result = {}
for split in ("development", "validation"):
    allowed = {x["observation_key"] for x in rows(HERE / f"REFERENCE_WRITES_{split}.jsonl.gz")}
    counts = Counter()
    examples = []
    for row in rows(HERE / f"REFERENCE_WRITE_READ_AUDIT_{split}.jsonl.gz"):
        if row["kind"] != "VETO":
            continue
        arm = row["arm"]
        counts[f"{arm}_veto"] += 1
        if row["observation_key"] not in allowed:
            counts[f"{arm}_outside_frozen_B0"] += 1
            if len(examples) < 20:
                examples.append(dict(arm=arm, observation_key=row["observation_key"]))
    result[split] = dict(counts=dict(counts), examples=examples)
out = HERE / "VETO_SCOPE_AUDIT.json"
assert not out.exists()
out.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
