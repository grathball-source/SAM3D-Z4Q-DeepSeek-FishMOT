"""Postseal arithmetic and source/delivery checks; no diagnostic rule changes."""
from collections import Counter
import json
import run

def main():
    run.verify_freeze();seal=run.old.read(run.HERE/'AUDIT_SEALED.json')
    for pin in seal['files']:run.old.verify_item(pin)
    frames=run.old.read(run.HERE/'FRAMES.json')['frames']
    endpoints=list(run.old.rows(run.HERE/'ENDPOINTS.jsonl.gz'))
    facts,assignments,pins=run.prior.load_sources(run.prior.load_features())
    assert len(frames)==168 and len(endpoints)==171 and {e['fact_id'] for e in endpoints}==set(facts)
    byframe={(r['segment'],r['frame']):r for r in frames};assert len(byframe)==168
    assert sum(r['projection']['status']=='EXACT_REPROJECTION_AND_SOURCE_INDEX_PASS' for r in frames)==168
    assert all(r['projection']['independently_rounded_pixel_mismatches']==0 for r in frames)
    raw={};RGB={};selected=[]
    def collect(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=value.keys():raw[value['path']]={k:value[k] for k in ('path','bytes','sha256')}
            else:
                for v in value.values():collect(v)
        elif isinstance(value,list):
            for v in value:collect(v)
    for f in frames:
        collect(f['raw_source_binding']);collect(f['calibration'])
        for p in f['RGB_binding']['all_RGB_files']:RGB[p['path']]=p;run.old.verify_item(p)
    for e in endpoints:
        frame=byframe[(e['segment'],e['frame'])];fact=facts[e['fact_id']]
        assert e['frame_record_sha256']==run.prior.digest(frame)
        assert (e['global_frame'],e['native'],e['time'])==(fact['global_frame'],fact['native'],fact['time'])
        assert e['original_mask_binding']==fact['certificate']['mask_binding']
        assert e['identity']=='UNKNOWN' and e['state_action']=='NONE'
        if e['global_frame'] in (159,905,190,1330):selected.append(e)
    def summary(subset):
        result=dict(endpoints=len(subset),DS22_statuses=dict(Counter(e['DS22_status'] for e in subset)))
        for name in ('depth','rgb'):
            vals=[e['spatial'][f'boundary_to_{name}_edge']['median_px'] for e in subset]
            good=[v for v in vals if v is not None]
            result[name+'_endpoint_median_distance_summary_px']=run.describe(good)
            vals=[e['spatial'][f'boundary_to_{name}_edge']['fractions_within_px']['3'] for e in subset]
            result[name+'_endpoint_fraction_within_3px_summary']=run.describe([v for v in vals if v is not None])
            result[name+'_UNKNOWN_endpoints']=sum(v is None for v in vals)
        result['mask_valid_depth_fraction_summary']=run.describe([e['spatial']['coverage']['mask']['valid_depth_fraction'] for e in subset])
        return result
    table=[dict(segment=name,**summary([e for e in endpoints if e['segment']==name])) for name in run.old.SEGMENTS]
    availability=[dict(DS22_status=s,**summary([e for e in endpoints if e['DS22_status']==s])) for s in ('AVAILABLE','UNKNOWN')]
    visual=run.old.read(run.HERE/'PRIVATE_VISUALS.json')
    for v in visual['figures']:
        run.old.verify_item(v['artifact']);image=run.cv2.imread(v['artifact']['path'])
        assert image.shape==(780,2340,3)
        record=next(e for e in endpoints if e['fact_id']==v['fact_id'])
        assert v['endpoint_record_sha256']==run.prior.digest(record)
    result=dict(status='COMPLETE_FIXED_CORRESPONDENCE_AUDIT',engineering='PASS',software_contract='PASS',
        unique_endpoints=171,frames=168,actions=90,original_mask_checks=2582,
        projection_frames_exact=168,RGB_original_sha_match_frames=168,
        saved_small_RGB_bit_exact_frames=sum(f['RGB_binding']['saved_small_RGB_bit_exact_to_INTER_AREA'] is True for f in frames),
        maximum_independent_projection_error_px=max(f['projection']['independent_opencv_formula_error_px']['max'] for f in frames),
        maximum_raster_component_error_px=max(f['projection']['raster_pixel_component_error_px']['max'] for f in frames),
        valid_projected_pixels=sum(f['projection']['valid_pixels'] for f in frames),
        time_delta_counts=dict(Counter(str(f['RGB_binding']['delta_us']) for f in frames)),
        per_source=table,by_DS22_support_availability=availability,selected_existing_diagnostic_frames=selected,
        private_figures_verified=len(visual['figures']),physical_registration_accuracy='UNKNOWN',
        segmentation_bias='UNKNOWN_WITH_PRIVATE_VISUAL_OBSERVATIONS',
        depth_absence_vs_sensor_background_return='NOT_IDENTIFIABLE_FROM_SOFTWARE_SELF_CONSISTENCY',
        no_unique_coordinate_repair_established=True,no_transform_search=True,
        new_tracking_metrics=None,new_predictions=False,new_scoring=False,new_model_http=0,cost_usd=0,
        audit_seal=run.old.artifact(run.HERE/'AUDIT_SEALED.json'),
        arithmetic_aggregation='DESCRIPTIVE_POSTSEAL_ONLY; MEDIAN_OF_ENDPOINT_MEDIANS_NOT_POOLED_PHYSICAL_ERROR')
    run.save('RESULTS.json',result)
    run.save('RESTRICTED_ARTIFACTS.json',dict(status='ACTUAL_PATH_BYTES_SHA_INVENTORY',private_figures=visual['figures'],
        original_raw_sources=list(raw.values()),RGB_input_files=list(RGB.values()),original_SAM3_sources=pins,
        reproduction='Fresh output directory; exact DS21/DS22 frozen facts and DS14 original N0 assignments; same raw/calibration/RGB source bytes. Run initialize, checks final, projection_checks, mask_time_checks, freeze, audit, review. Do not overwrite old seals.',
        python=str(run.sys.executable),deps=str(run.old.DEPS),GT_pixels_read=False,restored_read=False,
        RGB_use='PRIVATE_INPUT_DIAGNOSTIC_ONLY',new_model_http=0,cost_usd=0))
    run.save('POSTSEAL_REVIEW.json',dict(status='PASS',actual_frozen_files_and_measurement_seal_verified=True,
        endpoint_frame_bindings=171,projected_source_frames=168,private_figures=len(visual['figures']),
        no_transform_or_state_change=True,source_contract_checks=run.old.artifact(run.HERE/'MASK_TIME_CHECKS.json'),
        projection_metadata_checks=run.old.artifact(run.HERE/'PROJECTION_CHECKS.json'),
        actual_review_code=run.old.artifact(run.HERE/'review.py'),new_model_http=0,cost_usd=0))
    print(json.dumps({k:v for k,v in result.items() if k not in ('selected_existing_diagnostic_frames',)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
