"""Inventory M1 restricted files without copying pixels, file IDs, or raw wire to Git."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def describe(path: Path) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest)


def main(root: Path, out: Path) -> None:
    assert not out.exists()
    run = root / "run_v4"
    media = sorted(x for x in (run / "media").iterdir() if x.is_file())
    private = sorted(x for x in (run / "private").rglob("*") if x.is_file())
    preliminary = {name: dict(path=str(root / name),
                              files=sum(x.is_file() for x in (root / name).rglob("*")),
                              note="Failed/preflight-only preparation retained; no old AO1 archive modified")
                   for name in ("run_v1", "run_v2", "run_v3")}
    upload_ledger = run / "private/UPLOAD_LEDGER.jsonl"
    upload_rows = [json.loads(line) for line in upload_ledger.read_text().splitlines()]
    uploads = [x for x in upload_rows if x["status"] == "UPLOADED"]
    result = dict(status="M1_RESTRICTED_ARTIFACT_INVENTORY",
                  authoritative_run=str(run), private_media_count=len(media),
                  private_media_bytes=sum(x.stat().st_size for x in media),
                  private_media=[describe(x) for x in media],
                  private_wire_and_access_ids=[describe(x) for x in private],
                  official_files_uploaded_count=len(uploads),
                  official_files_uploaded_bytes=sum(x["bytes"] for x in uploads),
                  official_file_id_ledger=str(upload_ledger),
                  official_file_ids_publicly_redacted=True,
                  official_upload_lifetime_seconds=2592000,
                  preliminary=preliminary,
                  reproduction="Use AO1 range_corrected_run, the frozen M1 adapter/plan hashes and official Files API. Re-upload exact hashed private media if 30-day file IDs expire; never substitute frames or resize.",
                  omitted_from_public_git="Original/derived pixels, private request bodies with file IDs, raw reasoning/wire, API key")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(media=len(media), private_files=len(private), uploads=len(uploads))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    main(args.root, args.out)
