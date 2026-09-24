"""Inventory all restricted M2-T artifacts without publishing their content."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main(run: Path, pilot: Path, out: Path):
    assert (run / 'sender/public/RESPONSES_SEALED.json').exists()
    assert not out.exists()
    restricted = []
    for root, category in ((run / 'sender/media', 'private_pixel'),
                           (run / 'sender/private', 'private_provider_wire'),
                           (run / 'private', 'private_native_token_ledger'),
                           (pilot / 'sender/media', 'pilot_private_pixel'),
                           (pilot / 'private', 'pilot_private_native_token_ledger')):
        for path in sorted(root.rglob('*')):
            if path.is_file():
                restricted.append(dict(category=category, path=str(path.resolve()),
                                       bytes=path.stat().st_size,
                                       sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    for path in (run / 'sender/PLAN.json', pilot / 'sender/PLAN.json'):
        restricted.append(dict(category='private_logical_payload', path=str(path.resolve()),
                               bytes=path.stat().st_size,
                               sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    public = []
    for root in (run / 'public', run / 'sender/public', run / 'scored', pilot / 'public'):
        for path in sorted(root.rglob('*')):
            if path.is_file():
                public.append(dict(path=str(path.resolve()), bytes=path.stat().st_size,
                                   sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    out.write_text(json.dumps(dict(run_root=str(run.resolve()), pilot_root=str(pilot.resolve()),
         reproduction='Run build.py against the AO1 range_corrected_run SOURCE_MANIFEST and verified same-host observation/mask/RGB sources; use this batch exact build.py, seed, source hashes and CONFIG. The official provider file IDs and raw wire remain server-private; paid responses cannot be regenerated without separate authorization.',
         restricted=restricted, public=public), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(dict(restricted=len(restricted), public=len(public))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--pilot', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    options = parser.parse_args()
    main(options.run, options.pilot, options.out)
