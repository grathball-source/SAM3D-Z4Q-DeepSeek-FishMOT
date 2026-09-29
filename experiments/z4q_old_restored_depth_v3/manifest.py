"""Hash all distributable artifacts, excluding this output and caches."""
from run import HERE, px


def main():
    output = HERE / 'public/ARTIFACT_MANIFEST.json'
    assert not output.exists()
    entries = []
    for path in sorted(HERE.rglob('*')):
        if (not path.is_file() or path == output or '__pycache__' in path.parts
                or path.suffix == '.pyc'):
            continue
        entries.append(dict(path=path.relative_to(HERE).as_posix(),
                            bytes=path.stat().st_size, sha256=px.sha(path)))
    px.save(output, dict(status='PUBLIC_ARTIFACTS_HASHED_EXCEPT_THIS_FILE',
                         files=len(entries), total_bytes=sum(x['bytes'] for x in entries),
                         entries=entries))
    print(dict(files=len(entries), bytes=sum(x['bytes'] for x in entries)), flush=True)


if __name__ == '__main__':
    main()
