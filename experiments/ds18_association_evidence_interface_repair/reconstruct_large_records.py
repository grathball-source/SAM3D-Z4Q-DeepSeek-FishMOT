"""Restore sealed records from verified raw-byte parts without overwriting files."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGING = HERE / 'LARGE_RECORD_PACKAGING.json'
BLOCK = 1024 * 1024


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def safe_path(root, relative):
    path = (Path(root) / relative).resolve()
    assert path.is_relative_to(Path(root).resolve()), relative
    return path


def verified_packages(root=ROOT):
    metadata = json.loads(safe_path(root, PACKAGING.relative_to(ROOT)).read_text(encoding='utf-8'))
    assert metadata['schema'] == 'DS18_SEALED_RAW_BYTE_PARTS_V1'
    for record in metadata['records']:
        offset, joined = 0, hashlib.sha256()
        for part in record['parts']:
            path = safe_path(root, part['relative_path'])
            assert part['offset'] == offset and path.stat().st_size == part['bytes']
            assert 0 < part['bytes'] <= metadata['maximum_part_bytes']
            actual = hashlib.sha256()
            with path.open('rb') as handle:
                while chunk := handle.read(BLOCK):
                    actual.update(chunk)
                    joined.update(chunk)
            assert actual.hexdigest() == part['sha256'], path
            offset += part['bytes']
        assert offset == record['bytes']
        assert joined.hexdigest() == record['sha256'] == record['sealed_sha256']
    return metadata


def reconstruct(root=ROOT, output_root=None):
    # Validate every part of every record before creating any original record.
    metadata = verified_packages(root)
    destination_root = Path(output_root).resolve() if output_root else Path(root).resolve()
    restored = []
    for record in metadata['records']:
        destination = safe_path(destination_root, record['relative_path'])
        if destination.exists():
            assert destination.is_file() and destination.stat().st_size == record['bytes']
            assert digest(destination) == record['sha256'], 'Existing record differs; refusing overwrite'
            restored.append(dict(relative_path=record['relative_path'], status='EXISTING_IDENTICAL_VERIFIED'))
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=destination.name + '.rebuild-', dir=destination.parent)
        temporary = Path(temporary)
        try:
            with os.fdopen(handle, 'wb') as output:
                for part in record['parts']:
                    with safe_path(root, part['relative_path']).open('rb') as source:
                        while chunk := source.read(BLOCK):
                            output.write(chunk)
            assert temporary.stat().st_size == record['bytes']
            assert digest(temporary) == record['sha256']
            # Exclusive atomic link: a concurrent or pre-existing file is never replaced.
            os.link(temporary, destination)
            restored.append(dict(relative_path=record['relative_path'], status='MISSING_RECORD_CREATED_VERIFIED'))
        finally:
            temporary.unlink(missing_ok=True)
    return dict(status='ALL_RAW_PARTS_AND_ORIGINAL_SEALED_BYTES_VERIFIED', records=restored,
                packaging_sha256=digest(safe_path(root, PACKAGING.relative_to(ROOT))),
                output_root=str(destination_root), overwrite=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output-root', type=Path)
    options = parser.parse_args()
    print(json.dumps(reconstruct(options.root, options.output_root), ensure_ascii=False))
