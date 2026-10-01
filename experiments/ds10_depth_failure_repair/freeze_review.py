"""Record actual effective code and source contracts before any trial replay."""
from common import *
import inspect

def main():
    assert not RUN.exists() and not (HERE/'slice').exists()
    import association,forecast,depth_state,depth_measurement,runner
    assert association.CFG==read(HERE/'CONFIG.json')
    checks=read(HERE/'FORECAST_CHECKS.json');assert checks['status']=='PASS'
    for n in ('CONTROLLER_CHECKS.json','MEASUREMENT_CHECKS.json','ASSOCIATION_CHECKS.json','SCORE_CHECKS.json'):
        assert read(HERE/n)['status']=='PASS',n
    log=HERE/'logs/adaptive_tests.txt';assert 'Ran 10 tests' in log.read_text() and 'OK' in log.read_text()
    write_new(HERE/'ADAPTIVE_CHECKS.json',dict(status='PASS',checks=10,actual_log=artifact(log),
        code=artifact(HERE/'adaptive_tests.py'),scope='synthetic ROI and no-future geometry invariants only'))
    write_new(HERE/'REAL_INPUT_CHECKS.json',dict(status='PASS_SOURCE_REUSE',
        sources={name:artifact(input_dir(name)/'SOURCE_MANIFEST.json') for name in SEGMENTS},
        scope='DS9 SOURCE_OLD original masks/raw/depth/scan; full bytes rechecked by runner before prediction',new_model_http=0))
    write_new(HERE/'EFFECTIVE_PARAMETERS.json',dict(actual_config=association.CFG,
        forecast_source=inspect.getsource(forecast.predict),old_forecast_source=inspect.getsource(depth_state.predict),
        measurement_qualification_source=inspect.getsource(depth_measurement.usable),
        current_background_source=inspect.getsource(association._depth_background),
        individual_cache_frames=30,depth_window_max=10,short_history_old_exact_max=2,
        controller_same_as_DS9=sha(HERE/'controller.py')==sha(HERE.parent/'ds9_joint_h0_depth/controller.py'),
        actual_code=[artifact(p) for p in (HERE/'association.py',HERE/'forecast.py',HERE/'controller.py',DS1/'depth_state.py',DS1/'depth_measurement.py')],
        old_config_paid_or_025_weight_inactive=True,new_model_http=0,cost_usd=0))
    print('Effective parameters and measured source reuse frozen before replay')
if __name__=='__main__':main()
