"""Focused numerical checks plus two real fixed endpoint source slices."""
import copy, json, unittest
from pathlib import Path
import run
import test_measurement as numerical
from measurement import measure_local_background, array_binding

def main():
    suite=unittest.defaultTestLoader.loadTestsFromModule(numerical)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful()
    data=numerical.fixture(); first=numerical.measure(data)[0]
    data[0][:]+=200.; second=numerical.measure(data)[0]
    assert first['qualified_independent_n']==second['qualified_independent_n']
    assert abs(first['components'][0]['median_residual_mm']-second['components'][0]['median_residual_mm'])<1e-6
    def measured(values, status='AVAILABLE'):
        return dict(status=status,components=[dict(qualified=True,sign='NEARER',support_id=str(i),
            scale_mm=15.,median_residual_mm=v) for i,v in enumerate(values)],background=dict(residual_scale_mm=15.))
    assert run.compare_endpoints(measured([-100.,100.]),measured([-100.]))['status']=='DEPTH_EXPLANATION_COMPATIBLE_PROXY'
    assert run.compare_endpoints(measured([100.]),measured([-100.]))['status']=='DEPTH_EXPLANATION_CONFLICT_PROXY'
    assert run.compare_endpoints(measured([], 'UNKNOWN'),measured([100.]))['status']=='UNKNOWN'
    broad=measured([100.]);broad['components'][0]['scale_mm']=60.
    assert run.compare_endpoints(broad,measured([-100.]))['all_qualified_layer_pairs'][0]['threshold_mm']==90.
    features=run.load_features(); facts,assignments,pins=run.load_sources(features)
    selected=[next(f for f in features if f['global_frame']==g and f['segment'].startswith('feeding_')) for g in (159,905)]
    slices=[]
    for feature in selected:
        sensor=run.RawDepth(feature['segment'])
        try:
            for fid in sorted(run.endpoint_requests(feature),key=lambda i:facts[i]['frame']):
                fact=facts[fid]; arrays=run.load_endpoint_frame(fact['segment'],fact['frame'],facts,assignments,sensor)
                value,_=measure_local_background(arrays['depth'],arrays['source_index'],arrays['native_depth'],
                    arrays['masks'],fact['native'],fact['segment'],fact['frame'],fact['global_frame'],fact['time'],
                    source_binding=arrays['source_binding'],expected_source_binding=fact['_raw_measurement']['raw_source_binding'])
                assert value['mask_binding']==fact['certificate']['mask_binding']
                slices.append(dict(fact_id=fid,global_frame=fact['global_frame'],status=value['status'],reason=value['reason'],
                    original_whole_n=fact['certificate']['whole']['summary']['n'],
                    fixed_core_n=fact['certificate']['birth_core']['summary']['n'],
                    new_mask_n=value['mask_summary']['n'],new_qualified_n=value['qualified_independent_n'],
                    actual_source_binding=value['source_binding']))
        finally:sensor.close()
    from visualize import selfcheck
    visual_checks=selfcheck()
    run.save('CHECKS.json',dict(status='PASS',numerical_tests=result.testsRun,additional_comparison_checks=5,visual_checks=visual_checks,
        real_fixed_slices=slices,code=[run.old.artifact(run.HERE/n) for n in ('measurement.py','test_measurement.py','run.py','checks.py','visualize.py')],
        actual_source_pins=pins,physical_labels_read=False,new_prediction=False,new_scoring=False,new_model_http=0,cost_usd=0))
    print('DS22 focused checks + exact F159/F905 source slices PASS',len(slices))

if __name__=='__main__':main()
