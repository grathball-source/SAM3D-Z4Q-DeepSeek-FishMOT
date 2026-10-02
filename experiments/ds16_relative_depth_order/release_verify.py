"""Postexperiment Git delivery checks; never changes the frozen scientific run."""
from common import *
import subprocess
from datetime import datetime, timezone


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main(mode):
    manifest = read(HERE/'PUBLIC_ARTIFACT_MANIFEST.json')
    if mode == 'index':
        staged = git('diff', '--cached', '--name-only', '-z').decode().split('\0')[:-1]
        assert not any('/private/' in p or '/slice/' in p or '__pycache__' in p for p in staged)
        assert set(staged) >= {item['relative_path'] for item in manifest['files']}
        for item in manifest['files']:
            verify_item(item)
            assert hashlib.sha256(git('show', ':'+item['relative_path'])).hexdigest() == item['sha256'], item['relative_path']
        write_new(HERE/'REMOTE_INDEX_REVIEW.json', dict(status='PASS', staged_files=len(staged),
            manifested_public_files_verified=len(manifest['files']), private_or_GT_raster_paths_staged=False,
            numeric_plot_png='PUBLIC_AGGREGATE_METRICS_ONLY', public_manifest=artifact(HERE/'PUBLIC_ARTIFACT_MANIFEST.json'),
            time_utc=datetime.now(timezone.utc).isoformat()))
    elif mode == 'remote':
        local = git('rev-parse', 'HEAD').decode().strip()
        remote = git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
        assert local == remote
        git('fetch', 'origin', 'main')
        assert git('rev-parse', 'origin/main').decode().strip() == remote
        keys = ['DEEP_REVIEW.md', 'MAIN_JUDGEMENT.json', 'RESULTS.md', 'SUMMARY.json',
            'PUBLIC_ARTIFACT_MANIFEST.json', 'run/METRICS.json', 'run/ALL_PREDICTIONS_SEALED.json',
            'run/SCORE_PROVENANCE.json', 'controller.py', 'order_association.py', 'runner.py',
            'score.py', 'STRATEGY.json', 'RESTRICTED_ARTIFACTS.json', 'STATE_LIFECYCLE_AUDIT.json',
            'ORDER_MECHANISM_AUDIT.json', 'PIPELINE_READONLY_AUDIT.json',
            'STATE_BASELINE_DIVERGENCE_AUDIT.json', 'NEXT_STEP_PLAN.md', 'PRIVATE_STATE_VISUALS.json']
        checked = {}
        for key in keys:
            path = HERE/key
            relative = path.relative_to(ROOT).as_posix()
            body = git('show', remote+':'+relative)
            assert len(body) == path.stat().st_size and hashlib.sha256(body).hexdigest() == sha(path), relative
            checked[relative] = dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        write_new(HERE/'REMOTE_VERIFICATION.json', dict(status='ACTUAL_ORIGIN_MAIN_AND_KEY_BLOBS_VERIFIED',
            primary_result_commit=local, actual_ls_remote_main=remote, fetched_origin_main=remote,
            key_files=checked, mechanism='Actual ls-remote, fetch and SHA-bound remote commit blob reads',
            force_push=False, time_utc=datetime.now(timezone.utc).isoformat(),
            followup='This proof is committed afterward; final main is re-read live after the metadata push.'))
    else:
        raise ValueError(mode)
    print(mode, 'PASS')


if __name__ == '__main__':
    main(sys.argv[1])
