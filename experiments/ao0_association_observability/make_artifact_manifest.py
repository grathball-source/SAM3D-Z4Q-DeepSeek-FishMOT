"""Inventory public AO0 payloads and intentionally private source/media by size/hash."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIVATE = Path("/home/xiongxiong/ao0_private_visual_20260924")
SOURCES = {
    "validation_observations": "/home/xiongxiong/deepseek_z4q_closedloop_20260923_side/inputs/observations_validation.jsonl.gz",
    "validation_depth": "/home/xiongxiong/deepseek_z4q_closedloop_20260923_side/inputs/features_validation.jsonl.gz",
    "validation_appearance": "/home/xiongxiong/dmot-experiments/sam3_depth_assisted_tracking_at1_20260916/active_identity_v1_20260917/features_validation_2888.jsonl.gz",
    "validation_predicted_masks": "/home/data2/xiongxiong/d-mot/experiments/sam3_i3_validation_cpu16_20260915/run_validation_2888/assignments.jsonl.gz",
    "validation_exposed_GT_raster": "/home/data2/xiongxiong/d-mot/experiments/sam3_i1_validation_20260915/truth.jsonl.gz",
    "validation_exposed_matches": "/home/xiongxiong/dmot-experiments/sam3_depth_return_guard_20260918/experiment/offline_matches_validation.jsonl.gz",
    "development_observations": "/home/xiongxiong/dmot-experiments/sam3_depth_failure_repair_20260917/diagnosis/observations_development.jsonl.gz",
    "development_depth": "/home/xiongxiong/dmot-experiments/sam3_depth_birth_inherit_20260917/features_r2/features_development.jsonl.gz",
    "development_exposed_GT_raster": "/home/xiongxiong/rq0_private_gt_20260924/truth_development.jsonl.gz",
    "development_exposed_matches": "/home/xiongxiong/dmot-experiments/sam3_depth_return_guard_20260918/experiment/offline_matches_development.jsonl.gz",
}


def describe(path):
    path = Path(path)
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest)


def main():
    target = HERE / "ARTIFACT_MANIFEST.json"
    assert not target.exists()
    public = [dict(relative_path=str(path.relative_to(ROOT)).replace("\\", "/"),
                   bytes=path.stat().st_size, sha256=describe(path)["sha256"])
              for path in sorted(HERE.rglob("*")) if path.is_file() and
              path != target and "__pycache__" not in path.parts]
    images = [describe(PRIVATE / name) for name in ("ao0_whole_fish.png", "ao0_interaction_local.png")]
    source = {name: describe(path) for name, path in SOURCES.items()}
    rgb_index = json.loads((HERE / "VISUAL_INPUT_INDEX.json").read_text())
    rgb_paths = sorted({item["private_RGB_path"] for item in rgb_index["records"]
                        if "private_RGB_path" in item})
    report = dict(status="COMPLETE_AO0_PAYLOAD_INVENTORY_BEFORE_GIT_COMMIT",
        public_git_files=public, public_git_file_count=len(public),
        private_AO0_generated_images=images,
        private_AO0_generated_image_copy="E:/CAU/D-MOT/logs/ao0_private_visual_20260924/ (same SHA-256)",
        private_source_inputs=source,
        private_original_RGB_frames=[describe(path) for path in rgb_paths],
        excluded_reason="Original RGB, predicted RLE assignment stream, and exposed GT raster/source streams are private or large; the public repository contains reproducible provenance and derived AO0 scalar/ID diagnostics, not raw pixels or GT RLE.",
        reproduction="On the authorized lab host use the paths above and commands in RUN_RECORD.json; verify SHA-256 before replay. No model API or unexposed test GT is needed.",
        note="The manifest excludes itself to avoid a self-hash cycle; final Git/main commit and remote verification are recorded in the task handoff.")
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(public_files=len(public), private_images=len(images),
                          private_sources=len(source), RGB_frames=len(rgb_paths))))


if __name__ == "__main__":
    main()
