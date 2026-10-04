"""Postseal verification and numeric-only delivery; no prediction or tuning."""
from common import *
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import subprocess


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def save(name, value):
    write_new(HERE/name, value)


def files():
    omit = {'PUBLIC_ARTIFACT_MANIFEST.json', 'INDEX_REVIEW.json', 'REMOTE_VERIFICATION.json'}
    return sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in omit
                  and not {'private', '__pycache__'} & set(p.relative_to(HERE).parts))


def verify_pins(value):
    if isinstance(value, dict):
        if {'path', 'bytes', 'sha256'} <= value.keys():
            verify_item(value)
        else:
            for v in value.values():
                verify_pins(v)
    elif isinstance(value, list):
        for v in value:
            verify_pins(v)


def verify_science():
    runtime=read(HERE/'RUNTIME_FREEZE.json')
    for path,pin in runtime['code'].items(): assert sha(path)==pin,path
    allseal=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    verify_pins(allseal['seals']);verify_pins(allseal['access_seals'])
    verify_pins(read(HERE/'REPORT_PROVENANCE.json'));verify_pins(read(RUN/'SCORE_PROVENANCE.json'))
    result=read(HERE/'RESULTS.json');metrics=read(RUN/'METRICS.json');review=read(HERE/'INPUT_REVIEW.json')
    assert review['status']=='PASS' and review['frames']==20098 and review['objects']==181842
    assert read(sorted((HERE/'checks').glob('*.json'))[-1])['status']=='PASS'
    assert result['totals']['frames']==review['frames'] and result['totals']['objects']==review['objects']
    for k,r in [('checks','candidate_checks'),('veto_checks','veto_checks'),('changed_frames','changed_frames'),('measured_objects','measured_objects')]:
        assert result['totals'][k]==review[r]
    summaries={};restricted={};frames=0;actions=0
    for name in SEGMENTS:
        verify_seal(name);public=RUN/name/'public';frozen=read(public/'FREEZE.json')
        verify_pins(frozen['source_chain'])
        for key in ('source_manifest','original_prediction','original_prediction_seal','runtime'):verify_item(frozen[key])
        summary=read(public/'RUN_SUMMARY.json');frames+=summary['frames']
        assert len(metrics['segments'][name]['changed_frames'])==summary['changed_frames']
        for base in ARMS[:2]:
            archived=read(ROOT/'experiments/ds20_pending_confirmation_isolation/run/METRICS.json')['segments'][name]['metrics'][base]
            assert metrics['segments'][name]['metrics'][base]==archived
        tx=iter(rows(public/'TRANSACTIONS.jsonl.gz'));seen=False;bound=0
        for prediction,ledger,checks in zip(rows(public/'predictions.jsonl.gz'),rows(public/'PUBLISH_LEDGER.jsonl'),rows(public/'ORDER_CHECKS.jsonl.gz'),strict=True):
            original,modified=next(tx),next(tx);bound+=1
            assert ledger['prediction_row_sha256']==row_sha(prediction) and ledger['checks_row_sha256']==row_sha(checks)
            for actual in (original,modified):assert ledger['transaction_row_sha256'][actual['arm']]==row_sha(actual)
            seen=seen or any(c['veto'] for c in checks['checks'])
            if not seen:
                for key in ('engine_state_sha256','actual_published_mapping','actual_alias_targets','bank_anchors'):assert original[key]==modified[key]
            actions+=len(modified['actual_actions'])
        assert next(tx,None) is None and bound==summary['frames']
        summaries[name]=dict(frames=bound,changed_frames=summary['changed_frames'],veto_checks=summary['veto_checks'],all_publish_rows_bound=True,scientific_states_equal_until_first_real_veto=True)
        chain=frozen['source_chain'];restricted[name]=dict(saved_original_inputs=chain['derived_inputs'],raw_file_inventory=chain['raw_sources'],source_manifest=frozen['source_manifest'],original_saved_inputs=chain['original_inputs'])
    assert frames==20098
    visuals=read(HERE/'PRIVATE_VISUALS_V2.json');verify_pins(visuals);verify_pins(read(HERE/'PRIVATE_VISUALS.json'))
    assert all(not f['GT_raster'] and not f['used_for_prediction'] for f in visuals['figures'])
    return dict(status='PASS',frames=frames,frozen_runtime_sources=len(runtime['code']),segments=summaries,
        all_scientific_frozen_code_inputs_and_seals_unchanged=True,actual_modified_branch_actions=actions,
        private_figures_manually_inspected=len(visuals['figures']),no_parameter_changes_after_freeze=True,
        no_new_GT_read=True,new_model_http=0,cost_usd=0),restricted


def public_content_check(value, key=""):
    if isinstance(value, dict):
        assert not {'rle', 'polygons', 'segmentation', 'depth_pixels', 'pixel_values',
                    'api_key', 'provider_file_id'} & value.keys()
        for k,v in value.items():
            public_content_check(v,k)
    elif isinstance(value, list):
        assert len(value)<=32 or not all(isinstance(v,(int,float)) for v in value) or key in {'anonymous_interval_frames','changed_frames','evaluated_pre_frames','shared_pre_frames','pre_frames'}, ('Unreviewed numeric vector',key)
        for v in value:
            public_content_check(v,key)


def finalize():
    assert git('rev-parse', 'HEAD').decode().strip() == BASE
    assert not git('diff', '--name-only').decode().strip()
    qa, inputs = verify_science(); save('POSTSEAL_QA.json', qa)
    private = [artifact(p) for p in HERE.rglob('*') if p.is_file() and 'private' in p.relative_to(HERE).parts]
    packages = {}
    for name in ('numpy', 'scipy', 'opencv-python', 'h5py', 'Pillow'):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = 'NOT_REGISTERED_IN_THIS_INTERPRETER; SEE_FROZEN_SOURCE_PATHS'
    save('RESTRICTED_ARTIFACTS.json', dict(
        status='ACTUAL_LOCAL_PATH_BYTES_SHA_ONLY; NO_PRIVATE_PIXELS_PUBLISHED', private_figures=private,
        same_source_saved_inputs_and_complete_raw_file_inventories=inputs,
        private_figure_raw_RGB_dependencies=[artifact(HERE/'PRIVATE_VISUALS.json'),artifact(HERE/'PRIVATE_VISUALS_V2.json')],
        dependencies=dict(python=sys.executable, python_version=sys.version, packages=packages,
                          deps=str(DEPS), base_commit=BASE, frozen_runtime=artifact(HERE/'RUNTIME_FREEZE.json')),
        reproduction='Use the pinned review base and original source inventories. Copy the frozen DS25 science files '
                     '(not outputs or seals) into a fresh empty experiment directory in a separate checkout with '
                     'the same restricted inputs/dependencies accessible at recorded paths. Recreate checks and '
                     'the two real 200-frame prefixes plus the actual bounded 82-frame prefix and its read-only review; freeze.py requires BASE and an absent run directory. '
                     'Then guarded orchestrate.py, postseal review.py, score.py, visualize.py (v1), visualize_v2.py (layout repair only), report.py with recorded NEXT_STEP_SELECTION.json. '
                     'Never overwrite this experiment or old seals. Pixel rendering is postseal only.',
        RGB_read_for_postseal_private_visuals_only=True, GT_raster_not_published=True,
        new_model_http=0, cost_usd=0))
    result=read(HERE/'RESULTS.json'); totals=result['totals']
    handoff=(f"## DS25 contact-local anonymous-layer trial completed (2026-10-04)\n\n"
        f"Completed eight saved-source segments / {totals['frames']} frames, three own-state branches and postseal unified scoring. "
        f"Status {result['status']}; local edge vetoes {totals['veto_checks']}, changed publication frames {totals['changed_frames']}. "
        "Original Z4Q and Native same-source output/metrics reproduced. Unique local ROI facts2343, two-layer available2, no complete comparable spatial chain; all90 original actions retained. Current-stage empty ROI247/378 and all15 contact seeds lack two qualified layers. "
        "Raw-depth, frozen source versions and original two matrix entries retained. "
        "No model HTTP, training, SAM3 inference, completion service or cost. Private pixels remain local. "
        "Read experiments/ds25_contact_local_layers/FINAL_REVIEW.md and NEXT_STEP_PLAN.md. The next plan is unrun; old handoff bytes preserved below.\n\n").encode()
    additive = {}
    for path, prefix, extra in (
        (ROOT/'research/HANDOFF.md', True, handoff),
        (ROOT/'.gitignore', False, b'\n# DS25 actual RGB/depth/mask figures remain private.\n/experiments/ds25_contact_local_layers/private/\n')):
        old = artifact(path); data = path.read_bytes()
        path.write_bytes(extra+data if prefix else data+extra)
        assert (path.read_bytes()[len(extra):] if prefix else path.read_bytes()[:len(data)]) == data
        additive[path.relative_to(ROOT).as_posix()] = dict(old=old, new=artifact(path), old_bytes_preserved=True)
    save('HANDOFF_UPDATE.json', additive)
    assert set(git('diff', '--name-only').decode().splitlines()) == {'.gitignore', 'research/HANDOFF.md'}
    for pin in private:
        assert git('check-ignore', pin['path']).decode().strip()
    records = 0
    for path in files():
        assert path.suffix.lower() not in {'.png', '.jpg', '.npy', '.npz', '.h5', '.mp4'}
        if path.suffix == '.json':
            public_content_check(read(path)); records += 1
        elif path.name.endswith('.jsonl.gz') or path.suffix == '.jsonl':
            for row in rows(path):
                public_content_check(row); records += 1
    save('PUBLIC_CONTENT_REVIEW.json', dict(status='PASS', numeric_records=records, private_figures=len(private),
        only_two_old_metadata_files_additively_changed=True, no_serialized_private_pixels_GT_credentials_provider_ids=True,
        all_frozen_science_and_old_tracked_content_unchanged=True, new_model_http=0, cost_usd=0))
    public = [dict(artifact(p), relative_path=p.relative_to(ROOT).as_posix()) for p in files()]
    save('PUBLIC_ARTIFACT_MANIFEST.json', dict(files=public,
        repository_files=[dict(artifact(p), relative_path=p.relative_to(ROOT).as_posix())
                          for p in (ROOT/'.gitignore', ROOT/'research/HANDOFF.md')],
        private_pixels_excluded=True, new_model_http=0, cost_usd=0))
    print('Postseal science, numeric records and delivery PASS', len(public), 'public files', len(private), 'private figures')


def verify(mode):
    manifest = read(HERE/'PUBLIC_ARTIFACT_MANIFEST.json')
    pins = manifest['files']+manifest['repository_files']
    def add(name):
        path = HERE/name; pins.append(dict(artifact(path), relative_path=path.relative_to(ROOT).as_posix()))
    add('PUBLIC_ARTIFACT_MANIFEST.json')
    if mode == 'index':
        names = git('diff', '--cached', '--name-only', '-z').decode().split('\0')[:-1]
        assert set(names) == {p['relative_path'] for p in pins}
        for p in pins:
            data = git('show', ':'+p['relative_path'])
            assert len(data) == p['bytes'] and hashlib.sha256(data).hexdigest() == p['sha256']
        save('INDEX_REVIEW.json', dict(status='PASS', actual_staged_blobs_verified=len(names), no_private_pixels=True))
        print('Actual staged bytes PASS', len(names)); return
    head = git('rev-parse', 'HEAD').decode().strip()
    remote = git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
    assert head == remote
    git('fetch', 'origin', 'main')
    assert git('rev-parse', 'origin/main').decode().strip() == remote
    add('INDEX_REVIEW.json')
    if mode == 'final':
        add('REMOTE_VERIFICATION.json')
    result = {}
    for p in pins:
        data = git('show', remote+':'+p['relative_path'])
        assert len(data) == p['bytes'] and hashlib.sha256(data).hexdigest() == p['sha256']
        result[p['relative_path']] = dict(bytes=len(data), sha256=p['sha256'])
    if mode == 'remote':
        save('REMOTE_VERIFICATION.json', dict(status='ACTUAL_REMOTE_REF_AND_ALL_PUBLIC_BLOBS_VERIFIED',
            science_commit=head, remote_main=remote, files=result, force_push=False,
            verified_utc=datetime.now(timezone.utc).isoformat(),
            note='Receipt is committed next; final ref and all blobs reread after receipt push.',
            new_model_http=0, cost_usd=0))
    print(json.dumps(dict(status='ACTUAL_REMOTE_REF_AND_ALL_PUBLIC_BLOBS_VERIFIED', remote_main=remote, files=len(result))))


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'finalize':
        finalize()
    else:
        assert mode in ('index', 'remote', 'final'); verify(mode)
