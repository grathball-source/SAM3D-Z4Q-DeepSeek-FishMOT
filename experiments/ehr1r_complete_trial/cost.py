"""Postseal rate accounting from returned token usage; never claims a provider invoice."""
import argparse
import datetime
from pathlib import Path

from build import read, save


def main(root):
    root=Path(root);responses=root/'public/responses'
    date=datetime.date(2026,9,27)
    assert date.weekday()==6  # Sunday: official off-peak for the entire UTC day.
    rows=[]
    for path in sorted(responses.glob('*.json')):
        response=read(path);usage=response['usage']
        hit=usage.get('prompt_cache_hit_tokens',usage.get('prompt_tokens_details',{}).get('cached_tokens',0))
        miss=usage.get('prompt_cache_miss_tokens',usage['prompt_tokens']-hit)
        output=usage['completion_tokens']
        assert hit+miss==usage['prompt_tokens']
        off=(hit*.003+miss*.15+output*.6)/1_000_000
        rows.append(dict(attempt_id=response['attempt_id'],prompt_cache_hit_tokens=hit,
            prompt_cache_miss_tokens=miss,completion_tokens=output,
            offpeak_usage_rate_estimate_usd=round(off,9),
            peak_no_cache_upper_usd=response['charged_upper_usd']))
    assert len(rows)==11
    save(root/'public/COST_ACCOUNT.json',dict(status='USAGE_RATE_ESTIMATE_NOT_PROVIDER_INVOICE',
        actual_inference_http_attempts=11,formal_returned=10,smoke_returned=1,
        formal_unsent=15,unknown_http=0,official_price_url='https://api-docs.deepseek.com/quick_start/pricing/',
        pricing_calendar='2026-09-27 Sunday UTC, all hours off-peak under checked official schedule',
        rates_usd_per_m=dict(cache_hit_input=.003,cache_miss_input=.15,output=.6),
        total_prompt_cache_hit_tokens=sum(x['prompt_cache_hit_tokens'] for x in rows),
        total_prompt_cache_miss_tokens=sum(x['prompt_cache_miss_tokens'] for x in rows),
        total_completion_tokens=sum(x['completion_tokens'] for x in rows),
        offpeak_usage_rate_estimate_usd=round(sum(x['offpeak_usage_rate_estimate_usd'] for x in rows),9),
        peak_no_cache_upper_usd=round(sum(x['peak_no_cache_upper_usd'] for x in rows),9),
        cap_usd=3,provider_invoice_unavailable=True,attempts=rows))
    print(dict(returned=11,offpeak_usage_rate_estimate_usd=round(sum(x['offpeak_usage_rate_estimate_usd'] for x in rows),9)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    main(parser.parse_args().root)
