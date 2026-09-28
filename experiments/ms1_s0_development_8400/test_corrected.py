"""Prediction-only regression checks for the missed development merge."""
import copy
import json
from pathlib import Path

from event_packet import packet,token_map
from mask_geometry import mask
from source_scan import ASSIGN,OBS,rows

HERE=Path(__file__).resolve().parent
DRY=HERE/'dry_run_corrected'


def run():
    scan=json.loads((HERE/'private_source/scan_corrected.json').read_text(encoding='utf-8'))
    assert len(scan['suspects'])==1
    event=scan['suspects'][0]
    assert (event['frame'],event['sources'],event['group'])==(5933,[1,7],1)
    assert event['selection_route']=='DIRECT_MASK_TRANSITION'
    wanted={5932,5933,5938,5939}
    observations={x['frame']:x for x in rows(OBS) if x['frame'] in wanted}
    assignments={x['frame']:x for x in rows(ASSIGN) if x['frame'] in wanted}
    before={x['id']:x for x in observations[5932]['observations']}
    merged={x['id']:x for x in observations[5933]['observations']}
    split={x['id']:x for x in observations[5939]['observations']}
    assert (before[7]['area'],merged[7]['area'],merged[1]['area'],split[7]['area'])==(1623,0,1774,988)
    group=mask(assignments[5933]['masks']['n:1'])
    direct={n:float((mask(assignments[5932]['masks'][f'n:{n}']) & group).sum() /
                    max(1,mask(assignments[5932]['masks'][f'n:{n}']).sum())) for n in before}
    assert direct[7]>.99 and direct[1]>.84
    assert all(direct[n]<.15 for n in before if n not in (1,7))
    assert (mask(assignments[5932]['masks']['n:1']) &
            mask(assignments[5932]['masks']['n:7'])).sum()==0

    public=DRY/'public'
    seal=json.loads((public/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
    assert seal['frames']==seal['published_frames']==8400 and seal['http_attempts']==0
    assert seal['selected_episodes']==['MS1-F5933']
    events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8'))
    for arm in ('B-HOLD-S0','B-VLM-S0'):
        result=events[arm][0]
        assert result['confirm_frame']==5934
        assert result['q']==result['split_first_frame']==result['evidence_cutoff_frame']==5939
        assert result['numeric']['choice']=='H2'
        assert result['restore']['status']=='RESOLVE_NO_ID_CHANGE'
    ledger=[json.loads(x) for x in (public/'PUBLISH_LEDGER.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(ledger)==8400 and [x['frame'] for x in ledger]==list(range(1,8401))
    first=ledger[5938]['event_publish']
    assert set(first)=={'B-HOLD-S0','B-VLM-S0'}
    assert all(x['evidence_cutoff_frame']==5939 and x['post_sample_count']==1 for x in first.values())
    assert not (public/'CALL_LEDGER.jsonl').stat().st_size

    # A post-q mask mutation must not enter the frozen S0 body.
    q_state=json.loads((DRY/'private_source/MS1-F5933-B-VLM-S0-episode_q.json').read_text(encoding='utf-8'))
    tokens=token_map(list(rows(OBS)))
    history={x['frame']:x for x in rows(ASSIGN) if x['frame']<=5939}
    frozen=json.loads((public/'dry_packets/MS1-F5933-S0.json').read_text(encoding='utf-8'))
    assert packet(q_state,'S0',tokens,frozen['images'],history)==frozen
    tampered=copy.copy(history)
    tampered[5940]={'frame':5940,'masks':{'n:1':'tampered_future'}}
    assert packet(q_state,'S0',tokens,frozen['images'],tampered)==frozen
    report=dict(status='PASS',scanner='F5933 native 1+7 direct transition',
        first_publish_frame=5939,future_input_invariant=True,frames=8400,http_attempts=0)
    target=public/'TEST_REPORT.json'
    assert not target.exists(),target
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    run()
