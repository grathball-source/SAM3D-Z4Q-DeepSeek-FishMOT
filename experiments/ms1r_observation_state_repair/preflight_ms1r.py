"""Prediction-only budget and input gate before the single real replay."""
import json
from pathlib import Path

from provider import INPUT_RESERVE, MAX_TOKENS, PER_SLOT_USD, PRICE_INPUT, PRICE_OUTPUT, write_new
from replay import HERE, OLD, read, sha


def estimate(packet, extra_chars=0):
    return int(.6*(len(packet['system'])+len(packet['user'])+extra_chars))+16384*len(packet['images'])+1024


def main():
    config=read(HERE/'CONFIG.json')
    test=read(HERE/'TEST_REPORT.json')
    dry=read(HERE/'dry_run_ms1r/public/PREDICTIONS_SEALED.json')
    assert test['status']=='PASS' and dry['frames']==2888 and dry['http_attempts']==0
    assert sha(HERE/'private_source/scan.json')==sha(OLD/'private_source/scan.json')
    packets={stage:read(HERE/f'dry_run_ms1r/public/dry_packets/MS1-F2586-{stage}.json')
             for stage in ('M','S')}
    # S's dry packet has null M. The fixed parsed projection is bounded below
    # 25k characters even for a much longer raw M response.
    estimates=dict(M=estimate(packets['M']),S_with_max_projected_M=estimate(packets['S'],25000))
    assert max(estimates.values())<INPUT_RESERVE
    assert config['max_inference_http']*PER_SLOT_USD<=config['budget_usd']
    result=dict(status='PASS_BEFORE_PAID_CALL',price_checked_utc='2026-09-28',
        official_pricing_url='https://api-docs.deepseek.com/quick_start/pricing/',
        model='deepseek-flash',peak_cache_miss_input_usd_per_million=PRICE_INPUT,
        peak_output_usd_per_million=PRICE_OUTPUT,input_reserve_tokens=INPUT_RESERVE,
        output_reserve_tokens=MAX_TOKENS,per_http_upper_usd=PER_SLOT_USD,
        max_inference_http=config['max_inference_http'],full_limit_reserve_usd=config['max_inference_http']*PER_SLOT_USD,
        cap_usd=config['budget_usd'],dry_request_input_estimates=estimates,
        selected_prediction_only_event_count=len(read(HERE/'private_source/scan.json')['suspects']),
        trigger_scan_sha256=sha(HERE/'private_source/scan.json'),
        old_trigger_scan_sha256=sha(OLD/'private_source/scan.json'))
    write_new(HERE/'BUDGET_PREFLIGHT.json',result)
    print(json.dumps(result))


if __name__=='__main__':
    main()
