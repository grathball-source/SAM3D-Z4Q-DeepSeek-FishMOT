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
    assert read(HERE/'REPORT_VALIDATION.json')['status']=='PASS_REPORT_NUMBERS_SEALS_AND_EXECUTION_RECORDS'
    assert read(HERE/'VISUAL_ACCEPTANCE.json')['status']=='PASS_ACTUAL_OVERVIEW_AND_DETAIL_VISUAL_INSPECTION'
    for name in ('PRIVATE_VISUALS.json','FAILURE_VISUALS.json','REPORT_PROVENANCE.json','REPORT_VALIDATION.json','VISUAL_ACCEPTANCE.json'):verify_pins(read(HERE/name))
    result=read(HERE/'RESULTS.json')
    private=[artifact(p) for p in HERE.rglob('*') if p.is_file() and 'private' in p.relative_to(HERE).parts]
    write_new(HERE/'RESTRICTED_ARTIFACTS.json',dict(private_outputs=private,
        same_source_saved_inputs={n:read(RUN/n/'public/FREEZE.json')['source_chain'] for n in SEGMENTS},
        runtime=artifact(HERE/'RUNTIME_FREEZE.json'),python=sys.executable,python_version=sys.version,deps=str(DEPS),base_commit=BASE,
        reproduction='Use a separate checkout at the recorded BASE with the DS28 public source/config/PLAN files copied from this delivery. '
            'Keep old experiments and all restricted input inventories read-only; ensure the exact raw source bytes and recorded local Python/deps exist. '
            'Generate fresh check/prefix/freeze outputs; never copy this run directory, predictions, seals or scores into new results. '
            'Replay all8segments/fourarms with the frozen guard/runner; execute_unique.py can schedule sequential segment jobs to avoid clock log collisions. '
            'Build the fresh all8prediction/access manifest exactly as orchestrate.py does only after each final seal; then score/review/analyze and render fresh diagnostics. '
            'The original TECHNICAL_RECOVERY describes this run only, not scientific input or an old response to reuse. '
            'Change scheduling only if needed and pin it in the fresh freeze; do not change science parameters or reuse observed verdicts for selection.',
        private_pixels_GT_credentials_not_published=True,RGB_input=False,new_model_http=0,cost_usd=0))
    handoff=(f"## DS28 risk-driven depth entry completed (2026-10-05)\n\n"
        f"Eight same-source segments/20098frames, four ownstate branches; status {result['status']}. "
        "See experiments/ds28_risk_driven_depth_entry/FINAL_REVIEW.md. Near exactly reproducesDS27 C1/S5. "
        "Original predicted interaction/missing legal edge coverage495->1552,17wrongactions now checked but0fullpre/q comparisons. "
        "Five actual cost changes occur on one alreadycorrect restoration,0newidentitycommits/publication/metric gain. "
        "Native/originalZ4Q/full weak-reference boundaries and inheritedIDSW retained. All32depth/maskfigures private; noRGB/GT raster published. "
        "A prestart log-name collision prevented L3 launch; UUID logger completed its first run,7seals and all frozen code unchanged. "
        "No API/GPU/server/training/SAM3/completion/fees. One anonymous-current-pair joint interpretation plan is unstarted. Old handoff bytes preserved below.\n\n").encode()
    additive={}
    for path,data,before in [(ROOT/'research/HANDOFF.md',handoff,True),(ROOT/'.gitignore',b'\n# DS28 diagnostic raw-depth/mask pixels remain private.\n/experiments/ds28_risk_driven_depth_entry/private/\n',False)]:
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
