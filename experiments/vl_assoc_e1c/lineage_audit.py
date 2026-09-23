"""Prediction-only audit of old E1 sampled current segments against every intervening frame."""
import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
E1 = HERE.parent / "vl_assoc_e1"


def subset(path, needed):
    found = {}
    with gzip.open(path, "rt") as handle:
        for line in handle:
            row = json.loads(line)
            if row["frame"] in needed:
                found[row["frame"]] = row
    assert set(found) == needed
    return found


def main():
    p = argparse.ArgumentParser()
    for split in ("development", "validation"):
        for field in ("observations", "baseline"):
            p.add_argument(f"--{split}-{field}", type=Path, required=True)
    args = p.parse_args()
    episodes = {x["packet_id"]: x for x in map(json.loads, (E1 / "EPISODES.jsonl").read_text().splitlines())}
    packets = {ident: json.loads((E1 / "packets" / f"{ident}.json").read_text()) for ident in episodes}
    output = []
    for split in ("development", "validation"):
        these = [(ident, packet) for ident, packet in packets.items() if episodes[ident]["split"] == split]
        needed = {frame for _, packet in these for node in packet["current"]
                  for frame in range(node["samples"][0]["local_frame"], node["samples"][-1]["local_frame"] + 1)}
        obs = subset(getattr(args, f"{split}_observations"), needed)
        baseline = subset(getattr(args, f"{split}_baseline"), needed)
        for ident, packet in these:
            natives = {v: int(k) for k, v in episodes[ident]["source_aliases"]["native_alias"].items()}
            for node in packet["current"]:
                native = natives[node["label"]]
                sampled = [x["local_frame"] for x in node["samples"]]
                frames = range(sampled[0], sampled[-1] + 1)
                missing = [f for f in frames if native not in {o["id"] for o in obs[f]["observations"]}]
                publics = []
                contacts = []
                for f in frames:
                    assigned = [x["id"] for x in baseline[f]["variants"]["Z4Q_STABLE"]
                                if x["mask"] == f"n:{native}"]
                    publics.extend(assigned)
                    current = next((o for o in obs[f]["observations"] if o["id"] == native), None)
                    if current is not None:
                        contacts.append(bool(current.get("neighbors")))
                output.append(dict(packet_id=ident, split=split, label=node["label"], native=native,
                                   sampled_frames=sampled, missing_between_samples=missing,
                                   public_ids_seen=sorted(set(publics)),
                                   public_switch=len(set(publics)) > 1,
                                   contact_transition=len(set(contacts)) > 1))
    result = dict(old_packets=len(packets), current_segments=len(output),
                  segments_with_disappearance=sum(bool(x["missing_between_samples"]) for x in output),
                  segments_with_public_switch=sum(x["public_switch"] for x in output),
                  segments_with_contact_transition=sum(x["contact_transition"] for x in output),
                  note="Old packets sampled 3 frames but did not prove intervening continuity; these are observed trajectory defects, not GT labels.",
                  rows=output)
    out = HERE / "INPUT_LINEAGE_AUDIT.json"
    assert not out.exists()
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))


if __name__ == "__main__":
    main()
