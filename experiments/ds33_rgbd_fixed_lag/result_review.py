"""Independent arithmetic/provenance review of completed scores; never rescore."""
from common import *
from collections import Counter

FIELDS = ('IDF1', 'HOTA', 'AssA', 'DetA', 'IDSW', 'FP', 'FN')
ARCHIVED = ROOT / 'experiments/ds32_z4q_depth_conflict_veto/run'


def relation(query, reference):
    if query.get('status') != 'UNIQUE_IOU_MATCH' or reference.get('status') != 'UNIQUE_IOU_MATCH':
        return 'UNSCORABLE'
    return 'CORRECT' if query['gt_id'] == reference['gt_id'] else 'WRONG'


def main():
    metric = read(RUN / 'METRICS.json')
    provenance = read(RUN / 'SCORE_PROVENANCE.json')
    assert metric['status'] == 'SCORED_AFTER_ALL_EIGHT_FORMAL_PREDICTION_AND_ACCESS_SEALS'
    assert metric['frames'] == 20098 and tuple(metric['arms']) == ARMS
    assert provenance['reference_opened_after_all_seals'] and not provenance['GT_used_for_prediction']
    assert provenance['official_metric_math_unchanged'] and provenance['original_controls_exact']
    assert provenance['ignored_public_ids'] == 0 and metric['all_seal'] == artifact(RUN / 'ALL_PREDICTIONS_SEALED.json')
    for key in ('scorer', 'scoring_freeze', 'prediction_parity'):
        verify_item(provenance[key])
    parity = read(provenance['prediction_parity']['path'])
    assert parity['status'] == 'PASS' and not parity['GT_opened']
    seals = read(RUN / 'ALL_PREDICTIONS_SEALED.json')
    assert seals['status'] == 'ALL_PREDICTIONS_AND_ACCESS_SEALED'
    source_reviews, pins, discrepancies = {}, [], []
    totals = {arm:Counter() for arm in ARMS[2:]}
    physical = {arm:Counter() for arm in ARMS[1:]}
    public_origin = {arm:Counter() for arm in ARMS[1:]}
    switch_totals = {base:Counter() for base in ('SAM3_NATIVE', 'Z4Q_FROZEN', 'RGB_LAG')}
    action_examples = []
    for name, (start, stop) in SEGMENTS.items():
        p = RUN / name / 'public'
        assert read(seals['ends'][name]['path'])['exit_code'] == 0
        values = metric['segments'][name]['metrics']
        assert read(p / 'METRICS.json') == metric['segments'][name]
        prior = read(ARCHIVED / name / 'public/METRICS.json')['metrics']
        assert all(values[arm] == prior[arm] for arm in ARMS[:2])
        assert values['RGB_LAG'] == values['RGBD_LAG'] == values['Z4Q_FROZEN']
        native_delta = {key:values['RGBD_LAG'][key] - values['SAM3_NATIVE'][key] for key in FIELDS}
        assert native_delta == metric['segments'][name]['deltas']['SAM3_NATIVE']['RGBD_LAG']
        switches = read(p / 'SWITCHES.json')
        changes = read(p / 'SWITCH_CHANGES.json')
        for arm in ARMS:
            assert len(switches[arm]) == values[arm]['IDSW']
        assert switches['RGB_LAG'] == switches['RGBD_LAG'] == switches['Z4Q_FROZEN']
        source_switches = {}
        for base in ('SAM3_NATIVE', 'Z4Q_FROZEN', 'RGB_LAG'):
            changed = changes[base + '_TO_RGBD_LAG']
            old = {json.dumps(s, sort_keys=True, separators=(',', ':')) for s in switches[base]}
            new = {json.dumps(s, sort_keys=True, separators=(',', ':')) for s in switches['RGBD_LAG']}
            assert {json.dumps(s, sort_keys=True, separators=(',', ':')) for s in changed['added']} == new - old
            assert {json.dumps(s, sort_keys=True, separators=(',', ':')) for s in changed['eliminated']} == old - new
            occurrences = lambda ss:{(s['segment'], s['frame'], s['gt_id']) for s in ss}
            old_occ, new_occ = occurrences(switches[base]), occurrences(switches['RGBD_LAG'])
            assert occurrences(changed['occurrence_added']) == new_occ - old_occ
            assert occurrences(changed['occurrence_eliminated']) == old_occ - new_occ
            assert changed['net_IDSW'] == len(new) - len(old) == values['RGBD_LAG']['IDSW'] - values[base]['IDSW']
            counts = dict(exact_record_added=len(new-old), exact_record_eliminated=len(old-new),
                occurrence_added=len(new_occ-old_occ), occurrence_eliminated=len(old_occ-new_occ), net_IDSW=changed['net_IDSW'])
            source_switches[base] = counts; switch_totals[base].update(counts)
        audit = read(p / 'EVENT_AUDIT.json')
        assert audit == metric['event_audits'][name]
        by_arm = {arm:[] for arm in ARMS[1:]}
        for action in audit['automatic_actions']:
            arm = action['arm']; q = action['frame']
            assert action['actual_pre_reference']['frame'] < q
            assert action['physical_preanchor'] == relation(action['query_match'], action['preanchor_match'])
            assert action['public_reference_correctness'] == relation(action['query_match'], action['public_origin_match'])
            if action['public_origin_reference'] is not None:
                assert action['public_origin_reference']['frame'] < q
            physical[arm][action['physical_preanchor']] += 1
            public_origin[arm][action['public_reference_correctness']] += 1
            signature = {k:action[k] for k in ('frame', 'global_frame', 'phase', 'source', 'target', 'actual_pre_reference',
                'physical_preanchor', 'query_match', 'preanchor_match', 'public_origin_reference', 'public_origin_match',
                'public_reference_correctness', 'incidental_public_reference_return')}
            by_arm[arm].append(signature)
            if arm == 'Z4Q_FROZEN' and action['physical_preanchor'] != action['public_reference_correctness']:
                discrepancies.append(dict(segment=name, **signature))
            if arm == 'Z4Q_FROZEN' and name.startswith('feeding_') and action['physical_preanchor'] == 'WRONG':
                action_examples.append(dict(segment=name, global_frame=action['global_frame'], phase=action['phase'],
                    source=action['source'], target=action['target'], physical_preanchor='WRONG',
                    public_reference_correctness=action['public_reference_correctness'], inherited_by_both_new_arms=True))
        assert by_arm['RGB_LAG'] == by_arm['RGBD_LAG'] == by_arm['Z4Q_FROZEN']
        summary = read(p / 'RUN_SUMMARY.json')
        event_lists = read(p / 'EVENTS.json')
        for arm in ARMS[2:]:
            events = event_lists[arm]
            independent = [e for e in events if 'assessment' in e]
            counts = summary['counts'][arm]
            assert len(events) == counts['requests'] and len(independent) == counts['windows_resolved']
            assert counts['changed_commits'] == 0 and all(not e['actual_changes'] and e['submitted_option'] == 'KEEP' for e in events)
            assert all(not e['selection_changes_real_publication'] and not e['submitted_alternative'] for e in audit['event_arms'][arm])
            assert not audit['altered_event_counts'][arm]
            totals[arm].update(counts)
            totals[arm]['depth_weight_used_windows'] += sum(e['assessment'].get('depth_common_component_weight', 0)>0 for e in independent)
        source_reviews[name] = dict(frames=stop-start+1, metrics=values,
            RGBD_minus_RGB={key:0 for key in FIELDS}, RGBD_minus_Z4Q={key:0 for key in FIELDS},
            RGBD_minus_NATIVE_inherited_Z4Q_only=native_delta, switch_counts=source_switches,
            reference_status=metric['segments'][name]['reference_status'], original_controls_exact=True,
            retained_automatic_actions=len(by_arm['Z4Q_FROZEN']), no_new_changed_mapping=True)
        pins.extend(artifact(p / file) for file in ('METRICS.json', 'EVENT_AUDIT.json', 'SWITCHES.json', 'SWITCH_CHANGES.json', 'RUN_SUMMARY.json', 'EVENTS.json'))
    pool = metric['feeding_pooled']
    old_pool = read(ARCHIVED / 'METRICS.json')['feeding_pooled']['metrics']
    assert all(pool['metrics'][arm] == old_pool[arm] for arm in ARMS[:2])
    assert pool['metrics']['Z4Q_FROZEN'] == pool['metrics']['RGB_LAG'] == pool['metrics']['RGBD_LAG']
    assert all(value == 0 for comparison in pool['deltas']['Z4Q_FROZEN'].values() for value in comparison.values())
    assert sum(v['frames'] for v in source_reviews.values()) == 20098
    assert physical['Z4Q_FROZEN'] == physical['RGB_LAG'] == physical['RGBD_LAG']
    assert public_origin['Z4Q_FROZEN'] == public_origin['RGB_LAG'] == public_origin['RGBD_LAG']
    write_new(HERE / 'DATA_RESULT_REVIEW.json', dict(status='PASS_INDEPENDENT_COMPLETED_RESULTS_ARITHMETIC_AND_ATTRIBUTION_REVIEW',
        reviewer=artifact(__file__), score=artifact(RUN / 'METRICS.json'), provenance=artifact(RUN / 'SCORE_PROVENANCE.json'),
        result_inputs=pins, segments=source_reviews, feeding_pooled=pool,
        request_totals={a:dict(v) for a,v in totals.items()}, physical_preanchor_actual_actions={a:dict(v) for a,v in physical.items()},
        public_origin_actual_actions={a:dict(v) for a,v in public_origin.items()}, physical_vs_public_origin_discrepancies=discrepancies,
        retained_inherited_Feeding_wrong_actions=action_examples, switch_totals_to_RGBD={a:dict(v) for a,v in switch_totals.items()},
        new_successful_changes=0, new_incorrect_changes=0, new_changed_mapping_precision='UNDEFINED_ZERO_CHANGES',
        claims=dict(engineering_and_score_contract='PASS', input_physical_accuracy='UNKNOWN_CONDITIONAL_UNDERWATER_RGBD_CORRESPONDENCE',
            frozen_method_increment='NO_INCREMENT', depth_increment='ZERO_RGBD_MINUS_RGB',
            Native_comparison_benefits_and_harms='Entirely inherited original Z4Q; never credit to DS33.',
            inherited_WRONG_not_new_failure_or_safety_pass=True, UNSCORABLE_not_success=True,
            physical_correctness_not_public_integer_or_public_origin_equivalence=True,
            complete_RGBD_scene_flow_or_merge_mask_reconstruction_not_tested=True,
            no_claim_of_cross_dataset_blind_generalization=True),
        no_rescoring=True, no_GT_raster_or_annotations_read_by_this_review=True, frozen_source_unchanged=True,
        new_model_http=0, cost_usd=0))
    print('PASS independent completed-result review:', 20098, 'frames; 0 new changes', flush=True)


if __name__ == '__main__':
    main()
