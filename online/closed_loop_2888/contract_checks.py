"""Exercise the real copied runner with deterministic DeepSeek-shaped fixtures."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "z4q_source"
sys.path.insert(0, str(SOURCE))
sys.path.insert(1, str(HERE))

import runner  # noqa: E402
from bridge import read  # noqa: E402
from deepseek_gate import gate  # noqa: E402


def fixture(payload, context):
    assert payload["state"]["alternatives"]
    choice = next(iter(payload["state"]["alternatives"]))
    return {"_source": "ENGINEERING_FIXTURE", "answers": [
        {"choice": choice, "support_all": True, "displaced_all": True}
        for _ in range(3)
    ]}


def main():
    runner.gate = gate
    runner.fixture_response = fixture
    import fixture_tests  # noqa: E402

    proposal = {"changes": {9: 1}, "displaced": []}
    compiled = {"proposals": [proposal]}
    good = {"choice": "P01", "support_all": True, "displaced_all": True}
    assert gate([good] * 3, compiled) == (proposal, "qualifying_observation")
    assert gate([good, good, dict(good, choice="DEFER")], compiled)[1] == "vote_disagreement"
    assert gate([dict(good, support_all=False)] * 3, compiled)[0] is None
    assert gate([dict(good, choice="P99")] * 3, compiled)[1] == "unknown_proposal"
    assert gate([dict(good, choice="DEFER")] * 3, compiled)[1] == "DEFER"

    config = read(SOURCE / "CONFIG.json")
    single, first_rows, follow = fixture_tests.legal_single_reconnect(config)
    swaps = fixture_tests.legal_atomic_swap(config)
    withdrawn = fixture_tests.candidate_withdrawal_and_occupancy(config)
    assert first_rows[-1]["status"] == swaps[-1]["status"] == "COMMIT"
    assert follow["final_mapping"] == {9: 1, 2: 2}
    assert withdrawn["committed"] is None
    assert Path(runner.__file__).resolve().parent == SOURCE.resolve()
    result = {
        "status": "PASS_ENGINEERING_FIXTURE_NO_API",
        "checks": ["contract", "unanimity", "abstain", "single_reconnect", "atomic_swap",
                   "five_frame_confirmation", "candidate_withdrawal", "commit_once", "next_frame"],
        "imported_runner": str(Path(runner.__file__).resolve()),
        "runner_sha256": hashlib.sha256(Path(runner.__file__).read_bytes()).hexdigest(),
        "single_commit": first_rows[-1]["committed"],
        "swap_commit": swaps[-1]["committed"],
    }
    target = HERE / "CONTRACT_CHECKS_V2.json"
    assert not target.exists()
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(result["status"])


if __name__ == "__main__":
    main()
