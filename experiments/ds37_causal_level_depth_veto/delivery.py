"""Scoped non-force main delivery; verify actual refs and every public byte."""
from common import *
from datetime import datetime,timezone
import subprocess

OMIT={'PUBLIC_ARTIFACT_MANIFEST.json','INDEX_REVIEW.json','REMOTE_VERIFICATION.json'}

def git(*args):
    env=dict(os.environ);options={'http.sslBackend':'schannel','http.sslVerify':'true','http.proxy':'',
        'http.version':'HTTP/1.1','gc.auto':'0','pack.threads':'2'}
    env['GIT_CONFIG_COUNT']=str(len(options))
    for i,(k,v) in enumerate(options.items()):env[f'GIT_CONFIG_KEY_{i}']=k;env[f'GIT_CONFIG_VALUE_{i}']=v
    return subprocess.check_output(['git',*args],cwd=ROOT,env=env)

def files():
    return sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in OMIT and
        not {'private','__pycache__'}&set(p.relative_to(HERE).parts))

def numeric(v):
    if isinstance(v,dict):
        assert not {'rle','polygons','segmentation','depth_pixels','pixel_values','api_key','provider_file_id','counts_rle'}&v.keys()
        for child in v.values():numeric(child)
    elif isinstance(v,list):
        for child in v:numeric(child)

def prepare():
    from score import verify_all
    verify_all();assert git('rev-parse','HEAD').decode().strip()==BASE
    assert set(git('diff','--name-only').decode().splitlines())=={'.gitignore'}
    assert read(HERE/'REPORT_VALIDATION.json')['status'].startswith('PASS')
    assert read(HERE/'VISUAL_ACCEPTANCE.json')['status']=='PASS_ACTUAL_LOCAL_VISUAL_INSPECTION'
    assert (HERE/'DEEP_REVIEW.md').is_file()
    private=[artifact(p) for p in (HERE/'private').rglob('*') if p.is_file()]
    sources={n:read(RUN/n/'public/FREEZE.json')['source_chain'] for n in SEGMENTS}
    write_new(HERE/'PRIVATE_INVENTORY.json',dict(private_outputs=private,private_input_pins=sources,
        saved_depth_certificates={n:read(RUN/n/'public/FREEZE.json')['depth_cache'] for n in SEGMENTS},
        python=sys.executable,deps=str(DEPS),source_policy=artifact(HERE/'RUNTIME_FREEZE.json'),
        reproduce='Provide exact pinned DS14 saved masks/observations/raw-depth and DS18 numeric certificates, readonly DS31/DS32 controls. '
            'Use a new empty DS37 output directory at fixed BASE plus delivered source; checks, true F159 prefix/disabled prefix, '
            'accept, freeze, guard probe, orchestrate, report, actual local figure inspection and delivery. '
            'Restricted raw-depth/mask figures reproduced by visuals.py after all seals and score. '
            'No RGB, GT raster, model HTTP, new SAM3, training, restoration or hidden test reads.',
        private_pixels_excluded=True,model_http=0,cost_usd=0))
    handoff=ROOT/'research/HANDOFF.md';before=artifact(handoff);data=handoff.read_bytes()
    result=read(HERE/'RESULTS.json')
    header=(f'## DS37 stable-level causal depth veto completed (2026-10-07)\n\n'
        f'Full eight same-source segments / 20098frames / Native, original Z4Q, exact DS32 WLS veto, new LEVEL veto. '
        f'Own-state real candidate-matrix decisions; all masks and public IDs included; all prediction/access seals before official scoring. '
        f'Actual legal LEVEL deletions {result["actual_legal_depth_deletions"]}; changed frames versus original Z4Q {result["changed_frames_against_Z4Q"]}. '
        f'Status {result["status"]}. See experiments/ds37_causal_level_depth_veto/FINAL_REVIEW.md, DEEP_REVIEW.md, RESULTS.json '
        f'and run/EDGE_AUDIT.jsonl.gz for all real metrics, source/UNKNOWN, actions and switch changes. '
        f'Stop this frozen version; one unstarted next step in the report. No model HTTP/smoke/fees/GPU/server/SAM3/training/completion. '
        f'L3/LW weak references and physical depth uncertainty remain uncalibrated; no independent blind validation claim. '
        f'Initial zero-frame hash guard failure and unscored partial old-WLS validity coupling failure retained; '
        f'final v3 independently validates history and restarts every source from frame1, with unchanged numeric parameters. '
        f'Private actual depth/mask pictures stay off Git with real path/bytes/SHA reproduction inventory. Previous handoff bytes preserved below.\n\n').encode()
    handoff.write_bytes(header+data);assert handoff.read_bytes()[len(header):]==data
    write_new(HERE/'HANDOFF_UPDATE.json',dict(path=str(handoff),old=before,new=artifact(handoff),previous_bytes_preserved=True))
    records=0
    for p in files():
        assert p.suffix.lower() not in {'.png','.jpg','.jpeg','.npy','.npz','.h5','.mp4','.stats'}
        assert p.stat().st_size<95*1024**2,p
        if p.suffix=='.json':numeric(read(p));records+=1
        elif p.name.endswith('.jsonl.gz') or p.suffix=='.jsonl':
            try:
                for v in rows(p):numeric(v);records+=1
            except EOFError:
                assert 'partial_invalid_source_validation_v2' in p.parts
        elif p.suffix=='.svg':assert '<image' not in p.read_text(encoding='utf-8')
    for pin in private:assert git('check-ignore',pin['path']).decode().strip()
    write_new(HERE/'PUBLIC_CONTENT_REVIEW.json',dict(status='PASS_NUMERIC_RECORDS_NO_PRIVATE_RASTER_OR_CREDENTIAL_FIELDS',
        numeric_records=records,private_outputs=len(private),old_frozen_code_and_inputs_reverified=True,model_http=0,cost_usd=0))
    write_new(HERE/'PUBLIC_ARTIFACT_MANIFEST.json',dict(files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in files()],
        repository_files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in (ROOT/'.gitignore',handoff)],
        private_pixels_excluded=True))
    print('PUBLIC_DELIVERY_READY',records,len(private),flush=True)

def verify(mode):
    inventory=read(HERE/'PUBLIC_ARTIFACT_MANIFEST.json');pins=inventory['files']+inventory['repository_files']
    def append(name):pins.append(dict(artifact(HERE/name),relative_path=(HERE/name).relative_to(ROOT).as_posix()))
    append('PUBLIC_ARTIFACT_MANIFEST.json')
    for pin in pins:verify_item(pin)
    if mode=='index':
        names=git('diff','--cached','--name-only','-z').decode().split('\0')[:-1]
        assert set(names)=={p['relative_path'] for p in pins}
        for pin in pins:
            value=git('show',':'+pin['relative_path'])
            assert len(value)==pin['bytes'] and hashlib.sha256(value).hexdigest()==pin['sha256']
        write_new(HERE/'INDEX_REVIEW.json',dict(status='PASS',actual_staged_blobs=len(names),private_pixels_excluded=True))
        print('INDEX_PASS',len(names),flush=True);return
    head=git('rev-parse','HEAD').decode().strip();remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    assert head==remote;git('fetch','origin','main');assert git('rev-parse','origin/main').decode().strip()==remote
    append('INDEX_REVIEW.json')
    if mode=='final':
        append('REMOTE_VERIFICATION.json')
        assert read(HERE/'REMOTE_VERIFICATION.json')['science_commit'] in git('rev-list',remote).decode().splitlines()
    checked={}
    for pin in pins:
        verify_item(pin);value=git('show',remote+':'+pin['relative_path'])
        assert len(value)==pin['bytes'] and hashlib.sha256(value).hexdigest()==pin['sha256']
        checked[pin['relative_path']]=dict(bytes=len(value),sha256=pin['sha256'])
    if mode=='remote':write_new(HERE/'REMOTE_VERIFICATION.json',dict(status='ACTUAL_REMOTE_MAIN_ALL_PUBLIC_BLOBS_VERIFIED',
        science_commit=head,remote_main=remote,checked_utc=datetime.now(timezone.utc).isoformat(),files=checked,
        force_push=False,receipt_committed_next=True,model_http=0,cost_usd=0))
    print(json.dumps(dict(status='ACTUAL_REMOTE_MAIN_ALL_PUBLIC_BLOBS_VERIFIED',main=remote,files=len(checked))),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    else:verify(sys.argv[1])
