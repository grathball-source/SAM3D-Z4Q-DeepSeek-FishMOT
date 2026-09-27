"""Path/size/SHA inventory of restricted current-run files, without their contents."""
import argparse
from pathlib import Path

from build import save, sha


def main(run):
    run = Path(run)
    files = sorted(p for part in ('private', 'send') for p in (run/part).rglob('*') if p.is_file())
    rows = [{'path': str(path.resolve()), 'bytes': path.stat().st_size, 'sha256': sha(path)}
            for path in files]
    value = {'status': 'RESTRICTED_OFF_GIT', 'run': str(run.resolve()),
             'file_count': len(rows), 'total_bytes': sum(x['bytes'] for x in rows),
             'reproduction_dependencies': [
                 'review base f68552be88c20cc500be8281f6f1ec04db34b4ee',
                 'immutable old ehr1r_complete_trial logical requests and 55 SHA-verified media',
                 'immutable corrected_unsent v6 source and original predicted observation/depth streams',
                 'this run public request/body locks, code, ledger, responses, and scorer',
                 'official DeepSeek Files API access for a new separately authorized rerun'],
             'files': rows}
    save(run/'public/RESTRICTED_INVENTORY.json', value)
    print({'restricted_files': len(rows), 'restricted_bytes': value['total_bytes']})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True)
    main(p.parse_args().run)
