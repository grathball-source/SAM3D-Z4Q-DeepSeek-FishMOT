"""Delivery metadata only: preserve old bytes and verify actual remote blobs."""
import gzip, hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import run

HERE, ROOT = run.HERE, run.ROOT

def git(*args): return subprocess.check_output(['git', *args], cwd=ROOT)

def files():
    omit={'PUBLIC_ARTIFACT_MANIFEST.json','INDEX_REVIEW.json','REMOTE_VERIFICATION.json'}
    return sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in omit and
        'private' not in p.relative_to(HERE).parts and '__pycache__' not in p.relative_to(HERE).parts)

def finalize():
    run.verify_freeze(); run.verify_measurement_seal()
    assert run.old.read(HERE/'INDEPENDENT_REVIEW.json')['status']=='PASS'
    assert run.old.read(HERE/'RESULTS.json')['new_metrics'] is None
    base=run.old.read(HERE/'OLD_TRACKED_BASE.json')
    assert git('rev-parse','HEAD').decode().strip()==base['base_commit']
    assert not git('diff','--name-only').decode().strip()
    raw={}
    def collect(v):
        if isinstance(v,dict):
            if {'path','bytes','sha256'}<=v.keys():raw[v['path']]={k:v[k] for k in ('path','bytes','sha256')}
            else:
                for x in v.values():collect(x)
        elif isinstance(v,list):
            for x in v:collect(x)
    for row in run.old.rows(HERE/'MEASUREMENTS.jsonl.gz'):collect(row['measurement']['source_binding'])
    private=[run.old.artifact(p) for p in (HERE/'private').rglob('*') if p.is_file()]
    run.save('RESTRICTED_ARTIFACTS.json',dict(status='ACTUAL_LOCAL_PATH_BYTES_SHA_ONLY; PRIVATE_PIXELS_NOT_PUBLISHED',
        figures=private,original_raw_sources=list(raw.values()),
        dependencies=dict(python=sys.executable,base_commit=run.BASE,deps='E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps',
            original_source='DS14 private original SAM3 source; same DS21 seals/facts; no restored values'),
        reproduction='Fresh output directory only: execute run initialize, checks, run freeze, run measure, run join, visualize, INDEPENDENT_REVIEW. Preserve same source paths/metadata/manifests and source indexes. Never overwrite this run or old seals.',
        source_manifest_pins=run.old.read(HERE/'CHECKS.json')['actual_source_pins'],RGB_read=False,GT_raster_read=False,new_model_http=0,cost_usd=0))
    additive={}
    for path,pin,prefix,extra in (
        (ROOT/'research/HANDOFF.md',base['handoff'],True,
         ('## DS22 local-background measurement experiment completed (2026-10-04)\n\n'
          'All90 original actions: correct5 compatible/10 unknown, wrong1 weak conflict/3 compatible/13 unknown, '
          'unscorable1 conflict/3 compatible/54 unknown. All171 endpoints were reopened and validated. '
          'No tracker replay, new scores or model HTTP. Engineering complete; depth increment insufficient; '
          'STOP this frozen representation. Original Z4Q remains the reference. '
          'See experiments/ds22_local_background_depth/FINAL_REVIEW.md and NEXT_STEP_PLAN.md. '
          'The single next plan is a fixed RGB-D spatial-correspondence audit, not yet run. Old seals remain read-only; pixels private.\n\n').encode()),
        (ROOT/'.gitignore',base['gitignore'],False,
         b'\n# DS22 actual depth/mask/plane/support visual pixels remain private.\n/experiments/ds22_local_background_depth/private/\n')):
        run.old.verify_item(pin); old=path.read_bytes();path.write_bytes(extra+old if prefix else old+extra)
        assert (path.read_bytes()[len(extra):] if prefix else path.read_bytes()[:len(old)])==old
        additive[path.relative_to(ROOT).as_posix()]=dict(old=pin,new=run.old.artifact(path),old_bytes_preserved=True)
    run.save('HANDOFF_UPDATE.json',additive)
    assert set(git('diff','--name-only').decode().splitlines())=={'.gitignore','research/HANDOFF.md'}
    for pin in private: assert git('check-ignore',pin['path']).decode().strip()
    records=0
    def check(v):
        if isinstance(v,dict):
            assert not {'rle','polygons','segmentation','depth_pixels','pixel_values','api_key','provider_file_id'} & v.keys()
            for x in v.values():check(x)
        elif isinstance(v,list):
            assert len(v)<=32 or not all(isinstance(x,(int,float)) for x in v),'Private numerical raster'
            for x in v:check(x)
    for p in files():
        assert p.suffix.lower() not in {'.png','.jpg','.npy','.npz','.h5','.mp4'}
        if p.suffix=='.json':check(run.old.read(p));records+=1
        elif p.name.endswith('.jsonl.gz') or p.suffix=='.jsonl':
            opener=gzip.open if p.suffix=='.gz' else open
            with opener(p,'rt',encoding='utf-8') as f:
                for line in f:check(json.loads(line));records+=1
    run.save('PUBLIC_CONTENT_REVIEW.json',dict(status='PASS',numeric_records=records,private_figures=len(private),
        only_two_old_metadata_files_additively_changed=True,frozen_science_and_old_source_unchanged=True,
        no_serialized_private_pixels_GT_credentials_provider_ids=True,new_model_http=0,cost_usd=0))
    public=[dict(run.old.artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in files()]
    run.save('PUBLIC_ARTIFACT_MANIFEST.json',dict(files=public,repository_files=[dict(run.old.artifact(p),relative_path=p.relative_to(ROOT).as_posix())
        for p in (ROOT/'.gitignore',ROOT/'research/HANDOFF.md')],private_pixels_excluded=True,new_model_http=0,cost_usd=0))
    print('Delivery public/source/private checks PASS',len(public),'public files',len(private),'private figures')

def verify(mode):
    manifest=run.old.read(HERE/'PUBLIC_ARTIFACT_MANIFEST.json')
    pins=manifest['files']+manifest['repository_files']
    def add(name):
        p=HERE/name;pins.append(dict(run.old.artifact(p),relative_path=p.relative_to(ROOT).as_posix()))
    add('PUBLIC_ARTIFACT_MANIFEST.json')
    if mode=='index':
        names=git('diff','--cached','--name-only','-z').decode().split('\0')[:-1]
        assert set(names)=={p['relative_path'] for p in pins}
        for p in pins:assert hashlib.sha256(git('show',':'+p['relative_path'])).hexdigest()==p['sha256']
        run.save('INDEX_REVIEW.json',dict(status='PASS',actual_staged_blobs_verified=len(names),no_private_pixels=True))
        print('Actual staged bytes PASS',len(names));return
    head=git('rev-parse','HEAD').decode().strip();remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    assert head==remote;git('fetch','origin','main');assert git('rev-parse','origin/main').decode().strip()==remote
    add('INDEX_REVIEW.json')
    if mode=='final':add('REMOTE_VERIFICATION.json')
    result={}
    for p in pins:
        data=git('show',remote+':'+p['relative_path'])
        assert len(data)==p['bytes'] and hashlib.sha256(data).hexdigest()==p['sha256']
        result[p['relative_path']]=dict(bytes=len(data),sha256=p['sha256'])
    if mode=='remote':run.save('REMOTE_VERIFICATION.json',dict(status='ACTUAL_REMOTE_REF_AND_ALL_PUBLIC_BLOBS_VERIFIED',
        science_commit=head,remote_main=remote,files=result,force_push=False,verified_utc=datetime.now(timezone.utc).isoformat(),
        note='Receipt is committed next. Final ref and all blobs are reread after receipt push.',new_model_http=0,cost_usd=0))
    print(json.dumps(dict(status='ACTUAL_REMOTE_REF_AND_ALL_PUBLIC_BLOBS_VERIFIED',remote_main=remote,files=len(result))))

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='finalize':finalize()
    else:assert mode in ('index','remote','final');verify(mode)
