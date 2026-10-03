"""Postseal descriptive reading of existing depth facts; no new feature or action."""
from collections import Counter
from datetime import datetime, timezone
import statistics
import audit


def main():
    old=audit.old;here=audit.HERE
    assert not (here/'POSTSEAL_INTERPRETATION.json').exists()
    audit.verify_freeze()
    summary=old.read(here/'AUDIT_SUMMARY.json')
    old.verify_item(summary['action_artifact']);old.verify_item(summary['feature_seal'])
    actions=old.read(summary['action_artifact']['path'])['actions']
    seal=old.read(summary['feature_seal']['path'])
    for item in seal['artifacts']:old.verify_item(item)
    facts={v['fact_id']:v for v,_ in audit.sourced_rows(here/'OBSERVATION_FACTS.jsonl.gz')}
    endpoints=[];table=Counter();fixed_rejections=[];remaining_wrong=[];birth_anchors=[]
    def endpoint(action,part,side,purpose):
        feature=action['roi_features'][part];binding=feature[side+'_binding']
        assert binding is not None,'No invented alternative or missing historical binding'
        fid=audit.fact_id(action['segment'],binding['frame'],binding['native'])
        fact=facts[fid];certificate=fact['certificate'];roi=certificate[part]
        assert fact['frame']<=action['frame']
        assert audit.validate_bound_measurement(binding,binding['actual_scalar'],feature['role'],certificate,
            native=fact['native'],frame=fact['frame'])
        if side=='anchor':assert fact['frame']<action['frame']
        qualified=[layer for layer in roi['layers'] if layer['qualified']]
        categories=sorted({layer['background_compatibility'] for layer in qualified})
        category='NO_QUALIFIED_INDEPENDENT_LAYER' if not categories else '+'.join(categories)
        annulus=certificate['annulus']
        result=dict(action_id=action['action_id'],segment=action['segment'],frame=action['frame'],
            global_frame=action['global_frame'],origin_rule=action['origin_rule'],physical=action['physical'],
            actual_reference_physical=action['actual_reference_physical'],purpose=purpose,roi=part,side=side,
            endpoint_fact_id=fid,endpoint_frame=fact['frame'],native=fact['native'],
            binding_sha256=binding['binding_sha256'],certificate_sha256=certificate['certificate_sha256'],
            eligible_single=roi['eligible_single'],screened_eligible=binding['screened_eligible'],
            status=roi['status'],reason=roi['reason'],qualified_independent_layers=qualified,
            all_independent_layer_categories=[layer['background_compatibility'] for layer in roi['layers']],
            qualified_layer_background_category=category,annulus_quality_usable=annulus['quality_usable'],
            annulus_summary=annulus['summary'],inclusive_summary=roi['inclusive_summary'],
            independent_summary=roi['summary'],physical_background='UNKNOWN; ANNULUS IS A PROXY',
            physical_surface_identity='UNKNOWN')
        endpoints.append(result)
        table[(purpose,action['origin_rule'],part,side,roi['eligible_single'],
            annulus['quality_usable'],category,action['physical'])]+=1
        return result
    def small_core_detail(action,side):
        feature=action['roi_features']['birth_core'];binding=feature[side+'_binding']
        fid=audit.fact_id(action['segment'],binding['frame'],binding['native'])
        fact=facts[fid];roi=fact['certificate']['birth_core']
        pixel,independent=roi['inclusive_summary'],roi['summary']
        return dict(fact_id=fid,frame=fact['frame'],native=fact['native'],
            mask_area=fact['actual_profile']['area'],whole_valid_n=fact['actual_profile']['whole']['n'],
            core_geometric_area=pixel['area'],inclusive_valid_n=pixel['n'],valid_fraction=pixel['valid_fraction'],
            independent_source_n=independent['n'],independent_valid_fraction=independent['valid_fraction'],
            within_mask_duplicate_pixels_excluded=roi['within_mask_duplicate_pixels_excluded'],
            shared_source_pixels_excluded=roi['shared_source_pixels_excluded'],
            unverified_source_pixel_n=roi['source_population_unverified_n'],
            eligible=feature[side+'_eligible'],status=roi['status'],reason=roi['reason'],
            geometric_capacity_below_original_minimum_n=pixel['area']<audit.PARAMETERS['minimum_layer_n'],
            zero_valid_depth_in_nonempty_core=bool(pixel['area'] and not pixel['n']),
            missing_depth_reduces_available_pixels=pixel['n']<pixel['area'],
            source_exclusion_reduces_population=independent['n']<pixel['n'],
            interpretation='CAPACITY_OR_COVERAGE; NOT CERTIFIED_IDENTITY_EVIDENCE')
    for action in actions:
        part=action['original_scoring_roi']
        for side in ('current','anchor'):endpoint(action,part,side,'ORIGINAL_PRIMARY_SCORING_ROI')
        if action['origin_rule']=='BIRTH_REFINE':
            for side in ('current','anchor'):endpoint(action,'whole',side,'ORIGINAL_BIRTH_SECONDARY_WHOLE')
            birth_anchors.append(dict(action_id=action['action_id'],global_frame=action['global_frame'],
                literal_old_anchor=action['actual_old_anchor'],actual_core_anchor=action['original_action']['depth_anchors']['core']['anchor'],
                actual_whole_anchor=action['original_action']['depth_anchors']['whole']['anchor'],
                bound_core_frame=action['roi_features']['birth_core']['anchor_binding']['frame'],
                bound_whole_frame=action['roi_features']['whole']['anchor_binding']['frame'],
                correct_separate_ROI_bindings=True))
            assert birth_anchors[-1]['bound_whole_frame']==birth_anchors[-1]['actual_whole_anchor']['frame']
            assert birth_anchors[-1]['bound_core_frame']==birth_anchors[-1]['actual_core_anchor']['frame']
        core=action['roi_features']['birth_core']
        if not core['both_eligible'] and action['physical'] in ('WRONG','CORRECT'):
            fixed_rejections.append(dict(action_id=action['action_id'],segment=action['segment'],
                frame=action['frame'],global_frame=action['global_frame'],source=action['source'],target=action['target'],
                origin_rule=action['origin_rule'],physical=action['physical'],quality_status=core['quality_status'],
                current=small_core_detail(action,'current'),anchor=small_core_detail(action,'anchor')))
        if core['both_eligible'] and action['physical']=='WRONG':
            remaining_wrong.append(dict(action_id=action['action_id'],global_frame=action['global_frame'],
                origin_rule=action['origin_rule'],fixed_core_inclusive_residual_mm=core['absolute_inclusive_median_difference_mm'],
                current=facts[action['current_fact_id']]['certificate']['birth_core'],
                anchor=facts[audit.fact_id(action['segment'],core['anchor_binding']['frame'],core['anchor_binding']['native'])]['certificate']['birth_core']))
    descriptive_residuals={}
    for record in fixed_rejections:
        assert record['current']['geometric_capacity_below_original_minimum_n'] or record['anchor']['geometric_capacity_below_original_minimum_n']
        assert not record['current']['source_exclusion_reduces_population'] and not record['anchor']['source_exclusion_reduces_population']
    for grade in ('CORRECT','WRONG'):
        values=[a['roi_features']['birth_core']['absolute_inclusive_median_difference_mm'] for a in actions
            if a['physical']==grade and a['roi_features']['birth_core']['both_eligible']]
        descriptive_residuals[grade]=dict(actions=len(values),minimum_mm=min(values),median_mm=statistics.median(values),maximum_mm=max(values))
    old.write_new(here/'POSTSEAL_INTERPRETATION.json',dict(
        status='POSTSEAL_EXISTING_FACTS_DESCRIPTIVE_INTERPRETATION_COMPLETE',timestamp_utc=datetime.now(timezone.utc).isoformat(),
        source_action_artifact=summary['action_artifact'],feature_seal=summary['feature_seal'],
        source_fact_artifact=old.artifact(here/'OBSERVATION_FACTS.jsonl.gz'),interpretation_code=old.artifact(__file__),
        original_parameters=audit.PARAMETERS,accepted_actions=len(actions),
        primary_endpoints=sum(x['purpose']=='ORIGINAL_PRIMARY_SCORING_ROI' for x in endpoints),
        endpoints=endpoints,background_compatibility_crosstab=[dict(purpose=k[0],origin_rule=k[1],roi=k[2],side=k[3],
            eligible_single=k[4],annulus_quality_usable=k[5],qualified_layer_background_category=k[6],physical=k[7],actions=v)
            for k,v in sorted(table.items())],
        fixed_core_screen_excluded_scorable=fixed_rejections,
        excluded_scorable_counts=dict(Counter(x['physical'] for x in fixed_rejections)),
        remaining_wrong_fixed_core_both_eligible=remaining_wrong,separate_birth_anchor_bindings=birth_anchors,
        fixed_core_both_eligible_descriptive_residuals=descriptive_residuals,
        conclusions=['All eight scorable fixed-core screen exclusions have at least one core geometric capacity below16 pixels.',
            'The exclusions do not establish new depth identity discrimination; one known correct D1 action is also screened out.',
            'All four Birth actions already use fixed-core depth and pass both-endpoint fixed-core quality, including both wrong Birth actions.',
            'Existing annulus compatibility is a proxy statistic, not certified background or fish-surface truth.',
            'Rejected D1 edges lack exact archived anchors; alternate future assignment and full-run score effects remain UNKNOWN.'],
        no_new_feature_no_threshold_fit=True,no_new_prediction_no_metric_recalculation=True,
        GT_raster_read=False,new_model_http=0,cost_usd=0))
    print('POSTSEAL_INTERPRETATION',len(actions),len(endpoints),dict(Counter(x['physical'] for x in fixed_rejections)),flush=True)


if __name__=='__main__':main()
