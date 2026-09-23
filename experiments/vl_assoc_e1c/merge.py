"""Mechanical view of the two frozen prediction-only reachability streams."""
import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
freeze = json.loads((here / "EXPOSURE_MANIFEST.json").read_text())
names = ("CANDIDATE_REACHABILITY_development.jsonl", "CANDIDATE_REACHABILITY_validation.jsonl")
for name in names:
    assert hashlib.sha256((here / name).read_bytes()).hexdigest() == freeze["files"][name]
target = here / "CANDIDATE_REACHABILITY.jsonl"
assert not target.exists()
target.write_bytes(b"".join((here / name).read_bytes() for name in names))
assert len(target.read_text().splitlines()) == 289
print(hashlib.sha256(target.read_bytes()).hexdigest())
