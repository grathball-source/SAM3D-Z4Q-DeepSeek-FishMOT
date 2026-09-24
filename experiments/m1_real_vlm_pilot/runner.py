"""Isolated, stateless DeepSeek sender: no repository, score key, or GT inputs."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

HERE = Path("/work")
PRIVATE = HERE / "private"
PUBLIC = HERE / "public"
API = "https://api.deepseek.com"
CAP = 65536
PRICE_IN, PRICE_OUT = .30, 1.20
LIMIT_USD = 5.0


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: object) -> None:
    assert not path.exists(), path
    with path.open("xb") as stream:
        stream.write(encode(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def append(path: Path, value: object) -> None:
    with path.open("ab") as stream:
        stream.write(encode(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def post(endpoint: str, payload: bytes, key: str, content_type: str, timeout: int) -> tuple[bytes, str | None]:
    assert endpoint in ("/files", "/chat/completions")
    request = urllib.request.Request(API + endpoint, data=payload, method="POST",
                                     headers={"Authorization": "Bearer " + key,
                                              "Content-Type": content_type})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
        raw = response.read(16 * 1024 * 1024 + 1)
        assert len(raw) <= 16 * 1024 * 1024
        return raw, response.headers.get("x-ds-trace-id") or response.headers.get("x-request-id")


def key_from_stdin() -> str:
    key = sys.stdin.readline().strip()
    assert key and "\n" not in key and len(key) < 512
    return key


def upload_all(key: str, plan: dict) -> dict[str, str]:
    ledger = PRIVATE / "UPLOAD_LEDGER.jsonl"
    done = {x["sha256"]: x["file_id"] for x in rows(ledger) if x.get("status") == "UPLOADED"}
    wanted = {image["sha256"]: image for req in plan["requests"] for image in req["images"]}
    for number, (digest, item) in enumerate(wanted.items(), 1):
        media = HERE / "media" / item["media_file"]
        raw = media.read_bytes()
        assert sha(raw) == digest and len(raw) == item["bytes"]
        if digest in done:
            continue
        boundary = "m1-" + digest[:30]
        filename = "image_" + digest[:24] + media.suffix
        payload = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\nuser_data\r\n"
                   f"--{boundary}\r\nContent-Disposition: form-data; name=\"expires_after[anchor]\"\r\n\r\ncreated_at\r\n"
                   f"--{boundary}\r\nContent-Disposition: form-data; name=\"expires_after[seconds]\"\r\n\r\n2592000\r\n"
                   f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
                   f"Content-Type: image/{'png' if media.suffix == '.png' else 'jpeg'}\r\n\r\n").encode() + raw + f"\r\n--{boundary}--\r\n".encode()
        append(ledger, dict(status="UPLOAD_STARTED", at_utc=stamp(), sha256=digest,
                            bytes=len(raw), payload_sha256=sha(payload)))
        try:
            response_raw, _ = post("/files", payload, key, "multipart/form-data; boundary=" + boundary, 600)
            response = json.loads(response_raw)
            file_id = response["id"]
            assert file_id.startswith("file-api-") and response["bytes"] == len(raw)
        except Exception as exc:
            append(ledger, dict(status="UPLOAD_FAILED", at_utc=stamp(), sha256=digest,
                                exception_type=type(exc).__name__, http_code=getattr(exc, "code", None)))
            raise RuntimeError("upload failed; no research call made; inspect private upload ledger") from None
        done[digest] = file_id
        append(ledger, dict(status="UPLOADED", at_utc=stamp(), sha256=digest,
                            bytes=len(raw), file_id=file_id,
                            response_sha256=sha(response_raw)))
        if number % 50 == 0 or number == len(wanted):
            print(json.dumps(dict(uploaded=len(done), total=len(wanted))), flush=True)
    assert len(done) == len(wanted)
    return done


def body(req: dict, plan: dict, uploaded: dict[str, str]) -> dict:
    assert req["model_request_id"] in json.loads(req["text"])["request_id"]
    content = [dict(type="text", text=req["text"])]
    for item in req["images"]:
        content.append(dict(type="file", file_id=uploaded[item["sha256"]]))
    result = dict(model="deepseek-flash", messages=[dict(role="system", content=plan["system"]),
                                                     dict(role="user", content=content)],
                  thinking=dict(type="enabled"), reasoning_effort="high", max_tokens=CAP,
                  response_format=dict(type="json_object"), stream=False)
    wire_text = req["text"] + plan["system"]
    for forbidden in ("GT2", "GT6", "SWAP", "KEEP", "B0", "/home/", "P4218132",
                      "P04c303", "P175d295", "P1797ad", "SCORE_KEY", "api_key"):
        assert forbidden not in wire_text
    assert len(result["messages"]) == 2 and len(content) == len(req["images"]) + 1
    return result


def freeze(plan: dict, uploaded: dict[str, str]) -> None:
    assert not (PUBLIC / "REQUESTS_SEALED.json").exists()
    directory = PRIVATE / "bodies"
    directory.mkdir()
    records = []
    for req in plan["requests"]:
        value = body(req, plan, uploaded)
        payload = encode(value)
        assert len(payload) < 48 * 1024 * 1024
        (directory / (req["attempt_id"] + ".json")).write_bytes(payload)
        records.append(dict(attempt_id=req["attempt_id"], arm=req["arm"],
                            case_alias=req["case_alias"], payload_sha256=sha(payload),
                            payload_bytes=len(payload), image_count=len(req["images"]),
                            reserve_peak_usd=req["reserve_peak_usd"]))
    assert len(records) == 30
    save(PUBLIC / "REQUESTS_SEALED.json", dict(status="ALL_30_RESEARCH_BODIES_FROZEN_BEFORE_FIRST_RESEARCH_CALL",
         at_utc=stamp(), code_sha256=sha(Path(__file__).read_bytes()),
         plan_sha256=sha((PRIVATE / "PLAN.json").read_bytes()),
         prompt_sha256=sha((PUBLIC / "PROMPT.txt").read_bytes()),
         two_smoke_slots_reserved=True, records=records))


def smoke_png() -> bytes:
    def chunk(name: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
    rows = b"".join(b"\x00" + (b"\xff\x00\x00" * 128 + b"\x00\x00\xff" * 128)
                    for _ in range(256))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def smoke_body() -> dict:
    picture = "data:image/png;base64," + base64.b64encode(smoke_png()).decode()
    return dict(model="deepseek-flash", messages=[
        dict(role="system", content="Technical image-routing check. Read the actual image, return only JSON."),
        dict(role="user", content=[dict(type="text", text='A synthetic rectangle has two colored halves. Return JSON {"left_color":"red","right_color":"blue"} only if the image itself supports this; otherwise report what it actually shows.'),
                                   dict(type="image_url", image_url=dict(url=picture, detail="original"))])],
        thinking=dict(type="enabled"), reasoning_effort="high", max_tokens=CAP,
        response_format=dict(type="json_object"), stream=False)


def decision(content: object, req: dict, finish: object) -> dict:
    output = None
    try:
        output = json.loads(content) if isinstance(content, str) else None
    except json.JSONDecodeError:
        pass
    bound = (isinstance(output, dict) and output.get("request_id") == req["model_request_id"] and
             output.get("choice") in ("C1", "C2", "INSUFFICIENT"))
    if not bound:
        return dict(decision_valid=False, usable_decision=False, choice=None,
                    grounding_format_valid=False, grounding_reason="NO_BOUND_CHOICE")
    evidence = output.get("evidence")
    reason = None
    if not isinstance(evidence, list) or len(evidence) > 3:
        reason = "EVIDENCE_NOT_LIST_OR_OVER_THREE"
    by_id = {x["image_id"]: x for x in req["images"]}
    if reason is None:
        for citation in evidence:
            if not isinstance(citation, dict) or not all(isinstance(citation.get(k), str) for k in
                   ("image_id", "observation", "distinguishes_because")):
                reason = "MALFORMED_CITATION"
                break
            item = by_id.get(citation["image_id"])
            if item is None:
                reason = "UNSENT_IMAGE_CITED"
                break
            region = citation.get("region_or_time")
            if not isinstance(region, dict):
                reason = "REGION_NOT_OBJECT"
                break
            bbox = region.get("bbox_norm")
            relative = region.get("relative_seconds")
            if bbox is not None and (not isinstance(bbox, list) or len(bbox) != 4 or
                                     not all(type(v) in (float, int) for v in bbox) or
                                     not 0 <= bbox[0] < bbox[2] <= 1 or
                                     not 0 <= bbox[1] < bbox[3] <= 1 or
                                     not any(t["bbox_norm"][0] <= bbox[0] and
                                             t["bbox_norm"][1] <= bbox[1] and
                                             bbox[2] <= t["bbox_norm"][2] and
                                             bbox[3] <= t["bbox_norm"][3] for t in item["tiles"])):
                reason = "BBOX_OUTSIDE_SENT_TILE"
                break
            if relative is not None and (type(relative) not in (float, int) or
                                         not any(abs(relative - t["relative_seconds"]) <= .002
                                                 for t in item["tiles"])):
                reason = "TIME_NOT_ON_SENT_IMAGE"
                break
            if bbox is None and relative is None:
                reason = "NO_REGION_OR_TIME"
                break
    return dict(decision_valid=True, usable_decision=finish == "stop", choice=output["choice"],
                grounding_format_valid=reason is None, grounding_reason=reason,
                evidence=evidence, limitation=output.get("limitation"),
                grounding_semantics="UNKNOWN_NOT_INFERRED_BY_PARSER")


def budget_state(plan: dict) -> tuple[float, dict[str, dict]]:
    events = rows(PUBLIC / "CALL_LEDGER.jsonl")
    starts = {x["attempt_id"]: x for x in events if x["phase"] == "START"}
    ends = {x["attempt_id"]: x for x in events if x["phase"] == "END"}
    assert len(starts) == sum(x["phase"] == "START" for x in events)
    assert len(ends) == sum(x["phase"] == "END" for x in events)
    assert set(ends) == set(starts), "unresolved inference; no automatic retry"
    assert len(starts) <= 32
    charged = sum(x["charged_upper_usd"] for x in ends.values())
    pending = sum(x["reserve_peak_usd"] for x in plan["requests"] if x["attempt_id"] not in starts)
    assert charged + pending <= LIMIT_USD, ("BUDGET_BLOCKED", charged, pending)
    return charged, ends


def invoke(attempt: str, wire: bytes, reserve: float, key: str,
           req: dict | None = None) -> dict:
    ledger = PUBLIC / "CALL_LEDGER.jsonl"
    prior = rows(ledger)
    assert attempt not in {x["attempt_id"] for x in prior if x["phase"] == "START"}
    assert sum(x["phase"] == "START" for x in prior) < 32
    append(ledger, dict(phase="START", attempt_id=attempt, at_utc=stamp(),
                        payload_sha256=sha(wire), reserve_peak_usd=reserve))
    started = time.monotonic()
    try:
        raw, trace = post("/chat/completions", wire, key, "application/json", 900)
        (PRIVATE / "raw").mkdir(exist_ok=True)
        raw_path = PRIVATE / "raw" / (attempt + ".json")
        assert not raw_path.exists()
        raw_path.write_bytes(raw)
        response = json.loads(raw)
        selected = response["choices"][0]
        finish = selected.get("finish_reason")
        content = selected["message"].get("content")
        usage = response.get("usage") or {}
        prompt_tokens, completion_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
        charge = ((prompt_tokens * PRICE_IN + completion_tokens * PRICE_OUT) / 1e6
                  if type(prompt_tokens) is int and type(completion_tokens) is int and
                  prompt_tokens >= 0 and completion_tokens >= 0 else reserve)
        answer = decision(content, req, finish) if req else None
        if req is None:
            try:
                parsed = json.loads(content)
                smoke_ok = parsed.get("left_color", "").lower() == "red" and parsed.get("right_color", "").lower() == "blue" and finish == "stop"
            except (TypeError, ValueError, AttributeError):
                smoke_ok = False
        else:
            smoke_ok = None
        public = dict(attempt_id=attempt, at_utc=stamp(), transport_valid=True,
                      provider_trace_id=trace, response_id=response.get("id"),
                      returned_model=response.get("model"), finish_reason=finish,
                      content=content, usage=usage, decision=answer, smoke_ok=smoke_ok,
                      raw_private_sha256=sha(raw),
                      reasoning_private_sha256=sha(str(selected["message"].get("reasoning_content") or "").encode()),
                      latency_seconds=time.monotonic() - started,
                      charged_upper_usd=charge, reserve_peak_usd=reserve)
        (PUBLIC / "responses").mkdir(exist_ok=True)
        save(PUBLIC / "responses" / (attempt + ".json"), public)
        append(ledger, dict(phase="END", attempt_id=attempt, at_utc=stamp(),
                            transport_valid=True, charged_upper_usd=charge,
                            reserve_peak_usd=reserve, response_sha256=sha(encode(public) + b"\n")))
        assert charge <= reserve + 1e-6, "cost estimate overrun; stop"
        return public
    except Exception as exc:
        if not (PUBLIC / "responses" / (attempt + ".json")).exists():
            append(ledger, dict(phase="END", attempt_id=attempt, at_utc=stamp(),
                                transport_valid=False, exception_type=type(exc).__name__,
                                http_code=getattr(exc, "code", None),
                                charged_upper_usd=reserve, reserve_peak_usd=reserve,
                                latency_seconds=time.monotonic() - started))
        raise RuntimeError("inference failed; ledger sealed, no retry") from None


def main(phase: str) -> None:
    plan = read(PRIVATE / "PLAN.json")
    assert len(plan["requests"]) == 30 and plan["max_tokens"] == CAP
    assert read(PUBLIC / "PREFLIGHT.json")["reserved_total_usd"] <= LIMIT_USD
    key = key_from_stdin()
    if phase == "smoke":
        previous = rows(PUBLIC / "CALL_LEDGER.jsonl")
        started = {x["attempt_id"] for x in previous if x["phase"] == "START"}
        assert started in (set(), {"S001"})
        if started:
            first = [x for x in previous if x["phase"] == "END" and x["attempt_id"] == "S001"]
            assert len(first) == 1 and first[0]["transport_valid"] is False
        attempt = "S002" if started else "S001"
        body_value = smoke_body()
        reserve = ((len(encode(body_value)) + 4096 + 1024) * PRICE_IN + CAP * PRICE_OUT) / 1e6
        assert reserve <= read(PUBLIC / "PREFLIGHT.json")["reserved_two_smoke_usd"] / 2
        result = invoke(attempt, encode(body_value), reserve, key)
        print(json.dumps(dict(phase="SMOKE", ok=result["smoke_ok"],
                              charged_upper_usd=result["charged_upper_usd"])), flush=True)
        assert result["smoke_ok"], "SMOKE_FAILED"
        return
    assert phase == "formal"
    smoke_paths = [PUBLIC / "responses" / f"S{i:03d}.json" for i in (1, 2)]
    assert any(path.exists() and read(path)["smoke_ok"] is True for path in smoke_paths)
    if not (PUBLIC / "REQUESTS_SEALED.json").exists():
        uploaded = upload_all(key, plan)
        freeze(plan, uploaded)
    sealed = read(PUBLIC / "REQUESTS_SEALED.json")
    assert sealed["plan_sha256"] == sha((PRIVATE / "PLAN.json").read_bytes())
    assert sealed["code_sha256"] == sha(Path(__file__).read_bytes())
    lookup = {x["attempt_id"]: x for x in sealed["records"]}
    for item in plan["requests"]:
        charged, completed = budget_state(plan)
        attempt = item["attempt_id"]
        if attempt in completed:
            assert (PUBLIC / "responses" / (attempt + ".json")).exists() or not completed[attempt]["transport_valid"]
            continue
        wire = (PRIVATE / "bodies" / (attempt + ".json")).read_bytes()
        assert sha(wire) == lookup[attempt]["payload_sha256"]
        result = invoke(attempt, wire, item["reserve_peak_usd"], key, item)
        print(json.dumps(dict(attempt_id=attempt, arm=item["arm"],
                              valid=result["decision"]["decision_valid"],
                              usable=result["decision"]["usable_decision"],
                              charged_upper_usd=result["charged_upper_usd"])), flush=True)
        if result["charged_upper_usd"] > item["reserve_peak_usd"] + 1e-6:
            break
    _, completed = budget_state(plan)
    assert all(x["attempt_id"] in completed for x in plan["requests"])
    save(PUBLIC / "DECISIONS_SEALED.json", dict(status="ALL_30_CALLS_SEALED_BEFORE_SCORING",
         at_utc=stamp(), attempts=[dict(attempt_id=x["attempt_id"],
                                   response_sha256=sha((PUBLIC / "responses" / (x["attempt_id"] + ".json")).read_bytes()))
                                   for x in plan["requests"]]))
    print("ALL_30_CALLS_SEALED_BEFORE_SCORING", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("smoke", "formal"))
    main(parser.parse_args().phase)
