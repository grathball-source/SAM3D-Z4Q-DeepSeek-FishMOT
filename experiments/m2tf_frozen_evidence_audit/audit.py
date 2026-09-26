"""Read-only, post-score audit of the sealed M2-T batch. No network or model calls."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

OLD = Path(__file__).resolve().parents[1] / "m2t_motion_first"
SPEC = importlib.util.spec_from_file_location("m2t_frozen_score", OLD / "score.py")
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    with open(path, encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path, obj):
    path = Path(path)
    assert not path.exists(), path
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_lines(path, items):
    path = Path(path)
    assert not path.exists(), path
    path.write_text("".join(json.dumps(x, ensure_ascii=False, allow_nan=False) + "\n" for x in items), encoding="utf-8")


def evidence_status(evidence, sent):
    """Same valid-input contract as the sealed scorer; invalid input always has two returns."""
    if not isinstance(evidence, list):
        return "EVIDENCE_NOT_ARRAY", []
    if not evidence:
        return "EVIDENCE_EMPTY", []
    by_id = {image["image_id"]: image for image in sent}
    seen = set()
    for cite in evidence:
        if not isinstance(cite, dict) or not all(k in cite for k in
                ("image_id", "observation_tokens", "relative_seconds", "observation")):
            return "MALFORMED_CITATION", sorted(seen)
        image = by_id.get(cite["image_id"])
        if image is None or image["kind"] != "G":
            return "UNSENT_OR_NON_GEOMETRY_IMAGE", sorted(seen)
        tokens = cite["observation_tokens"]
        if not isinstance(tokens, list) or not tokens or not all(isinstance(x, str) for x in tokens):
            return "MISSING_OBSERVATION_TOKENS", sorted(seen)
        if not set(tokens) <= set(image["observation_tokens"]):
            return "UNSENT_OBSERVATION_TOKEN", sorted(seen)
        when = cite["relative_seconds"]
        if type(when) not in (int, float) or not math.isfinite(when) or abs(when - image["relative_seconds"]) > .002:
            return "UNSENT_TIME", sorted(seen)
        if not isinstance(cite["observation"], str) or not cite["observation"].strip():
            return "EMPTY_OBSERVATION", sorted(seen)
        seen.add((cite["image_id"], image["relative_seconds"]))
    return None, sorted(seen)


score.evidence_status = evidence_status


def parse(content, request_id, sent, endpoint_ids):
    # Python's default JSON parser silently replaces duplicate edge keys.
    duplicate = []
    def unique(pairs):
        keys = [key for key, _ in pairs]
        duplicate.extend(key for key, n in Counter(keys).items() if n > 1)
        return dict(pairs)
    try:
        json.loads(content, object_pairs_hook=unique)
    except (TypeError, ValueError):
        return dict(schema_valid=False, schema_reason="INVALID_JSON", edges={}, choice="ABSTAIN")
    if duplicate:
        return dict(schema_valid=False, schema_reason="DUPLICATE_JSON_KEY", edges={}, choice="ABSTAIN")
    return score.parse(content, request_id, sent, endpoint_ids)


def match_rows(path, wanted):
    result = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["frame"] in wanted:
                result[row["frame"]] = row
    assert set(result) == wanted, (path, sorted(wanted - set(result)))
    return result


def unique_gt(match, native):
    selected = [x for x in match["objects"] if int(x["native_id"]) == native]
    if len(selected) != 1:
        return dict(status="NO_UNIQUE_GT_OBSERVATION", reason="MISSING_OR_DUPLICATE_NATIVE", gt_id=None)
    obj = selected[0]
    result = dict(status="UNIQUE" if obj.get("gt_id") is not None and not obj.get("ambiguity") else
                  "NO_UNIQUE_GT_OBSERVATION", gt_id=obj.get("gt_id") if not obj.get("ambiguity") else None,
                  iou=obj.get("iou"), ambiguity=obj.get("ambiguity"),
                  candidate_gt_ids=obj.get("candidate_gt_ids"),
                  candidate_gt_count=obj.get("candidate_gt_count"),
                  competing_prediction_count=obj.get("competing_prediction_count"))
    if result["status"] == "UNIQUE":
        rivals = [x for x in match["objects"] if x is not obj and not x.get("ambiguity") and x.get("gt_id") == result["gt_id"]]
        if rivals:
            result.update(status="NO_UNIQUE_GT_OBSERVATION", gt_id=None, reason="MULTIPLE_PREDICTIONS_FOR_GT")
    return result


def claim_usage(observation, token, endpoint_roles, source_role, citation_token_count):
    if endpoint_roles:
        return "ENDPOINT_REFERENCE"
    suffix = token.split(":")[-1]
    text = observation.lower()
    role = re.escape(source_role.lower())
    if citation_token_count == 1 and re.search(r"^\s*(?:the\s+)?" + role + r"(?:'s)?\b", text) and re.search(
            r"track|continu|candidate|observ|trajectory|path|reach|mov|at\b", text):
        return "PATH_STEP"
    # Keep a competing fish in the same citation separate from the claimed path.
    at = text.find(suffix.lower())
    if at < 0:
        return "AMBIGUOUS_USAGE"
    prefix = re.split(r",|;|\bwhile\b|\bwhereas\b|\bbut\b|\band\b", text[:at])[-1]
    if re.search(r"\b" + role + r"(?:'s)?\b", prefix) and re.search(
            r"track|continu|candidate|observ|trajectory|path|reach|mov|at\b", prefix):
        return "PATH_STEP"
    if re.search(r"\b(?:a|b|x|y)(?:'s)?\b", prefix) or re.search(
            r"other|separate|different|competing|alternative", prefix):
        return "COMPARISON_OBJECT"
    return "AMBIGUOUS_USAGE"


def audit(run, repo, out, only_case=None):
    old = repo / "experiments/m2t_motion_first"
    artifact = read(old / "ARTIFACT_MANIFEST.json")
    assert Path(artifact["run_root"]) == run
    # Verify every archived restricted file, not merely the status of a directory.
    restricted = artifact["restricted"]
    checked = []
    for item in restricted:
        path = Path(item["path"])
        assert path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], path
        checked.append(item["path"])
    source = read(run / "public/SOURCE_MANIFEST.json")
    requests = read(run / "public/REQUEST_MANIFEST.json")
    plan = read(run / "sender/PLAN.json")
    assert sha(run / "sender/PLAN.json") == read(run / "sender/public/REQUESTS_SEALED.json")["plan_sha256"]
    assert source == read(old / "SOURCE_MANIFEST.json") and requests == read(old / "REQUEST_MANIFEST.json")
    assert sha(run / "public/SOURCE_MANIFEST.json") == sha(old / "SOURCE_MANIFEST.json")
    assert sha(run / "public/REQUEST_MANIFEST.json") == sha(old / "REQUEST_MANIFEST.json")
    assert sha(run / "sender/public/REQUESTS_SEALED.json") == sha(old / "REQUESTS_SEALED.json")
    assert sha(run / "sender/public/RESPONSES_SEALED.json") == sha(old / "RESPONSES_SEALED.json")
    assert score.verify_seal(run, requests)
    calls = rows(run / "sender/public/CALL_LEDGER.jsonl")
    starts = [x["attempt_id"] for x in calls if x["phase"] == "START"]
    ends = [x["attempt_id"] for x in calls if x["phase"] == "END"]
    assert len(starts) == len(ends) == len(set(starts)) == len(set(ends)) == 26
    assert set(starts) == set(ends) == {"S001"} | {x["attempt_id"] for x in requests["requests"]}
    req_seal = read(run / "sender/public/REQUESTS_SEALED.json")
    response_seal = read(run / "sender/public/RESPONSES_SEALED.json")
    assert sha(run / "sender/public/REQUESTS_SEALED.json") == read(old / "SCORE_PROVENANCE.json")["request_seal_sha256"]
    assert sha(run / "sender/public/RESPONSES_SEALED.json") == read(old / "SCORE_PROVENANCE.json")["response_seal_sha256"]
    # The exposed answer comes from the frozen score key, opened only after both seals.
    key_path = Path(read(old / "SCORE_PROVENANCE.json")["exposed_score_key_path"])
    assert sha(key_path) == read(old / "SCORE_PROVENANCE.json")["exposed_score_key_sha256"]
    key = {x["case_alias"]: x["private_score_answer"] for x in read(key_path)["cases"]}
    ao1_path = Path("/home/xiongxiong/ao1_input_fidelity_20260924/range_corrected_run/public/SOURCE_MANIFEST.json")
    assert sha(ao1_path) == source["ao1_source_sha256"]
    ao1 = {x["case_alias"]: x for x in read(ao1_path)["cases"]}
    token_ledger = read(run / "private/TOKEN_LEDGER.json")
    completed_uploads = [x for x in rows(run / "sender/private/UPLOAD_LEDGER.jsonl") if x["phase"] == "UPLOAD_END"]
    uploads = {x["sha256"]: x["file_id"] for x in completed_uploads}
    assert len(completed_uploads) == len(uploads)
    assert len(uploads) == 234  # 233 research media and the prior technical smoke.
    cases = {x["case_alias"]: x for x in source["cases"]}
    plan_map = {x["attempt_id"]: x for x in plan["requests"]}
    public_rows = {x["attempt_id"]: x for x in rows(old / "ATTEMPT_RESULTS.jsonl")}
    assert len(cases) == 5 and len(plan_map) == len(public_rows) == 25
    wanted = defaultdict(set)
    for case in source["cases"]:
        wanted[case["split"]].update(case["all_frames"])
    paths = {"validation": Path("/home/xiongxiong/dmot-experiments/sam3_depth_return_guard_20260918/experiment/offline_matches_validation.jsonl.gz"),
             "development": Path("/home/xiongxiong/dmot-experiments/sam3_depth_return_guard_20260918/experiment/offline_matches_development.jsonl.gz")}
    matches = {split: match_rows(paths[split], frames) for split, frames in wanted.items()}
    binding, edges, coverage, divergence, parity = [], [], [], [], []
    request_records = {x["attempt_id"]: x for x in req_seal["records"]}
    response_records = {x["attempt_id"]: x for x in response_seal["records"]}
    for alias in cases:
        assert request_records[alias + "-G-SEQ"]["payload_sha256"] == request_records[
            alias + "-G-SEQ-REPEAT"]["payload_sha256"]
        assert request_records[alias + "-G+AP"]["payload_sha256"] == request_records[
            alias + "-G+AP-REPEAT"]["payload_sha256"]
    for request in requests["requests"]:
        ident, alias = request["attempt_id"], request["case_alias"]
        if only_case and alias != only_case:
            continue
        case, planned = cases[alias], plan_map[ident]
        assert planned["arm"] == request["arm"] and planned["request_id"] == request["request_id"]
        assert [(x["image_id"], x["sha256"]) for x in planned["images"]] == [
            (x["image_id"], x["sha256"]) for x in request["images"]]
        body_path = run / "sender/private/bodies" / (ident + ".json")
        body = read(body_path)
        assert sha(body_path) == request_records[ident]["payload_sha256"]
        assert len(body["messages"]) == 2 and [x["role"] for x in body["messages"]] == ["system", "user"]
        content = body["messages"][1]["content"]
        expect = [("file", uploads[x["sha256"]]) for x in planned["images"] if x["kind"] == "G"]
        if planned["ap_text"]:
            expect += [("file", uploads[x["sha256"]]) for x in planned["images"] if x["kind"] == "AP"]
        actual = [(x["type"], x.get("file_id")) for x in content if x["type"] == "file"]
        assert actual == expect  # Ordered, individual file mapping; never publish IDs.
        texts = [x["text"] for x in content if x["type"] == "text"]
        assert texts == [planned["core_text"]] + ([planned["ap_text"]] if planned["ap_text"] else [])
        for image in planned["images"]:
            pixel = run / "sender/media" / image["media_file"]
            assert pixel.stat().st_size == image["bytes"] and sha(pixel) == image["sha256"]
        response_path = run / "sender/public/responses" / (ident + ".json")
        assert sha(response_path) == response_records[ident]["response_sha256"] == sha(old / "responses" / (ident + ".json"))
        response = read(response_path)
        frame_to_image = dict(zip(case["all_frames"], case["g_images"], strict=True))
        endpoint_ids = {frame_to_image[frame]["image_id"] for frame in case["endpoint_frames"]}
        parsed = parse(response["content"], request["request_id"], request["images"], endpoint_ids)
        frozen = public_rows[ident]
        ao1_choice = case["candidate_to_AO1_choice"].get(parsed["choice"])
        status = "ABSTAIN" if parsed["choice"] == "ABSTAIN" else "CORRECT" if ao1_choice == key[alias] else "WRONG"
        assert parsed["schema_valid"] == frozen["schema_valid"] and parsed["choice"] == frozen["decoded_relation"]
        assert ao1_choice == frozen["ao1_choice"] and status == frozen["identity_status"]
        for edge in score.EDGES:
            for field in ("status", "relation", "cue", "evidence_reason", "cited_times", "middle_cited"):
                actual = parsed["edges"][edge][field]
                if field == "cited_times":
                    actual = [list(x) for x in actual]
                assert actual == frozen["edges"][edge][field], (ident, edge, field)
        parity.append(dict(attempt_id=ident, edge_status_equal=True, decoded_equal=True, identity_equal=True))
        scene = json.loads(planned["core_text"])
        scene_frames = {x["image_id"]: x for x in scene["scene_frames"]}
        private = {x["frame"]: x for x in token_ledger[alias]}
        assert set(private) == set(case["all_frames"])
        frame_by_image = {image["image_id"]: frame for frame, image in frame_to_image.items()}
        ao1_roles = ao1[alias]["V1"]["roles"]
        anchors = defaultdict(set)
        anchor_rows = []
        for role, old_role in case["alias_to_AO1_role"].items():
            for item in ao1_roles:
                if item["role"] != old_role:
                    continue
                match = matches[case["split"]][item["frame"]]
                gt = unique_gt(match, int(item["native_mask_key"].split(":")[1]))
                anchors[role].add(gt["gt_id"] if gt["status"] == "UNIQUE" else None)
                anchor_rows.append(dict(role=role, original_role=old_role, frame=item["frame"],
                                        mask_key=item["native_mask_key"], gt=gt))
        anchor_status = {role: ("UNIQUE" if len(ids) == 1 and None not in ids else "ROLE_ANCHOR_AMBIGUOUS")
                         for role, ids in anchors.items()}
        binding.append(dict(attempt_id=ident, case_alias=alias, arm=request["arm"], body_sha256=sha(body_path),
                            response_sha256=sha(response_path), ordered_image_count=len(expect),
                            ordered_image_sha256=[x["sha256"] for x in planned["images"]],
                            ordered_mapping_verified=True, source_manifest_verified=True,
                            token_ledger_verified=True, frozen_answer=key[alias],
                            candidate_to_AO1_choice=case["candidate_to_AO1_choice"],
                            alias_to_AO1_role=case["alias_to_AO1_role"], anchor_rows=anchor_rows,
                            anchor_status=anchor_status))
        image_map = {x["image_id"]: x for x in request["images"] if x["kind"] == "G"}
        cites_by_edge = defaultdict(list)
        for edge in score.EDGES:
            detail = parsed["edges"][edge]
            for cite_index, cite in enumerate(detail["evidence"]):
                image_id = cite["image_id"]
                frame = frame_by_image[image_id]
                frame_meta = private[frame]
                assert frame_meta["image_sha256"] == image_map[image_id]["sha256"]
                original = next(x for x in case["source_rows"] if x["frame"] == frame)
                assert frame_meta["source_time"] == original["source_time"]
                assert abs(image_map[image_id]["relative_seconds"] -
                           (original["source_time"] - case["query_time"])) <= .002
                public_obs = {x["token"]: x for x in scene_frames[image_id]["observations"]}
                private_obs = {x["token"]: x for x in frame_meta["observations"]}
                refs = []
                for token in cite["observation_tokens"]:
                    obs = private_obs[token]
                    assert token in public_obs and public_obs[token]["center_norm"] == obs["center_norm"]
                    mask = obs["native_mask_key"]
                    native = int(mask.split(":")[1])
                    assert any(x["mask_key"] == mask and int(x["native_id"]) == native for x in original["predicted_masks"])
                    gt = unique_gt(matches[case["split"]][frame], native)
                    usage = claim_usage(cite["observation"], token, obs["endpoint_roles"], edge[0],
                                        len(cite["observation_tokens"]))
                    refs.append(dict(token=token, source_native=native, mask_key=mask,
                                     endpoint_roles=obs["endpoint_roles"], gt=gt, usage=usage))
                item = dict(citation_index=cite_index, image_id=image_id, image_sha256=image_map[image_id]["sha256"],
                            frame=frame, relative_seconds=cite["relative_seconds"],
                            original_observation=cite["observation"], token_bindings=refs)
                cites_by_edge[edge].append(item)
            edges.append(dict(attempt_id=ident, case_alias=alias, arm=request["arm"], edge=edge,
                              raw_relation=detail["relation"], cue=detail["cue"], status=detail["status"],
                              gaps_or_assumptions=detail["gaps_or_assumptions"],
                              competing_explanation=detail["competing_explanation"], citations=cites_by_edge[edge]))
        sent_g = [x for x in request["images"] if x["kind"] == "G"]
        sent_frames = [frame_by_image[x["image_id"]] for x in sent_g]
        b01_middle = [frame for frame in sent_frames if 1321 < frame < 1484] if alias == "B01" else []
        ordered_times = [x["relative_seconds"] for x in sent_g]
        gap_claims = []
        for edge in score.EDGES:
            detail = parsed["edges"][edge]
            claim = detail["gaps_or_assumptions"]
            if re.search(r"gap|unobserv|missing|缺|间隔|未观察|无观测", claim, re.I):
                named = list(dict.fromkeys(re.findall(r"\bG(\d{3})\b", claim)))
                item = dict(edge=edge, original_text=claim,
                            persistent_cross_frame_identity_label_sent=False,
                            sent_g_count_for_attempt=len(sent_g))
                if len(named) >= 2:
                    left_id, right_id = "G" + named[0], "G" + named[1]
                    left, right = sorted((frame_by_image[left_id], frame_by_image[right_id]))
                    middle = [f for f in sent_frames if left < f < right]
                    unknown = sum(unique_gt(matches[case["split"]][f], int(mask["native_id"]))["status"] != "UNIQUE"
                                  for f in middle for row in case["source_rows"] if row["frame"] == f
                                  for mask in row["predicted_masks"])
                    sequence = [x["relative_seconds"] for x in sent_g
                                if left <= frame_by_image[x["image_id"]] <= right]
                    absence = bool(re.search(r"unobserved interval|"
                                             r"no intermediate (?:g |image |frame |)observations?(?=[.;,]|$| exist| were| are| available)|"
                                             r"无中间观测|无观测", claim, re.I))
                    item.update(located=True, boundary_images=[left_id, right_id], boundary_frames=[left, right],
                                middle_sent_frames=middle, middle_sent_count=len(middle),
                                middle_predicted_observation_count=sum(len(private[f]["observations"]) for f in middle),
                                middle_no_unique_gt_observation_count=unknown,
                                middle_acquisition_frames_not_sent=right-left-1-len(middle),
                                max_sent_time_step_seconds=max((b-a for a,b in zip(sequence, sequence[1:])),
                                                               default=None),
                                model_middle_citation_count=sum(left < frame_by_image[x["image_id"]] < right
                                                                for x in detail["evidence"]),
                                coverage_conflict=absence and len(middle) > 0)
                else:
                    item.update(located=False, reason="NO_EXPLICIT_TWO_G_BOUNDARIES",
                                middle_sent_count=None, middle_predicted_observation_count=None,
                                coverage_conflict=None)
                gap_claims.append(item)
        coverage.append(dict(attempt_id=ident, case_alias=alias, arm=request["arm"],
                             sent_g_count=len(sent_g), sent_frame_count=len(sent_g),
                             max_sent_time_step_seconds=max(b-a for a,b in zip(ordered_times, ordered_times[1:]))
                             if len(ordered_times) > 1 else None,
                             b01_g009_to_g032_sent_middle_frames=b01_middle if alias == "B01" else None,
                             b01_middle_predicted_observation_count=sum(len(private[frame]["observations"])
                                for frame in b01_middle) if alias == "B01" else None,
                             b01_middle_acquisition_frames_not_sent=(1484 - 1321 - 1 - len(b01_middle))
                                if alias == "B01" else None,
                             gap_claims=gap_claims))
        for edge in score.EDGES:
            reference = edge[0]
            ref_ids = anchors[reference]
            status = anchor_status[reference]
            path = []
            for cite in cites_by_edge[edge]:
                for token in cite["token_bindings"]:
                    if token["usage"] != "PATH_STEP":
                        continue
                    relation = ("ROLE_REFERENCE_AMBIGUOUS" if status != "UNIQUE" else
                                "NO_UNIQUE_GT_OBSERVATION" if token["gt"]["status"] != "UNIQUE" else
                                "CITED_OBJECT_SAME_GT_AS_REFERENCE" if token["gt"]["gt_id"] in ref_ids else
                                "CITED_OBJECT_OTHER_GT")
                    path.append(dict(frame=cite["frame"], token=token["token"], relation=relation,
                                     gt_id=token["gt"]["gt_id"]))
            path.sort(key=lambda x: x["frame"])
            certified = None
            first = None
            for step in path:
                if step["relation"] == "CITED_OBJECT_SAME_GT_AS_REFERENCE":
                    certified = step
                elif step["relation"] == "CITED_OBJECT_OTHER_GT":
                    first = step
                    break
            reason = ("SAME_FRAME_MULTIPLE_PATH_OBJECTS" if first and certified and
                      first["frame"] == certified["frame"] else
                      "FIRST_CITED_STEP_WRONG" if first and certified is None and path[0] is first else
                      "FIRST_CHECKABLE_STEP_WRONG_AFTER_UNKNOWN" if first and certified is None else
                      "FIRST_INCONSISTENT_AFTER_CERTIFIED" if first else
                      "NO_MIDDLE_PATH_WITNESS" if not path else "NO_CERTIFIED_DIVERGENCE")
            divergence.append(dict(attempt_id=ident, edge=edge, raw_relation=parsed["edges"][edge]["relation"],
                                   anchor_status=status, anchor_gt_id=next(iter(ref_ids)) if status == "UNIQUE" else None,
                                   path_steps=path, first_error=reason,
                                   last_certified=certified, first_inconsistent=first,
                                   interval=[certified["frame"], first["frame"]] if certified and first and
                                   first["frame"] > certified["frame"] else None))
    for item in coverage:
        if item["case_alias"] != "B01":
            continue
        middle = item["b01_g009_to_g032_sent_middle_frames"]
        if item["arm"] == "G-END":
            assert middle == [] and item["b01_middle_predicted_observation_count"] == 0
        else:
            assert len(middle) == 22 and middle[0] == 1323 and middle[-1] == 1483
            assert item["b01_middle_predicted_observation_count"] == 132
        if item["arm"] == "G-SEQ-REPEAT":
            assert len(item["gap_claims"]) == 4
            assert all(x["located"] and x["middle_sent_count"] == 22 and x["coverage_conflict"]
                       for x in item["gap_claims"])
    out.mkdir(parents=True, exist_ok=False)
    write(out / "SOURCE_BINDING_AUDIT.json", dict(status="VERIFIED", restricted_files_checked=len(checked),
          request_seal_sha256=sha(run / "sender/public/REQUESTS_SEALED.json"),
          response_seal_sha256=sha(run / "sender/public/RESPONSES_SEALED.json"),
          source_sha256=sha(run / "public/SOURCE_MANIFEST.json"),
          score_key_sha256=sha(key_path), match_source={k: dict(path=str(v), bytes=v.stat().st_size, sha256=sha(v)) for k,v in paths.items()},
          attempts=binding))
    write(out / "REPLAY_PARITY.json", dict(count=len(parity), all_equal=all(x["edge_status_equal"] and
          x["decoded_equal"] and x["identity_equal"] for x in parity), attempts=parity))
    write_lines(out / "EDGE_CLAIM_BINDINGS.jsonl", edges)
    write_lines(out / "OBSERVATION_COVERAGE.jsonl", coverage)
    write_lines(out / "FIRST_DIVERGENCE.jsonl", divergence)
    print(json.dumps(dict(attempts=len(parity), edges=len(edges), citations=sum(len(x["citations"]) for x in edges),
                          restricted_files_checked=len(checked), first_errors=dict(Counter(x["first_error"] for x in divergence))),
                     ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--case")
    a = ap.parse_args()
    audit(a.run, a.repo, a.out, a.case)
