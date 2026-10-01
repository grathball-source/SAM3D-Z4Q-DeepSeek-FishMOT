"""Record this input-blocked audit; no retrospective prediction or test claims."""
from preflight import HERE, ROOT, WORK, BASE, artifact, write_new, verify
import hashlib
import json
import subprocess


def main():
    verify()
    references = [ROOT / ('experiments/' + relative) for relative in (
        'feeding_first_two_s0p/FINAL_REVIEW.md',
        'b0_same_source_regression_repair/FINAL_REVIEW.md',
        'z4q_anchor_evidence_retention/FINAL_REVIEW.md',
        'ne1_native_first_event_association/FINAL_REVIEW.md',
        'ds2_depth_transfer_validation/cohort.py',
        'ds6_multifragment_depth_tracking/common.py',
        'ds12_contact_depth_admission/NEXT_STEP_PLAN.md',
        'ds12_contact_depth_admission/RESULTS.md')]
    references += [WORK / relative for relative in (
        'data/AlignedFeeding_v1/README.md',
        'data/AlignedDataset_v1/README.md',
        'data/AlignedDataset_v1/provenance/metadata.json',
        'tools/prelabel_feeding_20260924/README.md',
        'tools/prelabel_feeding_20260924/build_aligned_feeding.py',
        'tools/depth_restoration_feeding_20260929/README.md',
        'tools/z4q_new_bags_20260923/README.md',
        'tools/z4q_new_bags_20260923/run.py',
        'tools/z4q_new_bags_20260923/audit_switches.py',
        'tools/annotation/render_new_bags_events.py',
        'tools/prelabel_new_bags_20260919/README.md',
        'tools/prelabel_new_bags_20260919/full_acceptance.json',
        'data/Metadata/README_20260919_new_bags.md')]
    write_new('SOURCE_RECORD_REFERENCES.json', dict(files=[artifact(p) for p in references],
        scope='BOUNDED_READONLY_RECORD_REVIEW; NOT_EXHAUSTIVE_EXTERNAL_TUNING_PROOF'))
    lock = json.loads((HERE / 'OLD_READONLY_LOCK.json').read_text(encoding='utf-8'))
    frozen = json.loads((HERE / 'FROZEN_R12_LOCK.json').read_text(encoding='utf-8'))
    write_new('CHECKS_RESULT.json', dict(status='SOURCE_LINEAGE_AND_BYTES_PASS',
        observed_command='E:/researchsoftware/anaconda3/envs/D-MOT/python.exe -B experiments/ds13_frozen_validation/checks.py',
        observed_exit_code=0, source_lineage_checks=5, old_files_reverified=lock['count'],
        frozen_bindings_reverified=len(frozen['code']),
        source_pixel_checks='NOT_RUN', tracking_equivalence='NOT_RUN', scientific_performance='NOT_EVALUATED'))
    write_new('EXECUTION_LOG.json', dict(base_commit=BASE,
        actions=['READ_TASK_AND_FROZEN_NEXT_STEP', 'INDEPENDENT_READONLY_SOURCE_USAGE_AND_SCORING_DEPENDENCY_REVIEWS',
                 'METADATA_PATH_AND_FILENAME_AUDIT', 'VERIFY_76_PREVIOUS_FORMAL_FREEZE_BINDINGS',
                 'LOCK_AND_REVERIFY_1314_OLD_TRACKED_FILES', 'RUN_FIVE_SOURCE_LINEAGE_CHECKS',
                 'WRITE_ACTUAL_INPUT_BLOCKED_REPORT'],
        new_prediction_frames=0, new_scoring_frames=0, new_model_http=0, cost_usd=0,
        network_during_tracking='NO_TRACKING_EXECUTION', private_pixel_outputs=[],
        no_GT_or_pixel_content_for_selection=True,
        pending_user_input='NEW_COHORT_PATH_OR_EXPLICIT_ALTERNATIVE_TWO_ARM_DIAGNOSTIC_SELECTION_NOT_RECEIVED'))
    write_new('RESTRICTED_INVENTORY.json', dict(new_restricted_outputs=[], new_restricted_output_bytes=0,
        source_metadata=artifact(HERE / 'SOURCE_METADATA_INVENTORY.json'),
        source_records=artifact(HERE / 'SOURCE_RECORD_REFERENCES.json'),
        actual_file_entries='See the two inventory documents for each real path/bytes/SHA256',
        predictions_and_private_pixels='NOT_OPENED; EXISTS_ONLY_INVENTORY_NOT_CONTENT_VERIFICATION',
        reproduction_dependencies=['original metadata/code paths from inventories', 'existing local D-MOT Python',
                                  'no API key/service/GPU/server dependency']))
    handoff = ROOT / 'research/HANDOFF.md'
    previous = handoff.read_bytes()
    prefix = (
        '# Latest: DS13 frozen validation source audit (2026-10-01)\r\n\r\n'
        'User authorized start of DS12 NEXT_STEP_PLAN. Read experiments/ds13_frozen_validation/RESULTS.md, '
        'PLAN.md, INPUT_AVAILABILITY.json, source/use inventories and frozen/old byte locks. '
        'Status DS13_INPUT_BLOCKED; no new prediction/scoring/restore or scientific outcome. '
        'Feeding only old1471 used frames;1907 saved SAM3 includes436 gaps outside complete aligned-reference package. '
        'L3/LW have complete raw sources and fixed earlier evaluation, no DS tuning record found; '
        'do not falsely classify baseline exposure as tuning. Their reference is dependent preannotation; '
        'F9 native-v2 chain absent in inspected entries, explicit fresh-dev scope/external tuning history UNKNOWN. '
        'The two camera acquisition intervals overlap97.882s, not two disjoint time segments.\r\n\r\n'
        'DS12 formal76 bindings and DS1-12 tracked1314 files verified unchanged. Five source-lineage checks PASS '
        'only; new source pixel/state/equivalence checks NOT_RUN. New metrics/success null; historical DS12 '
        'micro-gain stays old exposed development evidence, not DS13 validation. No HTTP/smoke/train/SAM3/'
        'completion/server/cost. Do not drop F9, substitute raw for v2, open sealed test or auto-tune R12. '
        'Questions about a new path or alternative L3/LW two-arm diagnosis await user reply; no dependent run started.\r\n\r\n'
        'One next step: provide complete approved untuned saved cohort with reference and three-arm depth inputs, '
        'then execute unchanged frozen validation. All older handoff bytes preserved below.\r\n\r\n')
    assert not previous.startswith(prefix.encode('utf-8'))
    handoff.write_bytes(prefix.encode('utf-8') + previous)
    assert handoff.read_bytes()[len(prefix.encode('utf-8')):] == previous
    write_new('HANDOFF_APPEND_PROOF.json', dict(previous_bytes=len(previous),
        previous_sha256=hashlib.sha256(previous).hexdigest(), unchanged_tail=True,
        new_handoff=artifact(handoff)))
    public = []
    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.name not in ('ARTIFACT_MANIFEST.json', 'REMOTE_VERIFICATION.json'):
            assert path.suffix in ('.py', '.json', '.md'), path
            item = artifact(path)
            public.append(dict(name=path.name, **item))
    write_new('ARTIFACT_MANIFEST.json', dict(files=public, count=len(public),
        bytes=sum(item['bytes'] for item in public),
        exclusions=['self digest', 'later append-only remote proof'], pixel_outputs=0))
    assert not (HERE / 'run').exists()
    changed = subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)
    print(json.dumps(dict(status='AUDIT_DELIVERY_PREPARED', old_files=lock['count'],
        public_files=len(public), changed=changed, no_new_scientific_result=True)))


if __name__ == '__main__':
    main()
