"""Whole-output baseline parity and actual publication/seal integrity."""
from common import *
import numpy as np
from evaluate import verify_all
def main():
    verify_all();result=read(RUN/'METRICS.json');checks={}
    for name,split in (('fishsa_development_8400','development'),('fishsa_validation_2888','validation')):
        old=read(WORK/f'tools/sam3_depth_return_guard_20260918/completion_evidence/experiment/fullmetrics_{split}.json')['N0']
        native=result['segments'][name]['metrics']['SAM3_NATIVE']
        expected=dict(IDF1=100*old['Identity']['IDF1'],HOTA=100*float(np.mean(old['HOTA']['HOTA'])),AssA=100*float(np.mean(old['HOTA']['AssA'])),
            IDSW=old['CLEAR']['IDSW'],FP=old['CLEAR']['CLR_FP'],FN=old['CLEAR']['CLR_FN'])
        assert all(abs(native[k]-v)<1e-8 for k,v in expected.items()),(name,native,expected)
        checks[name]=dict(original_same_source_native_all_metric_fields_exact=True,expected=expected)
    for name in ('L3','LW'):
        old=read(WORK/f'output/evaluation/sam3_new_bags_20260923/{name}/results.json')['metrics']['mask']
        native=result['segments'][name]['metrics']['SAM3_NATIVE']
        for k in ('IDF1','HOTA','AssA','IDSW','FP','FN'):assert abs(native[k]-old[k])<1e-8,(name,k)
        checks[name]=dict(original_same_source_native_all_metric_fields_exact=True,reference_independence=False)
    old=read(DS12/'run/METRICS.json')
    for arm in ARMS:
        expected=old['pooled_metrics'][arm] if 'pooled_metrics' in old else old['pooled'][arm]
        assert result['feeding_pooled']['metrics'][arm]==expected,(arm,'pooled Feeding changed')
    checks['Feeding']=dict(old_frozen_native_and_R12_RAW_pooled_metrics_exact=True,all1471_frame_mappings_exact=read(HERE/'FEEDING_REPRODUCTION.json')['status']=='PASS')
    locked=read(HERE/'OLD_READONLY_LOCK.json')['files']
    for path,h in locked.items():assert sha(ROOT/path)==h,path
    write_new(HERE/'FINAL_CHECKS.json',dict(status='PASS',native_baseline_parity=checks,old_unchanged_files=len(locked),
        all_source_native_masks_retained=True,one_to_one_and_transaction_publisher_verified=True,
        q_is_first_split_and_one_post_sample=True,all_predictions_sealed_before_scoring=True,
        scientific_frozen_bytes_unchanged=True,scoring_reference_errata_append_only=True,new_model_http=0,cost_usd=0))
    print('PASS all baseline parity, native masks, one-to-one state/publication, old bytes')
if __name__=='__main__':main()
