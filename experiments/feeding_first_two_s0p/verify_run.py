"""Audit complete source, publication and API ledgers without changing seals."""
import gzip
import hashlib
import json
from pathlib import Path

from prepare import SEGMENTS, digest, write_new

HERE=Path(__file__).resolve().parent


def lines(path):
    with Path(path).open('r',encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


def predictions(path):
    with gzip.open(path,'rt',encoding='utf-8') as handle:
        return [json.loads(line) for line in handle]


def verify():
    summary={}
    total_http=0
    total_charge=0.
    for name,(start,stop) in SEGMENTS.items():
        public=HERE/'run'/name/'public'
        private=HERE/'run'/name/'private_api'
        seal=json.loads((public/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
        assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
        expected={'predictions.jsonl.gz':'predictions_sha256',
                  'TRANSACTIONS.jsonl.gz':'transactions_sha256',
                  'PUBLISH_LEDGER.jsonl':'publish_ledger_sha256',
                  'EVENTS.json':'events_sha256','CALL_LEDGER.jsonl':'call_ledger_sha256',
                  'FREEZE.json':'freeze_sha256'}
        assert all(digest(public/file)==seal[key] for file,key in expected.items())
        pred=predictions(public/'predictions.jsonl.gz')
        dry=predictions(HERE/'dry_v2'/name/'public/predictions.jsonl.gz')
        ledger=lines(public/'PUBLISH_LEDGER.jsonl')
        assert len(pred)==len(dry)==len(ledger)==stop-start+1
        assert all(row['frame']==i and row['global_frame']==start+i-1
                   for i,row in enumerate(pred,1))
        assert all(row['variants']['B0']==dry[i]['variants']['B0'] and
                   row['variants']['B-HOLD']==dry[i]['variants']['B-HOLD']
                   for i,row in enumerate(pred))
        assert all(len({obj['id'] for obj in row['variants'][arm]})==
                   len(row['variants'][arm]) for row in pred for arm in ('B0','B-HOLD','B-VLM'))
        assert all(item['frame']==pred[i]['frame'] and
                   item['first_publish_time_monotonic']>=item['frame_received_monotonic']
                   for i,item in enumerate(ledger))
        q_publishes=[(arm,item) for item in ledger for arm in item['event_publish']]
        events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8'))
        expected_q=sum(item['q'] is not None for arm in ('B_HOLD','B_VLM')
                       for item in events[arm])
        assert len(q_publishes)==expected_q
        calls=lines(public/'CALL_LEDGER.jsonl')
        starts={item['tag']:item for item in calls if item['phase']=='START'}
        ends={item['tag']:item for item in calls if item['phase']=='END'}
        unknown=[item for item in calls if item['phase'] in ('HTTP_UNKNOWN','UNSENT')]
        assert len(starts)==seal['http_attempts'] and set(starts)==set(ends)
        assert not unknown
        charges=[]
        for tag,start_record in starts.items():
            packet_path=public/'requests'/f'{tag}.json'
            response_path=public/'responses'/f'{tag}.json'
            body_path=private/f'{tag}.body.json'
            raw_path=private/f'{tag}.raw.json'
            packet=json.loads(packet_path.read_text(encoding='utf-8'))
            body=json.loads(body_path.read_text(encoding='utf-8'))
            response=json.loads(response_path.read_text(encoding='utf-8'))
            wire=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()
            assert hashlib.sha256(wire).hexdigest()==start_record['body_sha256']
            assert hashlib.sha256(json.dumps(packet,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==start_record['public_packet_sha256']
            assert digest(response_path)==ends[tag]['response_sha256']
            assert digest(raw_path)==response['raw_private_sha256']
            assert response['finish_reason']=='stop' and response['parse_status']=='OK'
            assert response['request_start_monotonic']<=response['response_end_monotonic']
            assert packet['system']==body['messages'][0]['content']
            assert packet['user']==body['messages'][1]['content'][0]['text']
            cutoff=int(packet['user'].split('当前证据截止：',1)[1].split('\n',1)[0])
            assert all(item['frame']<=cutoff for item in packet['images'])
            charges.append(response['peak_charge_upper_usd'])
            if tag.endswith('-S0'):
                first=next(item for item in ledger if item['frame']==cutoff)
                assert first['first_publish_time_monotonic']>=response['response_end_monotonic']
        assert abs(sum(charges)-seal['peak_charge_upper_usd'])<1e-9
        for file in public.rglob('*'):
            if file.is_file():
                raw=file.read_bytes()
                assert not any(term in raw for term in (b'file-api-',b'DEEPSEEK_API_KEY',
                                                       b'Bearer ',b'\x89PNG\r\n\x1a\n')),(name,file)
        changed=sum(row['variants']['B-VLM']!=row['variants']['B-HOLD'] for row in pred)
        uploads=lines(public/'MEDIA_LEDGER.jsonl') if (public/'MEDIA_LEDGER.jsonl').exists() else []
        summary[name]=dict(frames=len(pred),calls=len(starts),uploads=len(uploads),
                           http_unknown_or_unsent=len(unknown),
                           q_publications=len(q_publishes),
                           B0_HOLD_equal_to_pre_api_dry=True,
                           VLM_vs_HOLD_changed_frames=changed,
                           peak_charge_upper_usd=sum(charges),
                           prediction_sha256=seal['predictions_sha256'])
        total_http+=len(starts)
        total_charge+=sum(charges)
    result=dict(status='PASS',segments=summary,total_http=total_http,
                peak_charge_upper_usd=total_charge,
                all_start_end_body_response_seal_bindings_valid=True,
                no_private_pixels_or_provider_file_ids_in_public=True,
                first_split_published_after_model_response=True)
    write_new(HERE/'run/VERIFICATION.json',result)
    print(json.dumps(result,ensure_ascii=False))
    return result


if __name__=='__main__':
    verify()
