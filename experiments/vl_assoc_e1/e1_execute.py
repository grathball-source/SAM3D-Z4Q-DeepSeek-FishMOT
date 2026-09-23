"""Authorized E1 calls only: immutable packets, bounded spend, no GT, no retries."""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from e1_protocol import decode, validate_packet, validate_response
from preflight_e1 import body, read, sha

HERE = Path(__file__).resolve().parent
RUN = HERE / "api_run_20260923"
PRIVATE = RUN / "private_api"
ENDPOINT = "https://api.deepseek.com/chat/completions"
PRICE_INPUT = .30
PRICE_OUTPUT = 1.20


def utc():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def save(path, value):
    with path.open("xb") as handle:
        handle.write(encoded(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def append(path, value):
    with path.open("ab") as handle:
        handle.write(encoded(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def rows(path):
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def no_truth(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes)):
        path = os.fsdecode(args[0]).replace("\\", "/").lower()
        if any(s in path for s in ("offline_matches", "gt_grid", "/labels/", "/truth", "/evaluation/")):
            raise PermissionError("E1 inference cannot read GT")


def verify():
    freeze = read(HERE / "FREEZE.json")
    auth = read(RUN / "RUN_AUTHORIZATION.json")
    config = read(HERE / "CONFIG.json")
    assert sha(HERE / "FREEZE.json") == auth["frozen_freeze_sha256"]
    assert freeze["status"] == "READY_FOR_E1_API" and freeze["model_calls"] == 0
    assert config["allow_api"] is False and auth["allow_api"] is True
    assert auth["E1_paid_call_authorized"] and auth["budget_usd_hard_cap"] == 5.0
    assert auth["max_formal_calls"] == 120 and auth["max_technical_smoke_calls"] == 2
    assert len(freeze["file_sha256"]) == 235
    for name, expected in freeze["file_sha256"].items():
        assert sha(HERE / name) == expected, name
    plan = read(HERE / "COST_PLAN_FINAL.json")
    assert plan["formal_calls"] == 120 and plan["combined_peak_worst_usd"] <= 5.
    assert config["model"] == plan["model"] == "deepseek-flash"
    assert config["max_tokens"] == plan["assumptions"]["max_output_tokens"] == 8192
    return config, plan


def key_from_fifo():
    fifo = PRIVATE / "key.fifo"
    assert not fifo.exists(), "stale key FIFO"
    os.mkfifo(fifo, 0o600)
    print("WAITING_FOR_KEY_FIFO", flush=True)
    try:
        with fifo.open("r", encoding="utf-8") as handle:
            key = handle.readline().strip()
    finally:
        fifo.unlink()
    assert key, "empty key"
    return key


def post(wire, key):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    req = urllib.request.Request(ENDPOINT, data=wire,
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json"}, method="POST")
    with urllib.request.build_opener(NoRedirect).open(req, timeout=180) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
        assert len(raw) <= 8 * 1024 * 1024, "response too large"
        return raw, response.headers.get("x-request-id")


def spent_and_attempts():
    ledger = rows(RUN / "CALL_LEDGER.jsonl")
    started = {x["id"]: x for x in ledger if x["phase"] == "start"}
    completed = {x["id"]: x for x in ledger if x["phase"] == "complete"}
    assert len(started) == sum(x["phase"] == "start" for x in ledger)
    assert len(completed) == sum(x["phase"] == "complete" for x in ledger)
    assert set(completed) == set(started), "unresolved attempt; audit before restart"
    return sum(x["charged_upper_usd"] for x in completed.values()), started, completed


def call(ident, phase, body_value, packet, baseline, plan_row, key, config):
    wire = encoded(body_value)
    request_sha = hashlib.sha256(wire).hexdigest()
    if plan_row:
        assert request_sha == plan_row["payload_sha256"] and len(wire) == plan_row["payload_bytes"]
        reserve = plan_row["reserved_peak_usd"]
    else:
        text_bytes = len(wire) if phase == "smoke_text" else len(encoded(packet)) + 2048
        reserve = ((text_bytes + (1024 if phase == "smoke_image" else 0)) * PRICE_INPUT +
                   config["max_tokens"] * PRICE_OUTPUT) / 1e6
    spent, started, _ = spent_and_attempts()
    assert ident not in started and len(started) < 122
    assert spent + reserve <= 5., "paid budget gate"
    request_private = PRIVATE / "requests" / f"{ident}.json"
    assert not request_private.exists()
    request_private.write_bytes(wire)
    os.chmod(request_private, 0o600)
    public_request = dict(id=ident, phase=phase, packet_id=packet["packet_id"] if packet else None,
                          arm=plan_row["request"] if plan_row else phase,
                          payload_sha256=request_sha, payload_bytes=len(wire),
                          image_sha256=plan_row["image_sha256"] if plan_row else None,
                          reserve_upper_usd=reserve, raw_body="SERVER_PRIVATE_NOT_PUBLISHED")
    save(RUN / "requests" / f"{ident}.json", public_request)
    append(RUN / "CALL_LEDGER.jsonl", dict(phase="start", id=ident, kind=phase,
                                           at_utc=utc(), payload_sha256=request_sha,
                                           reserve_upper_usd=reserve))
    start = time.monotonic()
    try:
        raw, provider_request_id = post(wire, key)
        seconds = time.monotonic() - start
        private_response = PRIVATE / "responses" / f"{ident}.json"
        private_response.write_bytes(raw)
        os.chmod(private_response, 0o600)
        response = json.loads(raw)
        choice = response["choices"][0]
        finish = choice.get("finish_reason")
        content = choice["message"].get("content")
        try:
            output = json.loads(content) if isinstance(content, str) else None
        except json.JSONDecodeError:
            output = None
        if phase == "smoke_image":
            valid, reason = isinstance(output, dict) and output.get("ok") is True and finish == "stop", "IMAGE_ROUTE"
        else:
            valid, reason = validate_response(packet, output) if isinstance(output, dict) else (False, "INVALID_JSON")
            if finish != "stop":
                valid, reason = False, "GENERATION_NOT_FINISHED"
        decision = decode(packet, output, baseline) if packet and phase != "smoke_image" else None
        usage = response.get("usage") or {}
        pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
        charge = ((pt * PRICE_INPUT + ct * PRICE_OUTPUT) / 1e6
                  if type(pt) is int and type(ct) is int and pt >= 0 and ct >= 0 else reserve)
        budget_anomaly = charge > reserve + .005
        if budget_anomaly:
            valid, reason = False, "COST_ESTIMATE_OVERRUN"
        public_response = dict(id=ident, response_id=response.get("id"),
                               returned_model=response.get("model"),
                               system_fingerprint=response.get("system_fingerprint"),
                               finish_reason=finish, content=content, usage=usage,
                               reasoning_content_sha256=hashlib.sha256(str(choice["message"].get("reasoning_content") or "").encode()).hexdigest(),
                               private_raw_response_sha256=hashlib.sha256(raw).hexdigest())
        save(RUN / "responses" / f"{ident}.json", public_response)
        complete = dict(phase="complete", id=ident, kind=phase, at_utc=utc(),
                        seconds=seconds, transport_ok=True, valid=bool(valid), reason=reason,
                        finish_reason=finish, usage=usage, returned_model=response.get("model"),
                        system_fingerprint=response.get("system_fingerprint"),
                        provider_request_id=provider_request_id,
                        charged_upper_usd=charge, reserve_upper_usd=reserve,
                        private_raw_response_sha256=hashlib.sha256(raw).hexdigest(),
                        public_response_sha256=sha(RUN / "responses" / f"{ident}.json"))
        append(RUN / "CALL_LEDGER.jsonl", complete)
        if budget_anomaly:
            raise RuntimeError("cost estimate overrun; stop for audit")
        return complete, decision
    except Exception as exc:
        # Never serialize exception text: HTTP errors can echo headers or prompt data.
        if not (RUN / "responses" / f"{ident}.json").exists():
            append(RUN / "CALL_LEDGER.jsonl", dict(phase="complete", id=ident, kind=phase,
                at_utc=utc(), seconds=time.monotonic() - start, transport_ok=False,
                valid=False, reason=type(exc).__name__, http_code=getattr(exc, "code", None),
                charged_upper_usd=reserve, reserve_upper_usd=reserve))
        raise RuntimeError("call_failed_or_unparsed; no automatic retry") from None


def smoke_bodies(config, dataset):
    packet = dict(schema="VL_ASSOC_RELATIVE_V1", packet_id="SMOKE_TEXT_SCHEMA",
                  snapshot_version="smoke-v1", query_time=1., evidence_cutoff=1.,
                  history=[dict(label=x, samples=[dict(source_time=0.)]) for x in ("A", "B")],
                  current=[dict(label=x, samples=[dict(source_time=1.)]) for x in ("X", "Y")],
                  fixed_observations={}, evidence={"E1": dict(source_time=1., pair="A:X")},
                  pairwise={}, candidates=[dict(candidate_id="C1", full_mapping={"X":"A", "Y":"B"}),
                                           dict(candidate_id="C2", full_mapping={"X":"B", "Y":"A"})])
    assert validate_packet(packet)
    prompt = (HERE / "PROMPT.txt").read_text(encoding="utf-8")
    text_body = body(packet, None, config, prompt)
    first = json.loads((dataset / "manifest.jsonl").open(encoding="utf-8").readline())
    assert first["frame_id"] + 1 == 2
    image = dataset / first["rgb_original"]
    assert sha(image) == first["source_rgb_sha256"] and image.is_file()
    mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
    image_body = dict(model=config["model"], thinking=config["thinking"],
                      reasoning_effort=config["reasoning_effort"],
                      response_format=config["response_format"], max_tokens=config["max_tokens"],
                      messages=[dict(role="system", content="Technical image-route test only. Return JSON with ok=true."),
                                dict(role="user", content=[dict(type="text", text="Return {\"ok\":true}."),
                                   dict(type="image_url", image_url=dict(url="data:" + mime + ";base64," +
                                                                          base64.b64encode(image.read_bytes()).decode("ascii")))])])
    return packet, text_body, image_body, sha(image)


def run_smoke(key, config, dataset):
    assert not (RUN / "SMOKE_REPORT.json").exists()
    packet, text_body, image_body, image_hash = smoke_bodies(config, dataset)
    one, _ = call("S000001", "smoke_text", text_body, packet, "C1", None, key, config)
    if not one["valid"]:
        raise RuntimeError("text schema smoke failed; stop without retuning")
    two, _ = call("S000002", "smoke_image", image_body, None, None, None, key, config)
    if not two["valid"]:
        raise RuntimeError("real image-route smoke failed; stop without retuning")
    save(RUN / "SMOKE_REPORT.json", dict(status="PASS_TWO_TECHNICAL_SMOKE", calls=2,
                                         real_source_image_sha256=image_hash,
                                         first_response=one["public_response_sha256"],
                                         second_response=two["public_response_sha256"],
                                         note="Non-research samples; excluded from E1 event denominator."))
    print("PASS_TWO_TECHNICAL_SMOKE", flush=True)


def run_formal(key, config, plan):
    assert read(RUN / "SMOKE_REPORT.json")["status"] == "PASS_TWO_TECHNICAL_SMOKE"
    assert not (RUN / "DECISIONS_SEALED.json").exists()
    lookup = {x["request"]: x for x in plan["requests"]}
    episodes = {x["packet_id"]: x for path in (HERE / "EPISODES_development.jsonl", HERE / "EPISODES_validation.jsonl")
                for x in rows(path)}
    alias_maps = read(HERE / "PERMUTATION_MAPS.json")
    schedule = read(HERE / "CALL_SCHEDULE.json")
    assert len(schedule) == len(episodes) == 24
    prompt = (HERE / "PROMPT.txt").read_text(encoding="utf-8")
    decisions_path = RUN / "DECISIONS.jsonl"
    spent, started, completed = spent_and_attempts()
    assert len([x for x in started if x.startswith("S")]) == 2
    for event_index, entry in enumerate(schedule):
        pid = entry["packet_id"]
        episode = episodes[pid]
        for arm_index, arm in enumerate(entry["main_order"] + entry["diagnostics"]):
            ident = f"F{event_index*5+arm_index+1:06d}"
            manifest_path = HERE / "request_manifest" / f"{pid}_{arm}.json"
            manifest = read(manifest_path)
            packet_path = HERE / "packets" / manifest["packet_file"]
            assert sha(packet_path) == manifest["packet_sha256"]
            packet = read(packet_path)
            assert validate_packet(packet)
            image_info = manifest["image"]
            image = HERE / "images" / image_info["file"] if image_info else None
            if image:
                assert sha(image) == image_info["sha256"]
            payload = body(packet, image, config, prompt)
            plan_row = lookup[manifest_path.name]
            baseline = episode["baseline_candidate"]
            if arm.endswith("permuted"):
                inverse = {v:k for k,v in alias_maps[pid].items()}
                baseline = inverse[baseline]
            if ident in completed:
                assert any(x["id"] == ident for x in rows(decisions_path)), "completed call lacks decision"
                continue
            complete, decision = call(ident, "formal", payload, packet, baseline,
                                      plan_row, key, config)
            selected = decision["selected"]
            if arm.endswith("permuted"):
                selected = alias_maps[pid][selected]
            result = dict(id=ident, packet_id=pid, arm=arm,
                          selected_original=selected, B0=episode["baseline_candidate"],
                          status=decision["status"], reason=decision["reason"],
                          response_valid=complete["valid"],
                          response_sha256=complete.get("public_response_sha256"),
                          query_time=episode["query_time"], at_utc=complete["at_utc"])
            append(decisions_path, result)
            print("FORMAL", ident, pid, arm, decision["status"], flush=True)
    final_spent, final_started, final_completed = spent_and_attempts()
    decisions = rows(decisions_path)
    assert len(decisions) == 120 and len({x["id"] for x in decisions}) == 120
    assert len(final_started) == len(final_completed) == 122 and final_spent <= 5.
    response_hashes = {p.name: sha(p) for p in sorted((RUN / "responses").glob("*.json"))}
    assert len(response_hashes) == 122
    seal = dict(status="SEALED_BEFORE_INDEPENDENT_E1_SCORING", formal_calls=120,
                technical_smoke_calls=2, E1_GT_read=False,
                freeze_sha256=sha(HERE / "FREEZE.json"),
                authorization_sha256=sha(RUN / "RUN_AUTHORIZATION.json"),
                ledger_sha256=sha(RUN / "CALL_LEDGER.jsonl"),
                decisions_sha256=sha(decisions_path), response_sha256=response_hashes,
                estimated_peak_upper_usd=final_spent,
                invalid_formal=sum(not x["response_valid"] for x in decisions),
                sealed_at_utc=utc())
    save(RUN / "DECISIONS_SEALED.json", seal)
    print("SEALED_E1_NO_GT", final_spent, seal["invalid_formal"], flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=("check", "smoke", "formal"))
    ap.add_argument("--dataset", type=Path)
    args = ap.parse_args()
    config, plan = verify()
    if args.phase == "check":
        assert len(read(HERE / "CALL_SCHEDULE.json")) == 24
        assert len(plan["requests"]) == 120
        print("PASS_EXECUTION_PREFLIGHT_NO_API", flush=True)
        return
    if args.phase == "smoke":
        assert args.dataset and args.dataset.is_dir()
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    for name in ("requests", "responses"):
        (RUN / name).mkdir(exist_ok=True)
        (PRIVATE / name).mkdir(mode=0o700, exist_ok=True)
    with (RUN / "run.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sys.addaudithook(no_truth)
        key = key_from_fifo()
        if args.phase == "smoke":
            run_smoke(key, config, args.dataset)
        else:
            run_formal(key, config, plan)


if __name__ == "__main__":
    main()
