"""Bind actual visual review to frozen prediction-only RQ0 selections."""
import argparse
import hashlib
import json
from pathlib import Path

UNUSABLE = {
    ("validation", 2578, 1): "Two separated red mask components, one near the lamp and one on the fish; not a coherent single-fish reference.",
    ("validation", 2747, 7): "Main red fish plus a separate small red component away from it; visibly contaminated mask reference.",
}
UNKNOWN = {
    ("development", 5165, 2): "Two fish approach/cross in the crop; attribution of the red edge is uncertain.",
    ("development", 8023, 3): "Nearby crossing bodies make the narrow red silhouette attribution uncertain.",
    ("development", 8053, 8): "A second fish overlaps the red tip; single-fish mask boundary is uncertain.",
    ("development", 8385, 8): "Adjacent fish almost touch the red body; boundary cannot be certified from one frame.",
    ("validation", 2573, 4): "Lamp glare and thin fragmented tip prevent confident mask-quality classification.",
    ("validation", 2726, 8): "Lamp glare and a nearby fish obscure the tail boundary.",
    ("validation", 2794, 7): "Lamp glare at the red tail and neighboring fish make the boundary uncertain.",
}


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--private-manifests", type=Path, required=True)
    args = parser.parse_args()
    output = args.experiment / "QUALITY_LABELS.jsonl"
    assert not output.exists()
    all_labels = []
    for split in ("development", "validation"):
        selection_path = args.experiment / f"QUALITY_SELECTION_{split}.json"
        manifest_path = args.private_manifests / f"{split}_render_manifest.json"
        selection = json.loads(selection_path.read_text())
        manifest = json.loads(manifest_path.read_text())
        assert manifest["selection_sha256"] == sha(selection_path)
        source = {key: sheet["sha256"] for sheet in manifest["sheets"] for key in sheet["observation_keys"]}
        assert len(source) == len(selection["selected"])
        for item in selection["selected"]:
            key = (split, item["frame"], item["native_id"])
            if key in UNUSABLE:
                label, reason = "VISIBLY_UNUSABLE", UNUSABLE[key]
            elif key in UNKNOWN:
                label, reason = "UNKNOWN", UNKNOWN[key]
            else:
                label = "VISIBLY_USABLE"
                reason = "One discernible fish and a predicted red mask mostly following that fish in the inspected current-frame RGB crop."
            all_labels.append(dict(split=split, frame=item["frame"], native_id=item["native_id"],
                                   observation_key=item["observation_key"], label=label, reason=reason,
                                   source_sheet_sha256=source[item["observation_key"]],
                                   review="actual_RGB_plus_predicted_mask_current_frame; no_GT_or_future"))
    with output.open("x") as handle:
        for label in all_labels:
            handle.write(json.dumps(label, ensure_ascii=False) + "\n")
    print(json.dumps({"labels": len(all_labels), "VISIBLY_UNUSABLE": sum(x["label"] == "VISIBLY_UNUSABLE" for x in all_labels),
                      "UNKNOWN": sum(x["label"] == "UNKNOWN" for x in all_labels), "GT_read": False}))


if __name__ == "__main__":
    main()
