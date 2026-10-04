"""Public numeric delivery and actual remote blob verification; no experiment mutations."""
from common import *
from datetime import datetime,timezone
import subprocess

OMIT={'PUBLIC_ARTIFACT_MANIFEST.json','INDEX_REVIEW.json','REMOTE_VERIFICATION.json'}
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def public_files():return sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in OMIT and not {'private','__pycache__'}&set(p.relative_to(HERE).parts))
def verify_pins(v):
    if isinstance(v,dict):
        if {'path','bytes','sha256'}<=v.keys():verify_item(v)
        else:
            for x in v.values():verify_pins(x)
    elif isinstance(v,list):
        for x in v:verify_pins(x)
def public_check(v,key=''):
    if isinstance(v,dict):
        assert not {'rle','polygons','segmentation','depth_pixels','pixel_values','api_key','provider_file_id'}&v.keys()
        for k,x in v.items():public_check(x,k)
    elif isinstance(v,list):
        assert len(v)<=32 or not all(isinstance(x,(int,float)) for x in v) or key in {'pre_frames','causal_query_limits','standardized_differences'},key
        for x in v:public_check(x,key)

def finalize():
    assert git('rev-parse','HEAD').decode().strip()==BASE
    assert not git('diff','--name-only').decode().strip()
    freeze=check_freeze();seal=read(RUN/'MEASUREMENTS_SEALED.json');verify_pins(seal)
    for p in freeze['inputs']:verify_item(p)
    for name in ('POSTSEAL_REVIEW.json','INDEPENDENT_REVIEW.json'):
        assert read(HERE/name)['status'].startswith('PASS')
    for name in ('PRIVATE_VISUALS.json','REPORT_PROVENANCE.json','REPORT_PROVENANCE_V2.json'):verify_pins(read(HERE/name))
    r=read(HERE/'RESULTS.json');assert len(r['contexts'])==15 and r['complete_contact_chains']==0
    summary=read(RUN/'SUMMARY.json');assert summary['logical_pairs']==532 and summary['paired_endpoints']==651
    private=[artifact(p) for p in HERE.rglob('*') if p.is_file() and 'private' in p.relative_to(HERE).parts]
    write_new(HERE/'RESTRICTED_ARTIFACTS.json',dict(private_outputs=private,
        source_manifests=freeze['source_manifests'],runtime=artifact(HERE/'FREEZE.json'),python=sys.executable,
        deps=str(DEPS),base_commit=BASE,
        reproduction='Use the pinned source paths and prior DS25 seals. In a fresh separate experiment directory copy only this code/config/plan; '
            'build_cohort.py --output-dir <fresh> --created-utc 2026-10-04T11:07:27.290910+00:00 reconstructs the original cohort. '
            'Run test_measurement, make TEST_RESULTS from its actual stdout, measure slice, freeze, measure all, review, '
            'postseal diagnose/independent_review/visualize/report. freeze.py expects BASE and an absent run. Never overwrite old outputs. '
            'All public/source absolute paths reflect this actual local run; pixel outputs remain private.',
        private_pixel_GT_credentials_not_published=True,GT_RGB_reads=0,new_model_http=0,cost_usd=0))
    prefix=("## DS26 phase measurement audit completed (2026-10-04)\n\n"
        "Same fixed DS25 cohort: 15 anchor/partner/seed contexts, 532 logical candidate pairs / 540 original references, "
        "119 pre and 532 post paired endpoints. Actual-mask ROI eliminates 346 empty post contact-window references, "
        "but only 9/119 pre and 2/532 post pairs have two disjoint sole anonymous proxy supports; all15 seeds lack two layers. "
        "Complete contact chains0; no identity state writes/new predictions, so no new IDF1/HOTA or claimed gain. "
        "1116 actual mask facts / 468 raw frames; all2343 old ROI facts and prior seals remain unchanged. "
        "Post actual-source masks are not certified old-target identities. All supports, background/missing/weak and UNKNOWN retained. "
        "See experiments/ds26_phase_roi_observability/FINAL_REVIEW_V2.md and NEXT_STEP_PLAN_V2.md (planned, not executed; user permits justified threshold changes). "
        "No model HTTP, RGB/GT reads, server/GPU, training, SAM3 or completion/cost. Old handoff bytes preserved below.\n\n").encode()
    additive={}
    for path,data,before in [(ROOT/'research/HANDOFF.md',prefix,True),(ROOT/'.gitignore',b'\n# DS26 actual raw-depth/mask evidence is private.\n/experiments/ds26_phase_roi_observability/private/\n',False)]:
        pin=artifact(path);old=path.read_bytes();path.write_bytes(data+old if before else old+data)
        assert (path.read_bytes()[len(data):] if before else path.read_bytes()[:len(old)])==old
        additive[path.relative_to(ROOT).as_posix()]=dict(old=pin,new=artifact(path),old_bytes_preserved=True)
    write_new(HERE/'HANDOFF_UPDATE.json',additive)
    assert set(git('diff','--name-only').decode().splitlines())=={'.gitignore','research/HANDOFF.md'}
    for p in private:assert git('check-ignore',p['path']).decode().strip()
    numeric=0
    for p in public_files():
        assert p.suffix.lower() not in {'.png','.jpg','.npy','.npz','.h5','.mp4'}
        if p.suffix=='.json':public_check(read(p));numeric+=1
        elif p.name.endswith('.jsonl.gz') or p.suffix=='.jsonl':
            for v in rows(p):public_check(v);numeric+=1
    write_new(HERE/'PUBLIC_CONTENT_REVIEW.json',dict(status='PASS',public_numeric_records=numeric,
        private_outputs=len(private),only_old_metadata_additively_changed=True,old_science_seals_unchanged=True,
        no_private_pixels_GT_credentials_provider_ids=True,new_model_http=0,cost_usd=0))
    pins=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in public_files()]
    write_new(HERE/'PUBLIC_ARTIFACT_MANIFEST.json',dict(files=pins,
        repository_files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in (ROOT/'.gitignore',ROOT/'research/HANDOFF.md')],private_pixels_excluded=True))
    print('Public delivery PASS',len(pins),'files;',len(private),'private outputs inventoried')

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
    checked={}
    for p in pins:
        b=git('show',remote+':'+p['relative_path']);assert len(b)==p['bytes'] and hashlib.sha256(b).hexdigest()==p['sha256']
        checked[p['relative_path']]=dict(bytes=len(b),sha256=p['sha256'])
    if mode=='remote':write_new(HERE/'REMOTE_VERIFICATION.json',dict(status='ACTUAL_REMOTE_MAIN_AND_ALL_PUBLIC_BLOBS_VERIFIED',
        science_commit=head,remote_main=remote,files=checked,verified_utc=datetime.now(timezone.utc).isoformat(),force_push=False,
        receipt_committed_next=True,new_model_http=0,cost_usd=0))
    print(json.dumps(dict(status='ACTUAL_REMOTE_MAIN_AND_ALL_PUBLIC_BLOBS_VERIFIED',main=remote,files=len(checked))))

if __name__=='__main__':
    if sys.argv[1]=='finalize':finalize()
    else:verify(sys.argv[1])
