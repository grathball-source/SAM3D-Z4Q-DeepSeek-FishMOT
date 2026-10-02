from common import *
import subprocess
from datetime import datetime,timezone

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def main(mode):
    if mode=='index':
        manifest=read(HERE/'PUBLIC_ARTIFACT_MANIFEST.json')
        staged=git('diff','--cached','--name-only','-z').decode().split('\0')[:-1]
        assert not any('/private/' in p or any(s.startswith('slice') for s in Path(p).parts) or '__pycache__' in p for p in staged)
        for item in manifest['files']:
            verify_item(item);assert hashlib.sha256(git('show',':'+item['relative_path'])).hexdigest()==item['sha256'],item['relative_path']
        write_new(HERE/'REMOTE_INDEX_REVIEW.json',dict(status='PASS',staged_files=len(staged),manifest_files=len(manifest['files']),no_private_pixels_or_credentials=True))
    elif mode=='remote':
        head=git('rev-parse','HEAD').decode().strip();remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
        assert head==remote;git('fetch','origin','main');assert git('rev-parse','origin/main').decode().strip()==remote
        keys=['FINAL_REVIEW.md', 'RESULTS.md', 'SUMMARY.json', 'MAIN_JUDGEMENT.json', 'PLAN.md', 'NEXT_STEP_PLAN.md', 'controller.py', 'mixed_depth.py', 'runner.py', 'score.py', 'STRATEGY.json', 'CHECKS.json', 'PREFIX_CHECKS.json', 'REAL_SLICE_CHECKS.json', 'SOURCE_INTERFACE_AUDIT.json', 'SOURCE_POPULATION_CHECKS.json', 'CONTROLLER_REVIEW.json', 'run/POSTSEAL_REPORT.json', 'run/METRICS.json', 'run/ALL_PREDICTIONS_SEALED.json', 'run/SCORE_PROVENANCE.json', 'run/DS16_PARITY.json', 'RESTRICTED_ARTIFACTS.json', 'PUBLIC_ARTIFACT_MANIFEST.json', 'FINAL_CHECKS.json', 'PRIVATE_VISUALS.json', 'EXECUTION_LOG.jsonl']
        checked={}
        keys.extend(['CHECKS_R5.json','IMMUTABLE_EQUIVALENCE.json','IMMUTABLE_RECORD_EQUIVALENCE.json','IMMUTABLE_FACTS_REVIEW.json','IMMUTABLE_RECORDS_REVIEW.json','IMMUTABLE_RECORD_PROFILE.json','REAL_SLICE_SOURCE_SCORER.json','source_population_checks_immutable/SERIALIZED_CASE_EQUIVALENCE.json','EFFECTIVE_RUNTIME.json','FAILURE_VISUALS.json','PUBLIC_PLOTS.json','METRIC_COMPARISON.png'])
        for key in keys:
            path=HERE/key;relative=path.relative_to(ROOT).as_posix();blob=git('show',remote+':'+relative)
            assert len(blob)==path.stat().st_size and hashlib.sha256(blob).hexdigest()==sha(path),relative
            checked[relative]=dict(bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest())
        write_new(HERE/'REMOTE_VERIFICATION.json',dict(status='ACTUAL_REMOTE_REF_AND_KEY_BLOBS_VERIFIED',experiment_commit=head,actual_remote_main=remote,fetched_origin_main=remote,files=checked,force_push=False,time_utc=datetime.now(timezone.utc).isoformat(),note='Verification metadata is committed afterward; final ref and blobs read again after that push.'))
    else:raise ValueError(mode)
    print(mode,'PASS')
if __name__=='__main__':main(sys.argv[1])
