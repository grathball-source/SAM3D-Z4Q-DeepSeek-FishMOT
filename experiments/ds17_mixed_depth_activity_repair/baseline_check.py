"""Postseal eight-segment equality to the already sealed DS15 native/Z4Q archives."""
from common import *
import argparse

FIELDS = ('IDF1', 'HOTA', 'AssA', 'IDSW', 'FP', 'FN')
BASELINES = ('SAM3_NATIVE', 'Z4Q_FROZEN')


def verify(run=None):
    run = Path(run or RUN)
    all_path = run / 'ALL_PREDICTIONS_SEALED.json'
    all_seal = read(all_path)
    assert all_seal['status'] in ('ALL_PREDICTIONS_AND_ACCESS_SEALED',
                                  'ALL_SIX_BRANCHES_EIGHT_SEGMENTS_SEALED')
    assert tuple(all_seal['arms']) == ARMS and all_seal['frames'] == 20098
    assert set(all_seal['seals']) == set(all_seal['access_seals']) == set(SEGMENTS)
    current_paths = {}
    for name, (start, stop) in SEGMENTS.items():
        verify_item(all_seal['seals'][name]); verify_item(all_seal['access_seals'][name])
        public = run / name / 'public'
        seal = read(public / 'PREDICTIONS_SEALED.json')
        assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
        assert seal['frames'] == seal['published_frames'] == stop - start + 1
        assert seal['original_frames'] == [start, stop] and tuple(seal['arms']) == ARMS
        for filename, digest in seal['artifacts_sha256'].items():
            assert sha(public / filename) == digest, (name, filename)
        current_paths[name] = public / 'predictions.jsonl.gz'

    # Archive reads follow the complete new-run seal checks above.
    old_summary = read(DS15 / 'SUMMARY.json')
    verify_item(old_summary['all_prediction_seal']); verify_item(old_summary['metrics'])
    old_all = read(DS15 / 'run/ALL_PREDICTIONS_SEALED.json')
    assert set(old_all['seals']) == set(SEGMENTS) and old_all['frames'] == 20098
    old_metrics = read(DS15 / 'run/METRICS.json')
    results = {}
    for name, (start, stop) in SEGMENTS.items():
        verify_item(old_all['seals'][name]); verify_item(old_all['access_seals'][name])
        old_public = DS15 / 'run' / name / 'public'
        old_seal = read(old_public / 'PREDICTIONS_SEALED.json')
        archive = old_public / 'predictions.jsonl.gz'
        assert sha(archive) == old_seal['artifacts_sha256']['predictions.jsonl.gz'], name
        count = objects = 0
        for count, (current, old) in enumerate(zip(rows(current_paths[name]), rows(archive), strict=True), 1):
            assert current['frame'] == old['frame'] == count
            assert current['global_frame'] == old['global_frame'] == start + count - 1
            assert current['time'] == old['time'], (name, count)
            for arm in BASELINES:
                assert current['variants'][arm] == old['variants'][arm], (name, count, arm)
            keys = [item['mask'] for item in current['variants']['SAM3_NATIVE']]
            for arm in ARMS:
                items = current['variants'][arm]
                assert [item['mask'] for item in items] == keys
                assert len(items) == len({item['id'] for item in items}), (name, count, arm)
            objects += len(keys)
        assert count == stop - start + 1
        values = old_metrics['segments'][name]['metrics']
        results[name] = dict(status='PASS', frames=count, objects=objects,
            prediction=artifact(current_paths[name]), archive=artifact(archive),
            archived_arms=list(BASELINES), old_prediction_seal=artifact(old_public / 'PREDICTIONS_SEALED.json'),
            expected_metrics={key: values['Z4Q_FROZEN'][key] for key in FIELDS},
            expected_baseline_metrics={arm: values[arm] for arm in BASELINES},
            reference_status='DEPENDENT_UNREVIEWED_PREANNOTATION' if name in ('L3', 'LW')
                else 'EXPOSED_EXISTING_REFERENCE')
    return dict(status='PASS', checked_segments=len(results), checked_frames=sum(x['frames'] for x in results.values()),
        checked_objects=sum(x['objects'] for x in results.values()), segments=results,
        all_predictions_seal=artifact(all_path), archived_predictions_seal=artifact(DS15 / 'run/ALL_PREDICTIONS_SEALED.json'),
        archived_metrics=artifact(DS15 / 'run/METRICS.json'), GT_read=False, new_predictions=0,
        new_model_http=0, comparison='Exact native and original Z4Q mask order, public IDs and source times on all eight segments')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, default=RUN)
    args = parser.parse_args()
    report = verify(args.run)
    write_new(args.run / 'BASELINE_PARITY.json', report)
    print(json.dumps(dict(status=report['status'], frames=report['checked_frames'],
                         segments=report['checked_segments'], objects=report['checked_objects'])))
