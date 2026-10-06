"""Describe frozen evidence failures after scoring; never adjust a decision rule."""
from common import *
from collections import Counter
from statistics import median


def distribution(values):
    return dict(n=len(values), minimum=min(values) if values else None,
        median=median(values) if values else None, maximum=max(values) if values else None)


def main():
    assert (RUN / 'ALL_PREDICTIONS_SEALED.json').exists() and (RUN / 'SCORE_PROVENANCE.json').exists()
    assert read(RUN / 'SCORE_PROVENANCE.json')['reference_opened_after_all_seals']
    aggregate = Counter()
    events = []
    flow_counts = Counter()
    flow_seconds = 0.
    for name in SEGMENTS:
        public = RUN / name / 'public'
        for row in rows(public / 'FLOW.jsonl.gz'):
            if row['pair'] is None:
                flow_counts['first_frame_no_previous'] += 1
                continue
            pair = row['pair']
            flow_counts['actual_pairs'] += 1
            # Preserve the original summary keys without assuming a measurement
            # is available merely because an image contains nonzero depth.
            if isinstance(pair.get('depth_status'), str):
                flow_counts['depth_status/'+pair['depth_status']] += 1
            flow_seconds += float(pair.get('flow_seconds', 0.))
        lists = read(public / 'EVENTS.json')
        times = {row['frame']: row['time'] for row in rows(public / 'predictions.jsonl.gz')}
        for arm, values in lists.items():
            for event in values:
                counter = Counter()
                fractions, ages_frames, ages_seconds, dice_scores, unknown_dice = [], [], [], [], []
                evidence = event.get('window_evidence', {})
                samples = evidence.get('samples', [])
                for sample in samples:
                    assert sample['time'] == times[sample['frame']]
                    counter['raw_clean_frames' if sample['clean'] else 'raw_nonclean_frames'] += 1
                    counter['source_generation_broken_frames'] += sample['source_generation_broken']
                    for comparison in sample['comparisons'].values():
                        assert comparison['frame'] == sample['frame']
                        counter['comparisons'] += 1
                        counter['RGB_available'] += comparison['status'] != 'UNKNOWN'
                        if comparison.get('reason'):
                            counter['reason/'+comparison['reason']] += 1
                        if 'depth_available' not in comparison:
                            counter['no_source_bound_contour_for_depth_check'] += 1
                            continue
                        fractions.append(comparison['reliable_fraction'])
                        dice_scores.append(comparison['rgb_dice'])
                        if comparison['status'] == 'UNKNOWN':
                            unknown_dice.append(comparison['rgb_dice'])
                        counter['predicted_contour_empty'] += comparison['predicted_area'] == 0
                        counter['trusted_contour_below_16_pixels'] += comparison['reliable_area'] < 16
                        counter['trusted_fraction_below_frozen_0_20'] += comparison['reliable_fraction'] < .20
                        anchor_frame = comparison['actual_reference']['frame']
                        assert 1 <= anchor_frame < event['request_frame'] <= sample['frame'] <= event['evidence_max_frame']
                        ages_frames.append(sample['frame'] - anchor_frame)
                        ages_seconds.append(sample['time'] - times[anchor_frame])
                        counter['pre_anchor_depth_not_usable'] += not comparison['anchor_depth_usable']
                        quality = comparison['source_depth_quality']
                        counter['current_depth_quality_unusable'] += not bool(quality.get('core_quality_usable'))
                        counter['current_depth_whole_multilayer'] += bool(quality.get('whole_multilayer'))
                        counter['current_depth_core_multilayer'] += bool(quality.get('core_multilayer'))
                        support = comparison['depth_support']
                        counter['conditional_3D_support_available'] += support['status'] == 'AVAILABLE_CONDITIONAL_3D_SUPPORT'
                        counter['conditional_3D_support_unknown'] += support['status'] != 'AVAILABLE_CONDITIONAL_3D_SUPPORT'
                        counter['full_pre_current_3D_depth_available'] += comparison['depth_available']
                aggregate.update(counter)
                q, cutoff = event['request_frame'], event['evidence_max_frame']
                assessment = event.get('assessment', {})
                events.append(dict(segment=name, arm=arm, global_frame=event['global_frame'], q=q,
                    evidence_max_frame=cutoff, status=event['status'],
                    source_ids=event['request'].get('sources'),
                    original_actions=event['request']['original_actions'],
                    request_component_count=len(event['request'].get('components', [])),
                    counters=dict(counter), actual_changes=event['actual_changes'],
                    cumulative_reliable_fraction=distribution(fractions),
                    checkpoint_bank_anchor_age_frames=distribution(ages_frames),
                    checkpoint_bank_anchor_age_seconds=distribution(ages_seconds),
                    all_plain_predicted_dice=distribution(dice_scores),
                    unknown_comparison_plain_predicted_dice=distribution(unknown_dice),
                    submitted_option=event['submitted_option'],
                    common_depth_weight=assessment.get('depth_common_component_weight', 0.),
                    assessment_reason=assessment.get('reason'),
                    score_explanations=assessment.get('scores', []),
                    invalid_candidate=event.get('invalid_candidate'),
                    raw_clean_tail=[s['frame'] for s in samples[-3:] if s['clean']],
                    no_GT_or_reference_used_to_change_this_frozen_trial=True))
    write_new(HERE / 'EVIDENCE_DIAGNOSTICS.json', dict(
        status='POSTSEAL_DESCRIPTIVE_ONLY_NO_PARAMETER_ADAPTATION', events=events,
        aggregate_both_arm_observation_counts=dict(aggregate),
        pair_flow_counts=dict(flow_counts), recorded_flow_seconds_sum=flow_seconds,
        denominator_limits='Both arms can describe the same raw pair; repeated targets across source candidates '
            'and both arms make these comparison-weighted summaries, not independent fish events. '
            'A checkpoint bank anchor is not assumed to equal an original action reference anchor.',
        scientific_limits='Unknown support is not a false correspondence, a protected negative, or a correct recovery.',
        reliability_diagnostics='Plain Dice is recorded even when cumulative visible support fails. '
            'Its numerical value alone does not certify a correct correspondence; these distributions never change the frozen rules.',
        new_model_http=0, cost_usd=0))
    print('Frozen evidence diagnostics complete', len(events), flush=True)


if __name__ == '__main__':
    main()
