"""Postexperiment public inventory and append-only handoff; no scientific changes."""
from common import *
from datetime import datetime, timezone


def main():
    summary = read(HERE/'SUMMARY.json')
    visuals = read(HERE/'PRIVATE_VISUALS.json')
    state_visuals = read(HERE/'PRIVATE_STATE_VISUALS.json')
    assert read(HERE/'VISUAL_QA.json')['status'] == 'ACTUAL_FIGURES_INSPECTED'
    assert read(HERE/'FINAL_CHECKS.json')['status'] == 'PASS'
    assert (HERE/'DEEP_REVIEW.md').exists()
    old = read(HERE/'OLD_READONLY_LOCK.json')['files']
    for path, digest in old.items():
        assert sha(ROOT/path) == digest, path
    for name in SEGMENTS:
        for path, digest in read(RUN/name/'public/FREEZE.json')['code_sha256'].items():
            assert sha(path) == digest, path
    for case in visuals['cases'] + state_visuals['cases']:
        verify_item(case['artifact'])
    handoff = ROOT/'research/HANDOFF.md'
    previous = handoff.read_bytes()
    judgement = summary['main_judgement']
    lines = ['# Latest: DS16 event-relative depth order (2026-10-02)', '',
        'Completed six independent real-state branches, eight segments/20098 frames; all predictions and access sealed before reference scoring. Read experiments/ds16_relative_depth_order/PLAN.md, RESULTS.md, DEEP_REVIEW.md, MAIN_JUDGEMENT.json, POSTSEAL_ORDER_REVIEW.json and the state/order/pipeline audits. All181842 saved native masks conserved; original native/Z4Q all-frame and full metric parity exact. No new model HTTP, smoke, SAM3, training, completion, GPU, server or cost.', '',
        'Common state repair advances real source/proposal continuity while freezing only protected public references. Original BirthRefine dev3902 n7->0 and validation global11488 n8->3 both retained; the ordinal inputs there are UNKNOWN, so these recoveries are common mechanism benefits. Group/unassigned post remain anonymous. The new event factor uses representative-core relative depth order, not verified local occlusion topology or a stable identity fingerprint.', '',
        'Frozen judgement: '+judgement['main']+'; ordinal: '+judgement['ordinal']+'.']
    for name, metrics in summary['main_units'].items():
        value = metrics['DEPTH_ORDER']
        delta = summary['deltas'][name]['Z4Q_FROZEN']
        lines.append(f"{name}: ORDER IDF1/HOTA/AssA/IDSW {value['IDF1']:.6f}/{value['HOTA']:.6f}/{value['AssA']:.6f}/{value['IDSW']}; versus original Z4Q {delta['IDF1']:+.6f}/{delta['HOTA']:+.6f}/{delta['AssA']:+.6f}/{delta['IDSW']:+g}.")
    lines += ['', 'Weak/UNKNOWN evidence, non-split events, stage rejection and unscorable reference are retained. Tiny negative ordinal support can veto an otherwise admitted geometric choice in this frozen version; its factor effect and admission-rule effect are reported separately. Raw adaptive-core pixel counts are not independent sensor-source counts or fish-surface accuracy. Feeding original four SOURCE_OLD ranges1471 only; another436 saved frames not tested. L3/LW dependent preannotation are weak diagnostics; exposed FishSA validation is not blind independent-video evidence. Private actual-pixel figures are inventoried and stay local.', '',
        'Only next step, superseding the report generator preliminary suggestion: separate immutable bank identity references from live activity/partner state, keep this ordinal formula/trigger/q/quality thresholds fixed, then run one same-source full state-repair contrast. Local crossing measurement is a later candidate, not another concurrent next step. No new experiment started. Prior handoff bytes remain verbatim below.', '']
    prefix = ('\n'.join(lines)+'\n').encode('utf-8')
    handoff.write_bytes(prefix+previous)
    assert handoff.read_bytes()[len(prefix):] == previous
    write_new(HERE/'HANDOFF_APPEND_PROOF.json', dict(path=str(handoff), old_bytes=len(previous),
        old_sha256=hashlib.sha256(previous).hexdigest(), prefix_bytes=len(prefix), old_suffix_unchanged=True,
        new=artifact(handoff)))
    write_new(HERE/'DELIVERY_EXECUTION.json', dict(command=[sys.executable, '-B', str(Path(__file__).resolve())],
        scientific_files_and_old_archives_verified_unchanged=True, public_handoff_appended=True,
        model_http=0, cost_usd=0, time_utc=datetime.now(timezone.utc).isoformat()))
    public = []
    for path in sorted(HERE.rglob('*')):
        if not path.is_file():
            continue
        parts = path.relative_to(HERE).parts
        if any(p in ('private', 'slice', '__pycache__') for p in parts):
            continue
        if path.name == 'PUBLIC_ARTIFACT_MANIFEST.json' or path.name.startswith('REMOTE_'):
            continue
        public.append(dict(relative_path=path.relative_to(ROOT).as_posix(), **artifact(path)))
    write_new(HERE/'PUBLIC_ARTIFACT_MANIFEST.json', dict(status='PUBLIC_DELIVERY_EXCLUDES_PRIVATE_PIXELS_AND_GT_RASTERS',
        files=public, count=len(public), total_bytes=sum(p['bytes'] for p in public),
        excluded=['private', 'slice', '__pycache__', 'self', 'subsequent_remote_sync_proof'],
        handoff=artifact(handoff), private_inventory=artifact(HERE/'RESTRICTED_ARTIFACTS.json'),
        model_requests=0, cost_usd=0))
    print('Final public delivery:', len(public), 'files; private figures', len(visuals['cases'])+len(state_visuals['cases']))


if __name__ == '__main__':
    main()
