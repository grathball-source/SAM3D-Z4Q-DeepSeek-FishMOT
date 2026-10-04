"""Focused numeric checks and the two fixed real source-to-metric slices."""
import run
from source import RawDepth
from spatial import spatial_metrics
import test_spatial
import unittest
import sys

def main():
    suite=unittest.defaultTestLoader.loadTestsFromModule(test_spatial)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful() and result.testsRun==5
    features=run.prior.load_features();facts,assignments,pins=run.prior.load_sources(features)
    slices=[]
    for segment,g,n in (('feeding_000000_000199',159,28),('feeding_000701_001060',905,123)):
        candidates=[f for f in facts.values() if f['segment']==segment and f['global_frame']==g]
        # F159 native is bound by the original action, never selected via GT.
        if g==159:
            original=next(f for f in features if f['segment']==segment and f['global_frame']==g)
            chosen=facts[original['current_fact_id']]
        else:chosen=next(f for f in candidates if f['native']==n)
        sensor=RawDepth(segment)
        try:
            arrays=run.prior.load_endpoint_frame(segment,chosen['frame'],facts,assignments,sensor)
            geom,pin=run.calibration(segment);projection=run.check_projection(arrays,geom)
            rgb,binding=run.rgb_frame(sensor,arrays)
            measurement,_=spatial_metrics(arrays['masks'][chosen['native']],arrays['depth'],rgb)
            slices.append(dict(fact_id=chosen['fact_id'],projection=projection,RGB_binding=binding,
                calibration=pin,spatial=measurement,no_GT=True,no_state=True))
        finally:sensor.close()
    name='CHECKS_FINAL.json' if len(sys.argv)>1 and sys.argv[1]=='final' else 'CHECKS.json'
    run.save(name,dict(status='PASS',numerical_tests=5,real_slices=slices,actual_source_pins=pins,
        code=[run.old.artifact(run.HERE/n) for n in ('run.py','checks.py','spatial.py','test_spatial.py')],new_model_http=0,cost_usd=0))
    print('PASS5 numerical checks and F159/F905 actual source→projection→RGB→metric slices',flush=True)

if __name__=='__main__':main()
