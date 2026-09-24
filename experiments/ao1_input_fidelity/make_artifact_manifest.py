"""Inventory every private AO1 media file and exact source without publishing pixels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_full import write_json
from build_input import digest


def item(path: Path) -> dict:
    assert path.is_file()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest(path))


def main(args):
    source = json.loads(args.source_manifest.read_text())
    blind = args.private_root / "blind"
    media = sorted(p for p in blind.rglob("*") if p.is_file() and p.name != "card.json")
    cards = sorted(blind.rglob("card.json"))
    additional = sorted(p for directory in args.additional_private_dir
                        for p in directory.rglob("*") if p.is_file())
    original = sorted({row["rgb_path"] for case in source["cases"] for row in case["source_by_frame"]})
    v0 = sorted({row["original_path"] for case in source["cases"] for row in case["V0"]["media"]})
    streams = [Path(path) for path in args.source_streams]
    output = dict(status="COMPLETE_RESTRICTED_MEDIA_INVENTORY",
                  private_root=str(args.private_root),
                  private_media_count=len(media), private_media_bytes=sum(p.stat().st_size for p in media),
                  private_review_cards_count=len(cards),
                  private_media=[item(p) for p in media],
                  private_review_cards=[item(p) for p in cards],
                  nonfinal_private_artifacts=[item(p) for p in additional],
                  original_rgb_sources=[item(Path(p)) for p in original],
                  old_v0_sources=[item(Path(p)) for p in v0],
                  source_streams=[item(p) for p in streams],
                  omitted_from_git="Raw RGB, predicted-mask RLE streams, original and derived private visual media; no credential or GT raster copied.",
                  reproduction="Use CONFIG.json, build_input.py --pilot, build_full.py and numeric_full.py on the authorized lab host with the exact stream paths in SOURCE_MANIFEST.json; verify SHA-256 before using source frames. No API or test GT.")
    write_json(args.output, output)
    print(json.dumps(dict(private_media_count=len(media), cards=len(cards),
                          source_rgb=len(original), bytes=output["private_media_bytes"])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-streams", nargs="+", required=True)
    parser.add_argument("--additional-private-dir", nargs="*", type=Path, default=[])
    main(parser.parse_args())
