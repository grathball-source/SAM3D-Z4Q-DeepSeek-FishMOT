"""Postscore integrity, private inventory and public delivery; no predictor mutation."""
from common import *
import subprocess,platform

def main():
    assert read(RUN/'SCORE_PROVENANCE.json')['reference_opened_after_all_seals']
    checked=0
    for name in SEGMENTS:
        seal=read(RUN/name/'public/PREDICTIONS_SEALED.json')
        for f,digest in seal['artifacts_sha256'].items():assert sha(RUN/name/'public'/f)==digest,(name,f)
        for f,digest in read(RUN/name/'public/FREEZE.json')['code_sha256'].items():assert sha(f)==digest,f
        checked+=1
    old=read(HERE/'OLD_READONLY_LOCK.json')
    for f,digest in old['files'].items():assert sha(ROOT/f)==digest,f
    restricted={}
    for name in SEGMENTS:
        for p in input_dir(name).iterdir():
            if p.is_file():restricted[str(p.resolve())]=artifact(p)
    for folder in ('private','slice'):
        for p in (HERE/folder).rglob('*'):
            if p.is_file():restricted[str(p.resolve())]=artifact(p)
    raw={}
    def collect(x):
        if isinstance(x,dict):
            if {'path','bytes','sha256'}<=x.keys():
                v={k:x[k] for k in ('path','bytes','sha256')};raw[v['path']]=v
            else:
                for v in x.values():collect(v)
        elif isinstance(x,list):
            for v in x:collect(v)
    for name in SEGMENTS:collect(read(input_dir(name)/'RAW_SOURCES.json'))
    write_new(HERE/'RESTRICTED_ARTIFACTS.json',dict(status='LOCAL_ONLY_NOT_FOR_GIT',derived_and_visual_artifacts=list(restricted.values()),raw_source_artifacts=list(raw.values()),dependencies=dict(python=sys.executable,version=platform.python_version(),deps=str(DEPS),base_commit=old['base_commit']),reproduction='Identical DS14/source raw inputs and deps; fresh output checkout only: execute.py tests.py; execute.py check_prefix.py; execute.py freeze.py; execute.py orchestrate.py; execute.py baseline_check.py; execute.py score.py; execute.py ds16_full_parity.py; execute.py report_schema_repair.py --run; execute.py postseal_action_review.py; execute.py visualize_postseal.py; execute.py failure_visuals.py; execute.py plot_results.py; python -B feeding_new_review.py; python -B measurement_policy_review.py; python -B review_state_postscore.py; execute.py build_report.py. Never overwrite previous output seals.',restricted_reasons='Actual mask/depth and private pixel visualizations. Public numeric statistics/hashes contain no raster or credentials.'))
    write_new(HERE/'FINAL_CHECKS.json',dict(status='PASS',frozen_code_and_all_prediction_bytes_exact=True,segments=checked,older_tracked_files_unchanged=old['count'],all_masks_scored=True,model_http=0,cost_usd=0))
    handoff=ROOT/'research/HANDOFF.md'
    if not handoff.exists():
        matches=list(ROOT.rglob('HANDOFF.md'));assert len(matches)==1,matches;handoff=matches[0]
    body=handoff.read_bytes();summary=read(HERE/'SUMMARY.json')
    headline=(HERE/'FINAL_REVIEW.md').read_text(encoding='utf8').split('## 真实主比较')[0].splitlines()[2:]
    prefix=('## DS17 mixed depth/activity repair completed (2026-10-02)\n\n'+ '\n'.join(headline)+'\n\nComplete code/logs/results: experiments/ds17_mixed_depth_activity_repair. Model HTTP/cost=0. Old seals immutable; private pixels inventoried locally. Follow NEXT_STEP_PLAN.md; no automatic new model run.\n\n').encode('utf8')
    handoff.write_bytes(prefix+body)
    assert handoff.read_bytes()[len(prefix):]==body
    write_new(HERE/'HANDOFF_UPDATE.json',dict(path=str(handoff),old_bytes=len(body),old_sha256=hashlib.sha256(body).hexdigest(),prefix_bytes=len(prefix),old_suffix_exact=True,new=artifact(handoff)))
    files=[]
    for p in HERE.rglob('*'):
        if not p.is_file() or any(x in p.relative_to(HERE).parts for x in ('private','slice','__pycache__')):continue
        if p.name in ('PUBLIC_ARTIFACT_MANIFEST.json','REMOTE_VERIFICATION.json','REMOTE_INDEX_REVIEW.json'):continue
        files.append(dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()))
    write_new(HERE/'PUBLIC_ARTIFACT_MANIFEST.json',dict(status='PUBLIC_NUMERIC_CODE_RECORDS_REPORTS_ONLY',files=files,count=len(files),restricted_pixel_paths_excluded=True,GT_raster=False,credentials=False,model_http=0,cost_usd=0))
    print('Delivery PASS',len(files),'public;',len(restricted),'private;',len(raw),'raw source items')
if __name__=='__main__':main()
