"""Decode every decisive sent G image; source-pixel checks are not identity judgments."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lines(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines()]


def main(run, old, audited, out):
    source = {x["case_alias"]: x for x in read(old / "SOURCE_MANIFEST.json")["cases"]}
    private = read(run / "private/TOKEN_LEDGER.json")
    attempts = {x["attempt_id"]: x for x in lines(old / "ATTEMPT_RESULTS.jsonl")}
    records = []
    for edge in lines(audited / "EDGE_CLAIM_BINDINGS.jsonl"):
        ident = edge["attempt_id"]
        if attempts[ident]["decoded_relation"] == "ABSTAIN" or edge["raw_relation"] == "UNRESOLVED":
            continue
        case = source[edge["case_alias"]]
        by_frame = dict(zip(case["all_frames"], case["g_images"], strict=True))
        private_by_frame = {x["frame"]: x for x in private[edge["case_alias"]]}
        for citation in edge["citations"]:
            image = by_frame[citation["frame"]]
            assert image["image_id"] == citation["image_id"]
            raw = (run / "sender/media" / image["media_file"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == citation["image_sha256"] == image["sha256"]
            pixels = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
            assert pixels is not None
            gray = bool(np.array_equal(pixels[:, :, 0], pixels[:, :, 1]) and
                        np.array_equal(pixels[:, :, 1], pixels[:, :, 2]))
            assert gray
            token_checks = []
            obs_by_token = {x["token"]: x for x in private_by_frame[citation["frame"]]["observations"]}
            for token in citation["token_bindings"]:
                box = obs_by_token[token["token"]]["bbox_norm"]
                h, w = pixels.shape[:2]
                x0, y0 = max(0, int(box[0] * w)), max(0, int(box[1] * h))
                x1, y1 = min(w, int(np.ceil(box[2] * w))), min(h, int(np.ceil(box[3] * h)))
                crop = pixels[y0:y1, x0:x1, 0]
                dark = int(np.count_nonzero(crop < 250))
                token_checks.append(dict(token=token["token"], native=token["source_native"],
                                         gt_status=token["gt"]["status"],
                                         bbox_norm=box, dark_pixels_in_bbox=dark,
                                         geometric_pixels_visible=dark > 0,
                                         semantic_continuity="NOT_ESTABLISHED_BY_PIXEL_DECODE"))
            records.append(dict(attempt_id=ident, edge=edge["edge"], relation=edge["raw_relation"],
                                image_id=image["image_id"], frame=citation["frame"],
                                sha256=image["sha256"], bytes=len(raw), width=pixels.shape[1],
                                height=pixels.shape[0], gray_decoded=gray, token_checks=token_checks,
                                reviewer="PROGRAMMATIC_ACTUAL_SENT_PIXEL_DECODE_POST_SCORE"))
    assert not out.exists()
    out.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in records), encoding="utf-8")
    print(json.dumps(dict(citations_decoded=len(records),
                          support=sum(x["relation"] == "SUPPORT" for x in records),
                          contradict=sum(x["relation"] == "CONTRADICT" for x in records),
                          distinct_images=len({(x["attempt_id"], x["image_id"]) for x in records}),
                          zero_dark_bbox_tokens=sum(not t["geometric_pixels_visible"] for x in records
                                                    for t in x["token_checks"]))))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--old", type=Path, required=True)
    ap.add_argument("--audited", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    main(a.run, a.old, a.audited, a.out)
