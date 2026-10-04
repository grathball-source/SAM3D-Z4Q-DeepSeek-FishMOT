"""The unchanged DS25 producer with private, effective per-arm parameters.

The lower scale floor changes the actual five-step IRLS fit as well as layer
scales. It is an experimental variability floor, never sensor accuracy.
"""
from types import FunctionType, ModuleType

from common import ROOT, VARIANTS, module

_original = module('ds28_readonly_ds25_measurement',
    ROOT / 'experiments/ds25_contact_local_layers/measurement.py')
array_binding = _original.array_binding


def _private_functions(original, replacements):
    """Bind existing function code to a private dictionary; no shared writes."""
    result = ModuleType(original.__name__ + '_ds28_private')
    result.__dict__.update(original.__dict__)
    result.__dict__.update(replacements)
    for name, value in original.__dict__.items():
        if isinstance(value, FunctionType) and value.__globals__ is original.__dict__:
            copied = FunctionType(value.__code__, result.__dict__, value.__name__,
                value.__defaults__, value.__closure__)
            copied.__kwdefaults__ = value.__kwdefaults__
            copied.__doc__ = value.__doc__
            result.__dict__[name] = copied
    return result


class Measurement:
    """Measurement(policy).measure_region has DS25's exact argument contract.

    policy is a VARIANTS dictionary or its arm name. All supports, source checks,
    missingness and population gates are retained. Multiple supports never gain
    physical ownership merely because this instance uses different thresholds.
    """
    array_binding = staticmethod(array_binding)

    def __init__(self, policy):
        policy = VARIANTS[policy] if isinstance(policy, str) else policy
        floor = float(policy['scale_floor_mm'])
        contrast, factor = map(float, policy['contrast'])
        assert floor in (15., 5.) and (contrast, factor) in ((30., 3.), (10., 2.))
        parameters = dict(_original.PARAMETERS, scale_floor_mm=floor,
            background_contrast_floor_mm=contrast, background_sigma_factor=factor)
        assert parameters['layer_gap_mm'] == 30., 'Changing floor must not change layer splitting'
        layers = _private_functions(_original._layers, {'PARAMETERS': dict(parameters)})
        background = _private_functions(_original._background,
            {'PARAMETERS': dict(parameters), '_old': layers})
        producer = _private_functions(_original, {'PARAMETERS': dict(parameters),
            '_background': background, '_layers': layers})
        self.PARAMETERS = producer.PARAMETERS
        self._layers, self._background = layers, background
        self.measure_region = producer.measure_region
        self.contact_seed = producer.contact_seed

