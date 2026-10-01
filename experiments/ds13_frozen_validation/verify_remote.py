"""Read the actual remote main ref and commit-pinned required file bytes."""
from preflight import HERE, ROOT, BASE, artifact, write_new
import hashlib
import json
import subprocess
import sys
import urllib.request

PROXY = 'http://127.0.0.1:7897'


def git(*args):
    return subprocess.check_output(['git', '-c', 'http.proxy=' + PROXY, *args], cwd=ROOT).decode('utf-8').strip()


if __name__ == '__main__':
    head = git('rev-parse', 'HEAD')
    assert git('branch', '--show-current') == 'main'
    remote = git('ls-remote', 'origin', 'refs/heads/main').split()[0]
    assert remote == head
    subprocess.run(['git', '-c', 'http.proxy=' + PROXY, 'fetch', 'origin', 'main'],
                   cwd=ROOT, check=True, capture_output=True)
    assert git('rev-parse', 'origin/main') == head
    changed = []
    for name in git('diff', '--name-only', BASE, head).splitlines():
        data = subprocess.check_output(['git', 'show', head + ':' + name], cwd=ROOT)
        assert data == (ROOT / name).read_bytes(), name
        changed.append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    keys = ('RESULTS.md', 'PLAN.md', 'preflight.py', 'checks.py', 'INPUT_AVAILABILITY.json',
            'FROZEN_R12_LOCK.json', 'CHECKS_RESULT.json', 'SOURCE_METADATA_INVENTORY.json',
            'OLD_READONLY_LOCK.json', 'RESTRICTED_INVENTORY.json', 'ARTIFACT_MANIFEST.json')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({'https': PROXY}))
    checked = []
    for name in ['experiments/ds13_frozen_validation/' + key for key in keys] + ['research/HANDOFF.md']:
        url = 'https://raw.githubusercontent.com/grathball-source/SAM3D-Z4Q-DeepSeek-FishMOT/' + head + '/' + name
        with opener.open(url, timeout=30) as response:
            data, status = response.read(), response.status
        assert status == 200 and data == (ROOT / name).read_bytes(), name
        checked.append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), status=status))
    proof = dict(main_SHA=head, actual_remote_SHA=remote, origin_main_SHA=git('rev-parse', 'origin/main'),
                 changed_blobs_byte_equal=changed, key_remote_files=checked, normal_push=True,
                 git_status=git('status', '--short'), new_model_http=0, cost_usd=0)
    if '--save' in sys.argv:
        write_new('REMOTE_VERIFICATION.json', proof)
    print(json.dumps(dict(main_SHA=head, actual_remote_SHA=remote, changed_files=len(changed),
                          remote_key_files=len(checked), git_status=proof['git_status'])))
