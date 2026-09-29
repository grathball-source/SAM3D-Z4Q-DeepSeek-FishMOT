"""Write concise postscore case findings, archived VLM facts, and restricted-path inventory."""
from collections import defaultdict
import json
from pathlib import Path

from source import DATA, HERE, ML, ROOT, SEGMENTS, descriptor, save, sha


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    manifest = read(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json')
    causes = read(HERE / 'public/POSTSEAL_CAUSE_REVIEW.json')['source']
    old = causes['SOURCE_OLD']
    harmful = next(action for action in old['accepted_frozen_reconnects']
                   if action['physical_relation'] == 'DIFFERENT_GT')
    assert harmful['original_frame'] == 159 and harmful['native_id'] == 26
    save(HERE / 'public/FIRST_HARMFUL_ACTION.json', dict(status='POSTSEAL_CONFIRMED',
        action=harmful, first_decision_prestate_sha256=read(
            HERE / 'public/counterfactual_F159/ALLOW/SEAL.json')['decision_pre_state_sha256'],
        same_source_counterfactual='public/counterfactual_F159/POSTSEAL_SCORE.json',
        visualization='public/cases/SOURCE_OLD_159_native26.svg',
        source_old_switch_occurrence=(harmful['segment'], harmful['original_frame'], 26)))
    old_correct = [action for action in old['accepted_frozen_reconnects']
                   if action['physical_relation'] == 'SAME_GT']
    assert not old_correct and not old['occurrence_native_only_vs_frozen']
    baseline_correct = [action for action in causes['SOURCE_BASELINE']['accepted_frozen_reconnects']
                        if action['physical_relation'] == 'SAME_GT']
    assert baseline_correct and baseline_correct[0]['original_frame'] == 372
    save(HERE / 'public/FIRST_BENEFICIAL_ACTION.json', dict(
        status='NO_VERIFIED_SOURCE_OLD_BENEFICIAL_ACTION',
        definition='physically same GT at actual anchor and current source, or a native switch occurrence eliminated',
        source_old='none; F194 is unscorable, F468 has different anchor/current GT; native-only switch occurrences=0',
        separate_source_baseline_first_same_gt=baseline_correct[0],
        caveat='F372 is physically same-GT but adds a CLEAR switch at publication; it is not proven metric-beneficial',
        visualization='public/cases/SOURCE_BASELINE_372_native28.svg'))
    old_audit = read(ROOT / 'experiments/feeding_first_two_s0p/run/ANCHOR_AUDIT.json')
    old_metrics = read(ROOT / 'experiments/feeding_first_two_s0p/run/METRICS.json')
    events = []
    for frame in (419, 519):
        pair = [event for event in old_audit['events'] if event['original_q'] == frame
                and event['arm'] in ('B-HOLD', 'B-VLM')]
        assert len(pair) == 2
        events.extend(dict(original_q=frame, arm=event['arm'], raw_choice=event['raw_choice'],
            numeric_choice=event['numeric_choice'], selected_choice=event['selected_choice'],
            selected_mapping=event['selected_mapping'], physical=event['physical'],
            anchor_audit_event=event['event']) for event in pair)
    save(HERE / 'public/ARCHIVED_VLM_FACTS.json', dict(status='ARCHIVED_REFERENCE_ONLY',
        events=events, old_source_pooled_B_VLM=old_metrics['pooled_metrics']['B-VLM'],
        old_anchor_audit_sha256=sha(ROOT / 'experiments/feeding_first_two_s0p/run/ANCHOR_AUDIT.json'),
        old_metrics_sha256=sha(ROOT / 'experiments/feeding_first_two_s0p/run/METRICS.json'),
        new_model_http=0, new_state_reuse=False))
    aligned = {row['frame']: row for row in map(json.loads,
        (DATA / 'manifest.jsonl').read_text(encoding='utf-8').splitlines())}
    segments = defaultdict(list)
    for name, (start, stop) in SEGMENTS.items():
        for frame in range(start, stop+1):
            metadata = aligned[frame]
            original = DATA / metadata['rgb_original']
            resized = DATA / metadata['rgb']
            gt = DATA / 'labels_640x360' / f'{frame:06d}.json'
            rgb = descriptor(original)
            assert rgb['sha256'] == metadata['source_rgb_sha256']
            segments[name].append(dict(original_frame=frame, rgb_original=rgb,
                rgb_aligned=descriptor(resized), edited_reference=descriptor(gt),
                reference_checked=False))
    inputs = {}
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        inputs[source] = {}
        for name in SEGMENTS:
            item = manifest['segments'][source][name]
            inputs[source][name] = dict(prediction_dir=item['prediction_dir'],
                raw_prediction_files=[dict(path=row['prediction_path'], bytes=row['prediction_bytes'],
                    sha256=row['prediction_sha256'], original_frame=row['original_frame'])
                    for row in item['frames']],
                aligned_depth_files=[dict(path=row['depth_path'], bytes=row['depth_bytes'],
                    sha256=row['depth_sha256'], original_frame=row['original_frame'])
                    for row in item['frames']],
                derived=item['derived'])
    baseline_new_private = HERE / 'private/baseline/feeding_000351_000555'
    assert all(Path(entry['path']).is_file() for entry in inputs['SOURCE_BASELINE']['feeding_000351_000555']['derived'].values())
    save(HERE / 'public/RESTRICTED_INVENTORY.json', dict(status='HASHED_PATHS_NO_CONTENT',
        data_root=str(DATA), raw_prediction_sources=inputs, common_rgb_and_edited_reference=segments,
        task_private_derived_dir=str(baseline_new_private),
        reproduction='Run source.py only in a new empty task directory with the listed saved SAM3 raw JSON, aligned manifest/depth and old derived source; then trace.py, score.py, counterfactual.py run|score, test_onefix.py, onefix.py, score_onefix.py, postscore.py, visualize.py, latency.py, supplements.py. Existing sealed files are immutable.',
        no_private_pixels_in_git=True, no_gt_raster_in_git=True, no_model_http=True))
    print('case findings, archived facts, restricted paths sealed', flush=True)


if __name__ == '__main__':
    main()
