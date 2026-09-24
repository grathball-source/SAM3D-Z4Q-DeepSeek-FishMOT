"""Post-seal exposed-development GT rasterization; private output, never a gate input."""
import argparse
import gzip
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import cv2
import numpy as np
from pycocotools import mask as mu

sys.path.insert(0, "/home/data2/xiongxiong/dmot-annotation/evaluation/sam3_continuous_20260912")
from run_sam3_trackeval import encode  # noqa: E402


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seal-dir", type=Path, required=True)
    args = parser.parse_args()
    for split in ("development", "validation"):
        seal = json.loads((args.seal_dir / f"OUTPUT_SEAL_{split}.json").read_text())
        assert seal["status"] == "PREDICTIONS_SEALED_AWAITING_GT" and seal["GT_read"] is False
    assert not args.output.exists() and args.output.parent.is_dir()
    with zipfile.ZipFile(args.archive) as archive, gzip.open(args.output, "wt") as out:
        manifest = json.loads(archive.read("manifest.json"))
        assert len(manifest["gt"]) >= 12188
        for i, row in enumerate(manifest["gt"][:8400], 1):
            raw = archive.read(row["key"])
            assert hashlib.sha256(raw).hexdigest() == row["sha256"]
            ids, masks, _, _ = encode(json.loads(raw)["shapes"])
            gt = []
            for gid, encoded in zip(ids, masks):
                grid = cv2.resize(mu.decode(encoded), (640, 360), interpolation=cv2.INTER_NEAREST)
                packed = mu.encode(np.asfortranarray(grid))
                gt.append(dict(id=int(gid), rle=dict(size=packed["size"], counts=packed["counts"].decode())))
            out.write(json.dumps(dict(global_frame_id=i, gt_grid=gt), separators=(",", ":")) + "\n")
    print(json.dumps(dict(status="EXPOSED_DEVELOPMENT_TRUTH_PREPARED_POST_SEAL", frames=8400,
                          archive_sha256=sha(args.archive), output_sha256=sha(args.output))))


if __name__ == "__main__":
    main()
