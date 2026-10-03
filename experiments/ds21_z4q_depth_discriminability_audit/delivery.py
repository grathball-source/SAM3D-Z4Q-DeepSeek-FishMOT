"""Delivery-only public-byte review, additive handoff and actual remote checks."""
from pathlib import Path
from datetime import datetime,timezone
import gzip,hashlib,json,platform,subprocess,sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.dont_write_bytecode=True

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def item(p):
    p=Path(p).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
def write(name,obj):
    with (HERE/name).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def public_files():
    excluded={'PUBLIC_ARTIFACT_MANIFEST.json','REMOTE_INDEX_REVIEW.json','REMOTE_VERIFICATION.json'}
    return sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in excluded and
        'private' not in p.relative_to(HERE).parts and '__pycache__' not in p.relative_to(HERE).parts)

def finalize():
    proof=read(HERE/'INDEPENDENT_CHECK.json');assert proof['status']=='PASS'
    assert read(HERE/'DIAGNOSTIC_RESULTS.json')['new_metrics'] is None
    assert (HERE/'FINAL_REVIEW.md').exists() and (HERE/'NEXT_STEP_PLAN.md').exists()
    freeze=read(HERE/'FREEZE.json')
    for path,pin in freeze['code'].items():
        p=Path(path);assert p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],path
    for pin in read(HERE/'BEGIN_SOURCE_CHECK.json')['artifacts']:
        assert item(pin['path'])=={k:pin[k] for k in ('path','bytes','sha256')},pin['path']
    base=read(HERE/'OLD_TRACKED_BASE.json');assert git('rev-parse','HEAD').decode().strip()==base['base_commit']
    assert git('diff','--name-only').decode().strip()=='','Old tracked files changed before delivery'
    restricted=[item(p) for p in (HERE/'private').rglob('*') if p.is_file()]
    figures=read(HERE/'PRIVATE_VISUALS.json')
    raw={}
    def collect(v):
        if isinstance(v,dict):
            if {'path','bytes','sha256'}<=v.keys():raw[v['path']]={k:v[k] for k in ('path','bytes','sha256')}
            else:
                for x in v.values():collect(x)
        elif isinstance(v,list):
            for x in v:collect(x)
    for figure in figures['figures']:
        for panel in figure['panels']:collect(panel['raw_source_binding'])
    write('RESTRICTED_ARTIFACTS.json',dict(status='LOCAL_ONLY_ACTUAL_PRIVATE_PIXELS_NOT_FOR_GIT',
        derived_figures=restricted,raw_sources_referenced_by_actual_visual_bindings=list(raw.values()),
        original_derived_source_manifests=[pin for pin in read(HERE/'BEGIN_SOURCE_CHECK.json')['artifacts']
            if 'ds14_raw_multidataset/private/' in pin['path'].replace('\\','/')],
        dependencies=dict(python=sys.executable,version=platform.python_version(),base_commit=base['base_commit'],
            old_measurement_cache='experiments/ds18_association_evidence_interface_repair/run',
            source='experiments/ds14_raw_multidataset/private',deps='E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps'),
        reproduction='Fresh output directory only. Preserve exact DS20 seals and DS18 cache parts/ledgers plus DS14 derived/raw manifests. Run initialize, checks, freeze, audit, visualize, review and report in that order using the logged interpreter. Never overwrite old code, predictions or audit outputs.',
        raw_pixels_SHA_policy='Actual selected raw arrays were reopened and matched every complete frozen source/array binding during visualize; figures have actual file bytes/SHA. Original source manifests list full raw file paths/bytes/SHA.',
        GT_raster=False,RGB=False,new_model_http=0,cost_usd=0))
    suffix_checks={}
    handoff=ROOT/'research/HANDOFF.md';old=handoff.read_bytes()
    assert len(old)==base['handoff']['bytes'] and hashlib.sha256(old).hexdigest()==base['handoff']['sha256']
    prefix=('## DS21 original Z4Q depth discriminability audit completed (2026-10-04)\n\n'
        'All 90 original durable actions were audited symmetrically, including correct, wrong and unscorable cases. '
        'No new predictions, scoring or model HTTP were run. Measurement eligibility is not a tracking gain. '
        'See experiments/ds21_z4q_depth_discriminability_audit/FINAL_REVIEW.md and NEXT_STEP_PLAN.md for evidence and the single next action. '
        'Original Z4Q remains the performance reference; the current combined route is not automatically extended. '
        'Old seals are read-only; actual depth/mask figures remain private.\n\n').encode()
    handoff.write_bytes(prefix+old);assert handoff.read_bytes()[len(prefix):]==old
    suffix_checks['handoff']=dict(old_sha256=base['handoff']['sha256'],added_bytes=len(prefix),old_suffix_exact=True,new=item(handoff))
    ignore=ROOT/'.gitignore';old=ignore.read_bytes()
    assert len(old)==base['gitignore']['bytes'] and hashlib.sha256(old).hexdigest()==base['gitignore']['sha256']
    extra=b'\n# DS21 actual diagnostic depth/mask figures remain private.\n/experiments/ds21_z4q_depth_discriminability_audit/private/\n'
    ignore.write_bytes(old+extra);assert ignore.read_bytes()[:len(old)]==old
    suffix_checks['gitignore']=dict(old_sha256=base['gitignore']['sha256'],added_bytes=len(extra),old_prefix_exact=True,new=item(ignore))
    write('HANDOFF_UPDATE.json',suffix_checks)
    changed=git('diff','--name-only').decode().splitlines()
    assert set(changed)=={'.gitignore','research/HANDOFF.md'}
    for path in restricted:
        assert git('check-ignore',path['path']).decode().strip()
    assert not any(p.suffix.lower() in ('.png','.jpg','.npy','.npz','.mp4') for p in public_files())
    # No raster/RLE or long numeric pixel population may be serialized publicly.
    records=0
    def inspect(v):
        nonlocal records
        if isinstance(v,dict):
            assert not {'rle','segmentation','polygons','pixel_values','depth_pixels','provider_file_id','api_key'} & set(v)
            if 'mask' in v:assert isinstance(v['mask'],str) and v['mask'].startswith('n:')
            for child in v.values():inspect(child)
        elif isinstance(v,list):
            assert len(v)<=32 or not all(isinstance(x,(int,float)) for x in v),'Serialized numeric raster'
            for child in v:inspect(child)
    for path in public_files():
        if path.suffix=='.json':inspect(read(path));records+=1
        elif path.name.endswith('.jsonl.gz') or path.suffix=='.jsonl':
            opener=gzip.open if path.name.endswith('.gz') else open
            with opener(path,'rt',encoding='utf-8') as f:
                for line in f:inspect(json.loads(line));records+=1
    write('PUBLIC_CONTENT_REVIEW.json',dict(status='PASS',logical_numeric_records=records,
        private_figures=len(restricted),only_two_old_repository_files_additively_changed=True,
        frozen_science_and_original_source_bytes_unchanged=True,no_pixels_RLE_GT_RGB_credentials_or_provider_ids=True,
        new_predictions=0,new_scoring=0,new_model_http=0,cost_usd=0))
    files=[dict(item(p),relative_path=p.relative_to(ROOT).as_posix()) for p in public_files()]
    write('PUBLIC_ARTIFACT_MANIFEST.json',dict(status='PUBLIC_DIAGNOSTIC_CODE_NUMERIC_FACTS_LOGS_REPORTS_ONLY',files=files,
        repository_files=[dict(item(p),relative_path=p.relative_to(ROOT).as_posix()) for p in (handoff,ignore)],
        count=len(files),new_model_http=0,cost_usd=0,private_pixels_excluded=True))
    print('DS21 delivery source/public/private checks PASS',len(files),'public',len(restricted),'private')

def verify(mode):
    manifest=read(HERE/'PUBLIC_ARTIFACT_MANIFEST.json')
    items=manifest['files']+manifest['repository_files']
    items+=[dict(item(HERE/'PUBLIC_ARTIFACT_MANIFEST.json'),relative_path=(HERE/'PUBLIC_ARTIFACT_MANIFEST.json').relative_to(ROOT).as_posix())]
    if mode=='index':
        staged=git('diff','--cached','--name-only','-z').decode().split('\0')[:-1]
        for p in staged:assert '/private/' not in p and '__pycache__' not in p
        assert set(staged)=={p['relative_path'] for p in items}
        for p in items:assert hashlib.sha256(git('show',':'+p['relative_path'])).hexdigest()==p['sha256']
        write('REMOTE_INDEX_REVIEW.json',dict(status='PASS',staged_files=len(staged),actual_staged_blobs_exact=True))
        print('Actual index PASS',len(staged));return
    head=git('rev-parse','HEAD').decode().strip()
    remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    assert head==remote;git('fetch','origin','main')
    assert git('rev-parse','origin/main').decode().strip()==remote
    for filename in ('REMOTE_INDEX_REVIEW.json',)+(('REMOTE_VERIFICATION.json',) if mode=='final' else ()):
        p=HERE/filename;items.append(dict(item(p),relative_path=p.relative_to(ROOT).as_posix()))
    verified={}
    for p in items:
        blob=git('show',remote+':'+p['relative_path'])
        assert len(blob)==p['bytes'] and hashlib.sha256(blob).hexdigest()==p['sha256'],p['relative_path']
        verified[p['relative_path']]=dict(bytes=len(blob),sha256=p['sha256'])
    if mode=='remote':write('REMOTE_VERIFICATION.json',dict(status='ACTUAL_REMOTE_REF_AND_ALL_PUBLIC_BLOBS_VERIFIED',
        science_commit=head,remote_main=remote,files=verified,force_push=False,
        verified_utc=datetime.now(timezone.utc).isoformat(),note='Receipt is committed next; final ref and blobs are reread after second push.'))
    print(json.dumps(dict(status='ACTUAL_REMOTE_REF_AND_ALL_PUBLIC_BLOBS_VERIFIED',remote_main=remote,files=len(verified))))

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='finalize':finalize()
    else:assert mode in ('index','remote','final');verify(mode)
