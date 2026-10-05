"""Publish only numeric artifacts, then verify actual remote ref and every blob."""
from common import *
from datetime import datetime,timezone
import subprocess
OMIT={'PUBLIC_ARTIFACT_MANIFEST.json','INDEX_REVIEW.json','REMOTE_VERIFICATION.json'}
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def files():return sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in OMIT and not {'private','__pycache__'}&set(p.relative_to(HERE).parts))
def check(v):
    if isinstance(v,dict):
        assert not {'rle','polygons','segmentation','depth_pixels','pixel_values','api_key','provider_file_id','counts_rle'}&v.keys()
        for x in v.values():check(x)
    elif isinstance(v,list):
        for x in v:check(x)
def finalize():
    assert git('rev-parse','HEAD').decode().strip()==BASE
    assert not git('diff','--name-only').decode().strip()
    import score
    score.verify_all()
    assert read(HERE/'MECHANISM_ANALYSIS.json')['status']=='PASS_FULL_SEAL_BINDING_PUBLICATION_AND_CAUSAL_READ_AUDIT'
    assert read(HERE/'REPORT_VALIDATION.json')['status']=='PASS_REPORT_NUMBERS_SEALS_AND_EXECUTION_RECORDS'
    assert read(HERE/'VISUAL_ACCEPTANCE.json')['status']=='PASS_ACTUAL_VISUAL_INSPECTION'
    for path,h in read(HERE/'RUNTIME_FREEZE.json')['code'].items():assert sha(path)==h,path
    for p in read(HERE/'PRIVATE_VISUALS.json')['figures']:verify_item(p)
    private=[artifact(p) for p in (HERE/'private').rglob('*') if p.is_file()]
    write_new(HERE/'RESTRICTED_ARTIFACTS.json',dict(private_outputs=private,
        exact_saved_inputs={n:read(RUN/n/'public/FREEZE.json')['source_chain'] for n in SEGMENTS},
        runtime=artifact(HERE/'RUNTIME_FREEZE.json'),python=sys.executable,python_version=sys.version,deps=str(DEPS),base_commit=BASE,
        reproduction='Use a separate checkout at BASE, copy this experiment code/config/PLAN from the delivery, retain exactly inventoried DS14 saved sources and raw depth. '
            'Use recorded local Python/deps; do not copy old predictions or seals. Run checks and guarded prefixes, freeze once, orchestrate eight segments/three own branches, '
            'then score only after all prediction/access seals. Review, render actual publications, report and deliver fresh outputs. '
            'Source observer uses current/past raw only, every original mask remains unchanged; no model or service needed. '
            'Postseal q+2 illustrations are never runtime inputs. Current old DS28/DS1/etc paths are readonly dependencies, not new results.',
        private_RGB_GT_raster_credentials_not_published=True,new_model_http=0,cost_usd=0))
    header=(f"## DS30 original Z4Q depth increment completed (2026-10-05)\n\n"
        f"Status: {read(HERE/'RESULTS.json')['status']}. Eight same-source segments/20098frames, three own-state branches, no API/GPU/training/SAM3/completion/fees. "
        "See experiments/ds30_original_z4q_depth_increment/FINAL_REVIEW.md and full metrics. Original Z4Q authoritative, read-only event observer; exact pre anchors; measured supports/common null. "
        "Complete negative/positive sourcewise results retained; original own-branch state retained on null, DEFER or failed stage; shared source points remeasured. "
        "Old source/seals unchanged; all private figures inventoried. One next-step plan unstarted. Old handoff bytes preserved below.\n\n").encode()
    changes={}
    for path,data,prefix in [(ROOT/'research/HANDOFF.md',header,True),(ROOT/'.gitignore',b'\n# DS30 raw-depth/mask diagnostic pixels remain private.\n/experiments/ds30_original_z4q_depth_increment/private/\n',False)]:
        prior=path.read_bytes();pin=artifact(path);path.write_bytes(data+prior if prefix else prior+data)
        assert (path.read_bytes()[len(data):] if prefix else path.read_bytes()[:len(prior)])==prior
        changes[path.relative_to(ROOT).as_posix()]=dict(old=pin,new=artifact(path),old_bytes_preserved=True)
    write_new(HERE/'HANDOFF_UPDATE.json',changes)
    assert set(git('diff','--name-only').decode().splitlines())=={'.gitignore','research/HANDOFF.md'}
    for p in private:assert git('check-ignore',p['path']).decode().strip()
    count=0
    for p in files():
        assert p.suffix.lower() not in {'.png','.jpg','.npy','.npz','.h5','.mp4'}
        assert p.stat().st_size<95*1024*1024,'Publishability size limit'
        if p.suffix=='.json':check(read(p));count+=1
        elif p.name.endswith('.jsonl.gz') or p.suffix=='.jsonl':
            for value in rows(p):check(value);count+=1
    write_new(HERE/'PUBLIC_CONTENT_REVIEW.json',dict(status='PASS',numeric_records=count,private_outputs=len(private),
        old_science_and_seals_unchanged=True,new_model_http=0,cost_usd=0))
    write_new(HERE/'PUBLIC_ARTIFACT_MANIFEST.json',dict(files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in files()],
        repository_files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in (ROOT/'.gitignore',ROOT/'research/HANDOFF.md')],private_pixels_excluded=True))
    print('Numeric delivery validated',count,'records',len(private),'private figures',flush=True)

def verify(mode):
    m=read(HERE/'PUBLIC_ARTIFACT_MANIFEST.json');pins=m['files']+m['repository_files']
    def add(name):pins.append(dict(artifact(HERE/name),relative_path=(HERE/name).relative_to(ROOT).as_posix()))
    add('PUBLIC_ARTIFACT_MANIFEST.json')
    if mode=='index':
        names=git('diff','--cached','--name-only','-z').decode().split('\0')[:-1]
        assert set(names)=={p['relative_path'] for p in pins}
        for p in pins:
            b=git('show',':'+p['relative_path']);assert len(b)==p['bytes'] and hashlib.sha256(b).hexdigest()==p['sha256']
        write_new(HERE/'INDEX_REVIEW.json',dict(status='PASS',actual_staged_blobs=len(names),private_pixels_excluded=True));print('Index PASS',len(names));return
    head=git('rev-parse','HEAD').decode().strip();remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    assert head==remote;git('fetch','origin','main');assert git('rev-parse','origin/main').decode().strip()==remote
    add('INDEX_REVIEW.json')
    if mode=='final':add('REMOTE_VERIFICATION.json')
    verified={}
    for p in pins:
        b=git('show',remote+':'+p['relative_path']);assert len(b)==p['bytes'] and hashlib.sha256(b).hexdigest()==p['sha256']
        verified[p['relative_path']]=dict(bytes=len(b),sha256=p['sha256'])
    if mode=='remote':write_new(HERE/'REMOTE_VERIFICATION.json',dict(status='ACTUAL_REMOTE_MAIN_AND_ALL_PUBLIC_BLOBS_VERIFIED',
        science_commit=head,remote_main=remote,files=verified,verified_utc=datetime.now(timezone.utc).isoformat(),force_push=False,
        receipt_committed_next=True,new_model_http=0,cost_usd=0))
    print(json.dumps(dict(status='ACTUAL_REMOTE_MAIN_AND_ALL_PUBLIC_BLOBS_VERIFIED',main=remote,files=len(verified))),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='finalize':finalize()
    else:verify(sys.argv[1])
