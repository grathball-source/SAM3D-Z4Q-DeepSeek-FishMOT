"""Capture actual functions/constants before the first source-to-body replay."""
from common import *
import inspect,importlib.util

def main():
    assert not RUN.exists() and not (HERE/'slice').exists()
    spec=importlib.util.spec_from_file_location('ds12_actual_runner_freeze',HERE/'runner.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    import reconnect,forecast,depth_state,depth_measurement,birth_memory,contact_measurement
    assert reconnect.CFG==forecast.CFG==birth_memory.CFG==read(HERE/'CONFIG.json')
    for n in ('CONTROLLER_CHECKS.json','FORECAST_CHECKS.json','RECONNECT_CHECKS.json','SCORE_CHECKS.json','PREFLIGHT_REVIEW.json',
              'CONTACT_MEASUREMENT_CHECKS.json','CONTACT_MEASUREMENT_FINAL_CHECKS.json'):
        status=read(HERE/n)['status']
        assert status=='PASS' or (n=='CONTACT_MEASUREMENT_FINAL_CHECKS.json' and status=='PASS_FINAL_VALIDATOR_SOURCE_BINDING_CHECKS'),n
    final=read(HERE/'CONTACT_MEASUREMENT_FINAL_CHECKS.json')
    for key in ('original_checks','final_code','tests','final_execution_log'):verify_item(final[key])
    write_new(HERE/'EFFECTIVE_PARAMETERS.json',dict(actual_config=reconnect.CFG,
        birth_selector=inspect.getsource(reconnect.choose),birth_qualification=inspect.getsource(reconnect.qualification),
        birth_memory=inspect.getsource(birth_memory.BirthMemory),batch_control=inspect.getsource(runner.plan_births),
        current_source_builder=inspect.getsource(runner.build_contact_frame),
        current_measurement=inspect.getsource(contact_measurement.measure_contact),
        current_core_arithmetic=inspect.getsource(contact_measurement.adaptive_core),
        current_certificate_validator=inspect.getsource(contact_measurement.check_certificate),
        contact_stage=inspect.getsource(runner.DepthNativeBridge.stage_contact_reconnect),
        birth_forecast=inspect.getsource(forecast.predict),group_selector=inspect.getsource(runner._old9.choose),
        raw_core_qualification=inspect.getsource(depth_measurement.usable),
        actual_code=[artifact(p) for p in (HERE/'reconnect.py',HERE/'forecast.py',HERE/'controller.py',
            HERE/'birth_memory.py',HERE/'runner.py',HERE/'contact_measurement.py',
            HERE.parent/'ds11_depth_birth_reconnect/reconnect.py',DS1/'depth_state.py',DS1/'depth_measurement.py')],
        raw_history_only=True,source_history_joint_endpoint=True,new_model_http=0,cost_usd=0,
        independent_scoring_after_all_seals=True,old_auto_rules_veto_before_write=True))
    print('Actual constants/functions frozen before first slice, no GT')
if __name__=='__main__':main()
