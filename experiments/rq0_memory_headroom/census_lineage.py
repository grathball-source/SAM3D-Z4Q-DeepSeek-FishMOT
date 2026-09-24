"""Bind every census interval start to original predicted-mask provenance."""
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
source = json.loads((ROOT / "experiments/vl_assoc_e1c/RUN_RECORD.json").read_text())["sources"]


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt") as handle:
        yield from map(json.loads, handle)


output = HERE / "FULL_SEQUENCE_ERROR_LINEAGE.jsonl"
assert not output.exists()
with output.open("x") as handle:
    for split in ("development", "validation"):
        masks_path = Path(source[f"{split}_masks"])
        mask_source_sha = sha(masks_path)
        intervals = [json.loads(line) for line in
                     (HERE / f"FULL_SEQUENCE_ERROR_CENSUS_{split}_v2.jsonl").read_text().splitlines()]
        need = {x["start"] for x in intervals if x["first_native_id"] is not None}
        found = {}
        for row in rows(masks_path):
            if row["frame"] in need:
                found[row["frame"]] = row
        assert set(found) == need
        for number, interval in enumerate(intervals, 1):
            frame, native = interval["start"], interval["first_native_id"]
            mask_key = None if native is None else f"n:{native}"
            encoded = None if native is None else found[frame]["masks"].get(mask_key)
            assert native is None or encoded is not None
            packed = None if encoded is None else json.dumps(encoded, sort_keys=True, separators=(",", ":")).encode()
            handle.write(json.dumps(dict(split=split, census_record_id=f"{split}:C{number:04d}",
                                         start_frame=frame, gt_id=interval["gt_id"], status=interval["status"],
                                         observation_key=None if native is None else f"{split}:{frame}:n:{native}",
                                         mask_key=mask_key, original_predicted_RLE_sha256=None if packed is None else hashlib.sha256(packed).hexdigest(),
                                         source_assignment_sha256=mask_source_sha,
                                         source_assignment_path=str(masks_path),
                                         mask_read_from_actual_host=encoded is not None,
                                         tracking_fixed_base="6320f29bdaf8d33ed64dd7e4888089a0f19e3319",
                                         note="GT relationship is post-seal; mask source is original fixed predicted RLE, not GT mask.")) + "\n")
print(json.dumps(dict(status="CENSUS_SOURCE_MASKS_BOUND", intervals=sum(1 for _ in output.open()),
                      missing_observation_intervals=sum(json.loads(x)["observation_key"] is None for x in output.read_text().splitlines()))))
