"""Reuse exact immutable DS32 provenance; change only its forecast call."""
from common import OLD32, CFG, readonly_module
from predictor import predict, DEPTH
import inspect, textwrap, hashlib

OLD = readonly_module('ds37_readonly_ds32_evidence', OLD32.HERE/'evidence.py')
original = textwrap.dedent(inspect.getsource(OLD.DepthEvidence.query))
replacements = {
    '_depth.forecast(samples, now)': 'self.forecast(samples, now)',
    "forecast.get('status') != 'WLS_LINEAR_TIME'": "forecast.get('status') not in ('WLS_LINEAR_TIME', 'LOCAL_LEVEL_INNOVATION')",
    "'TARGET_WLS_UNAVAILABLE'": "'TARGET_FORECAST_UNAVAILABLE'"}
adapted = original
for source, target in replacements.items():
    assert adapted.count(source) == 1, source
    adapted = adapted.replace(source, target)
scope = dict(vars(OLD))
exec(compile(adapted, __file__+':exact_query_adapter', 'exec'), scope)
state_source = textwrap.dedent(inspect.getsource(OLD.DepthEvidence.state))
state_scope = dict(vars(OLD), _read_identity=lambda value: value)
assert state_source.count('copy.deepcopy(') == 6
exec(compile(state_source.replace('copy.deepcopy(', '_read_identity('),
    __file__+':internal_read_state', 'exec'), state_scope)
ADAPTATION = dict(original_query_sha256=hashlib.sha256(original.encode()).hexdigest(),
    adapted_query_sha256=hashlib.sha256(adapted.encode()).hexdigest(), replacements=replacements,
    immutable_registry_source=str(OLD32.HERE/'evidence.py'),
    old_source_unmodified=True, no_quality_anchor_candidate_or_threshold_change=True)

class DepthEvidence(OLD.DepthEvidence):
    query = scope['query']
    _raw_read_state = state_scope['state']

    def __init__(self, namespace, cfg, mode='LEVEL'):
        super().__init__(namespace, cfg)
        assert mode in ('WLS', 'LEVEL')
        self.predictor_mode = mode
        self.predictor_config = dict(CFG)

    def forecast(self, samples, now):
        return DEPTH.forecast(samples, now) if self.predictor_mode == 'WLS' else predict(samples, now)

    def state(self):
        return dict(super().state(), predictor_mode=self.predictor_mode,
                    predictor_config=dict(self.predictor_config))

    def _read_state(self):
        """Internal hash-only view; recompute every time, never cache or mutate it."""
        return dict(self._raw_read_state(), predictor_mode=self.predictor_mode,
                    predictor_config=dict(self.predictor_config))
