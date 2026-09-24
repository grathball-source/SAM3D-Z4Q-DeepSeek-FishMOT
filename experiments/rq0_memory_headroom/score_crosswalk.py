"""Exhaustive old native_to_gt vs objects.gt_id/ambiguity definition check."""
import gzip
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = json.loads((HERE.parent / "vl_assoc_e1c/RUN_RECORD.json").read_text())["sources"]
result = {}
for split in ("development", "validation"):
    path = Path(SOURCE["exposed_matches"].replace("{development,validation}", split))
    # RUN_RECORD uses a brace pattern to document both sealed input paths.
    assert path.is_file(), path
    counts = Counter()
    policies = Counter()
    examples = []
    with gzip.open(path, "rt") as handle:
        for line in handle:
            row = json.loads(line)
            counts["frames"] += 1
            policies[(row.get("matching"), row.get("ambiguity_policy"))] += 1
            objects = {str(x["native_id"]): x for x in row["objects"]}
            old = row["native_to_gt"]
            counts["old_extra_keys"] += len(set(old) - set(objects))
            counts["objects_without_old_key"] += len(set(objects) - set(old))
            for native, obj in objects.items():
                counts["objects"] += 1
                certified = None if obj.get("ambiguity") else obj.get("gt_id")
                old_value = old.get(native)
                if certified is None:
                    counts["unknown"] += 1
                if old_value != certified:
                    counts["mismatch"] += 1
                    if len(examples) < 20:
                        examples.append(dict(frame=row["frame"], native_id=int(native), old=old_value,
                                             gt_id=obj.get("gt_id"), ambiguity=obj.get("ambiguity")))
    result[split] = dict(counts=dict(counts), policies=[dict(matching=k[0], ambiguity_policy=k[1], frames=v)
                                                          for k, v in policies.items()], examples=examples)
out = HERE / "SCORER_CROSSWALK.json"
assert not out.exists()
out.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
