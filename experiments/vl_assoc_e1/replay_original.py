"""Replay the sealed online run using its exact saved requests and responses. No API."""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "online/closed_loop_2888"
sys.path.insert(0, str(OLD / "z4q_source"))
sys.path.insert(1, str(OLD))
from bridge import read, rows, sha, stream  # noqa: E402
import runner  # noqa: E402
from deepseek_gate import gate  # noqa: E402

runner.gate = gate


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class SavedResponses:
    def __init__(self, source):
        self.source = source
        self.config = read(OLD / "MODEL_CONFIG.json")
        self.prompt = (OLD / "PROMPT.txt").read_text(encoding="utf-8")
        self.ledger = [json.loads(line) for line in (source / "CALL_LEDGER.jsonl").read_text(encoding="utf-8").splitlines()]
        self.starts = [x for x in self.ledger if x["phase"] == "start"]
        self.completes = {x["id"]: x for x in self.ledger if x["phase"] == "complete"}
        self.used = 0
        assert len(self.starts) == len(self.completes) == 33

    def __call__(self, payload, context):
        body = dict(model=self.config["model"],
                    messages=[dict(role="system", content=self.prompt),
                              dict(role="user", content=canonical(payload))],
                    thinking=self.config["thinking"], reasoning_effort=self.config["reasoning_effort"],
                    response_format=self.config["response_format"], max_tokens=self.config["max_tokens"])
        encoded = canonical(body).encode("utf-8")
        answers = []
        for vote_index in range(1, 4):
            start = self.starts[self.used]
            self.used += 1
            ident = start["id"]
            request_path = self.source / "requests" / f"{ident}.json"
            response_path = self.source / "responses" / f"{ident}.json"
            assert start["frame"] == context["frame"] and start["vote_index"] == vote_index
            assert sha(request_path) == start["request_sha256"]
            assert request_path.read_bytes() == encoded + b"\n", f"CACHE_MISMATCH:{ident}"
            complete = self.completes[ident]
            assert complete["ok"] and complete["valid"] and sha(response_path) == complete["response_sha256"]
            response = read(response_path)
            choice = response["choices"][0]
            assert choice["finish_reason"] == "stop"
            vote = json.loads(choice["message"]["content"])
            assert vote == complete["vote"]
            answers.append(vote)
        return dict(_source="DEEPSEEK_REAL_API", answers=answers)


def main(source):
    seal = read(source / "PREDICTIONS_SEALED.json")
    for filename, field in (("predictions_validation.jsonl.gz", "predictions_sha256"),
                            ("transactions_validation.jsonl.gz", "transactions_sha256"),
                            ("CALL_LEDGER.jsonl", "call_ledger_sha256")):
        assert sha(source / filename) == seal[field], filename
    freeze = read(OLD / "SOURCE_FREEZE.json")
    for filename, digest in freeze["files"].items():
        assert sha(OLD / filename) == digest, filename
    for path, digest in freeze["inputs"].items():
        assert sha(source / "inputs" / Path(path).name) == digest, path
    provider = SavedResponses(source)
    b0 = runner.RepairedRunner(read(OLD / "z4q_source/CONFIG.json"), "B0")
    b1 = runner.RepairedRunner(read(OLD / "z4q_source/CONFIG.json"), "B1", provider)
    history, times = {}, {}
    statuses, votes = Counter(), Counter()
    count = difference_frames = edits = 0
    with gzip.open(source / "predictions_validation.jsonl.gz", "rt", encoding="utf-8") as pred_file, \
         gzip.open(source / "transactions_validation.jsonl.gz", "rt", encoding="utf-8") as tx_file:
        for (row, profiles), old, pred_line, tx_line in zip(
            stream(source / "inputs/observations_validation.jsonl.gz",
                   source / "inputs/features_validation.jsonl.gz", 2888, 9301),
            rows(source / "inputs/predictions_validation_archived.jsonl.gz"), pred_file, tx_file, strict=True
        ):
            frame, now = row["frame"], row["time"]
            history[frame] = {}
            times[frame] = now
            for earlier in list(history):
                if now - times[earlier] > 12:
                    del history[earlier], times[earlier]
            ids0, _, trace0 = b0.step(row, profiles, history)
            ids1, _, trace1 = b1.step(row, profiles, history)
            if trace1.get("committed"):
                trace1["commit_provenance"] = {str(n): b1.bridge.provenance.get(n) for n in trace1["committed"]}
            out0 = [dict(id=ids0[o["id"]], mask=o["mask"]) for o in row["native"]]
            out1 = [dict(id=ids1[o["id"]], mask=o["mask"]) for o in row["native"]]
            assert out0 == old["variants"]["Z4Q_STABLE"]
            expected_pred = dict(frame=frame, global_frame=row["global_frame"], time=now,
                                 variants=dict(B0=out0, B1=out1))
            expected_tx = dict(frame=frame, global_frame=row["global_frame"], time=now,
                               variants=dict(B0=trace0, B1=trace1))
            assert json.loads(pred_line) == expected_pred, f"prediction:{frame}"
            assert json.loads(tx_line) == json.loads(canonical(expected_tx)), f"transaction:{frame}"
            statuses[trace1["status"]] += 1
            votes.update(v["choice"] for v in trace1.get("answers", []) if v is not None)
            difference_frames += out0 != out1
            edits += bool(trace1.get("committed"))
            count += 1
    assert count == seal["frames"] == 2888 and provider.used == seal["HTTP_attempts"] == 33
    result = dict(status="PASS_ORIGINAL_REPLAY_NO_API_NO_GT", base_commit="a566dc6d606ab77696f08f5490486d6f541ebe15",
                  sealed_hashes={key: seal[key] for key in ("predictions_sha256", "transactions_sha256", "call_ledger_sha256")},
                  frames=count, global_first=9301, global_last=12188, exact_prediction_rows=count,
                  exact_transaction_rows=count, request_response_bindings=provider.used,
                  difference_frames=difference_frames, committed_transactions=edits,
                  statuses=dict(statuses), vote_choices=dict(votes),
                  estimated_usd=seal["estimated_usd"], API_calls=0)
    destination = Path(__file__).resolve().parent / "REPLAY_AUDIT.json"
    assert not destination.exists(), destination
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["status"], count, provider.used)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: replay_original.py ORIGINAL_SIDE_DIRECTORY")
    main(Path(sys.argv[1]).resolve())
