"""Seal prediction-only candidate replay before the independent GT reader starts."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
names = ("CANDIDATE_REACHABILITY_development.jsonl", "CANDIDATE_REACHABILITY_validation.jsonl",
         "PRIOR_RESULT_REAUDIT.json", "probe.py", "reaudit.py")
out = HERE / "EXPOSURE_MANIFEST.json"
assert not out.exists()
files = {n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in names}
out.write_text(json.dumps(dict(status="E1C_A_PREDICTION_ONLY_FROZEN", at_utc=datetime.now(timezone.utc).isoformat(),
                               fixed_base="12c6dcf60df86deedc71c719b867d56e8ab53838", GT_read=False,
                               allow_api=False, files=files), indent=2) + "\n")
print(json.dumps(files))
