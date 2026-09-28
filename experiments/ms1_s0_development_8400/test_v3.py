"""Regression: local merge scan, first-split timing, and complete dry replay."""
import copy
import json
from pathlib import Path

from event_packet import packet,token_map
from source_scan import ASSIGN,OBS,rows

HERE=Path(__file__).resolve().parent
RUN=HERE/'dry_run_v3'


def test():
    scan=json.loads((HERE/'private_source/scan_v3.json').read_text(encoding='utf-8'))
    suspects={x['frame']:x for x in scan['suspects']}
    assert len(suspects)==15
    assert (suspects[5927]['sources'],suspects[5927]['donor'],suspects[5927]['group'])==([1,7],1,7)
    assert (suspects[7997]['sources'],suspects[7997]['donor'],suspects[7997]['group'])==([2,5],2,5)
    assert (suspects[1152]['sources'],suspects[1152]['donor'],suspects[1152]['group'])==([0,2],0,2)
    assert not any(word in (HERE/'source_scan_v3.py').read_text(encoding='utf-8').lower()
                   for word in ('gt_grid','offline_matches','truth.jsonl'))
    public=RUN/'public'
    seal=json.loads((public/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
    assert seal['frames']==seal['published_frames']==8400 and seal['http_attempts']==0
    assert len(seal['selected_episodes'])==8
    events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8'))
    assert len(events['B-HOLD-S0'])==len(events['B-VLM-S0'])==13
    by_frame={x['suspect_frame']:x for x in events['B-HOLD-S0']}
    assert by_frame[5927]['confirm_frame']==5928
    assert by_frame[5927]['q']==by_frame[5927]['split_first_frame']==5939
    assert by_frame[7997]['q']==8035
    assert sum(x['q'] is not None for x in by_frame.values())==9
    assert by_frame[5927]['numeric']['choice']=='UNRESOLVED'
    state=json.loads((RUN/'private_source/MS1-F5927-B-VLM-S0-episode_q.json').read_text(encoding='utf-8'))
    area_5932=next(x['area'] for row in rows(OBS) if row['frame']==5932
                   for x in row['observations'] if x['id']==1)
    assert area_5932<state['minimum_restored_area']
    ledger=[json.loads(x) for x in (public/'PUBLISH_LEDGER.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(ledger)==8400 and [x['frame'] for x in ledger]==list(range(1,8401))
    first=ledger[5938]['event_publish']
    assert set(first)=={'B-HOLD-S0','B-VLM-S0'}
    assert all(x['evidence_cutoff_frame']==5939 and x['post_sample_count']==1 for x in first.values())
    assert (public/'CALL_LEDGER.jsonl').stat().st_size==0
    metrics=json.loads((public/'METRICS.json').read_text(encoding='utf-8'))
    assert metrics['archived_B0_fullmetrics_exact'] is True
    assert metrics['changed_frames']['HOLD_vs_VLM']==0
    assert metrics['interpretation']=='DRY_NO_API_MODEL_UNTESTED'

    tokens=token_map(list(rows(OBS)))
    history={x['frame']:x for x in rows(ASSIGN) if x['frame']<=5939}
    frozen=json.loads((public/'dry_packets/MS1-F5927-S0.json').read_text(encoding='utf-8'))
    assert packet(state,'S0',tokens,frozen['images'],history)==frozen
    modified=copy.copy(history)
    modified[5940]={'frame':5940,'masks':{'n:1':'future_changed'}}
    assert packet(state,'S0',tokens,frozen['images'],modified)==frozen
    report=dict(status='PASS',frames=8400,suspects=15,started_events=13,first_split_q=9,
                selected_by_confirmation=8,http_attempts=0,
                f5927_confirm=5928,f5927_first_split=5939,
                later_input_cannot_change_s0_packet=True)
    out=public/'TEST_REPORT.json'
    assert not out.exists(),out
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    test()
