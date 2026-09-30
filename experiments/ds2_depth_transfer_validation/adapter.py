"""Read-only DS1 scoring adapter: only the WLS mean drift is ablated."""
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DS1 = ROOT / 'experiments/ds1_depth_only'
sys.path.insert(0, str(DS1))
import replay as frozen
from depth_state import predict
from depth_score import dynamic_choice


def zero_drift_predict(fragment, query_time):
    value = predict(fragment, query_time)
    if value['status'] == 'WLS_LINEAR_TIME':
        return dict(value, unablated_mu_mm=value['mu_mm'],
                    mu_mm=value['beta_intercept_mm'], applied_drift_mm=0.,
                    mean_policy='ZERO_DRIFT_MATCHED_SCALE')
    return value


# Separate globals dictionary, identical frozen score bytecode. No mutation of
# DS1 modules and no shared branch selector/state. Only predict is rebound.
zero_drift_choice = types.FunctionType(
    dynamic_choice.__code__, dict(dynamic_choice.__globals__, predict=zero_drift_predict),
    'zero_drift_choice', dynamic_choice.__defaults__)

ARMS = ('SAM3_NATIVE', 'D0_GEOMETRY', 'D1_STATIC_LEGACY', 'D2_FROZEN',
        'D3_ZERO_DRIFT_MATCHED_SCALE')
