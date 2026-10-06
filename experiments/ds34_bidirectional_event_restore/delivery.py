"""Public numeric inventory; actual non-force main/ref/blob verification."""
from common import *
import subprocess
from datetime import datetime, timezone

OMIT = {'PUBLIC_ARTIFACT_MANIFEST.json', 'INDEX_REVIEW.json', 'REMOTE_VERIFICATION.json'}

def git(*args):
    env = os.environ.copy()
    options = {'http.sslBackend':'schannel', 'http.sslVerify':'true', 'http.proxy':'',
               'gc.auto':'0', 'pack.threads':'2', 'http.version':'HTTP/1.1'}
    env['GIT_CONFIG_COUNT'] = str(len(options))
    for i,(key,value) in enumerate(options.items()):
        env[f'GIT_CONFIG_KEY_{i}'],env[f'GIT_CONFIG_VALUE_{i}'] = key,value
    return subprocess.check_output(['git',*args],cwd=ROOT,env=env)

def files():
    return sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in OMIT
        and not {'private','__pycache__'} & set(p.relative_to(HERE).parts))

def numeric(value):
    if isinstance(value,dict):
        assert not {'rle','polygons','segmentation','depth_pixels','pixel_values',
                    'api_key','provider_file_id','counts_rle'} & value.keys()
        for child in value.values(): numeric(child)
    elif isinstance(value,list):
        for child in value: numeric(child)

def prepare():
    from verify_inputs import verify_all
    verify_all()
    assert git('rev-parse','HEAD').decode().strip()==BASE
    assert not git('diff','--name-only').decode().strip()
    assert read(HERE/'REPORT_VALIDATION.json')['status']=='PASS'
    assert read(HERE/'VISUAL_ACCEPTANCE.json')['status']=='PASS_ACTUAL_LOCAL_VISUAL_INSPECTION'
    for path,expected in read(HERE/'RUNTIME_FREEZE.json')['code'].items():
        assert sha(path)==expected
    private=[artifact(p) for p in (HERE/'private').rglob('*') if p.is_file()]
    previous=ROOT/'experiments/ds33_rgbd_fixed_lag'
    write_new(HERE/'PRIVATE_INVENTORY.json',dict(private_outputs=private,
        source_sensor_files=artifact(previous/'SENSOR_AUDIT.json'),
        source_RGB_files=artifact(previous/'RGB_INPUT_PINS.jsonl'),
        saved_source_and_depth={name:read(RUN/name/'public/FREEZE.json') for name in SEGMENTS},
        runtime=artifact(HERE/'RUNTIME_FREEZE.json'),Python=sys.executable,dependencies=str(DEPS),
        reproduction='Use a fresh checkout of frozen BASE plus delivered DS34 code. Provide the exact recorded private '
            'DS14 SAM3 N0 masks, native/aligned raw depth, RGB/calibrations and sealed DS18 packets with hashes. '
            'Run checks/guarded engineering slices and freeze in fresh output directories, then orchestrate. '
            'Only after all predictions/access/START/END seals exist run score, report and post_visuals. '
            'No API, training, SAM3 or depth completion. Old seals and interrupted engineering attempts stay readonly. '
            'Three post observations are explicit future evidence within a finite30frame first-publication buffer; '
            'no previously published masks are rewritten.',
        excluded=['private RGB/GT raster','private raw masks/sensor/flow arrays','credentials'],
        new_model_http=0,cost_usd=0))
    result=read(HERE/'RESULTS.json')
    header=('## DS34 event bidirectional fragment restoration completed (2026-10-06)\n\n'
        f'Status: {result["status"]}. Eight exact saved sources/20098frames: Native/original Z4Q/EVENT_RGB/EVENT_RGBD. '
        'Original controls reproduced; original scan_v4 preserved. Event-local joint restoration includes continuing '
        'native and new sources. Full own-state suffix replay precedes first publication with finite30frame lag; '
        'future measurements never enter q histories. All raw masks/residuals scored, no inpainting or RGB texture model. '
        'Depth contribution is EVENT_RGBD minus EVENT_RGB; shared protection and local rollback are separate. '
        'Exposed exploratory references; L3/LW weak. No API/GPU/training/SAM3/completion. '
        'See experiments/ds34_bidirectional_event_restore/FINAL_REVIEW.md and all receipts. '
        'Frozen trial complete; one unstarted next step. Previous handoff bytes preserved below.\n\n').encode()
    changes={}
    for path,data,prefix in [(ROOT/'research/HANDOFF.md',header,True),
        (ROOT/'.gitignore',b'\n# DS34 restricted RGB/depth/flow diagnostics.\n/experiments/ds34_bidirectional_event_restore/private/\n',False)]:
        prior,before=path.read_bytes(),artifact(path)
        path.write_bytes(data+prior if prefix else prior+data)
        assert (path.read_bytes()[len(data):] if prefix else path.read_bytes()[:len(prior)])==prior
        changes[path.relative_to(ROOT).as_posix()]=dict(old=before,new=artifact(path),previous_bytes_preserved=True)
    write_new(HERE/'HANDOFF_UPDATE.json',changes)
    assert set(git('diff','--name-only').decode().splitlines())=={'.gitignore','research/HANDOFF.md'}
    for item in private: assert git('check-ignore',item['path']).decode().strip()
    records=0;partial=[]
    for path in files():
        assert path.suffix.lower() not in {'.png','.jpg','.jpeg','.npy','.npz','.h5','.mp4'}
        assert path.stat().st_size<95*1024*1024,path
        if path.suffix=='.json': numeric(read(path));records+=1
        elif path.name.endswith('.jsonl.gz') or path.suffix=='.jsonl':
            try:
                for value in rows(path): numeric(value);records+=1
            except (EOFError,gzip.BadGzipFile,json.JSONDecodeError):
                assert any(part.startswith('slice_') for part in path.parts),'Only interrupted unscored engineering streams may be incomplete'
                partial.append(artifact(path))
        elif path.suffix=='.partial':
            partial.append(artifact(path))
    write_new(HERE/'PUBLIC_CONTENT_REVIEW.json',dict(status='PASS',numeric_records=records,
        private_outputs=len(private),incomplete_engineering_attempts=partial,
        incomplete_engineering_attempts_never_scored=True,old_seals_readonly=True,new_model_http=0,cost_usd=0))
    write_new(HERE/'PUBLIC_ARTIFACT_MANIFEST.json',dict(
        files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in files()],
        repository_files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix())
            for p in (ROOT/'.gitignore',ROOT/'research/HANDOFF.md')],private_pixels_excluded=True))
    print('Public delivery inventory ready',records,len(private),flush=True)

def verify(mode):
    inventory=read(HERE/'PUBLIC_ARTIFACT_MANIFEST.json');pins=inventory['files']+inventory['repository_files']
    def append(name): pins.append(dict(artifact(HERE/name),relative_path=(HERE/name).relative_to(ROOT).as_posix()))
    append('PUBLIC_ARTIFACT_MANIFEST.json')
    for item in pins: verify_item(item)
    if mode=='index':
        names=git('diff','--cached','--name-only','-z').decode().split('\0')[:-1]
        assert set(names)=={item['relative_path'] for item in pins}
        for item in pins:
            blob=git('show',':'+item['relative_path'])
            assert len(blob)==item['bytes'] and hashlib.sha256(blob).hexdigest()==item['sha256']
        write_new(HERE/'INDEX_REVIEW.json',dict(status='PASS',actual_staged_blobs=len(names),private_pixels_excluded=True))
        print('Staged actual blobs verified',len(names),flush=True);return
    head=git('rev-parse','HEAD').decode().strip()
    remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    assert head==remote
    git('fetch','origin','main')
    assert git('rev-parse','origin/main').decode().strip()==remote
    append('INDEX_REVIEW.json')
    if mode=='final':
        append('REMOTE_VERIFICATION.json')
        assert read(HERE/'REMOTE_VERIFICATION.json')['science_commit'] in git('rev-list',head).decode().splitlines()
    verified={}
    for item in pins:
        verify_item(item);blob=git('show',remote+':'+item['relative_path'])
        assert len(blob)==item['bytes'] and hashlib.sha256(blob).hexdigest()==item['sha256']
        verified[item['relative_path']]=dict(bytes=len(blob),sha256=item['sha256'])
    if mode=='remote':
        write_new(HERE/'REMOTE_VERIFICATION.json',dict(status='ACTUAL_REMOTE_MAIN_AND_ALL_PUBLIC_BLOBS_VERIFIED',
            science_commit=head,remote_main=remote,verified_utc=datetime.now(timezone.utc).isoformat(),files=verified,
            force_push=False,receipt_committed_next=True,new_model_http=0,cost_usd=0))
    print(json.dumps(dict(status='ACTUAL_REMOTE_MAIN_AND_ALL_PUBLIC_BLOBS_VERIFIED',main=remote,files=len(verified))),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare': prepare()
    else: verify(sys.argv[1])
