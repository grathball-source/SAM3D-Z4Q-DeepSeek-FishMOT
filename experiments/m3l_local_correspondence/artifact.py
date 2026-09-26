"""Inventory restricted M3-L bytes without copying them into Git."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path('/home/xiongxiong/m3l_local_correspondence_20260926')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def main():
    restricted = []
    sender = ROOT / 'sender'
    for rel, category in (('media', 'private_pixel'), ('private/bodies', 'provider_file_id_body'),
                          ('private/raw', 'private_api_wire')):
        for path in sorted((sender / rel).glob('*')):
            if path.is_file():
                restricted.append(dict(category=category, path=str(path), bytes=path.stat().st_size,
                                       sha256=digest(path)))
    for path in sorted((ROOT/'private_visual').glob('*')):
        if path.is_file():
            restricted.append(dict(category='posthoc_private_pixel', path=str(path),
                                   bytes=path.stat().st_size, sha256=digest(path)))
    for path, category in ((sender/'private/UPLOAD_LEDGER.jsonl','provider_file_ids'),
       (Path('/home/xiongxiong/m2t_motion_first_20260924/full_run/private/TOKEN_LEDGER.json'), 'old_private_token_ledger'),
       (Path('/home/xiongxiong/dmot-experiments/sam3_depth_return_guard_20260918/experiment/offline_matches_validation.jsonl.gz'), 'exposed_gt_match_source'),
       (Path('/home/data2/xiongxiong/d-mot/experiments/sam3_i3_validation_cpu16_20260915/run_validation_2888/assignments.jsonl.gz'), 'predicted_mask_source')):
        assert path.is_file()
        restricted.append(dict(category=category, path=str(path), bytes=path.stat().st_size,
                               sha256=digest(path)))
    public = ROOT / 'public/ARTIFACT_MANIFEST.json'
    assert not public.exists()
    public.write_text(json.dumps(dict(status='INVENTORIED', run_root=str(ROOT),
       reproduction='Use prepare.py with the fixed old M2-T SOURCE_MANIFEST, TOKEN_LEDGER and media on this host; run the frozen isolated sender only under a new authorization. Exact paid responses cannot be recreated without a new authorization. Postscore uses the listed already-exposed validation matches and masks.',
       restricted=restricted), indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(restricted_files=len(restricted), categories=sorted({x['category'] for x in restricted}))))


if __name__=='__main__':
    main()
