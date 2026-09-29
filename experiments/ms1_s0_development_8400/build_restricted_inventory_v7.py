"""List exact local evidence retained outside Git for the paid V7 run."""
import json
from pathlib import Path

from build_restricted_inventory import digest
from postseal_event import MATCHES
from replay_v7 import ARCHIVED, PROFILES, SCAN
from score import GT
from source_scan import ASSIGN, OBS

HERE = Path(__file__).resolve().parent
RUNS = ('run_development_v7_paid', 'run_development_v7_recovery')


def main():
    originals = (OBS, ASSIGN, PROFILES, ARCHIVED, GT, MATCHES, SCAN)
    restricted = sorted(p for run in RUNS for p in (HERE/run).rglob('*')
                        if p.is_file() and any(x in ('private_source', 'private_api') for x in p.parts))
    files = [dict(path=str(p.resolve()), bytes=p.stat().st_size, sha256=digest(p),
                  kind='external_or_source_input' if p in originals else 'local_restricted_artifact')
             for p in (*originals, *restricted)]
    result = dict(status='LOCAL_RESTRICTED_V7_INVENTORY', count=len(files), files=files,
                  public_run='run_development_v7_paid and run_development_v7_recovery',
                  reproduction=('Use the exact-hash local inputs, interrupted private API records and '
                                'the offline recovery commands in PAID_RUN_V7_FINAL_REVIEW.md. '
                                'No private pixels, provider IDs or GT raster are committed.'))
    out = HERE/'RESTRICTED_INVENTORY_V7.json'
    with out.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps(dict(count=len(files), output=str(out))))


if __name__ == '__main__':
    main()
