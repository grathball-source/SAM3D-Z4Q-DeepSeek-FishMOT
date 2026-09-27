"""Reread the five immutable source streams with the previous source auditor."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main(legacy, old_run, output):
    legacy, old_run, output = map(Path, (legacy, old_run, output))
    assert not output.exists()
    sys.path.insert(0, str(legacy))
    import validate as previous
    result = previous.check_projection(old_run)
    assert result['status'] == 'SOURCE_TO_LOGICAL_PASS' and result['requests'] == 25
    assert len(result['cases']) == 5
    value = {'status': 'PASS', 'scope': 'FIVE_CASE_SOURCE_STREAM_RECHECK_ONLY',
             'old_E_endpoint_contract': 'KNOWN_FALSE_POSITIVE_NOT_ACCEPTED',
             'checked_at_utc': datetime.now(timezone.utc).isoformat(),
             'old_run': str(old_run), 'cases': result['cases'],
             'requests': result['requests'],
             'legacy_code_sha256': {name: hashlib.sha256((legacy/name).read_bytes()).hexdigest()
                                    for name in ('build.py', 'validate.py')},
             'old_logical_sha256': result['logical_sha256'],
             'old_manifest_sha256': result['manifest_sha256']}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'source_recheck': value['status'], 'cases': 5, 'requests': 25,
                      'source_observations': sum(x['source_observations'] for x in result['cases'])}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('legacy', 'old-run', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args(); main(a.legacy, a.old_run, a.output)
