"""Actual staged bytes and fetched remote main contents, never just a push receipt."""
from common import *
import subprocess
from datetime import datetime,timezone


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)


def main(mode):
    manifest=read(HERE/'PUBLIC_ARTIFACT_MANIFEST.json')
    if mode=='index':
        staged=git('diff','--cached','--name-only','-z').decode().split('\0')[:-1]
        assert not any('/private/' in path or any(part.startswith('slice') for part in Path(path).parts)
            or '__pycache__' in path for path in staged)
        for item in manifest['files']+manifest['repository_files']:
            verify_item(item)
            assert hashlib.sha256(git('show',':'+item['relative_path'])).hexdigest()==item['sha256'],item['relative_path']
        write_new(HERE/'REMOTE_INDEX_REVIEW.json',dict(status='PASS',staged_files=len(staged),
            manifest_files=len(manifest['files']),repository_files=len(manifest['repository_files']),
            no_private_pixels_or_credentials=True))
    elif mode in ('remote','final'):
        head=git('rev-parse','HEAD').decode().strip()
        remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
        assert head==remote;git('fetch','origin','main')
        assert git('rev-parse','origin/main').decode().strip()==remote
        checked={}
        items=list(manifest['files'])+manifest['repository_files']
        for name in ('PUBLIC_ARTIFACT_MANIFEST.json','REMOTE_INDEX_REVIEW.json'):
            path=HERE/name
            items.append(dict(artifact(path),relative_path=path.relative_to(ROOT).as_posix()))
        if mode=='final':
            path=HERE/'REMOTE_VERIFICATION.json'
            items.append(dict(artifact(path),relative_path=path.relative_to(ROOT).as_posix()))
        # The execution ledger can acquire delivery-only records after its manifest snapshot.
        for item in items:
            path=ROOT/item['relative_path'];blob=git('show',remote+':'+item['relative_path'])
            assert len(blob)==path.stat().st_size and hashlib.sha256(blob).hexdigest()==sha(path),item['relative_path']
            if path.name!='EXECUTION_LOG.jsonl':assert sha(path)==item['sha256'],path
            checked[item['relative_path']]=dict(bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest())
        record=dict(status='ACTUAL_REMOTE_REF_AND_ALL_PUBLIC_BLOBS_VERIFIED',experiment_commit=head,
            actual_remote_main=remote,fetched_origin_main=remote,files=checked,force_push=False,
            time_utc=datetime.now(timezone.utc).isoformat())
        if mode=='remote':
            record['note']='Delivery metadata is committed afterward; final ref and every public blob read again after that push.'
            write_new(HERE/'REMOTE_VERIFICATION.json',record)
        else:print(json.dumps(dict(status=record['status'],remote_main=remote,verified_files=len(checked))))
    else:raise ValueError(mode)
    print(mode,'PASS')


if __name__=='__main__':main(sys.argv[1])
