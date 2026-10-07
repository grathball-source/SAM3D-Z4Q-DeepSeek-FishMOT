"""Verify original absolute-path seals and exact local copy before frozen delivery."""
from common import *
import delivery
from datetime import datetime, timezone


def prepare():
    pins = read(HERE / 'STORAGE_DELIVERY_COPY.json')
    original = Path(pins['original_repository'])
    assert ROOT == Path(pins['delivery_repository']) and ROOT != original
    for pin in pins['copied_files']:
        source = Path(pin['original_path'])
        target = Path(pin['delivery_path'])
        assert source.stat().st_size == pin['bytes'] and sha(source) == pin['sha256'], source
        if target == HERE / 'EXECUTION_LOG.jsonl':
            assert target.read_bytes().startswith(source.read_bytes())
        else:
            assert target.stat().st_size == pin['bytes'] and sha(target) == pin['sha256'], target
    science = read(HERE / 'RUNTIME_FREEZE.json')
    copied_science = 0
    for path, expected in science['code'].items():
        source = Path(path)
        assert sha(source) == expected, source
        if source.is_relative_to(original):
            assert sha(ROOT / source.relative_to(original)) == expected, source
            copied_science += 1
    original_here = original / HERE.relative_to(ROOT)
    original_common = module('ds37_original_absolute_path_common', original_here / 'common.py')
    previous_common = sys.modules['common']
    try:
        sys.modules['common'] = original_common
        original_score = module('ds37_original_absolute_path_score', original_here / 'score.py')
    finally:
        sys.modules['common'] = previous_common
    original_score.verify_all()
    write_new(HERE / 'DELIVERY_COPY_BINDING.json', dict(
        status='PASS_ORIGINAL_ABSOLUTE_PATH_SEALS_AND_ALL_COPIED_BYTES',
        checked_utc=datetime.now(timezone.utc).isoformat(),
        original_scorer=artifact(original_here / 'score.py'),
        original_common=artifact(original_here / 'common.py'),
        frozen_delivery=artifact(HERE / 'delivery.py'),
        copy_inventory=artifact(HERE / 'STORAGE_DELIVERY_COPY.json'),
        copied_files_verified=len(pins['copied_files']), copied_science_sources_verified=copied_science,
        original_prediction_access_and_input_seals_fully_verified=True,
        only_execution_ledger_appended=True, science_score_and_seals_unchanged=True,
        method='Run the unchanged original scorer seal verification at its original E paths; '
               'verify every cloned artifact byte and repository science source against that verified original. '
               'Temporarily bind only the delivery-time score import, restoring it in finally.',
        model_http=0, cost_usd=0))
    previous_score = sys.modules.get('score')
    try:
        sys.modules['score'] = original_score
        delivery.prepare()
    finally:
        if previous_score is None:
            sys.modules.pop('score', None)
        else:
            sys.modules['score'] = previous_score


if __name__ == '__main__':
    assert sys.argv[1:] == ['prepare']
    prepare()
