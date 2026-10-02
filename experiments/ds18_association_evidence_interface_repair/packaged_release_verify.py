"""Delivery-only manifest and Git checks for fully preserved sealed large records."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from reconstruct_large_records import ROOT, HERE, BLOCK, safe_path, verified_packages

MANIFEST = HERE / 'GIT_DELIVERY_MANIFEST.json'
LATE_METADATA = ('PACKAGED_INDEX_REVIEW.json', 'PACKAGED_REMOTE_VERIFICATION.json')


def artifact(path):
    path = Path(path).resolve()
    with path.open('rb') as handle:
        sha = hashlib.file_digest(handle, 'sha256').hexdigest()
    return dict(relative_path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size, sha256=sha)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def blob_digest(spec, aggregate=None):
    process = subprocess.Popen(['git', 'show', spec], cwd=ROOT, stdout=subprocess.PIPE)
    size, sha = 0, hashlib.sha256()
    for chunk in iter(lambda: process.stdout.read(BLOCK), b''):
        size += len(chunk)
        sha.update(chunk)
        if aggregate is not None:
            aggregate.update(chunk)
    assert process.wait() == 0, spec
    return size, sha.hexdigest()


def save_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write('\n')


def forbidden(relative):
    path = Path(relative)
    if any(part == 'private' or part.startswith('slice') or part == '__pycache__' for part in path.parts):
        return True
    if path.suffix.lower() in ('.npy', '.npz', '.h5', '.hdf5', '.jpg', '.jpeg', '.mp4', '.pt', '.pth'):
        return True
    if path.suffix.lower() == '.png' and path.name != 'METRIC_COMPARISON.png':
        return True
    return path.name == '.env' or 'secret' in path.name.lower() or 'api_key' in path.name.lower()


def manifest():
    assert (HERE / 'FINAL_CHECKS.json').exists(), 'Run finalization before delivery manifest'
    logical_path = HERE / 'PUBLIC_ARTIFACT_MANIFEST.json'
    logical = json.loads(logical_path.read_text(encoding='utf-8'))
    packaging = verified_packages()
    packaged = {item['relative_path'] for item in packaging['records']}
    files = {}
    for item in logical['files']:
        path = safe_path(ROOT, item['relative_path'])
        actual = artifact(path)
        assert actual['bytes'] == item['bytes'] and actual['sha256'] == item['sha256']
        if item['relative_path'] not in packaged:
            files[item['relative_path']] = actual
    for record in packaging['records']:
        for part in record['parts']:
            files[part['relative_path']] = artifact(safe_path(ROOT, part['relative_path']))
    handoff = json.loads((HERE / 'HANDOFF_UPDATE.json').read_text(encoding='utf-8'))
    for path in (logical_path, ROOT / '.gitignore', Path(handoff['path'])):
        item = artifact(path)
        files[item['relative_path']] = item
    for item in files.values():
        assert not forbidden(item['relative_path']), item['relative_path']
        assert item['bytes'] < 100000000, ('Unpackaged GitHub large file', item['relative_path'])
    save_new(MANIFEST, dict(status='PHYSICAL_GIT_DELIVERY_WITH_COMPLETE_LOGICAL_SEALED_RECORDS',
        files=list(files.values()), count=len(files), logical_manifest=artifact(logical_path),
        packaging=artifact(HERE / 'LARGE_RECORD_PACKAGING.json'), packaged_records=packaging['records'],
        original_large_files_not_staged=sorted(packaged), no_scientific_bytes_changed=True,
        local_pixels_excluded=True, reconstruction='python reconstruct_large_records.py in a fresh checkout; all parts verified first'))
    return dict(mode='manifest', status='PASS', files=len(files), packaged_records=len(packaged))


def index():
    record = json.loads(MANIFEST.read_text(encoding='utf-8'))
    expected = {item['relative_path']: item for item in record['files']}
    own = artifact(MANIFEST)
    expected[own['relative_path']] = own
    for filename in LATE_METADATA:
        path = HERE / filename
        if path.exists():
            item = artifact(path)
            expected[item['relative_path']] = item
    staged = git('diff', '--cached', '--name-only', '-z').decode().split('\0')[:-1]
    for path in staged:
        assert not forbidden(path) and path in expected, ('Unexpected staged file', path)
    for path, item in expected.items():
        actual = artifact(safe_path(ROOT, path))
        assert actual == item, ('Local delivery artifact changed', path)
        assert blob_digest(':' + path) == (item['bytes'], item['sha256']), ('Index bytes differ', path)
    verified_packages()
    output = dict(mode='index', status='ALL_ACTUAL_STAGED_PATHS_AND_EXPECTED_INDEX_BLOBS_VERIFIED',
                  staged_files=len(staged), expected_files=len(expected), staged=staged,
                  delivery_manifest=own, no_original_large_gzip_staged=True,
                  no_private_pixels=True, notes='Late verification metadata needs another explicit stage/check or final committed blob verification.')
    if not (HERE / 'PACKAGED_INDEX_REVIEW.json').exists():
        save_new(HERE / 'PACKAGED_INDEX_REVIEW.json', output)
    return output


def remote():
    head = git('rev-parse', 'HEAD').decode().strip()
    ref = git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
    assert ref == head
    git('fetch', 'origin', 'main')
    assert git('rev-parse', 'origin/main').decode().strip() == ref
    record = json.loads(MANIFEST.read_text(encoding='utf-8'))
    files = record['files'] + [artifact(MANIFEST)]
    files.extend(artifact(HERE / filename) for filename in LATE_METADATA if (HERE / filename).exists())
    checked = {}
    for item in files:
        assert blob_digest(ref + ':' + item['relative_path']) == (item['bytes'], item['sha256'])
        checked[item['relative_path']] = dict(bytes=item['bytes'], sha256=item['sha256'])
    joins = []
    for original in record['packaged_records']:
        merged, size = hashlib.sha256(), 0
        for part in original['parts']:
            part_size, part_sha = blob_digest(ref + ':' + part['relative_path'], merged)
            assert (part_size, part_sha) == (part['bytes'], part['sha256'])
            size += part_size
        seal = json.loads(git('show', ref + ':' + original['seal_relative_path']))
        sealed = seal['artifacts_sha256'][Path(original['relative_path']).name]
        assert size == original['bytes'] and merged.hexdigest() == original['sha256'] == sealed
        exists = subprocess.run(['git', 'cat-file', '-e', ref + ':' + original['relative_path']], cwd=ROOT,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        assert not exists, 'Original large gzip must be delivered via complete parts'
        joins.append(dict(relative_path=original['relative_path'], bytes=size, sha256=merged.hexdigest(),
                          sealed_sha256=sealed, remote_parts_complete=True))
    output = dict(mode='remote', status='ACTUAL_REMOTE_REF_ALL_DELIVERY_BLOBS_AND_SEALED_RAW_JOINS_VERIFIED',
                  commit=head, actual_remote_main=ref, files=checked, reconstructed_records=joins,
                  force_push=False, checked_utc=datetime.now(timezone.utc).isoformat(),
                  note='If this metadata is committed afterward, reread the final ref and critical blobs after that push.')
    if not (HERE / 'PACKAGED_REMOTE_VERIFICATION.json').exists():
        save_new(HERE / 'PACKAGED_REMOTE_VERIFICATION.json', output)
    return output


if __name__ == '__main__':
    assert len(sys.argv) == 2 and sys.argv[1] in ('manifest', 'index', 'remote')
    print(json.dumps({'manifest': manifest, 'index': index, 'remote': remote}[sys.argv[1]](), ensure_ascii=False))
