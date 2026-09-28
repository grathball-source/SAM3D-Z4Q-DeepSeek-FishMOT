"""Four new event calls in a full B0/B2 copy-on-write Z4Q replay."""
from __future__ import annotations

import gzip
import importlib.util
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("frozen_direct_replay_b2",
                                              HERE.parent / "direct_history_replay/replay.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
from compile import compile_event_evidence  # noqa: E402
preflight_spec = importlib.util.spec_from_file_location("event_evidence_preflight", HERE / "preflight.py")
preflight_module = importlib.util.module_from_spec(preflight_spec)
preflight_spec.loader.exec_module(preflight_module)
source_fact_index = preflight_module.source_fact_index
sources = preflight_module.sources

SYSTEM = ("Compare H1 and H2 as complete physical identity explanations of this full event. "
          "Use pre-entry clean fragments, anonymous risk observations, short post-return fragments, "
          "time-aligned motion, actual core and whole depth changes and quality, and the attached images. "
          "A fragment line certifies only local observation continuity. Fish can turn, change depth and pose. "
          "Endpoint shape, depth or left/right similarity alone is not observed identity continuity; "
          "candidate edges are hypotheses and weak comparisons are not proof. "
          "If one complete explanation is better supported, choose it; if both remain plausible, DEFER. "
          "Return a JSON object with preferred_hypothesis H1, H2, or DEFER; optional reason and citations.")


def body(packet, file_ids, config):
    content = old.wire(packet).decode("utf-8")
    for forbidden in ("SRC-F", "frame_local:n:", "native_mask_key", "SCORE_KEY", "GT2", "GT6", "/home/"):
        assert forbidden not in content, forbidden
    assert len(packet["IMAGE_INDEX"]) == 12
    return dict(model=config["model"],
                messages=[dict(role="system", content=SYSTEM),
                          dict(role="user", content=[dict(type="text", text=content)] +
                               [dict(type="file", file_id=file_ids[x["sha256"]])
                                for x in packet["IMAGE_INDEX"]])],
                thinking=dict(type="enabled"), reasoning_effort="high",
                max_tokens=config["max_tokens"], response_format=dict(type="json_object"), stream=False)


def reserve_from_chars(chars, images, config):
    tokens = int(chars * .6) + images * config["image_token_reserve"] + 1024
    return (tokens * config["peak_input_usd_per_million"] +
            config["max_tokens"] * config["peak_output_usd_per_million"]) / 1_000_000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request(endpoint, payload, content_type):
    assert endpoint in ("/files", "/chat/completions")
    req = urllib.request.Request("https://api.deepseek.com" + endpoint, data=payload,
        headers={"Authorization": "Bearer " + os.environ["DEEPSEEK_API_KEY"],
                 "Content-Type": content_type}, method="POST")
    with urllib.request.build_opener(NoRedirect).open(req, timeout=900) as response:
        raw = response.read(16 * 1024 * 1024 + 1)
    assert len(raw) <= 16 * 1024 * 1024
    return raw


def upload_overview(case, path, expected_sha):
    raw = path.read_bytes()
    assert old.digest(raw) == expected_sha and raw[:8] == b"\x89PNG\r\n\x1a\n"
    boundary = "event-b2-" + expected_sha[:30]
    header = (f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nuser_data\r\n'
              f'--{boundary}\r\nContent-Disposition: form-data; name="expires_after[anchor]"\r\n\r\ncreated_at\r\n'
              f'--{boundary}\r\nContent-Disposition: form-data; name="expires_after[seconds]"\r\n\r\n2592000\r\n'
              f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="overview_{case}.png"\r\n'
              'Content-Type: image/png\r\n\r\n').encode()
    payload = header + raw + f"\r\n--{boundary}--\r\n".encode()
    ledger = HERE / "private_api/UPLOAD_LEDGER.jsonl"
    old.append(ledger, dict(phase="START", case=case, at=time.time(), sha256=expected_sha,
                            bytes=len(raw)))
    try:
        response = request("/files", payload, "multipart/form-data; boundary=" + boundary)
        obj = json.loads(response)
        assert obj["id"].startswith("file-api-") and obj["bytes"] == len(raw)
        old.append(ledger, dict(phase="END", case=case, at=time.time(), sha256=expected_sha,
                                file_id=obj["id"], response_sha256=old.digest(response)))
        old.append(HERE / "public/MEDIA_LEDGER.jsonl",
                   dict(case=case, phase="UPLOADED", sha256=expected_sha, bytes=len(raw),
                        response_sha256=old.digest(response)))
        return obj["id"]
    except Exception as exc:
        old.append(ledger, dict(phase="UNKNOWN", case=case, at=time.time(), sha256=expected_sha,
                                exception_type=type(exc).__name__, http_code=getattr(exc, "code", None)))
        raise RuntimeError("overview upload uncertain; no retry") from None


def infer(case, packet, physical, payload, reserve_usd, spent_upper, config):
    assert spent_upper + reserve_usd <= config["max_usd"]
    private = HERE / "private_api"
    public = HERE / "public"
    old.store(private / f"{case}.body.json", json.loads(payload))
    assert old.sha(private / f"{case}.body.json") == old.digest(payload + b"\n")
    old.store(public / "request_bindings" / f"{case}.json",
              dict(q=packet["q_frame"], body_sha256=old.digest(payload),
                   packet_sha256=old.digest(old.wire(packet)),
                   media_sha256=[x["sha256"] for x in packet["IMAGE_INDEX"]],
                   physical=physical, reserve_peak_usd=reserve_usd))
    old.append(public / "CALL_LEDGER.jsonl",
               dict(phase="START", case=case, at=time.time(), body_sha256=old.digest(payload),
                    reserve_peak_usd=reserve_usd))
    started = time.monotonic()
    try:
        raw = request("/chat/completions", payload, "application/json")
        with (private / f"{case}.raw.json").open("xb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        reply = json.loads(raw)
        answer = reply["choices"][0]
        usage = reply.get("usage") or {}
        prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
        charge = ((prompt * config["peak_input_usd_per_million"] +
                   completion * config["peak_output_usd_per_million"]) / 1_000_000
                  if type(prompt) is int and type(completion) is int else reserve_usd)
        content = answer["message"].get("content")
        choice, parse_status = old.parse_choice(content, answer.get("finish_reason"))
        if isinstance(content, str) and any(s in content for s in ("file-api-", "Bearer ", "DEEPSEEK_API_KEY")):
            public_content = "REDACTED_PROVIDER_OR_SECRET_TOKEN"
        else:
            public_content = content
        record = dict(case=case, at=time.time(), returned_model=reply.get("model"),
                      finish_reason=answer.get("finish_reason"), content=public_content,
                      usage=usage, choice=choice, parse_status=parse_status,
                      latency_seconds=time.monotonic()-started, charge_peak_upper_usd=charge,
                      raw_private_sha256=old.digest(raw),
                      reasoning_private_sha256=old.digest(str(
                          answer["message"].get("reasoning_content") or "").encode()))
        old.store(public / "responses" / f"{case}.json", record)
        old.append(public / "CALL_LEDGER.jsonl",
                   dict(phase="END", case=case, at=time.time(),
                        response_sha256=old.sha(public / "responses" / f"{case}.json"),
                        charge_peak_upper_usd=charge, parse_status=parse_status))
        return choice, parse_status, charge, True
    except Exception as exc:
        old.append(public / "CALL_LEDGER.jsonl",
                   dict(phase="HTTP_UNKNOWN", case=case, at=time.time(),
                        exception_type=type(exc).__name__, http_code=getattr(exc, "code", None),
                        latency_seconds=time.monotonic()-started,
                        charge_reserved_upper_usd=reserve_usd))
        return None, "HTTP_UNKNOWN", reserve_usd, False


def prepare(config, fixed):
    public = HERE / "public"
    assert not public.exists(), "single-use public result directory"
    public.mkdir()
    assert old.read(HERE / "preflight_output_v7/REPORT.json")["status"] == "PASS_NO_MODEL_NO_GT"
    overview_sha, frozen_packet_sha, reserves = {}, {}, {}
    for case in config["cases_by_q"]:
        source = HERE / "preflight_output_v7/overviews" / f"{case}.png"
        target = public / "overviews" / f"{case}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert old.sha(source) == old.sha(target)
        overview_sha[case] = old.sha(target)
        packet = old.read(HERE / "preflight_output_v7/packets" / f"{case}.json")
        assert packet["q_frame"] == fixed[case]["q"]
        frozen_packet_sha[case] = old.digest(old.wire(packet))
        meta = old.read(HERE / "preflight_output_v7/overviews" / f"{case}.metadata.json")
        meta.update(media_file=f"overviews/{case}.png", sha256=overview_sha[case],
                    bytes=target.stat().st_size)
        packet["IMAGE_INDEX"].append(meta)
        assert all(x["frame"] <= packet["q_frame"] for x in packet["IMAGE_INDEX"])
        old.store(public / "requests" / f"{case}.json", packet)
        reserves[case] = reserve_from_chars(len(SYSTEM) + len(old.wire(packet).decode()),
                                            len(packet["IMAGE_INDEX"]), config)
    assert sum(reserves.values()) <= config["max_usd"] and len(reserves) == 4
    code = {name: old.sha(HERE / name) for name in
            ("compile.py", "preflight.py", "replay.py", "score.py", "CONFIG.json")}
    freeze = dict(status="FROZEN_BEFORE_FIRST_INFERENCE", at=time.time(),
                  review_base=config["review_base"], code_sha256=code,
                  source_sha256={str(p): old.sha(p) for p in (old.OBS, old.PROFILES, old.ARCHIVED)},
                  source_logical_sha256=old.sha(old.OLD / "public/REQUESTS_LOGICAL.json"),
                  schedule=[dict(case=c, q=fixed[c]["q"], anchors=fixed[c]["anchors"],
                                 old_images_sha256=[x["sha256"] for x in fixed[c]["images"]])
                            for c in config["cases_by_q"]],
                  overview_sha256=overview_sha, compiled_source_packet_sha256=frozen_packet_sha,
                  reserve_peak_usd=reserves, total_reserve_peak_usd=sum(reserves.values()),
                  max_http=config["max_inference_http"], max_usd=config["max_usd"],
                  rates_source="https://api-docs.deepseek.com/quick_start/pricing/",
                  model=config["model"], exposure=config["exposure"])
    old.store(public / "FREEZE.json", freeze)
    return freeze


def run():
    config = old.read(HERE / "CONFIG.json")
    fixed = old.cases()
    assert [x for x in sorted(fixed, key=lambda c: fixed[c]["q"])] == config["cases_by_q"]
    assert os.environ.get("DEEPSEEK_API_KEY")
    assert all(old.sha(p) == expected for p, expected in
               ((old.OBS, "3fc24d623ca3af22520dc7333ba07ad1479bc766425a2c548b1a13aa922a2e87"),
                (old.PROFILES, "91a154246748146896ac846f0bdd934bb67be874fe823124263650e88ad62f0e")))
    freeze = prepare(config, fixed)
    (HERE / "private_api").mkdir(exist_ok=True)
    file_ids = old.file_ids()
    assert all(x["sha256"] in file_ids for item in fixed.values() for x in item["images"])
    for case in config["cases_by_q"]:
        file_ids[freeze["overview_sha256"][case]] = upload_overview(
            case, HERE / "public/overviews" / f"{case}.png", freeze["overview_sha256"][case])
    obs, depth = sources()
    lineage = source_fact_index()
    refs = {case: {} for case in fixed}
    anchors = {}
    for case, item in fixed.items():
        for role, frame in item["anchors"].items():
            anchors.setdefault(frame, []).append((case, role, item["native"][role]))
    b0 = old.Bridge(old.read(old.Z4Q / "z4q_source/CONFIG.json"))
    b2 = old.Bridge(old.read(old.Z4Q / "z4q_source/CONFIG.json"))
    sys.addaudithook(old.no_truth)
    public = HERE / "public"
    attempts = 0
    spent_upper = 0.0
    send_enabled = True
    events = []
    started = time.monotonic()
    pred = gzip.open(public / "predictions_validation.jsonl.gz", "wt", encoding="utf-8")
    traces = gzip.open(public / "transactions_validation.jsonl.gz", "wt", encoding="utf-8")
    try:
        for frame, archived in zip(range(1, 2889), old.rows(old.ARCHIVED), strict=True):
            row = obs[frame]
            profiles = {x["id"]: dict(x, frame=frame) for x in depth[frame]["observations"]}
            view0 = b0.preview(frame, row["time"], row["observations"], profiles)
            ids0, _ = b0.commit_once(view0)
            view2 = b2.preview(frame, row["time"], row["observations"], profiles)
            transaction = None
            record = dict(frame=frame, status="NATIVE", committed=None)
            for case in config["cases_by_q"]:
                item = fixed[case]
                if frame != item["q"]:
                    continue
                assert len(refs[case]) == 2
                packet, debug = compile_event_evidence(dict(item, case=case), obs, depth,
                    dict(source_fact_by_observed=lineage[case]["by_observed"],
                         case_source_fact_ids=lineage[case]["source_ids"], view=view2,
                         refs=refs[case], images=item["packet"]["IMAGE_INDEX"]))
                assert old.digest(old.wire(packet)) == freeze["compiled_source_packet_sha256"][case]
                frozen = old.read(public / "requests" / f"{case}.json")
                assert frozen["IMAGE_INDEX"][:-1] == packet["IMAGE_INDEX"]
                physical = old.hypotheses(frozen, refs[case], view2, item["native"])
                payload = old.wire(body(frozen, file_ids, config))
                reserve_usd = reserve_from_chars(len(SYSTEM) + len(old.wire(frozen).decode()),
                                                 len(frozen["IMAGE_INDEX"]), config)
                assert reserve_usd == freeze["reserve_peak_usd"][case]
                old.store(HERE / "private_api/source_bindings" / f"{case}.json", debug)
                if send_enabled:
                    assert attempts < config["max_inference_http"]
                    choice, parse_status, charge, http_ok = infer(
                        case, frozen, physical, payload, reserve_usd, spent_upper, config)
                    attempts += 1
                    spent_upper += charge
                    if not http_ok:
                        send_enabled = False
                else:
                    choice, parse_status = None, "UNSENT_AFTER_HTTP_UNKNOWN"
                    old.append(public / "CALL_LEDGER.jsonl",
                               dict(phase="UNSENT", case=case, at=time.time(), reason=parse_status))
                event = dict(case=case, frame=frame, references=refs[case],
                             q_native=item["native"], before=view2["mapping"],
                             choice=choice, parse_status=parse_status,
                             proposal=None, status="FALLBACK", first_reject_reason=None)
                if choice in ("H1", "H2"):
                    wanted = physical[choice]
                    delta = old.changes(choice, physical, view2["mapping"])
                    event["proposal"] = wanted
                    event["changes"] = delta
                    if not delta:
                        event["status"] = "KEEP"
                    elif not wanted["one_to_one"]:
                        event["status"] = "STAGE_REJECTED"
                        event["first_reject_reason"] = "occupied_target"
                    else:
                        transaction, reason = b2.stage(view2, delta)
                        event["status"] = "COMMIT" if transaction else "STAGE_REJECTED"
                        event["first_reject_reason"] = reason
                elif choice == "DEFER":
                    event["status"] = "DEFER"
                else:
                    event["status"] = ("UNSENT_FALLBACK" if parse_status == "UNSENT_AFTER_HTTP_UNKNOWN"
                                       else "HTTP_UNKNOWN_FALLBACK" if parse_status == "HTTP_UNKNOWN"
                                       else "FALLBACK_INVALID")
                events.append(event)
                record.update(status=event["status"], case=case, choice=choice,
                              selected_proposal=dict(displaced=[]),
                              stage_error=event["first_reject_reason"])
            ids2, _ = b2.commit_once(view2, transaction)
            for case, role, native in anchors.get(frame, []):
                refs[case][role] = dict(anchor_frame=frame, native=native,
                    public_id=ids2[native], epoch=b2.epochs[native], branch_version=b2.version)
            if record["status"] == "COMMIT":
                record["committed"] = transaction["changes"]
                record["commit_provenance"] = {
                    str(n): b2.provenance.get(n) for n in transaction["changes"]}
                events[-1]["after"] = ids2
                events[-1]["bridge_version_after"] = b2.version
            out0 = [dict(id=ids0[x["id"]], mask=x["mask"]) for x in row["native"]]
            out2 = [dict(id=ids2[x["id"]], mask=x["mask"]) for x in row["native"]]
            assert out0 == archived["variants"]["Z4Q_STABLE"], frame
            assert [x["mask"] for x in out0] == [x["mask"] for x in out2]
            assert len({x["id"] for x in out2}) == len(out2)
            meta = dict(frame=frame, global_frame=row["global_frame"], time=row["time"])
            pred.write(json.dumps(dict(meta, variants=dict(B0=out0, B2=out2)), separators=(",", ":")) + "\n")
            traces.write(json.dumps(dict(meta, variants=dict(B0=dict(status="NATIVE"), B2=record)),
                                   separators=(",", ":")) + "\n")
            if frame % 200 == 0:
                print("FRAME", frame, "HTTP", attempts, "UPPER_USD", round(spent_upper, 6), flush=True)
    finally:
        pred.close()
        traces.close()
    old.store(public / "EVENTS.json", events)
    old.store(public / "PREDICTIONS_SEALED.json",
              dict(status="SEALED_AWAITING_INDEPENDENT_SCORING", frames=2888,
                   HTTP_attempts=attempts, peak_no_cache_upper_usd=spent_upper,
                   wall_seconds=time.monotonic() - started,
                   predictions_sha256=old.sha(public / "predictions_validation.jsonl.gz"),
                   transactions_sha256=old.sha(public / "transactions_validation.jsonl.gz"),
                   call_ledger_sha256=old.sha(public / "CALL_LEDGER.jsonl")))
    print("SEALED", 2888, "HTTP", attempts, "UPPER_USD", spent_upper, flush=True)


if __name__ == "__main__":
    run()
