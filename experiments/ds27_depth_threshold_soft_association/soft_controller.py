"""Bounded depth costs in the original two assignment matrices, before publish."""
import copy
import importlib.util
import math
import sys
from common import HERE, read
from bridge import Bridge

# A package-qualified hierarchy avoids old px_* modules already on sys.path.
_package = 'ds27_controller_source'
if _package not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_package, HERE/'source/__init__.py',
        submodule_search_locations=[str(HERE/'source')])
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_package] = _module
    _spec.loader.exec_module(_module)
from ds27_controller_source.px_return import StableReturn

CFG = read(HERE/'CONFIG.json')
STATE_EXTRAS = ('soft_context', 'soft_cost_checks')


class SoftReturn(StableReturn):
    def __init__(self, config):
        super().__init__(config)
        self.soft_context = None
        self.soft_cost_checks = []

    def edge_veto(self, frame, now, observation, public, anchor, origin_rule):
        return dict(veto=False, status='DISABLED', reason='DS27_NO_HARD_VETO',
                    origin_rule=origin_rule)

    def apply_depth_soft(self, matrix, terms, frame, now, phase, observations):
        """Competition is fixed from original costs, including each own dummy."""
        old_count = matrix.shape[1] - matrix.shape[0]
        assert old_count >= 0 and phase in ('D1_DELAYED', 'BIRTH_REFINE')
        by_native = {o['id']: o for o in observations}
        assert len(by_native) == len(observations)
        for (i, j), term in terms.items():
            assert j < old_count and math.isfinite(float(matrix[i, j]))
            original = float(matrix[i, j])
            assert original == term['cost'] and original >= 0
            term.update(cost_original=original, cost_effective=original)
        for i in range(matrix.shape[0]):
            dummy = old_count + i
            assert matrix[i, dummy] == 1.
            legal = sorted(j for row, j in terms if row == i)
            original_costs = {j: float(matrix[i, j]) for j in legal}
            minimum = min([1., *original_costs.values()])
            near = [j for j in legal if original_costs[j] <= minimum + CFG['competition_window']]
            dummy_near = 1. <= minimum + CFG['competition_window']
            if len(near) + int(dummy_near) < 2:
                continue
            for j in near:
                term = terms[i, j]
                n, k = term['native_id'], term['canonical_id']
                anchor = self.bank[k].get('anchor')
                if self.soft_context is None:
                    result = dict(delta_cost=0., status='DISABLED', reason='NO_NEW_EVIDENCE')
                else:
                    result = self.soft_context.check(self, by_native[n], k,
                        copy.deepcopy(anchor), phase)
                delta = float(result['delta_cost'])
                assert math.isfinite(delta) and abs(delta) <= CFG['soft_weight'] + 1e-12
                if result.get('status') in ('UNKNOWN', 'DISABLED', 'COMMON_NULL'):
                    assert delta == 0., 'Unknown evidence cannot alter a matrix cost'
                original = original_costs[j]
                effective = max(0., original + delta)
                check = dict(result, origin_rule=phase, native_id=n, public_id=k,
                    query_frame=frame, query_time=now, anchor=copy.deepcopy(anchor),
                    cost_original=original, cost_effective=effective,
                    requested_delta_cost=delta, applied_delta_cost=effective-original,
                    row_original_minimum=minimum, own_dummy_cost=1.,
                    own_dummy_near=dummy_near, near_target_ids=[terms[i, x]['canonical_id'] for x in near],
                    competition_window=CFG['competition_window'], hard_veto=False)
                self.soft_cost_checks.append(copy.deepcopy(check))
                term.update(cost=effective, cost_effective=effective, depth_soft=check)
                matrix[i, j] = effective
            assert matrix[i, dummy] == 1.

    def step(self, frame, now, observations, profiles=None):
        self.soft_cost_checks = []
        mapping, trace = super().step(frame, now, observations, profiles)
        trace['depth_soft_checks'] = copy.deepcopy(self.soft_cost_checks)
        return mapping, trace


def engine_state(engine):
    return {k: v for k, v in vars(engine).items() if k not in STATE_EXTRAS}


class SoftBridge(Bridge):
    def __init__(self, config):
        super().__init__(config)
        self.engine = SoftReturn(config)
