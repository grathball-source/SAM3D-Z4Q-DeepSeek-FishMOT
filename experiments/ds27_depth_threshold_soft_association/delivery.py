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
        assert len(v)<=32 or not all(isinstance(x,(int,float)) for x in v) or key in {'pre_frames','causal_query_limits','standardized_differences','changed_frames',*ARMS},key
        for x in v:public_check(x,key)

def finalize():
    assert git('rev-parse','HEAD').decode().strip()==BASE
    assert not git('diff','--name-only').decode().strip()
    import score
    score.verify_all()
    freeze=read(HERE/'RUNTIME_FREEZE.json')
    for path,expected in freeze['code'].items():assert sha(path)==expected,path
    assert read(HERE/'POSTSEAL_QA.json')['status'].startswith('PASS')
    assert read(HERE/'INDEPENDENT_FINAL_RECEIPT.json')['status']=='PASS_NUMERIC_AND_FINAL_V2_REPORT_REVIEW_COMPLETE'
    verify_pins(read(HERE/'INDEPENDENT_FINAL_RECEIPT.json'))
    for name in ('PRIVATE_VISUALS.json','PRIVATE_VISUALS_V2.json','REPORT_PROVENANCE.json','REPORT_PROVENANCE_V2.json'):verify_pins(read(HERE/name))
    result=read(HERE/'RESULTS.json')
    private=[artifact(p) for p in HERE.rglob('*') if p.is_file() and 'private' in p.relative_to(HERE).parts]
    write_new(HERE/'RESTRICTED_ARTIFACTS.json',dict(private_outputs=private,
        same_source_saved_inputs={n:read(RUN/n/'public/FREEZE.json')['source_chain'] for n in SEGMENTS},
        runtime=artifact(HERE/'RUNTIME_FREEZE.json'),python=sys.executable,python_version=sys.version,deps=str(DEPS),base_commit=BASE,
        reproduction='Use the recorded same-source inventories and local dependency paths in a separate checkout. Copy only frozen DS27 code/config/plan into a fresh empty experiment directory, '
            'run checks and the two guarded disabled200/real205 prefixes, freeze with recordedBASE and an absentrun, then orchestrate all8sixarms, postseal score/review/visualize/report. '
            'Recreate CALIBRATION in a fresh output from immutable DS26 PRE facts; do not overwrite this or any old output/seal. '
            'The optional postseal diagnostic pixel figures are separate from formal association inputs.',
        private_pixels_GT_credentials_not_published=True,RGB_input=False,new_model_http=0,cost_usd=0))
    handoff=(f"## DS27 depth threshold soft-association completed (2026-10-04)\n\n"
        f"Eight same-source segments/20098frames; Native, originalZ4Q and four frozen contrast/floor combinations with genuine ownstate replay. "
        f"Status {result['status']}. See experiments/ds27_depth_threshold_soft_association/FINAL_REVIEW_V2.md for all metrics, cost/publication coverage, UNKNOWN and actual actions. "
        "Depth thresholds were changed with PRE-only numerical rationale, not GT tuning. All original masks/IDs remain evaluated. "
        "No model HTTP/smoke, GPU/server, completion, training or newSAM3/cost. Old science/seals unchanged. One next plan is recorded but not started. Old handoff bytes preserved below.\n\n").encode()
    additive={}
    for path,data,before in [(ROOT/'research/HANDOFF.md',handoff,True),(ROOT/'.gitignore',b'\n# DS27 diagnostic raw-depth/mask pixels remain private.\n/experiments/ds27_depth_threshold_soft_association/private/\n',False)]:
        old=path.read_bytes();pin=artifact(path);path.write_bytes(data+old if before else old+data)
        assert (path.read_bytes()[len(data):] if before else path.read_bytes()[:len(old)])==old
        additive[path.relative_to(ROOT).as_posix()]=dict(old=pin,new=artifact(path),old_bytes_preserved=True)
    write_new(HERE/'HANDOFF_UPDATE.json',additive)
    assert set(git('diff','--name-only').decode().splitlines())=={'.gitignore','research/HANDOFF.md'}
    for p in private:assert git('check-ignore',p['path']).decode().strip()
    records=0
    for p in public_files():
        assert p.suffix.lower() not in {'.png','.jpg','.npy','.npz','.h5','.mp4'}
        if p.suffix=='.json':public_check(read(p));records+=1
        elif p.name.endswith('.jsonl.gz') or p.suffix=='.jsonl':
            for value in rows(p):public_check(value);records+=1
    write_new(HERE/'PUBLIC_CONTENT_REVIEW.json',dict(status='PASS',public_numeric_records=records,private_outputs=len(private),
        old_science_seals_unchanged=True,no_private_pixels_GT_credentials_provider_ids=True,new_model_http=0,cost_usd=0))
    pins=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in public_files()]
    write_new(HERE/'PUBLIC_ARTIFACT_MANIFEST.json',dict(files=pins,
        repository_files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in (ROOT/'.gitignore',ROOT/'research/HANDOFF.md')],private_pixels_excluded=True))
    print('Public numeric delivery PASS',len(pins),'files;',len(private),'private outputs inventoried')

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
