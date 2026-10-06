"""Postseal descriptive analysis, delay accounting and publication deltas; no tuning."""
from common import *
from collections import Counter
import numpy as np


def main():
    from verify_inputs import verify_all
    verify_all()
    metric = read(RUN / 'METRICS.json')
    assert metric['status'].startswith('SCORED_AFTER_ALL')
    by_source, totals = {}, {arm:Counter() for arm in ARMS[2:]}
    for name in SEGMENTS:
        public = RUN / name / 'public'
        event_lists = read(public / 'EVENTS.json')
        count = {arm:Counter() for arm in ARMS[2:]}
        changed = {arm:[] for arm in ARMS[2:]}
        depth_different, depth_same = [], 0
        delay_frames, delay_seconds, wall = [], [], []
        times = {row['frame']:row['time'] for row in rows(public / 'predictions.jsonl.gz')}
        for record in rows(public / 'PUBLISH_LEDGER.jsonl'):
            assert record['actual_delay_frames'] == record['first_publish_at_arrival_frame']-record['frame']
            assert record['actual_delay_frames'] <= 30
            delay_frames.append(record['actual_delay_frames'])
            delay_seconds.append(times[record['first_publish_at_arrival_frame']]-times[record['frame']])
            wall.append(record['receive_to_first_publish_seconds'])
        for prediction in rows(public / 'predictions.jsonl.gz'):
            for arm in ARMS[2:]:
                if prediction['variants'][arm] != prediction['variants']['Z4Q_FROZEN']:
                    changed[arm].append(prediction['global_frame'])
            if prediction['variants']['RGBD_LAG'] != prediction['variants']['RGB_LAG']:
                depth_different.append(prediction['global_frame'])
            else:
                depth_same += 1
        reasons = {arm:Counter() for arm in ARMS[2:]}
        for arm in ARMS[2:]:
            for event in event_lists[arm]:
                count[arm]['requests'] += 1
                count[arm]['status/'+event['status']] += 1
                count[arm]['changed_commits'] += bool(event.get('actual_changes')) and event.get('submitted_option') != 'KEEP'
                count[arm]['changed_event_q_publications'] += bool(event.get('actual_changes'))
                count[arm]['invalid_candidates'] += event.get('invalid_candidate') is not None
                evidence = event.get('window_evidence', {})
                samples = evidence.get('samples', [])
                count[arm]['observed_window_frames'] += len(samples)
                count[arm]['actual_raw_clean_frames'] += sum(s['clean'] for s in samples)
                assessment = event.get('assessment', {})
                count[arm]['three_clean_confirmations'] += len(assessment.get('confirmation_frames', [])) == 3 and all(
                    s['clean'] for s in samples[-3:])
                count[arm]['depth_weight_used_windows'] += assessment.get('depth_common_component_weight', 0) > 0
                if assessment.get('reason'):
                    reasons[arm][assessment['reason']] += 1
                for sample in samples:
                    for comparison in sample['comparisons'].values():
                        count[arm]['edge_observations'] += 1
                        count[arm]['RGB_available_edge_observations'] += comparison['status'] != 'UNKNOWN'
                        count[arm]['depth_available_edge_observations'] += bool(comparison.get('depth_available'))
                        if comparison.get('reason'):
                            reasons[arm][comparison['reason']] += 1
            totals[arm].update(count[arm])
        def distribution(values):
            return dict(n=len(values), min=float(min(values)), median=float(np.median(values)),
                p95=float(np.quantile(values, .95)), max=float(max(values)))
        by_source[name] = dict(arm_counts={a:dict(c) for a,c in count.items()},
            reasons={a:dict(c) for a,c in reasons.items()},
            changed_publication_global_frames=changed,
            RGBD_minus_RGB_changed_global_frames=depth_different, RGBD_RGB_equal_frames=depth_same,
            publication_delay_frames=distribution(delay_frames),
            publication_data_time_delay_seconds=distribution(delay_seconds),
            receive_to_first_publish_wall_seconds=distribution(wall),
            metrics=metric['segments'][name]['metrics'], deltas=metric['segments'][name]['deltas'],
            reference_status=metric['segments'][name]['reference_status'])
    write_new(HERE / 'RESULTS.json', dict(status='COMPLETE_FROZEN_RGB_RGBD_FINITE_LAG_TRIAL',
        frames=20098, segments=by_source, totals={a:dict(c) for a,c in totals.items()},
        feeding_pooled=metric['feeding_pooled'],
        total_RGBD_minus_RGB_changed_frames=sum(len(s['RGBD_minus_RGB_changed_global_frames']) for s in by_source.values()),
        all_predictions_sealed_before_scoring=True, original_native_and_Z4Q_exact=True,
        no_missing_masks_or_scoring_ID_exclusions=True,
        claim_limits=['Exposed iterative exploratory segments', 'L3/LW weak prediction-derived reference',
            'Conditional camera-coordinate 3D support, not identity or underwater accuracy',
            'Replayed associations only from accepted-action q; no merge-period mask reconstruction',
            'Fixed-lag first publication, not zero-latency deployment'],
        new_model_http=0, cost_usd=0))
    print('DS33 postseal descriptive analysis complete', flush=True)


if __name__ == '__main__':
    main()
