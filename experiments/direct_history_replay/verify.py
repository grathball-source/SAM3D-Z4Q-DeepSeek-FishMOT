"""Postseal chain, metric, and restricted-artifact verification; no inference."""
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PUBLIC = HERE/'public'


def sha(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def lines(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines()]


def gzrows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as source:
        yield from map(json.loads, source)


def main():
    freeze, seal, metrics = (load(PUBLIC/name) for name in ('FREEZE.json', 'PREDICTIONS_SEALED.json', 'METRICS.json'))
    assert freeze['code_sha256'] == sha(HERE/'replay.py')
    assert freeze['config_sha256'] == sha(HERE/'CONFIG.json')
    assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
    assert seal['frames'] == 2888 and seal['HTTP_attempts'] == 4
    assert seal['predictions_sha256'] == sha(PUBLIC/'predictions_validation.jsonl.gz')
    assert seal['transactions_sha256'] == sha(PUBLIC/'transactions_validation.jsonl.gz')
    assert seal['call_ledger_sha256'] == sha(PUBLIC/'CALL_LEDGER.jsonl')
    assert metrics['source_prediction_sha256'] == seal['predictions_sha256']
    assert metrics['status'] == 'SCORED_EXPOSED_VALIDATION'
    ledger = lines(PUBLIC/'CALL_LEDGER.jsonl')
    schedule = [x['case'] for x in freeze['schedule']]
    assert len(ledger) == 8
    assert [(x['phase'], x['case']) for x in ledger] == [z for case in schedule for z in (('START', case), ('END', case))]
    responses = []
    for case, (start, end) in zip(schedule, zip(ledger[::2], ledger[1::2], strict=True), strict=True):
        binding = load(PUBLIC/'request_bindings'/f'{case}.json')
        body = HERE/'private_api'/f'{case}.body.json'
        assert hashlib.sha256(body.read_bytes().rstrip(b'\n')).hexdigest() == binding['body_sha256'] == start['body_sha256']
        assert hashlib.sha256((PUBLIC/'requests'/f'{case}.json').read_bytes().rstrip(b'\n')).hexdigest() == binding['text_sha256']
        result_path = PUBLIC/'responses'/f'{case}.json'
        result = load(result_path)
        assert result['case'] == case and result['returned_model'] == 'deepseek-flash'
        assert sha(result_path) == end['response_sha256']
        assert sha(HERE/'private_api'/f'{case}.raw.json') == result['raw_private_sha256']
        assert result['choice'] in ('H1', 'H2', 'DEFER') and result['parse_status'] == 'VALID'
        responses.append(result)
    assert abs(sum(x['charge_peak_upper_usd'] for x in responses)-seal['peak_no_cache_upper_usd']) < 1e-10
    assert seal['peak_no_cache_upper_usd'] < 4
    assert sum(x['reserve_peak_usd'] for x in ledger if x['phase']=='START') < 4
    events = load(PUBLIC/'EVENTS.json')
    assert [(x['case'], x['frame']) for x in events] == [(x['case'], x['q']) for x in freeze['schedule']]
    assert [x['choice'] for x in events] == [x['choice'] for x in responses]
    assert sum(x['status']=='COMMIT' for x in events) == 2
    assert [x['frame'] for x in events if x['status']=='COMMIT'] == [377, 2638]
    rows = list(gzrows(PUBLIC/'predictions_validation.jsonl.gz'))
    assert len(rows) == 2888 and [x['frame'] for x in rows] == list(range(1, 2889))
    assert all([y['mask'] for y in x['variants']['B0']] == [y['mask'] for y in x['variants']['B1']] for x in rows)
    different = [x['frame'] for x in rows if x['variants']['B0'] != x['variants']['B1']]
    assert different == list(range(377, 2889)) and len(different) == metrics['difference_frames']
    assert sum(x['verdict']=='wrong' for x in metrics['transactions']) == 2
    assert metrics['transaction_counts'] == {'correct': 0, 'wrong': 2, 'unscorable': 0}
    assert metrics['metrics']['B0']['IDF1'] == 80.69758683623512
    assert metrics['metrics']['B0']['HOTA'] == 69.24386895965796
    for image in load(PUBLIC/'VISUAL_MANIFEST.json'):
        assert sha(image['path']) == image['sha256']
    for forbidden in (b'file-api-', b'Bearer ', b'DEEPSEEK_API_KEY'):
        assert all(forbidden not in path.read_bytes() for path in PUBLIC.rglob('*') if path.is_file())
    metric_names = ('IDF1', 'HOTA', 'AssA', 'IDSW', 'FP', 'FN')
    delta = {k: metrics['metrics']['B1'][k]-metrics['metrics']['B0'][k] for k in metric_names}
    offpeak_est = sum(((x['usage']['prompt_tokens']-x['usage'].get('prompt_cache_hit_tokens', 0))*.15+
        x['usage'].get('prompt_cache_hit_tokens', 0)*.003+x['usage']['completion_tokens']*.6)/1e6 for x in responses)
    summary = dict(status='COMPLETE_NEGATIVE_EXPOSED_REPLAY', review_base=load(HERE/'CONFIG.json')['review_base'],
        frames=2888, event_opportunities=4, HTTP_attempts=4, valid_choices=4,
        defer=0, exceptions=0, proposals=2, commits=2, stage_rejections=0,
        prediction_difference_frames=len(different), transactions=metrics['transactions'],
        metrics=metrics['metrics'], delta_B1_minus_B0=delta,
        peak_no_cache_upper_usd=seal['peak_no_cache_upper_usd'],
        offpeak_usage_estimate_usd=offpeak_est, provider_invoice='UNAVAILABLE',
        wall_seconds=seal['wall_seconds'])
    (PUBLIC/'SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    private = sorted(p for p in (HERE/'private_api').rglob('*') if p.is_file())
    media_dir = ROOT/'experiments/ehr_contract_first_trial/run/private/media'
    unique_media = sorted({x['media_file'] for case in schedule for x in load(PUBLIC/'requests'/f'{case}.json')['IMAGE_INDEX']})
    private += [media_dir/name for name in unique_media]
    private.append(ROOT/'experiments/ehr_contract_first_trial/run/send/UPLOAD_LEDGER.jsonl')
    inventory = [dict(path=str(p.resolve()), bytes=p.stat().st_size, sha256=sha(p)) for p in private]
    (PUBLIC/'RESTRICTED_INVENTORY.json').write_text(json.dumps(dict(
        status='LOCAL_RESTRICTED_NO_GIT', count=len(inventory), total_bytes=sum(x['bytes'] for x in inventory),
        reproduction='Use the frozen old H-D logical package and media, saved Files API IDs, local Z4Q observations/features; run replay.py once with new authorization. GT is scored only after prediction seal on the lab host.',
        files=inventory), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    acceptance = dict(status='PASS_COMPLETE_NEGATIVE', checks=['CODE_INPUT_FREEZE', 'FOUR_START_END_BODY_RESPONSE_BINDING',
        'PREDICTION_SEAL', 'B0_EXACT_OFFICIAL_BASELINE', '2888_MASK_AND_ID_CONTINUITY',
        'TWO_REAL_COMMIT_AND_NEXT_FRAME_STATE', 'OFFICIAL_TRACK_EVAL_POSTSEAL', 'NO_PUBLIC_CREDENTIAL_OR_FILE_ID'],
        prediction_sha256=seal['predictions_sha256'], score_sha256=sha(PUBLIC/'METRICS.json'),
        scorer_source_sha256=sha(ROOT/'online/closed_loop_2888/score.py'))
    (PUBLIC/'ACCEPTANCE.json').write_text(json.dumps(acceptance, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(summary['status'], delta, 'restricted', len(inventory))


if __name__ == '__main__':
    main()
