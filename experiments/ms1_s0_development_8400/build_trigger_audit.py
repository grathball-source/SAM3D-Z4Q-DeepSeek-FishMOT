"""Publish a nonpixel account of every prediction-only scan opportunity."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    scan=json.loads((HERE/'private_source/scan_v4.json').read_text(encoding='utf-8'))
    public=HERE/'dry_run_v6/public'
    events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8'))['B-HOLD-S0']
    selected=set(json.loads((public/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))['selected_episodes'])
    by_start={e['suspect_frame']:e for e in events}
    result=[]
    for suspect in scan['suspects']:
        frame=suspect['frame']
        event=by_start.get(frame)
        active=next((e['id'] for e in events if e['suspect_frame']<frame<=e['end']),None)
        reason=(None if event else 'ANOTHER_EVENT_ACTIVE' if active else
                'LIVE_REFERENCE_PRECONDITION_NOT_MET')
        result.append(dict(frame=frame,sources=suspect['sources'],
            route=suspect['selection_route'],donor=suspect['donor'],group=suspect['group'],
            direct_mask_transfer=suspect['coverage'][str(suspect['donor'])],
            area_ratio=round(suspect['donor_area']/suspect['donor_reference_area'],4),
            candidate_count_change=[suspect['previous_count'],suspect['current_count']],
            live_event_id=event['id'] if event else None,
            not_started_reason=reason,overlapping_event=active,
            confirm_frame=event['confirm_frame'] if event else None,
            first_split_q=event['q'] if event else None,
            outcome=event['status'] if event else 'NOT_STARTED',
            selected_for_model_if_authorized=bool(event and event['id'] in selected)))
    assert len(result)==15 and len(events)==13
    assert sum(x['first_split_q'] is not None for x in result)==9
    assert sum(x['selected_for_model_if_authorized'] for x in result)==8
    out=dict(status='PREDICTION_ONLY_SCAN_AND_CAUSAL_DRY_REPLAY',
             frames=8400,suspects=15,started=13,first_split_q=9,
             selected_by_confirmation=8,http_attempts=0,events=result,
             warning='suspect and q do not themselves prove physical identity or model benefit')
    path=public/'TRIGGER_AUDIT.json'
    with path.open('x',encoding='utf-8') as handle:
        json.dump(out,handle,ensure_ascii=False,indent=2)
        handle.write('\n')
    print(path)


if __name__=='__main__':
    main()
