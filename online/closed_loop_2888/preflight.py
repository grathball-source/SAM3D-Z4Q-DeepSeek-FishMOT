"""Read-only input and Z4Q baseline check for the isolated DeepSeek experiment."""
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "z4q_source"
sys.path.insert(0, str(SOURCE))

from bridge import read, stream  # noqa: E402
from runner import RepairedRunner  # noqa: E402

INPUTS = HERE / "inputs"
OBS = INPUTS / "observations_validation.jsonl.gz" if INPUTS.is_dir() else Path(r"E:/CAU/D-MOT/tools/sam3_depth_failure_repair_20260917/diagnosis_evidence/diagnosis/observations_validation.jsonl.gz")
PROFILES = INPUTS / "features_validation.jsonl.gz" if INPUTS.is_dir() else Path(r"E:/CAU/D-MOT/tools/sam3_depth_birth_inherit_20260917/completion_evidence/features_r2/features_validation.jsonl.gz")
ARCHIVED = INPUTS / "predictions_validation_archived.jsonl.gz" if INPUTS.is_dir() else Path(r"E:/CAU/D-MOT/tools/sam3_depth_return_guard_20260918/completion_evidence/experiment/predictions_validation.jsonl.gz")


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    for path in (OBS, PROFILES, ARCHIVED):
        assert path.is_file(), path
    runner = RepairedRunner(read(SOURCE / "CONFIG.json"), "B0")
    count = 0
    with gzip.open(ARCHIVED, "rt", encoding="utf-8") as handle:
        for (row, profiles), line in zip(stream(OBS, PROFILES, 2888, 9301), handle, strict=True):
            old = json.loads(line)
            ids, _, record = runner.step(row, profiles)
            output = [{"id": ids[o["id"]], "mask": o["mask"]} for o in row["native"]]
            assert output == old["variants"]["Z4Q_STABLE"], row["frame"]
            assert record["committed"] is None
            count += 1
    assert count == 2888
    result = {
        "status": "B0_EXACT_2888_NO_API_NO_GT",
        "exposure": "EXPOSED_VALIDATION_FEASIBILITY_NOT_BLIND",
        "frames": count,
        "inputs_sha256": {str(path): digest(path) for path in (OBS, PROFILES, ARCHIVED)},
        "z4q_source_sha256": {str(path.relative_to(SOURCE)): digest(path) for path in sorted(SOURCE.rglob("*")) if path.is_file() and path.suffix in {".py", ".json"}},
    }
    target = HERE / "PREFLIGHT_V2.json"
    assert not target.exists(), target
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["status"])


if __name__ == "__main__":
    main()
