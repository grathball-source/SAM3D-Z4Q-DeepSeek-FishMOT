"""Freeze the unchanged historical endpoint and new measurement-only entrance."""
from common import *

def main():
    assert not RUN.exists()
    old=HERE.parent/'ds11_depth_birth_reconnect'
    previous=read(old/'ENDPOINT_CONTRACT.json')
    write_new(HERE/'ENDPOINT_CONTRACT.json',dict(
        status='DS12_CURRENT_CONTACT_MEASUREMENT_ONLY_EXTENSION',
        previous_endpoint=artifact(old/'ENDPOINT_CONTRACT.json'),
        input_review=artifact(HERE/'INPUT_REVIEW.json'),source_inventory=artifact(HERE/'SOURCE_INVENTORY.json'),
        query=dict(trigger=previous['query']['trigger'],
            quality='ORIGINAL_CONFIDENCE_AND_AREA_GE64; CLEAN_OR_ACTUAL_CURRENT_CONTACT_CERTIFICATE',
            v2='CURRENT_ACTUAL_RETAINED_COMPONENTS_ONLY; INFERRED_RECORDED_NOT_CERTIFICATION'),
        history=previous['history'],anchors=previous['anchors'],timing=previous['timing'],risk=previous['risk'],
        runtime_required=previous['runtime_required'],
        certificate=dict(actual_source_index=True,shared_mask_and_sensor_sources_excluded=True,
            repeated_sensor_points='FIXED_ROW_MAJOR_CANONICAL_ONCE',components='ACTUAL_8_CONNECTED_CORE',
            quality=dict(min_points=16,min_fraction=.2,scale_floor_mm=15,max_scale_mm=60),
            weights='EQUAL_ALL_QUALIFIED_PIECES_SHARED_BY_ALL_CANDIDATES',
            fish_surface_identity='UNKNOWN',background_identity='UNKNOWN',
            current_neighbors_kept=True,no_current_contact_in_pre=True),
        scoring=dict(endpoint_mapping_correct='QUERY_SAME_AS_LAST_ACTUAL_JOINT_CLEAN_REFERENCE',
            certified_physical_restore='ENDPOINT_CORRECT_AND_SOURCE_INITIAL_TO_CLEAN_SAME_AND_BANK_TO_CLEAN_SAME',
            inconsistent_or_missing_reference='DIFFERENT_OR_UNKNOWN_SEPARATE; NOT_SAFE_OR_TRUE_RESTORE',
            only_after_all_predictions_sealed=True),
        no_GT_scoring_reference_reads=True,no_RGB_pixels=True,no_new_model=True,no_v3=True))
    print('DS12 historical source/anchor contract retained, current-contact entrance explicit')

if __name__=='__main__':main()
