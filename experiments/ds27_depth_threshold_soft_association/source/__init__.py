"""Isolated controller hierarchy; the original balance base is read-only."""
import importlib.util
from pathlib import Path
import sys

BASE_CONTROLLER = (Path(__file__).resolve().parents[3] /
    'online/closed_loop_2888/z4q_source/source/sam3_depth_identity_balance_20260917/controller.py')
_name = __name__ + '.frozen_balance'
_spec = importlib.util.spec_from_file_location(_name, BASE_CONTROLLER)
_base = importlib.util.module_from_spec(_spec)
sys.modules[_name] = _base
_spec.loader.exec_module(_base)
DepthIdentityBalance, center = _base.DepthIdentityBalance, _base.center
