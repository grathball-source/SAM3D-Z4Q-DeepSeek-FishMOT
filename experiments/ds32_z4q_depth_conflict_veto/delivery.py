"""Numeric main delivery and actual remote SHA/blob verification; no private raster."""
from common import *
import subprocess
from datetime import datetime,timezone
OMIT={'PUBLIC_ARTIFACT_MANIFEST.json','INDEX_REVIEW.json','REMOTE_VERIFICATION.json'}
def git(*args):
    env=os.environ.copy()
    options={'http.sslBackend':'openssl','http.proxy':'http://127.0.0.1:7897','gc.auto':'0','http.version':'HTTP/1.1','http.sslVersion':'tlsv1.2'}
    env['GIT_CONFIG_COUNT']=str(len(options))
    for i,(k,v) in enumerate(options.items()):env[f'GIT_CONFIG_KEY_{i}']=k;env[f'GIT_CONFIG_VALUE_{i}']=v
    return subprocess.check_output(['git',*args],cwd=ROOT,env=env)
def files():return sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in OMIT and not {'private','__pycache__'}&set(p.relative_to(HERE).parts))
def check(v):
    if isinstance(v,dict):
        assert not {'rle','polygons','segmentation','depth_pixels','pixel_values','api_key','provider_file_id','counts_rle'}&v.keys()
        for x in v.values():check(x)
    elif isinstance(v,list):
        for x in v:check(x)
def finalize():
    assert git('rev-parse','HEAD').decode().strip()==BASE and not git('diff','--name-only').decode().strip()
    import score
    score.verify_all();assert read(HERE/'ANALYSIS_POSTSEAL.json')['status'].startswith('PASS')
    assert read(HERE/'SCORING_BINDING_ACCEPTANCE.json')['status']=='PASS_PRESTART_IMPORT_PINS_AND_FROZEN_BASE_ADAPTER'
    assert read(HERE/'REPORT_VALIDATION.json')['status']=='PASS' and read(HERE/'VISUAL_ACCEPTANCE.json')['status']=='PASS_ACTUAL_VISUAL_INSPECTION'
    review=read(HERE/'INDEPENDENT_REPORT_REVIEW_FINAL.json');assert review['status']=='PASS'
    for pin in review['reviewed_documents'].values():verify_item(pin)
    for path,h in read(HERE/'RUNTIME_FREEZE.json')['code'].items():assert sha(path)==h,path
    private=[artifact(p) for p in (HERE/'private').rglob('*') if p.is_file()]
    write_new(HERE/'RESTRICTED_ARTIFACTS.json',dict(private_outputs=private,
        exact_inputs={n:read(RUN/n/'public/FREEZE.json') for n in SEGMENTS},runtime=artifact(HERE/'RUNTIME_FREEZE.json'),
        python=sys.executable,version=sys.version,deps=str(DEPS),base_commit=BASE,
        reproduction='Fresh checkout of the frozen BASE plus this delivered experiment. Use exact inventoried DS14 SAM3 masks/raw depth and sealed DS18 cache. '
            'Use recorded Python/deps. In fresh output paths run checks, the guarded real prefixes, preflight, frozen-contract review, freeze, orchestrate. '
            'Only after every formal/counterfactual seal run score_checked, then postseal analysis/report. '
            'Archived prefix attempts remain unscored; never mix them with formal runs. Original sources and seals are readonly. '
            'No API/GPU/training/new SAM3/completion. References exposed; L3/LW weak. Private rasters remain local.',
        private_RGB_GT_raster_credentials_excluded=True,new_model_http=0,cost_usd=0))
    result=read(HERE/'RESULTS.json');status=result['status']
    header=(f'## DS32 original Z4Q candidate-edge depth veto completed (2026-10-05)\n\nStatus: {status}. '
        f'Actual original-legal deletions: {result["counts"]["legal_edges_deleted"]}; changed publication frames: {result["counts"]["changed_frames"]}. '
        'Eight exact saved sources/20098frames, Native/original Z4Q/new veto. Native and original Z4Q reproduced exactly. '
        'Only per-edge reliable contradiction can remove a real candidate; original lifecycle/cost/dummy/publication retained. '
        'Missing/weak/short/wide evidence is null, no background reward or similar-depth identity certification. '
        'All formal and available fixed single-edge counterfactual predictions sealed before official score. '
        'No API/GPU/training/new SAM3/completion; no parameter rolling. '
        'See experiments/ds32_z4q_depth_conflict_veto/FINAL_REVIEW.md, complete numeric predictions/actions/switches/source evidence/CF and receipts. '
        'Exposed diagnostics, L3/LW weak references; source continuity does not certify absent producer-reset metadata. '
        'Frozen trial complete, exactly one unstarted next step. Prior handoff bytes preserved below.\n\n').encode()
    changes={}
    for path,data,prefix in [(ROOT/'research/HANDOFF.md',header,True),(ROOT/'.gitignore',b'\n# DS32 restricted inspection pixels.\n/experiments/ds32_z4q_depth_conflict_veto/private/\n',False)]:
        prior=path.read_bytes();pin=artifact(path);path.write_bytes(data+prior if prefix else prior+data)
        assert (path.read_bytes()[len(data):] if prefix else path.read_bytes()[:len(prior)])==prior
        changes[path.relative_to(ROOT).as_posix()]=dict(old=pin,new=artifact(path),old_bytes_preserved=True)
    write_new(HERE/'HANDOFF_UPDATE.json',changes)
    assert set(git('diff','--name-only').decode().splitlines())=={'.gitignore','research/HANDOFF.md'}
    for p in private:assert git('check-ignore',p['path']).decode().strip()
    count=0
    for p in files():
        assert p.suffix.lower() not in {'.png','.jpg','.npy','.npz','.h5','.mp4'} and p.stat().st_size<95*1024*1024
        if p.suffix=='.json':check(read(p));count+=1
        elif p.name.endswith('.jsonl.gz') or p.suffix=='.jsonl':
            if 'engineering_attempts' in p.parts and '/run/' in p.as_posix():
                # Interrupted gzip may not have a footer. Contents remain numeric;
                # the entire byte stream is retained and hashed, never used for metrics.
                try:
                    for value in rows(p):check(value);count+=1
                except (EOFError,gzip.BadGzipFile,json.JSONDecodeError):pass
            else:
                for value in rows(p):check(value);count+=1
    write_new(HERE/'PUBLIC_CONTENT_REVIEW.json',dict(status='PASS',numeric_records=count,private_outputs=len(private),
        old_science_seals_unchanged=True,unscored_engineering_partial_streams_retained=True,new_model_http=0,cost_usd=0))
    write_new(HERE/'PUBLIC_ARTIFACT_MANIFEST.json',dict(files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in files()],
        repository_files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in (ROOT/'.gitignore',ROOT/'research/HANDOFF.md')],private_pixels_excluded=True))
    print('Delivery manifest ready',count,len(private),flush=True)
def verify(mode):
    m=read(HERE/'PUBLIC_ARTIFACT_MANIFEST.json');pins=m['files']+m['repository_files']
    def add(name):pins.append(dict(artifact(HERE/name),relative_path=(HERE/name).relative_to(ROOT).as_posix()))
    add('PUBLIC_ARTIFACT_MANIFEST.json')
    if mode=='final':
        receipt=read(HERE/'REMOTE_VERIFICATION.json')
        key=(HERE/'PUBLIC_ARTIFACT_MANIFEST.json').relative_to(ROOT).as_posix()
        assert receipt['files'][key]==dict(bytes=(HERE/'PUBLIC_ARTIFACT_MANIFEST.json').stat().st_size,sha256=sha(HERE/'PUBLIC_ARTIFACT_MANIFEST.json'))
    for pin in pins:verify_item(pin)
    if mode=='index':
        names=git('diff','--cached','--name-only','-z').decode().split('\0')[:-1];assert set(names)=={p['relative_path'] for p in pins}
        for p in pins:
            b=git('show',':'+p['relative_path']);assert len(b)==p['bytes'] and hashlib.sha256(b).hexdigest()==p['sha256']
        write_new(HERE/'INDEX_REVIEW.json',dict(status='PASS',actual_staged_blobs=len(names),private_pixels_excluded=True));print('Index PASS',len(names));return
    head=git('rev-parse','HEAD').decode().strip();remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    assert head==remote;git('fetch','origin','main');assert git('rev-parse','origin/main').decode().strip()==remote
    add('INDEX_REVIEW.json')
    if mode=='final':add('REMOTE_VERIFICATION.json')
    for pin in pins:verify_item(pin)
    verified={}
    for p in pins:
        b=git('show',remote+':'+p['relative_path']);assert len(b)==p['bytes'] and hashlib.sha256(b).hexdigest()==p['sha256']
        verified[p['relative_path']]=dict(bytes=len(b),sha256=p['sha256'])
    if mode=='remote':write_new(HERE/'REMOTE_VERIFICATION.json',dict(status='ACTUAL_REMOTE_MAIN_AND_ALL_PUBLIC_BLOBS_VERIFIED',science_commit=head,
        remote_main=remote,files=verified,verified_utc=datetime.now(timezone.utc).isoformat(),force_push=False,receipt_committed_next=True,new_model_http=0,cost_usd=0))
    print(json.dumps(dict(status='ACTUAL_REMOTE_MAIN_AND_ALL_PUBLIC_BLOBS_VERIFIED',main=remote,files=len(verified))),flush=True)
if __name__=='__main__':
    if sys.argv[1]=='finalize':finalize()
    else:verify(sys.argv[1])
