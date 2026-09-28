"""Create postseal geometry/depth/ID diagnostics, never sent to the model."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"
COLORS = {"A": "#1565c0", "B": "#ef6c00", "X": "#00897b", "Y": "#c2185b"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    events = {x["case"]: x for x in read(PUBLIC / "EVENTS.json")}
    audit = {x["case"]: x for x in read(PUBLIC / "PHYSICAL_REFERENCE_AUDIT.json")["events"]}
    freeze = read(PUBLIC / "FREEZE.json")
    wanted_frames = {q for x in events.values() for q in (x["frame"], x["frame"] + 20)}
    predictions = {}
    with gzip.open(PUBLIC / "predictions_validation.jsonl.gz", "rt", encoding="utf-8") as source:
        for raw in source:
            item = json.loads(raw)
            if item["frame"] in wanted_frames:
                predictions[item["frame"]] = item["variants"]

    def public_id(frame, arm, native):
        return next((x["id"] for x in predictions[frame][arm]
                     if x["mask"] == f"n:{native}"), "ABSENT")

    images = []
    output = PUBLIC / "postscore_visuals"
    output.mkdir(exist_ok=False)
    for case in [x["case"] for x in freeze["schedule"]]:
        packet = read(PUBLIC / "requests" / f"{case}.json")
        event, truth = events[case], audit[case]
        q, now = event["frame"], packet["q_time_seconds"]
        fragments = packet["named_fragments"]
        fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
        fig.suptitle(f"POSTSEAL DIAGNOSTIC — {case} @ F{q}: {event['choice']} / {event['status']} / "
                     f"reference {truth['selected_reference_verdict']}\n"
                     "Not sent to DeepSeek; exposed validation GT IDs appear only in the lower-right panel",
                     fontsize=12, fontweight="bold")
        ax = axes[0, 0]
        for fragment in packet["anonymous_clean_fragments"]:
            pts = fragment["observations"]
            ax.plot([x[3] for x in pts], [x[4] for x in pts], color="#9e9e9e",
                    linewidth=.55, alpha=.55)
        for interval in packet["risk_intervals"]:
            pts = interval["observations"]
            ax.scatter([x[3] for x in pts], [x[4] for x in pts], s=3,
                       color="#5f6368", alpha=.25)
        for role, fragment in fragments.items():
            pts = fragment["observations"]
            ax.plot([x[3] for x in pts], [x[4] for x in pts], color=COLORS[role],
                    linewidth=2, label=f"{role} F{pts[0][1]}–{pts[-1][1]}")
            ax.scatter([pts[-1][3]], [pts[-1][4]], color=COLORS[role], s=20)
        ax.set_title("Observed centers: lines only within clean fragments")
        ax.set_xlabel("full-frame x (px)")
        ax.set_ylabel("full-frame y (px, down)")
        ax.set_xlim(0, 640)
        ax.set_ylim(360, 0)
        ax.legend(fontsize=8, loc="best")

        ax = axes[0, 1]
        for role, fragment in fragments.items():
            pts = fragment["observations"]
            seconds = [x[2] - now for x in pts]
            for part, index, style in (("core", 7, "-"), ("whole", 11, "--")):
                ax.plot(seconds, [float("nan") if x[index] is None else x[index] for x in pts],
                        style, color=COLORS[role], linewidth=1.4,
                        label=f"{role} {part}")
        ax.set_title("Measured depth within each clean fragment")
        ax.set_xlabel("seconds relative to q")
        ax.set_ylabel("pipeline mm; water-surface calibration unverified")
        ax.legend(fontsize=7, ncol=2)

        ax = axes[1, 0]
        for role, fragment in fragments.items():
            pts = fragment["observations"]
            seconds = [x[2] - now for x in pts]
            ax.plot(seconds, [float("nan") if x[10] is None else x[10] for x in pts],
                    color=COLORS[role], linewidth=1.4, label=f"{role} core")
            ax.plot(seconds, [float("nan") if x[14] is None else x[14] for x in pts],
                    "--", color=COLORS[role], linewidth=1, label=f"{role} whole")
        ax.set_title("Depth valid fraction; availability is not identity")
        ax.set_xlabel("seconds relative to q")
        ax.set_ylabel("valid fraction")
        ax.set_ylim(-.05, 1.05)
        ax.legend(fontsize=7, ncol=2)

        ax = axes[1, 1]
        ax.axis("off")
        rows = ["Frozen reference GT / B2 public ID at anchor:"]
        for role in "AB":
            ref = event["references"][role]
            rows.append(f" {role}: GT {truth['reference_gt'][role]} | public {ref['public_id']} | "
                        f"F{ref['anchor_frame']}")
        rows.append("\nq-local actual GT / B0 public / B2 public:")
        for role in "XY":
            native = event["q_native"][role]
            rows.append(f" {role}: GT {truth['q_gt'][role]} | B0 {public_id(q, 'B0', native)} | "
                        f"B2 {public_id(q, 'B2', native)}")
        rows.append("\nSame native handles, q+20 frames:")
        for role in "XY":
            native = event["q_native"][role]
            rows.append(f" {role}: B0 {public_id(q + 20, 'B0', native)} | "
                        f"B2 {public_id(q + 20, 'B2', native)}")
        rows.append(f"\nH1 reference: {truth['hypotheses']['H1']['verdict']}")
        rows.append(f"H2 reference: {truth['hypotheses']['H2']['verdict']}")
        ax.text(.01, .98, "\n".join(rows), va="top", ha="left", family="monospace",
                fontsize=10, transform=ax.transAxes)
        ax.set_title("Public IDs and postseal exposed-GT reference audit")
        target = output / f"{case}.png"
        fig.savefig(target, dpi=150)
        plt.close(fig)
        images.append(dict(case=case, purpose="POSTSEAL_DIAGNOSTIC_NOT_MODEL_INPUT",
                           path=target.relative_to(HERE).as_posix(), bytes=target.stat().st_size,
                           sha256=sha(target)))
    for case in events:
        path = PUBLIC / "overviews" / f"{case}.png"
        assert sha(path) == freeze["overview_sha256"][case]
        images.append(dict(case=case, purpose="ACTUAL_MODEL_INPUT_GEOMETRY_OVERVIEW",
                           path=path.relative_to(HERE).as_posix(), bytes=path.stat().st_size,
                           sha256=sha(path)))
    manifest = PUBLIC / "VISUAL_MANIFEST.json"
    assert not manifest.exists(), manifest
    manifest.write_text(json.dumps(images, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("VISUALS", len(images))


if __name__ == "__main__":
    main()
