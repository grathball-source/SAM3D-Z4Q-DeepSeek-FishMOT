"""Postscore byte integrity, private inventory and non-destructive handoff."""
from common import *
import platform
from datetime import datetime


def main():
    assert read(RUN/'SCORE_PROVENANCE.json')['reference_opened_after_all_seals']
    for name in SEGMENTS:
        public=RUN/name/'public'
        for file,digest in read(public/'PREDICTIONS_SEALED.json')['artifacts_sha256'].items():
            assert sha(public/file)==digest,(name,file)
        for path,digest in read(public/'FREEZE.json')['code_sha256'].items():assert sha(path)==digest,path
    old=read(HERE/'OLD_READONLY_LOCK.json')
    for path,digest in old['files'].items():assert sha(ROOT/path)==digest,path
    restricted={};raw={}
    for name in SEGMENTS:
        for path in input_dir(name).iterdir():
            if path.is_file():restricted[str(path.resolve())]=artifact(path)
    for folder in HERE.iterdir():
        if folder.is_dir() and (folder.name=='private' or folder.name.startswith('slice')):
            for path in folder.rglob('*'):
                if path.is_file():restricted[str(path.resolve())]=artifact(path)
    def collect(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=value.keys():
                item={k:value[k] for k in ('path','bytes','sha256')};raw[item['path']]=item
            else:
                for child in value.values():collect(child)
        elif isinstance(value,list):
            for child in value:collect(child)
    for name in SEGMENTS:collect(read(input_dir(name)/'RAW_SOURCES.json'))
    write_new(HERE/'RESTRICTED_ARTIFACTS.json',dict(status='LOCAL_ONLY_NOT_FOR_GIT',
        derived_and_visual_artifacts=list(restricted.values()),raw_source_artifacts=list(raw.values()),
        dependencies=dict(python=sys.executable,version=platform.python_version(),deps=str(DEPS),
            base_commit=old['base_commit'],sealed_measurements=str(DS18/'run')),
        reproduction='Use same DS14 source manifests and exact DS18 sealed measurement cache; DS19 old controller and RETURN branches are read-only controls. Fresh output directory only. Through execute.py run checks.py, cache_checks.py, check_prefix.py, check_prefix_sources.py, review_confirmation_slices.py, check_runtime.py, freeze.py, orchestrate.py, score.py, audit_confirmation.py, report.py and postscore audits/visuals. Run finalize_delivery.py directly after all logs are complete. Never overwrite existing sources/results/seals.',
        restricted_reasons='Actual masks, depth, private pixel visualizations and engineering slices. Numeric facts/hashes are public; no raster or credentials.'))
    write_new(HERE/'FINAL_CHECKS.json',dict(status='PASS',segments=len(SEGMENTS),frames_per_arm=20098,
        frozen_code_and_all_prediction_bytes_exact=True,old_tracked_files_unchanged=old['count'],
        all_masks_scored=True,new_model_http=0,cost_usd=0))
    handoff=ROOT/'research/HANDOFF.md';body=handoff.read_bytes()
    summary=read(HERE/'SUMMARY.json')
    prefix=(f'## DS20 pending confirmation isolation completed ({datetime.now().astimezone().date()})\n\n'
        f"主判定：{summary['status']}。六列八段，每列20098帧；模型HTTP/费用=0。\n"
        '完整结果见 experiments/ds20_pending_confirmation_isolation/RESULTS.md、FINAL_REVIEW.md。'
        '确认隔离工程、事务恢复与深度增量分列，DS19旧seal只读。仅规划 NEXT_STEP_PLAN.md，不自动启动模型。\n\n').encode('utf-8')
    handoff.write_bytes(prefix+body)
    assert handoff.read_bytes()[len(prefix):]==body
    write_new(HERE/'HANDOFF_UPDATE.json',dict(path=str(handoff),old_bytes=len(body),
        old_sha256=hashlib.sha256(body).hexdigest(),prefix_bytes=len(prefix),old_suffix_exact=True,new=artifact(handoff)))
    files=[]
    excluded={'PUBLIC_ARTIFACT_MANIFEST.json','REMOTE_VERIFICATION.json','REMOTE_INDEX_REVIEW.json'}
    for path in HERE.rglob('*'):
        if not path.is_file() or path.name in excluded or any(part=='private' or part=='__pycache__' or part.startswith('slice')
            for part in path.relative_to(HERE).parts):continue
        files.append(dict(artifact(path),relative_path=path.relative_to(ROOT).as_posix()))
    write_new(HERE/'PUBLIC_ARTIFACT_MANIFEST.json',dict(status='PUBLIC_NUMERIC_CODE_LOGS_PREDICTIONS_AND_REPORTS_ONLY',
        files=files,count=len(files),repository_files=[dict(artifact(path),relative_path=path.relative_to(ROOT).as_posix())
            for path in (handoff,ROOT/'.gitignore')],
        restricted_pixel_paths_excluded=True,GT_raster=False,credentials=False,
        new_model_http=0,cost_usd=0))
    print('Delivery PASS',len(files),'public;',len(restricted),'restricted;',len(raw),'raw source files')


if __name__=='__main__':main()
