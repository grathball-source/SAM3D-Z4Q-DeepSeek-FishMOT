"""Frozen DS27 measurement equality in synthetic and an actual sealed endpoint."""
from common import *
from measurement import Measurement, _original
import copy
import numpy as np

def maps_equal(a,b):
    assert a.keys()==b.keys()
    for k in a:
        if isinstance(a[k],dict):maps_equal(a[k],b[k])
        else:assert np.array_equal(a[k],b[k],equal_nan=True),k

def run_checks():
    before=[copy.deepcopy(m.PARAMETERS) for m in (_original,_original._background,_original._layers)]
    producers={a:Measurement(p) for a,p in VARIANTS.items()}
    old=Measurement(dict(contrast=(10.,2.),scale_floor_mm=5.))
    assert len({id(m.measure_region.__globals__) for m in producers.values()})==2
    fixture=module('ds28_frozen_measurement_fixture',ROOT/'experiments/ds25_contact_local_layers/source_checks.py')
    for offsets in ((-400.,-200.),(-20.,-200.),(-200.,0.)):
        arrays=fixture._fixture(offsets);binding=fixture._binding(_original,arrays)
        expected,maps=old.measure_region(*arrays,'synthetic',1,0,0.,source_binding=binding,expected_source_binding=binding)
        for arm,p in producers.items():
            f,m=p.measure_region(*arrays,'synthetic',1,0,0.,source_binding=binding,expected_source_binding=binding)
            assert f==expected and f['parameters']['scale_floor_mm']==5.
            maps_equal(m,maps)
    name='feeding_001201_001906'
    f=next(r['measurement'] for r in rows(DS27/'run'/name/'public/MEASUREMENTS.jsonl.gz') if r['arm']=='SOFT_C1_S5')
    frame=f['frame'];assignment=next(r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame']==frame)
    saved=next(r for r in rows(input_dir(name)/'DEPTH_OBSERVATIONS.jsonl.gz') if r['frame']==frame)
    source=module('ds28_measurement_check_raw',ROOT/'experiments/ds16_relative_depth_order/source.py')
    sensor=source.RawDepth(name)
    try:
        depth,index,native,binding=sensor(saved['global_frame'],saved['time']);masks=source.native_masks(assignment)
        # Use the exact original-mask binding, not a public integer or GT label.
        from mixed_depth import array_binding
        mask_id=next(n for n,m in masks.items() if array_binding(m)==f['roi_binding'])
        args=(depth,index,native,masks,masks[mask_id],name,frame,saved['global_frame'],saved['time'])
        expected,maps=old.measure_region(*args,source_binding=binding,expected_source_binding=saved['raw_source_binding'])
        assert expected==f,'Actual archived endpoint changed'
        for arm,p in producers.items():
            actual,newmaps=p.measure_region(*args,source_binding=binding,expected_source_binding=saved['raw_source_binding'])
            assert actual==f;maps_equal(newmaps,maps)
    finally:sensor.close()
    assert [m.PARAMETERS for m in (_original,_original._background,_original._layers)]==before
    return dict(status='PASS',synthetic_policies_exact=True,actual_DS27_endpoint_exact=True,
        exact_fact_sha256=digest(f),segment=name,frame=frame,source_native=mask_id,
        clone_globals_independent=True,old_global_parameters_unchanged=True,
        no_RGB_GT_restored_model_read=True,new_model_http=0,cost_usd=0)
