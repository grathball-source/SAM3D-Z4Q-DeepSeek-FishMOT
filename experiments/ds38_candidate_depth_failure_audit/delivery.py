"""Scoped ordinary-main synchronization with all public byte and archive checks."""
from common import *
OMIT={'PUBLIC_ARTIFACT_MANIFEST.json','INDEX_REVIEW.json','REMOTE_VERIFICATION.json'}

def files():
    return sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in OMIT
        and not {'private','__pycache__'}&set(p.relative_to(HERE).parts))
def privacy(value):
    if isinstance(value,dict):
        assert not {'rle','segmentation','polygons','depth_pixels','pixel_values','api_key','provider_file_id'}&value.keys()
        for v in value.values(): privacy(v)
    elif isinstance(value,list):
        for v in value: privacy(v)

def prepare():
    verified_freeze()
    assert git('rev-parse','HEAD').decode().strip()==BASE
    assert set(git('diff','--name-only').decode().splitlines())=={'.gitignore'}
    assert read(HERE/'REPORT_ACCEPTANCE.json')['replay_frames']==1471
    assert read(HERE/'VISUAL_INSPECTION.json')['status']=='ACTUAL_LOCAL_INSPECTION_COMPLETED'
    for pin in read(HERE/'FEATURES_SEALED.json')['files']: verify_item(pin)
    oldfiles=read(HERE/'INPUT_PINS.json')['files']
    for pin in oldfiles: verify_item(pin)
    save('ARCHIVE_PRESERVATION.json',dict(status='ALL_PINNED_OLD_CODE_SOURCE_SEAL_AND_OUTPUT_BYTES_UNCHANGED',
        files_verified=len(oldfiles),old_inputs_and_outputs_read_only=True))
    handoff=ROOT/'research/HANDOFF.md';before=artifact(handoff);oldbytes=handoff.read_bytes()
    results=read(HERE/'RESULTS.json')['summary']
    header=('## DS38 complete candidate/raw-depth failure audit (2026-10-08)\n\n'
        'All27 original Feeding actions:17 WRONG,8 CORRECT,2 UNSCORABLE; four original segments/1471frames. '
        'Passive original-controller matrix snapshots; engine SHA, trace, mapping and version exact at every frame. '
        'All bank/core/whole anchors, raw independent-source distributions and local order recorded before existing reference-match join. '
        f'Wrong-action independent-correct-reference causes: {json.dumps(results["WRONG"]["causes"])}. '
        'No new tracker gain claim; exposed diagnostic cohort, no threshold fit, RGB, GT raster, hidden test, HTTP, fees, training, SAM3 or restoration. '
        'See experiments/ds38_candidate_depth_failure_audit/FINAL_REVIEW.md, DEEP_REVIEW.md, RESULTS.json and NEXT_STEP.md. '
        'Restricted real raw depth/mask views and populations inventoried; all previous handoff bytes preserved below.\n\n').encode()
    handoff.write_bytes(header+oldbytes);assert handoff.read_bytes()[len(header):]==oldbytes
    save('HANDOFF_UPDATE.json',dict(before=before,after=artifact(handoff),all_previous_bytes_preserved=True))
    count=0
    for p in files():
        assert p.suffix.lower() not in {'.png','.jpg','.npz','.npy','.h5','.mp4','.pdf'}
        assert p.stat().st_size<95*1024**2,p
        if p.suffix=='.json': privacy(read(p));count+=1
        elif p.name.endswith('.jsonl.gz'):
            for v in rows(p): privacy(v);count+=1
        elif p.suffix=='.svg': assert '<image' not in p.read_text(encoding='utf-8')
    private=[artifact(p) for p in (HERE/'private').rglob('*') if p.is_file()]
    for pin in private: assert git('check-ignore',pin['path']).decode().strip()
    save('FINAL_PRIVATE_INVENTORY.json',dict(files=private,python=sys.executable,deps=str(LEGACY.DEPS),
        input_manifest=artifact(HERE/'INPUT_PINS.json'),
        reproduction='New empty output directory; exact E-volume readonly originals and frozen Python/deps. initialize/checks/freeze/replay/measurements/join/report. No network model or new inference.',
        private_pixels_excluded=True))
    save('PUBLIC_CONTENT_REVIEW.json',dict(status='NUMERIC_PUBLIC_RECORDS_NO_PRIVATE_PIXELS_CREDENTIALS_OR_PROVIDER_IDS',
        numeric_records=count,private_files=len(private),model_http=0,cost_usd=0))
    save('PUBLIC_ARTIFACT_MANIFEST.json',dict(files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in files()],
        repository_files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in (ROOT/'.gitignore',handoff)]))
    print('DELIVERY READY',count,len(private),flush=True)

def verify(mode):
    manifest=read(HERE/'PUBLIC_ARTIFACT_MANIFEST.json');pins=manifest['files']+manifest['repository_files']
    def append(name): pins.append(dict(artifact(HERE/name),relative_path=(HERE/name).relative_to(ROOT).as_posix()))
    append('PUBLIC_ARTIFACT_MANIFEST.json')
    for pin in pins: verify_item(pin)
    if mode=='index':
        names=git('diff','--cached','--name-only','-z').decode().split('\0')[:-1]
        assert set(names)=={p['relative_path'] for p in pins}
        for pin in pins:
            blob=git('show',':'+pin['relative_path']);assert len(blob)==pin['bytes'] and hashlib.sha256(blob).hexdigest()==pin['sha256']
        save('INDEX_REVIEW.json',dict(status='PASS_ALL_STAGED_BYTES',files=len(names),private_pixels_excluded=True))
        print('INDEX VERIFIED',len(names));return
    head=git('rev-parse','HEAD').decode().strip();remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    assert head==remote;git('fetch','origin','main');assert git('rev-parse','origin/main').decode().strip()==remote
    append('INDEX_REVIEW.json')
    if mode=='final': append('REMOTE_VERIFICATION.json')
    checked={}
    for pin in pins:
        blob=git('show',remote+':'+pin['relative_path']);assert len(blob)==pin['bytes'] and hashlib.sha256(blob).hexdigest()==pin['sha256']
        checked[pin['relative_path']]=dict(bytes=len(blob),sha256=pin['sha256'])
    if mode=='remote': save('REMOTE_VERIFICATION.json',dict(status='ACTUAL_REMOTE_MAIN_AND_ALL_PUBLIC_FILES_VERIFIED',
        science_commit=head,remote_main=remote,checked_utc=utc(),files=checked,force_push=False,receipt_committed_next=True))
    print(json.dumps(dict(status='ACTUAL_REMOTE_MAIN_AND_ALL_PUBLIC_FILES_VERIFIED',main=remote,files=len(checked))),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare': prepare()
    else: verify(sys.argv[1])
