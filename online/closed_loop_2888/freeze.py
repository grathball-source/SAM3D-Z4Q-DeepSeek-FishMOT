"""Freeze the isolated server experiment before real API calls."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ("run_closed_loop.py", "score.py", "deepseek_gate.py", "preflight.py",
         "contract_checks.py", "fixture_tests.py", "PROMPT.txt", "MODEL_CONFIG.json",
         "PROTOCOL.md", "PREFLIGHT_V2.json", "CONTRACT_CHECKS_V2.json",
         "SCORER_FIXTURE.json")


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    target = HERE / "SOURCE_FREEZE.json"
    assert not target.exists()
    sources = [HERE / name for name in NAMES]
    sources.extend(path for path in (HERE / "z4q_source").rglob("*")
                   if path.is_file() and path.suffix in {".py", ".json"})
    inputs = sorted((HERE / "inputs").glob("*.jsonl.gz"))
    assert len(inputs) == 3 and all(path.is_file() for path in sources)
    result = dict(status="FROZEN_BEFORE_REAL_API", exposure="EXPOSED_VALIDATION_FEASIBILITY_NOT_BLIND",
                  files={str(path.relative_to(HERE)): sha(path) for path in sources},
                  inputs={str(path): sha(path) for path in inputs},
                  model="deepseek-flash", votes_per_check=3, API_calls_at_freeze=0)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(result["status"], "files", len(sources), "inputs", len(inputs))


if __name__ == "__main__":
    main()
