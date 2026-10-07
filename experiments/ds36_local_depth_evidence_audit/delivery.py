"""Scoped public delivery, old-byte preservation and actual remote blob verification."""
from common import *
from datetime import datetime,timezone

OMIT={'PUBLIC_ARTIFACT_MANIFEST.json','INDEX_REVIEW.json','REMOTE_VERIFICATION.json'}

def public_files():
    return sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in OMIT
                  and not {'private','__pycache__'}&set(p.relative_to(HERE).parts))

def numeric(value):
    if isinstance(value,dict):
        assert not {'rle','polygons','segmentation','depth_pixels','pixel_values','api_key','provider_file_id','counts_rle'}&value.keys()
        for child in value.values():numeric(child)
    elif isinstance(value,list):
        for child in value:numeric(child)

def prepare():
    verify_freeze();assert git('rev-parse','HEAD').decode().strip()==BASE
    assert not git('diff','--name-only').decode().strip()
    assert read(HERE/'REPORT_VALIDATION.json')['status']=='PASS'
    assert read(HERE/'VISUAL_ACCEPTANCE.json')['status']=='PASS_ACTUAL_LOCAL_VISUAL_INSPECTION'
    assert (HERE/'DEEP_REVIEW.md').is_file()
    initial=read(HERE/'ENVIRONMENT_INITIAL_V2.json')
    for key in ('original_handoff','original_gitignore'):verify_item(initial[key])
    private=[artifact(p) for p in (HERE/'private').rglob('*') if p.is_file()]
    save('PRIVATE_INVENTORY.json',dict(private_outputs=private,
        sensor_inputs=read(HERE/'MEASUREMENT_SUMMARY.json')['sensor_files'],
        saved_inputs=artifact(HERE/'INPUT_PINS.json'),source_freeze=artifact(HERE/'FREEZE.json'),
        python=sys.executable,dependencies=str(DEPS),
        reproduce='Use an empty output checkout at BASE plus delivered DS36 source; provide exact private DS14 saved N0 '
            'masks/raw-depth inputs, DS18 original certificates and immutable DS35/DS21 records with recorded hashes. '
            'Run initialize, checks, freeze, measure, join and report in that order, then inspect figures and prepare delivery. '
            'No GT raster/RGB, model API, new SAM3, restoration, training, state write or new metrics.',
        private_pixels_excluded=True,model_http=0,cost_usd=0))
    header=('## DS36 local depth evidence and causal forecast audit completed (2026-10-07)\n\n'
        'Read-only audit of all90 original Z4Q actions and all75 DS35 automatic events on eight saved sources/20098frames. '
        'Local whole/core/geometry-only patches and every neighboring anonymous mask, deduplicated raw native sources, '
        'local annulus proxies, frozen WLS variance components and causal held-out source-proxy observations are recorded. '
        'Features sealed before existing postseal physical-label join; correct/wrong/unscorable and missing opportunities retained. '
        'No original identity state or predictions changed; no new tracking scores. '
        'See experiments/ds36_local_depth_evidence_audit/FINAL_REVIEW.md and DEEP_REVIEW.md for evidence and one unstarted next step. '
        'No model HTTP/smoke/GPU/server/SAM3/training/completion/fees; L3/LW weak and source/physical ownership UNKNOWN. '
        'Private depth/mask plots inventoried; public numeric records synchronized. Previous handoff bytes preserved below.\n\n').encode()
    changes={}
    for path,extra,prefix in [(ROOT/'research/HANDOFF.md',header,True),
        (ROOT/'.gitignore',b'\n# DS36 private actual depth/mask diagnostics.\n/experiments/ds36_local_depth_evidence_audit/private/\n',False)]:
        before=artifact(path);data=path.read_bytes();path.write_bytes(extra+data if prefix else data+extra)
        assert (path.read_bytes()[len(extra):] if prefix else path.read_bytes()[:len(data)])==data
        changes[path.relative_to(ROOT).as_posix()]=dict(old=before,new=artifact(path),previous_bytes_preserved=True)
    save('HANDOFF_UPDATE.json',changes)
    records=0
    for p in public_files():
        assert p.suffix.lower() not in {'.png','.jpg','.jpeg','.npy','.npz','.h5','.mp4'}
        assert p.stat().st_size<95*1024**2
        if p.suffix=='.json':numeric(read(p));records+=1
        elif p.name.endswith('.jsonl.gz') or p.suffix=='.jsonl':
            for v in rows(p):numeric(v);records+=1
    for p in private:assert git('check-ignore',p['path']).decode().strip()
    save('PUBLIC_CONTENT_REVIEW.json',dict(status='PASS',numeric_records=records,private_outputs=len(private),
        old_frozen_bytes_reverified=True,new_metrics=False,new_predictions=False,model_http=0,cost_usd=0))
    save('PUBLIC_ARTIFACT_MANIFEST.json',dict(files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in public_files()],
        repository_files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in (ROOT/'.gitignore',ROOT/'research/HANDOFF.md')],
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
            data=git('show',':'+pin['relative_path']);assert len(data)==pin['bytes'] and hashlib.sha256(data).hexdigest()==pin['sha256']
        save('INDEX_REVIEW.json',dict(status='PASS',actual_staged_blobs=len(names),private_pixels_excluded=True))
        print('INDEX_PASS',len(names),flush=True);return
    head=git('rev-parse','HEAD').decode().strip();remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    assert head==remote;git('fetch','origin','main');assert git('rev-parse','origin/main').decode().strip()==remote
    append('INDEX_REVIEW.json')
    if mode=='final':
        append('REMOTE_VERIFICATION.json')
        assert read(HERE/'REMOTE_VERIFICATION.json')['science_commit'] in git('rev-list',remote).decode().splitlines()
    results={}
    for p in pins:
        verify_item(p);data=git('show',remote+':'+p['relative_path'])
        assert len(data)==p['bytes'] and hashlib.sha256(data).hexdigest()==p['sha256']
        results[p['relative_path']]=dict(bytes=len(data),sha256=p['sha256'])
    if mode=='remote':save('REMOTE_VERIFICATION.json',dict(status='ACTUAL_REMOTE_MAIN_AND_ALL_PUBLIC_BLOBS_VERIFIED',
        science_commit=head,remote_main=remote,checked_utc=datetime.now(timezone.utc).isoformat(),files=results,
        force_push=False,receipt_committed_next=True,model_http=0,cost_usd=0))
    print(json.dumps(dict(status='ACTUAL_REMOTE_MAIN_AND_ALL_PUBLIC_BLOBS_VERIFIED',main=remote,files=len(results))),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    else:verify(sys.argv[1])
