"""Postseal descriptive gate decomposition, never threshold selection."""
from common import *
from collections import Counter
import numpy as np

def distribution(values):
    a=np.asarray([v for v in values if v is not None],float)
    return dict(n=len(a),minimum=float(a.min()) if len(a) else None,
        q10=float(np.quantile(a,.1)) if len(a) else None,median=float(np.median(a)) if len(a) else None,
        q90=float(np.quantile(a,.9)) if len(a) else None,maximum=float(a.max()) if len(a) else None)

assert read(HERE/'POSTSEAL_REVIEW.json')['status']=='PASS'
facts=list(rows(RUN/'ENDPOINT_FACTS.jsonl.gz'));pairs=list(rows(RUN/'PAIRINGS.jsonl.gz'))
analysis={}
for name in SEGMENTS:
    group=[f for f in facts if f['segment']==name]
    measured=[l for f in group for l in f['layers'] if l['kind']=='MEASURED_DEPTH_SUPPORT']
    substantial=[l for l in measured if l['substantial']]
    partitions=Counter()
    for f in group:
        parent=f.get('inclusive_independent_support_agreement') is True and f.get('inclusive_independent_partition_agreement') is True
        if f['reason']=='BACKGROUND_RESIDUAL_TOO_BROAD':partitions['BACKGROUND_MODEL_SCALE_FAILED']+=1
        elif f['reason']=='SUBSTANTIAL_NOISY_OR_UNRESOLVED_SUPPORT':partitions['SUBSTANTIAL_UNRESOLVED_SUPPORT']+=1
        elif not parent:partitions['PARENT_OR_POPULATION_GATE_FAILED']+=1
        elif len(f['qualified_support_ids'])==1:partitions['SOLE_QUALIFIED_PROXY']+=1
        elif not f['qualified_support_ids']:partitions['NO_QUALIFIED_SUPPORT_WITH_PARENT_GATES_PASSED']+=1
        else:partitions['MULTIPLE_QUALIFIED_SUPPORTS']+=1
    analysis[name]=dict(unique_actual_mask_facts=len(group),reason_counts=dict(Counter(f['reason'] for f in group)),
        mutually_exclusive_diagnostic=partitions,measured_components=len(measured),substantial_components=len(substantial),
        substantial_background_compatibility=dict(Counter(l['background_compatibility'] for l in substantial)),
        layer_qualified_flags=sum(l['qualified'] for l in measured),declared_qualified=sum(len(f['qualified_support_ids']) for f in group),
        annulus_residual_scale_mm=distribution(f['plane']['residual_scale_mm'] for f in group if f['plane']),
        annulus_contrast_threshold_mm=distribution(f['plane']['contrast_threshold_mm'] for f in group if f['plane']),
        substantial_abs_residual_mm=distribution(abs(l['median_residual_mm']) if l['median_residual_mm'] is not None else None for l in substantial),
        substantial_combined_sigma_mm=distribution(l['sigma_mm'] for l in substantial),
        independent_roi_fraction=distribution(f['summary']['valid_fraction'] for f in group),
        inclusive_valid_fraction=distribution(f['inclusive_summary']['valid_fraction'] for f in group),
        roi_area=distribution(f['original_roi_area'] for f in group),
        post_pair_proxy=sum(p['cross_role']['pair_proxy_eligible'] for p in pairs if p['segment']==name and p['phase'].startswith('POST')))
observed=[]
for p in pairs:
    if p['cross_role']['pair_proxy_eligible']:
        observed.append(dict(task_id=p['task_id'],context_id=p['context_id'],segment=p['segment'],
            frame=p['frame'],global_frame=p['global_frame'],phase=p['phase'],native_roles=p['native_roles'],
            role_provenance=p['role_provenance'],measured_depth_difference_mm=p['cross_role']['measured_depth_difference_mm'],
            propagated_sigma_mm=p['cross_role']['propagated_sigma_mm'],standardized_difference=p['cross_role']['standardized_difference'],
            measured_order=p['cross_role']['measured_order'],identity='UNKNOWN',selected_after_seal_for_reporting_only=True))
write_new(HERE/'GATE_DIAGNOSIS.json',dict(status='POSTSEAL_DESCRIPTIVE_DECOMPOSITION; NO_TUNING',
    actual_measurement_parameters=PARAMETERS,segments=analysis,all_sole_pair_measurements=observed,
    unit='UNIQUE_ACTUAL_FRAME_MASK_FACT; PAIR REFERENCES REPORTED SEPARATELY',
    no_threshold_change=True,no_GT_read=True,new_model_http=0,cost_usd=0,
    provenance=dict(code=artifact(Path(__file__)),facts=artifact(RUN/'ENDPOINT_FACTS.jsonl.gz'),seal=artifact(RUN/'MEASUREMENTS_SEALED.json'))))
print(json.dumps(analysis,ensure_ascii=False))
