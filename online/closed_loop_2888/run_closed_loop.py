"""Causal B0/B1 replay with real DeepSeek votes. Never reads GT."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "z4q_source"
sys.path.insert(0, str(SOURCE))

import runner as zrunner  # noqa: E402
from bridge import read, save, sha, stream, rows  # noqa: E402
from deepseek_gate import gate  # noqa: E402
from preflight import OBS, PROFILES, ARCHIVED  # noqa: E402

zrunner.gate = gate


def credential():
    value = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not value and os.name == "nt":
        import winreg
        for root, path in ((winreg.HKEY_CURRENT_USER, "Environment"),
                           (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
            try:
                with winreg.OpenKey(root, path) as key:
                    value = winreg.QueryValueEx(key, "DEEPSEEK_API_KEY")[0].strip()
            except FileNotFoundError:
                pass
            if value:
                break
    fifo = HERE / "key.fifo"
    if not value and fifo.exists():
        print("WAITING_FOR_KEY_FIFO", flush=True)
        with fifo.open("r", encoding="utf-8") as handle:
            value = handle.readline().strip()
        fifo.unlink()
    return value


def no_truth(event, args):
    if event != "open" or not args or not isinstance(args[0], (str, bytes)):
        return
    path = os.fsdecode(args[0]).replace("\\", "/").lower()
    if any(token in path for token in ("offline_matches", "gt_grid", "/labels/", "/truth", "/metrics", "/evaluation")):
        raise PermissionError("Inference cannot read scoring data")


def append(path, value):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_gz(handle, value):
    handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    handle.flush()


def verify_freeze():
    freeze = read(HERE / "SOURCE_FREEZE.json")
    for name, expected in freeze["files"].items():
        assert sha(HERE / name) == expected, name
    for name, expected in freeze["inputs"].items():
        assert sha(Path(name)) == expected, name
    assert freeze["status"] == "FROZEN_BEFORE_REAL_API"


class DeepSeekVotes:
    def __init__(self, key, config, prompt):
        self.key, self.config, self.prompt = key, config, prompt
        self.attempts = 0
        self.input_tokens = 0
        self.cost_usd = 0.0
        self.started = time.monotonic()
        self.ledger = HERE / "CALL_LEDGER.jsonl"
        (HERE / "requests").mkdir(exist_ok=False)
        (HERE / "responses").mkdir(exist_ok=False)

    def call(self, request_payload, context):
        choices = {"H0", "DEFER", *request_payload["state"]["alternatives"]}
        body = dict(model=self.config["model"],
                    messages=[dict(role="system", content=self.prompt),
                              dict(role="user", content=json.dumps(request_payload, ensure_ascii=False,
                                                                     separators=(",", ":"), allow_nan=False))],
                    thinking=self.config["thinking"], reasoning_effort=self.config["reasoning_effort"],
                    response_format=self.config["response_format"], max_tokens=self.config["max_tokens"])
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        reserve = ((len(encoded) + 1024) * self.config["peak_usd_per_million_input_tokens"] +
                   self.config["max_tokens"] * self.config["peak_usd_per_million_output_tokens"]) / 1e6
        votes = []
        for vote_index in range(1, self.config["votes_per_check"] + 1):
            if self.attempts >= self.config["max_http_attempts"] or \
               self.cost_usd + reserve > self.config["max_estimated_usd"] or \
               time.monotonic() - self.started > self.config["max_wall_seconds"]:
                raise RuntimeError("formal_budget_stop")
            ident = f"R{self.attempts + 1:06d}"
            request_path = HERE / "requests" / f"{ident}.json"
            request_path.write_text(encoded.decode("utf-8") + "\n", encoding="utf-8")
            append(self.ledger, dict(phase="start", id=ident, frame=context["frame"],
                                     vote_index=vote_index, request_sha256=sha(request_path),
                                     reserve_usd=reserve, at=time.time()))
            self.attempts += 1
            start = time.monotonic()
            try:
                class NoRedirect(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self, *args, **kwargs):
                        return None

                req = urllib.request.Request(self.config["base_url"], data=encoded,
                    headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"},
                    method="POST")
                with urllib.request.build_opener(NoRedirect).open(req, timeout=self.config["timeout_seconds"]) as response:
                    raw = json.load(response)
                seconds = time.monotonic() - start
                response_path = HERE / "responses" / f"{ident}.json"
                response_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                usage = raw.get("usage") or {}
                prompt_tokens = usage.get("prompt_tokens")
                completion_tokens = usage.get("completion_tokens")
                if all(type(v) is int and v >= 0 for v in (prompt_tokens, completion_tokens)):
                    charge = (prompt_tokens * self.config["peak_usd_per_million_input_tokens"] +
                              completion_tokens * self.config["peak_usd_per_million_output_tokens"]) / 1e6
                    self.input_tokens += prompt_tokens
                else:
                    charge = reserve
                self.cost_usd += charge
                choice = raw["choices"][0]
                vote = json.loads(choice["message"]["content"])
                valid = (choice["finish_reason"] == "stop" and isinstance(vote, dict) and
                         set(vote) == {"choice", "support_all", "displaced_all"} and
                         vote["choice"] in choices and
                         type(vote["support_all"]) is bool and type(vote["displaced_all"]) is bool)
                if not valid:
                    vote = None
                append(self.ledger, dict(phase="complete", id=ident, frame=context["frame"],
                    vote_index=vote_index, ok=True, valid=valid, vote=vote,
                    seconds=seconds, usage=usage, returned_model=raw.get("model"),
                    system_fingerprint=raw.get("system_fingerprint"), charge_usd=charge,
                    response_sha256=sha(response_path)))
                votes.append(vote)
            except Exception as exc:
                if not isinstance(exc, (KeyError, IndexError, TypeError, ValueError)):
                    self.cost_usd += reserve
                    append(self.ledger, dict(phase="complete", id=ident, frame=context["frame"],
                        vote_index=vote_index, ok=False, exception_type=type(exc).__name__,
                        http_code=getattr(exc, "code", None), charge_usd=reserve,
                        seconds=time.monotonic() - start))
                    raise RuntimeError("real_service_or_storage_failure") from None
                # A malformed model response is an explicit invalid vote, never retried.
                append(self.ledger, dict(phase="invalid_contract", id=ident, frame=context["frame"],
                    vote_index=vote_index, exception_type=type(exc).__name__))
                votes.append(None)
            if self.input_tokens > self.config["max_input_tokens"]:
                raise RuntimeError("input_token_budget_stop")
        return {"_source": "DEEPSEEK_REAL_API", "answers": votes}


def main():
    assert read(HERE / "CONTRACT_CHECKS_V2.json")["status"] == "PASS_ENGINEERING_FIXTURE_NO_API"
    assert read(HERE / "PREFLIGHT_V2.json")["status"] == "B0_EXACT_2888_NO_API_NO_GT"
    assert not (HERE / "MODEL_RUN_STARTED.json").exists()
    for name in ("CALL_LEDGER.jsonl", "predictions_validation.jsonl.gz",
                 "transactions_validation.jsonl.gz", "PREDICTIONS_SEALED.json"):
        assert not (HERE / name).exists(), name
    verify_freeze()
    key = credential()
    assert key, "DEEPSEEK_API_KEY unavailable"
    config = read(HERE / "MODEL_CONFIG.json")
    prompt = (HERE / "PROMPT.txt").read_text(encoding="utf-8")
    sys.addaudithook(no_truth)
    save(HERE / "MODEL_RUN_STARTED.json", dict(at=time.time(), model=config["model"],
         source_freeze_sha256=sha(HERE / "SOURCE_FREEZE.json"), frames=2888,
         exposure=config["exposure"], API_key_present=True))
    client = DeepSeekVotes(key, config, prompt)
    b0 = zrunner.RepairedRunner(read(SOURCE / "CONFIG.json"), "B0")
    b1 = zrunner.RepairedRunner(read(SOURCE / "CONFIG.json"), "B1", client.call)
    history, times = {}, {}
    count = 0
    try:
        with gzip.open(HERE / "predictions_validation.jsonl.gz", "wt", encoding="utf-8") as predictions, \
             gzip.open(HERE / "transactions_validation.jsonl.gz", "wt", encoding="utf-8") as transactions:
            for (row, profiles), old in zip(stream(OBS, PROFILES, 2888, 9301), rows(ARCHIVED), strict=True):
                f, now = row["frame"], row["time"]
                history[f] = {}
                times[f] = now
                for earlier in list(history):
                    if now - times[earlier] > 12:
                        del history[earlier], times[earlier]
                ids0, _, trace0 = b0.step(row, profiles, history)
                ids1, _, trace1 = b1.step(row, profiles, history)
                if trace1.get("committed"):
                    trace1["commit_provenance"] = {
                        str(n): b1.bridge.provenance.get(n) for n in trace1["committed"]
                    }
                out0 = [{"id": ids0[o["id"]], "mask": o["mask"]} for o in row["native"]]
                out1 = [{"id": ids1[o["id"]], "mask": o["mask"]} for o in row["native"]]
                assert out0 == old["variants"]["Z4Q_STABLE"], f
                assert [x["mask"] for x in out0] == [x["mask"] for x in out1]
                assert len({x["id"] for x in out1}) == len(out1)
                meta = dict(frame=f, global_frame=row["global_frame"], time=now)
                write_gz(predictions, dict(meta, variants=dict(B0=out0, B1=out1)))
                write_gz(transactions, dict(meta, variants=dict(B0=trace0, B1=trace1)))
                count += 1
                if count % 100 == 0:
                    save(HERE / "RUN_PROGRESS.json", dict(status="RUNNING", frames=count,
                        attempts=client.attempts, cost_usd=client.cost_usd, input_tokens=client.input_tokens))
        assert count == 2888
        verify_freeze()
        seal = dict(status="SEALED_AWAITING_INDEPENDENT_SCORING", frames=count,
                    model=config["model"], exposure=config["exposure"],
                    HTTP_attempts=client.attempts, estimated_usd=client.cost_usd,
                    input_tokens=client.input_tokens,
                    predictions_sha256=sha(HERE / "predictions_validation.jsonl.gz"),
                    transactions_sha256=sha(HERE / "transactions_validation.jsonl.gz"),
                    call_ledger_sha256=sha(client.ledger),
                    source_freeze_sha256=sha(HERE / "SOURCE_FREEZE.json"))
        save(HERE / "PREDICTIONS_SEALED.json", seal)
        print("PREDICTIONS_SEALED", "frames", count, "HTTP", client.attempts, flush=True)
    except Exception as exc:
        save(HERE / "RUN_FAILURE.json", dict(status="INCOMPLETE_NOT_SCORABLE", frames=count,
            attempts=client.attempts, cost_usd=client.cost_usd,
            exception_type=type(exc).__name__, reason=str(exc) if isinstance(exc, (AssertionError, RuntimeError)) else "local_error"))
        raise


if __name__ == "__main__":
    main()
