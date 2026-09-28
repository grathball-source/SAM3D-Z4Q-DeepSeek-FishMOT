"""Freeze the fixed paid cohort and inspect all causal dry packet envelopes."""
import hashlib
import json
import re
from pathlib import Path

from provider_v7 import INPUT_RESERVE, parse_split

HERE=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config=json.loads((HERE/'CONFIG_V7.json').read_text(encoding='utf-8'))
    dry=HERE/'dry_run_v6/public'
    seal=json.loads((dry/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
    events=json.loads((dry/'EVENTS.json').read_text(encoding='utf-8'))['B-HOLD-S0']
    assert config['fixed_model_episodes']==seal['selected_episodes']
    assert config['max_inference_http']==2*len(config['fixed_model_episodes'])==16
    assert config['budget_usd'] is None
    assert config['paid_authorization']=='USER_APPROVED_FIXED_EIGHT_NO_COST_CAP_2026_09_28'
    by_id={x['id']:x for x in events}
    packets=[]
    for episode in config['fixed_model_episodes']:
        event=by_id[episode]
        assert event['confirm_frame'] is not None and event['q'] is not None
        for stage,cutoff in (('M',event['confirm_frame']),('S0',event['q'])):
            path=dry/'dry_packets'/f'{episode}-{stage}.json'
            body=json.loads(path.read_text(encoding='utf-8'))
            estimate=int(.6*(len(body['system'])+len(body['user'])))+16384*len(body['images'])+1024
            assert estimate+30000<INPUT_RESERVE,(path,estimate)
            assert all(x['frame']<=cutoff for x in body['images'])
            facts={int(x) for x in re.findall(r'F(\d+):O\d+',body['user'])}
            assert not facts or max(facts)<=cutoff,(path,max(facts),cutoff)
            assert not any(x in body['user'] for x in ('native_id','public_id','gt_grid','file-api-'))
            packets.append(dict(episode=episode,stage=stage,cutoff=cutoff,
                                image_count=len(body['images']),estimated_input_tokens=estimate,
                                dry_packet_sha256=sha(path)))
    assert parse_split('{"choice":"H2","reason":"extra allowed"}','stop')==('H2','OK')
    assert parse_split('{"choice":"DEFER"}','stop')==('DEFER','OK')
    assert parse_split('{"choice":"H1","mapping":{"A":"Y","B":"X"}}','stop')[0] is None
    report=dict(status='PASS_BEFORE_PAID_SEND',fixed_model_episodes=config['fixed_model_episodes'],
                max_inference_http=16,cost_cap_usd=None,official_model='deepseek-flash',
                image_transport='official Files API',context_input_estimate_ceiling=INPUT_RESERVE,
                max_estimated_dry_input_tokens=max(x['estimated_input_tokens'] for x in packets),
                note='S0 includes the actual bounded M hypothesis only after M returns; this dry packet has M=null.',
                packets=packets)
    target=HERE/'PREFLIGHT_V7.json'
    with target.open('x',encoding='utf-8') as handle:
        json.dump(report,handle,ensure_ascii=False,indent=2)
        handle.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='packets'},ensure_ascii=False))


if __name__=='__main__':
    main()
