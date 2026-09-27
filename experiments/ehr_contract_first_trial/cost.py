"""Conservative returned-token account; this is not a provider invoice."""
import argparse
from datetime import datetime
from pathlib import Path

from build import read, save
from score import lines


def rate(at):
    when = datetime.fromisoformat(at)
    peak = when.weekday() < 5 and (1 <= when.hour < 4 or 6 <= when.hour < 10)
    return (.006, .30, 1.20) if peak else (.003, .15, .60)


def main(run):
    public = Path(run)/'public'
    budget = read(public/'BUDGET.json')
    events = lines(public/'CALL_LEDGER.jsonl')
    starts = {x['attempt_id']: x for x in events if x['phase'] == 'START'}
    ends = {x['attempt_id']: x for x in events if x['phase'] == 'END'}
    rows = []
    for attempt, event in starts.items():
        path = public/'responses'/(attempt+'.json')
        if attempt not in ends or not path.exists():
            rows.append({'attempt_id': attempt, 'state': 'HTTP_UNKNOWN',
                         'peak_reserved_usd': event['reserve_peak_usd']})
            continue
        response = read(path); usage = response['usage']
        prompt = usage.get('prompt_tokens', 0); completion = usage.get('completion_tokens', 0)
        hit = usage.get('prompt_cache_hit_tokens')
        miss = usage.get('prompt_cache_miss_tokens')
        if type(hit) is not int or type(miss) is not int or hit+miss != prompt:
            hit, miss = 0, prompt
        hit_rate, miss_rate, output_rate = rate(event['at'])
        estimate = (hit*hit_rate+miss*miss_rate+completion*output_rate)/1_000_000
        rows.append({'attempt_id': attempt, 'state': 'RETURNED',
                     'prompt_tokens': prompt, 'cache_hit_tokens': hit, 'cache_miss_tokens': miss,
                     'completion_tokens': completion,
                     'peak_no_cache_upper_usd': response['charged_upper_usd'],
                     'actual_time_rate_estimate_usd': round(estimate, 9),
                     'rate_tier': 'PEAK' if miss_rate == .30 else 'OFF_PEAK'})
    formal = [x for x in rows if x['attempt_id'].startswith('B')]
    technical = [x for x in rows if x['attempt_id'].startswith('S')]
    value = {'status': 'USAGE_ACCOUNT_NOT_PROVIDER_INVOICE',
             'authorized_inference_max': 27, 'authorized_usd_max': 4,
             'precall_peak_reserve_usd': budget['total_reserve_usd'],
             'technical_started': len(technical), 'formal_started': len(formal),
             'formal_unsent': 25-len(formal),
             'http_unknown': sum(x['state'] == 'HTTP_UNKNOWN' for x in rows),
             'returned_peak_no_cache_upper_usd': round(sum(x.get('peak_no_cache_upper_usd', 0) for x in rows), 9),
             'unknown_reserved_usd': round(sum(x.get('peak_reserved_usd', 0) for x in rows), 9),
             'actual_time_rate_estimate_usd': round(sum(x.get('actual_time_rate_estimate_usd', 0) for x in rows), 9),
             'rows': rows}
    save(public/'COST_ACCOUNT.json', value)
    print({k: value[k] for k in ('technical_started', 'formal_started', 'formal_unsent',
                                 'http_unknown', 'returned_peak_no_cache_upper_usd')})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True)
    main(p.parse_args().run)
