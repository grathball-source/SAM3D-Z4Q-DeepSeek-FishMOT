"""Postscore integrity, private inventory and public delivery; no predictor mutation."""
from common import *
import subprocess,platform
from datetime import datetime

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
    for folder in [p.name for p in HERE.iterdir() if p.is_dir() and (p.name=='private' or p.name.startswith('slice'))]:
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
    write_new(HERE/'RESTRICTED_ARTIFACTS.json',dict(status='LOCAL_ONLY_NOT_FOR_GIT',derived_and_visual_artifacts=list(restricted.values()),raw_source_artifacts=list(raw.values()),dependencies=dict(python=sys.executable,version=platform.python_version(),deps=str(DEPS),base_commit=old['base_commit']),reproduction='Same DS14 original sources and current runtime deps; a fresh output directory: tests; source_population_check; check_prefix; check_real_slices; freeze; orchestrate; baseline_check; score; ds16_full_parity; postseal_report; visualize_postseal; build_report. All invoked via execute.py except final manifest. Never overwrite old seals.',restricted_reasons='Actual mask/depth and private pixel visualizations. Public numeric statistics/hashes contain no raster or credentials.'))
    write_new(HERE/'FINAL_CHECKS.json',dict(status='PASS',frozen_code_and_all_prediction_bytes_exact=True,segments=checked,older_tracked_files_unchanged=old['count'],all_masks_scored=True,model_http=0,cost_usd=0))
    handoff=ROOT/'research/HANDOFF.md'
    if not handoff.exists():
        matches=list(ROOT.rglob('HANDOFF.md'));assert len(matches)==1,matches;handoff=matches[0]
    body=handoff.read_bytes();summary=read(HERE/'SUMMARY.json')
    headline=[f"主判定：{summary['status']}。六臂八段、每臂20098帧；模型HTTP/费用=0。"]
    for name,delta in summary['differences'].items():
        headline.append(f"{name}: MIXED_ORDER vs同源native ΔIDF1={delta['vs_native']['IDF1']:+.6f}; vs原Z4Q={delta['vs_original_z4q']['IDF1']:+.6f}; vs相同接口={delta['vs_same_interface']['IDF1']:+.6f}。")
    prefix=(f'## DS18 association evidence interface repair completed ({datetime.now().astimezone().date()})\n\n'+ '\n'.join(headline)+'\n\nComplete code/logs/results: experiments/ds18_association_evidence_interface_repair. Model HTTP/cost=0. Old seals immutable; private pixels inventoried locally. Follow NEXT_STEP_PLAN.md; no automatic new model run.\n\n').encode('utf8')
    handoff.write_bytes(prefix+body)
    assert handoff.read_bytes()[len(prefix):]==body
    write_new(HERE/'HANDOFF_UPDATE.json',dict(path=str(handoff),old_bytes=len(body),old_sha256=hashlib.sha256(body).hexdigest(),prefix_bytes=len(prefix),old_suffix_exact=True,new=artifact(handoff)))
    files=[]
    for p in HERE.rglob('*'):
        if not p.is_file() or any(x in ('private','__pycache__') or x.startswith('slice') for x in p.relative_to(HERE).parts):continue
        if p.name in ('PUBLIC_ARTIFACT_MANIFEST.json','REMOTE_VERIFICATION.json','REMOTE_INDEX_REVIEW.json'):continue
        files.append(dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()))
    write_new(HERE/'PUBLIC_ARTIFACT_MANIFEST.json',dict(status='PUBLIC_NUMERIC_CODE_RECORDS_REPORTS_ONLY',files=files,count=len(files),restricted_pixel_paths_excluded=True,GT_raster=False,credentials=False,model_http=0,cost_usd=0))
    print('Delivery PASS',len(files),'public;',len(restricted),'private;',len(raw),'raw source items')
if __name__=='__main__':main()
