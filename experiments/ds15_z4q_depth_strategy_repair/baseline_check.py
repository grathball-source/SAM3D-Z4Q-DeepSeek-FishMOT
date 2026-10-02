"""Postseal exact Z4Q archive parity, without running a predictor or reading GT."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = Path('E:/CAU/D-MOT')
RETURN = WORK / 'tools/sam3_depth_return_guard_20260918/completion_evidence/experiment'
BAGS = WORK / 'tools/z4q_new_bags_20260923/results'
NE1 = ROOT / 'experiments/ne1_native_first_event_association/run'
FIELDS = ('IDF1', 'HOTA', 'AssA', 'IDSW', 'FP', 'FN')
RANGES = {
    'feeding_000000_000199': (0, 199),
    'feeding_000351_000555': (351, 555),
    'feeding_000701_001060': (701, 1060),
    'feeding_001201_001906': (1201, 1906),
    'fishsa_development_8400': (1, 8400),
    'fishsa_validation_2888': (9301, 12188),
    'L3': (0, 3709), 'LW': (0, 3628),
}
ARCHIVES = {
    'fishsa_development_8400': (RETURN / 'predictions_development.jsonl.gz',
        '18793b53c7f751b149d0bbaa01f307b6c86a48f9c831edb761fe87e2b2a9a8cb',
        'Z4Q_STABLE'),
    'fishsa_validation_2888': (RETURN / 'predictions_validation.jsonl.gz',
        '9a95ed32e184d2e37c185104df184c943733c00d2cbed8b3e85967e8728dbdef',
        'Z4Q_STABLE'),
    'feeding_000000_000199': (NE1 / 'feeding_000000_000199/public/predictions.jsonl.gz',
        '888c5f78804d6f8b69acc1f84b7f5f5ef819711ab2e3cee6543946b5c5dc7ba8',
        'Z4Q_FROZEN'),
    'feeding_000351_000555': (NE1 / 'feeding_000351_000555/public/predictions.jsonl.gz',
        '62d99809c392d17fe772ce25bc45cee0464708a2ea59082019d09113fbd5f0af',
        'Z4Q_FROZEN'),
    'L3': (BAGS / 'L3_predictions.jsonl.gz',
        '302234416f202d8793d97e6539cf91957ba2fe5b41654b78ea950075f10c2522', None),
    'LW': (BAGS / 'LW_predictions.jsonl.gz',
        'f31792aa477a004a610b74ca16b994ff8c58ce0e77e21fdb4512ba59b193a03b', None),
}
METRIC_FILES = {
    'fishsa_development_8400': (RETURN / 'metrics_development.json',
        'f513fbaa31e2c163bb6cbd95040a2debadbbf06a6e03714d3c93fc3d730d0f4a'),
    'fishsa_validation_2888': (RETURN / 'metrics_validation.json',
        '2051886795ee5a975f054d277a3a657236c888debc7774ddcc7390a6aa9ebd42'),
    'feeding_000000_000199': (NE1 / 'METRICS.json',
        '72dbff505b40cb40d28e95e1ddf3daedf4a3b0ccac11d7c24cd6a7ecb918fdc8'),
    'feeding_000351_000555': (NE1 / 'METRICS.json',
        '72dbff505b40cb40d28e95e1ddf3daedf4a3b0ccac11d7c24cd6a7ecb918fdc8'),
    'L3': (BAGS / 'L3_metrics.json',
        '8d9c7a8fa09c0ae2927e257f439d11295f3c932e927d1994282362a9b0564252'),
    'LW': (BAGS / 'LW_metrics.json',
        '2f372c0400ceebe1a718bc7d72bd6289b3cb031d0c48ca3b53b6b596929f850b'),
}


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        yield from map(json.loads, handle)


def artifact(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def verify(run=None):
    run = Path(run or HERE / 'run')
    all_seal_path = run / 'ALL_PREDICTIONS_SEALED.json'
    # This gate precedes all new prediction, archived prediction and metric reads.
    assert all_seal_path.is_file(), 'All eight prediction seals are required first'
    all_seal = read(all_seal_path)
    assert all_seal['frames'] == 20098
    assert set(all_seal['seals']) == set(RANGES)
    assert set(all_seal['arms']) == {
        'SAM3_NATIVE', 'Z4Q_FROZEN', 'R12_RAW', 'Z4Q_SHARED', 'Z4Q_DEPTH'}
    new_predictions = {}
    for name, (start, stop) in RANGES.items():
        seal_path = run / name / 'public/PREDICTIONS_SEALED.json'
        assert artifact(seal_path) == all_seal['seals'][name], name
        seal = read(seal_path)
        assert seal['frames'] == stop - start + 1
        pred = seal_path.parent / 'predictions.jsonl.gz'
        assert sha(pred) == seal['artifacts_sha256'][pred.name], name
        new_predictions[name] = pred

    result = {}
    for name, (old_path, old_sha, old_arm) in ARCHIVES.items():
        assert sha(old_path) == old_sha, (name, 'canonical archive changed')
        start, stop = RANGES[name]
        count = objects = 0
        for count, (current, old) in enumerate(zip(
                rows(new_predictions[name]), rows(old_path), strict=True), 1):
            assert current['frame'] == old['frame'] == count, (name, count)
            assert current['global_frame'] == start + count - 1, (name, count)
            if old_arm is None:
                expected = [dict(mask=f'n:{n}', id=k) for n, k in
                    zip(old['native_ids'], old['public_ids'], strict=True)]
                assert [o['mask'] for o in current['variants']['SAM3_NATIVE']] == [
                    f'n:{n}' for n in old['native_ids']], (name, count, 'native source order')
            else:
                expected = old['variants'][old_arm]
                assert current['global_frame'] == old['global_frame'], (name, count)
                assert current['time'] == old['time'], (name, count, 'source timestamp')
                native_arm = 'N0' if old_arm == 'Z4Q_STABLE' else 'SAM3_NATIVE'
                assert current['variants']['SAM3_NATIVE'] == old['variants'][native_arm], (
                    name, count, 'same-source native/mask parity')
            actual = current['variants']['Z4Q_FROZEN']
            assert actual == expected, (name, count, 'frozen Z4Q mapping/mask mismatch',
                                        actual, expected)
            assert len(actual) == len({o['mask'] for o in actual}) == len({o['id'] for o in actual})
            objects += len(actual)
        assert count == stop - start + 1, (name, count)
        metric_path, metric_sha = METRIC_FILES[name]
        assert sha(metric_path) == metric_sha, (name, 'canonical metric changed')
        metrics = read(metric_path)
        if name.startswith('fishsa_'):
            metrics = metrics['Z4Q_STABLE']
        elif name.startswith('feeding_'):
            metrics = metrics['segment_metrics'][name]['Z4Q_FROZEN']
        else:
            metrics = metrics['metrics']['mask']
        result[name] = dict(status='PASS', frames=count, objects=objects,
            prediction=artifact(new_predictions[name]), archive=artifact(old_path),
            archived_arm=old_arm or 'native_ids/public_ids', metric_archive=artifact(metric_path),
            expected_metrics={k: metrics[k] for k in FIELDS},
            reference_status='DEPENDENT_UNREVIEWED_PREANNOTATION' if name in ('L3', 'LW')
                else 'EXPOSED_EXISTING_REFERENCE')
    return dict(status='PASS', checked_segments=6,
        checked_frames=sum(s['frames'] for s in result.values()), segments=result,
        unavailable_archived_segments=['feeding_000701_001060', 'feeding_001201_001906'],
        unavailable_policy='New frozen Z4Q replay scored independently; no historical score fabricated',
        all_predictions_seal=artifact(all_seal_path), GT_read=False, new_predictions=0,
        new_model_http=0, comparison='Exact ordered public ID and every original mask token; native source parity')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, default=HERE / 'run')
    args = parser.parse_args()
    report = verify(args.run)
    with (args.run / 'BASELINE_PARITY.json').open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps(dict(status=report['status'], frames=report['checked_frames'],
                         segments=report['checked_segments'])))
