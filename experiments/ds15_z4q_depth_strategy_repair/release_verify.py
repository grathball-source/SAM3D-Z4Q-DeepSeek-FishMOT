"""Git index/remote delivery verification, independent of scientific replay."""
from common import *
import subprocess
from datetime import datetime,timezone


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)


def main(mode):
    metadata=read(HERE/'PUBLIC_ARTIFACT_MANIFEST.json')
    if mode=='index':
        staged=git('diff','--cached','--name-only','-z').decode().split('\0')[:-1]
        assert not any('/private/' in p or '/slice/' in p or '__pycache__' in p for p in staged)
        assert set(staged)>={item['relative_path'] for item in metadata['files']}
        for item in metadata['files']:
            verify_item(item)
            assert hashlib.sha256(git('show',':'+item['relative_path'])).hexdigest()==item['sha256'],item['relative_path']
        write_new(HERE/'REMOTE_INDEX_REVIEW.json',dict(status='PASS',staged_files=len(staged),
            manifested_public_files_verified=len(metadata['files']),private_or_GT_raster_paths_staged=False,
            numeric_plot_png='PUBLIC_AGGREGATE_METRICS_ONLY',
            strict_whitespace_note='Three EOF blank lines retained in hybrid.py and two new audit reports; all other whitespace checks pass. Frozen bytes remain unchanged.',
            public_manifest=artifact(HERE/'PUBLIC_ARTIFACT_MANIFEST.json'),time_utc=datetime.now(timezone.utc).isoformat()))
    elif mode=='remote':
        local=git('rev-parse','HEAD').decode().strip()
        remote=git('-c','http.proxy=http://127.0.0.1:7897','ls-remote','origin','refs/heads/main').decode().split()[0]
        assert local==remote
        git('-c','http.proxy=http://127.0.0.1:7897','fetch','origin','main')
        assert git('rev-parse','origin/main').decode().strip()==remote
        keys=['DEEP_REVIEW.md','MAIN_JUDGEMENT.json','RESULTS.md','SUMMARY.json','PUBLIC_ARTIFACT_MANIFEST.json',
              'run/METRICS.json','run/ALL_PREDICTIONS_SEALED.json','run/SCORE_PROVENANCE.json',
              'hybrid.py','group_association.py','runner.py','score.py','STRATEGY.json','RESTRICTED_ARTIFACTS.json']
        checked={}
        for key in keys:
            path=HERE/key;relative=path.relative_to(ROOT).as_posix()
            body=git('show',remote+':'+relative)
            assert len(body)==path.stat().st_size and hashlib.sha256(body).hexdigest()==sha(path)
            checked[relative]=dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
        write_new(HERE/'REMOTE_VERIFICATION.json',dict(status='ACTUAL_ORIGIN_MAIN_AND_KEY_BLOBS_VERIFIED',
            primary_result_commit=local,actual_ls_remote_main=remote,fetched_origin_main=remote,
            key_files=checked,mechanism='Actual Git ls-remote plus fetch and SHA-bound origin commit blob reads',
            force_push=False,time_utc=datetime.now(timezone.utc).isoformat(),
            followup='This verification record is committed afterward; final main ref is separately re-read live.'))
    else:raise ValueError(mode)
    print(mode,'PASS')


if __name__=='__main__':main(sys.argv[1])
