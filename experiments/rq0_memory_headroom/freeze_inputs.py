"""Seal RQ0 prediction-only selection and implementation before exposed GT."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ("quality_gate.py", "canary.py", "select_quality.py", "OBSERVABLE_QUALITY_PROTOCOL.md",
         "CANARY_DEVELOPMENT.json", "QUALITY_SELECTION_development.json",
         "QUALITY_SELECTION_validation.json", "REFERENCE_WRITES_development.jsonl.gz",
         "REFERENCE_WRITES_validation.jsonl.gz")


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    target = HERE / "SOURCE_FREEZE.json"
    assert not target.exists()
    files = {name: sha(HERE / name) for name in NAMES}
    for split in ("development", "validation"):
        selection = json.loads((HERE / f"QUALITY_SELECTION_{split}.json").read_text())
        assert selection["GT_read"] is False and 0 < len(selection["selected"]) <= 48
        assert selection["writes_sha256"] == files[f"REFERENCE_WRITES_{split}.jsonl.gz"]
    result = dict(status="RQ0_PREDICTION_INPUTS_FROZEN_BEFORE_GT", at_utc=datetime.now(timezone.utc).isoformat(),
                  fixed_base="6320f29bdaf8d33ed64dd7e4888089a0f19e3319", files=files,
                  GT_read=False, API_calls=0)
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "files": len(files)}))


if __name__ == "__main__":
    main()
