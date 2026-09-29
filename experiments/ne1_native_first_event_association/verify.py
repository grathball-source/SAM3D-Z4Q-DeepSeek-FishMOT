"""Read-only postseal integrity and publication verification, before GT scoring."""
import gzip
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FEED=ROOT/'experiments/feeding_first_two_s0p'
SEGMENTS={'feeding_000000_000199':(0,199),'feeding_000351_000555':(351,555)}


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def lines(path):
    with Path(path).open(encoding='utf-8') as handle:
        return [json.loads(s) for s in handle if s.strip()]


def gzlines(path):
    with gzip.open(path,'rt',encoding='utf-8') as handle:
        return [json.loads(s) for s in handle]


def verify():
    run=HERE/'run'
    summary={}
    calls=0
    charged=0.
    for name,(start,stop) in SEGMENTS.items():
        public=run/name/'public'
        private=run/name/'private_api'
        seal=json.loads((public/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
        assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
        assert seal['frames']==seal['published_frames']==stop-start+1
        for filename,key in (('predictions.jsonl.gz','predictions_sha256'),
                             ('TRANSACTIONS.jsonl.gz','transactions_sha256'),
                             ('PUBLISH_LEDGER.jsonl','publish_ledger_sha256'),
                             ('EVENTS.json','events_sha256'),
                             ('AUTO_RECONNECT_AUDIT.json','auto_reconnect_audit_sha256'),
                             ('CALL_LEDGER.jsonl','call_ledger_sha256'),
                             ('FREEZE.json','freeze_sha256')):
            assert digest(public/filename)==seal[key],filename
        freeze=json.loads((public/'FREEZE.json').read_text(encoding='utf-8'))
        assert freeze['mode']=='real' and freeze['original_frames']==[start,stop]
        for path,expected in freeze['code_sha256'].items():
            assert digest(path)==expected,path
        for item in freeze['derived_inputs'].values():
            path=Path(item['path'])
            assert path.stat().st_size==item['bytes'] and digest(path)==item['sha256']
        pred=gzlines(public/'predictions.jsonl.gz')
        old=gzlines(FEED/'run'/name/'public/predictions.jsonl.gz')
        ledger=lines(public/'PUBLISH_LEDGER.jsonl')
        transactions=gzlines(public/'TRANSACTIONS.jsonl.gz')
        assert len(pred)==len(ledger)==len(old)==stop-start+1
        assert len(transactions)==3*len(pred)
        events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8'))
        q_publications=0
        for i,(row,old_row,pub) in enumerate(zip(pred,old,ledger,strict=True),1):
            assert row['frame']==pub['frame']==i
            assert row['global_frame']==pub['global_frame']==start+i-1
            assert row['variants']['Z4Q_FROZEN']==old_row['variants']['B0']
            masks=[obj['mask'] for obj in row['variants']['SAM3_NATIVE']]
            assert all(obj['id']==int(obj['mask'][2:]) for obj in row['variants']['SAM3_NATIVE'])
            for arm in ('Z4Q_FROZEN','EVENT_NUM','EVENT_VLM'):
                objects=row['variants'][arm]
                assert [obj['mask'] for obj in objects]==masks
                assert len({obj['id'] for obj in objects})==len(objects)
            assert pub['first_publish_time_monotonic']>=pub['frame_received_monotonic']
            wire=(json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
            assert hashlib.sha256(wire).hexdigest()==pub['prediction_row_sha256']
            for arm,item in pub['event_publish'].items():
                q_publications+=1
                assert pub['frame']==item['q']
                assert item['post_sample_count']==1
                assert len(item['first_public_pair'])==2
                assert len(set(item['first_public_pair'].values()))==2
        assert q_publications==sum(e['q'] is not None for arm in ('EVENT_NUM','EVENT_VLM')
                                   for e in events[arm])
        auto=json.loads((public/'AUTO_RECONNECT_AUDIT.json').read_text(encoding='utf-8'))
        assert all(value==0 for arm in ('EVENT_NUM','EVENT_VLM')
                   for value in auto['accepted'][arm].values())
        call=lines(public/'CALL_LEDGER.jsonl')
        starts={item['tag']:item for item in call if item['phase']=='START'}
        ends={item['tag']:item for item in call if item['phase']=='END'}
        unknown=[item for item in call if item['phase']=='HTTP_UNKNOWN']
        unsent=[item for item in call if item['phase']=='UNSENT']
        assert len(starts)==seal['http_attempts']
        assert set(ends).issubset(starts) and len(ends)+len(unknown)==len(starts)
        amount=0.
        for tag,item in starts.items():
            packet_path=public/'requests'/f'{tag}.json'
            body_path=private/f'{tag}.body.json'
            packet=json.loads(packet_path.read_text(encoding='utf-8'))
            body=json.loads(body_path.read_text(encoding='utf-8'))
            assert hashlib.sha256(json.dumps(packet,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==item['public_packet_sha256']
            assert hashlib.sha256(json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==item['body_sha256']
            assert body['messages'][0]['content']==packet['system']
            assert body['messages'][1]['content'][0]['text']==packet['user']
            assert len(body['messages'][1]['content'])==len(packet['images'])+1
            cutoff=int(packet['user'].split('当前证据截止：',1)[1].split('\n',1)[0])
            assert all(image['frame']<=cutoff for image in packet['images'])
            if tag in ends:
                answer=json.loads((public/'responses'/f'{tag}.json').read_text(encoding='utf-8'))
                assert digest(public/'responses'/f'{tag}.json')==ends[tag]['response_sha256']
                assert digest(private/f'{tag}.raw.json')==answer['raw_private_sha256']
                assert answer['response_end_monotonic']>=answer['request_start_monotonic']
                if tag.endswith('-S0'):
                    assert ledger[cutoff-1]['first_publish_time_monotonic']>=answer['response_end_monotonic']
                amount+=answer['peak_charge_upper_usd']
            else:
                amount+=next(v['peak_reserve_usd'] for v in unknown if v['tag']==tag)
        assert abs(amount-seal['peak_charge_upper_usd'])<1e-8
        for path in public.rglob('*'):
            if path.is_file():
                raw=path.read_bytes()
                assert not any(term in raw for term in (b'file-api-',b'Bearer ',b'DEEPSEEK_API_KEY',b'\x89PNG\r\n\x1a\n')),(name,path)
        summary[name]=dict(frames=len(pred),starts=len(starts),ends=len(ends),
            http_unknown=len(unknown),unsent=len(unsent),q_publications=q_publications,
            peak_charge_upper_usd=amount,auto=auto)
        calls+=len(starts)
        charged+=amount
    assert calls<=16 and charged<=4.
    selection=json.loads((run/'SELECTION.json').read_text(encoding='utf-8'))
    assert selection['actual_http']==calls
    assert abs(selection['peak_charge_upper_usd']-charged)<1e-8
    result=dict(status='PASS',segments=summary,actual_chat_http=calls,
        peak_charge_upper_usd=charged,selection=selection['selected_confirmed'],
        same_source_z4q_frozen_exact=True,no_private_media_or_ids_in_public=True,
        all_start_body_response_end_bindings_valid=True,
        both_prediction_seals_checked_before_gt=True)
    target=run/'VERIFICATION.json'
    assert not target.exists()
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(http=calls,charged=charged,segments={k:{x:v[x] for x in ('frames','starts','ends','http_unknown','unsent')} for k,v in summary.items()})))


if __name__=='__main__':
    verify()
