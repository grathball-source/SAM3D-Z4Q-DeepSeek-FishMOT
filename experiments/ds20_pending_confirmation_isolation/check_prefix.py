"""Three real causal prefixes; compare archived controls before reference reads."""
import guard
from common import *
from concurrent.futures import ThreadPoolExecutor, as_completed
from execute import run
import argparse
import re


PREFIXES = {'feeding_000000_000199': (200, 'feeding'),
            'LW': (960, 'LW'), 'L3': (3030, 'L3')}
CONTROL_ARMS = ('SAM3_NATIVE', 'Z4Q_FROZEN', 'ACTIVITY_RETURN', 'MIXED_RETURN')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', default='r2')
    args = parser.parse_args()
    assert re.fullmatch(r'[A-Za-z0-9_-]+', args.tag), 'tag must be a single directory suffix'
    prefixes = {name: (stop, f'slice_{label}_{args.tag}')
                for name, (stop, label) in PREFIXES.items()}
    assert ARMS == ('SAM3_NATIVE', 'Z4Q_FROZEN', 'ACTIVITY_RETURN',
                    'ACTIVITY_ISOLATED', 'MIXED_RETURN', 'MIXED_ISOLATED')
    assert RETURN_ARMS == EVENT_ARMS and MIXED_ARMS == ('MIXED_RETURN', 'MIXED_ISOLATED')
    sources = (HERE/'check_prefix.py', HERE/'runner.py', HERE/'controller.py',
               HERE/'common.py', HERE/'guard.py')
    before = {str(p): sha(p) for p in sources}
    logs = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks = {pool.submit(run, 'guard.py', 'slice', name, str(stop), directory): name
                 for name, (stop, directory) in prefixes.items()}
        for task in as_completed(tasks):
            logs[tasks[task]] = task.result()
    assert all(x['exit_code'] == 0 for x in logs.values()), logs
    checks = {}
    for name, (stop, directory) in prefixes.items():
        public = HERE/directory/name/'public'
        archived = iter(rows(ROOT/'experiments/ds19_protected_event_return/run'/name/
                             'public/predictions.jsonl.gz'))
        count = 0
        for prediction in rows(public/'predictions.jsonl.gz'):
            previous = next(archived)
            count += 1
            assert (prediction['frame'], prediction['global_frame']) == (
                previous['frame'], previous['global_frame'])
            assert prediction['frame'] == count
            for arm in CONTROL_ARMS:
                assert prediction['variants'][arm] == previous['variants'][arm], (
                    name, count, arm)
            masks = [item['mask'] for item in prediction['variants']['SAM3_NATIVE']]
            for arm in ARMS:
                outputs = prediction['variants'][arm]
                assert [item['mask'] for item in outputs] == masks, (name, count, arm)
                assert len({item['id'] for item in outputs}) == len(masks), (name, count, arm)
        assert count == stop, (name, count, stop)
        access = read(public/'ACCESS.json')
        assert access['status'] == 'NO_GT_RGB_RESTORED_NETWORK'
        events = read(public/'EVENTS.json')
        for arm_events in events.values():
            for event in arm_events:
                if event['q'] is not None:
                    assert event['evidence_cutoff_frame'] == event['q']
                    assert all(point['frame'] == event['q']
                               for point in event['post_first_observations'].values())
        checks[name] = dict(frames=count, original_frames=[SEGMENTS[name][0],
            SEGMENTS[name][0]+stop-1], control_arms_exact_DS19=list(CONTROL_ARMS),
            all_native_masks_retained=True, all_public_ids_unique=True,
            actual_slice_predictions=artifact(public/'predictions.jsonl.gz'),
            predictions=artifact(public/'predictions.jsonl.gz'), access=artifact(public/'ACCESS.json'),
            events=artifact(public/'EVENTS.json'), source_manifest=artifact(input_dir(name)/'SOURCE_MANIFEST.json'),
            measurement_cache=cache_reference(name), prefix_is_not_complete_formal_seal=True)
    stable = all(sha(p) == before[str(p)] for p in sources)
    assert stable, 'prefix code changed during execution'
    write_new(HERE/'PREFIX_CHECKS.json', dict(status='PASS', checks=checks,
        tag=args.tag, prefix_frames=sum(stop for stop, _ in prefixes.values()), source_logs=logs,
        actual_test_sources=before, source_stable_during_tests=stable,
        GT_read=False, metrics_read=False, model_http=0, cost_usd=0))
    print('PASS 4190 real prefix frames: four exact DS19 controls, six unique publishers')


if __name__ == '__main__':
    main()
