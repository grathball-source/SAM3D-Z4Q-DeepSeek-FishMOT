"""Document the open final START without altering the original call ledger."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE/'run_development_v7_paid'
PUBLIC = RUN/'public'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ledger = PUBLIC/'CALL_LEDGER.jsonl'
    rows = [json.loads(x) for x in ledger.read_text(encoding='utf-8').splitlines()]
    starts = [x for x in rows if x['phase'] == 'START']
    ends = [x for x in rows if x['phase'] == 'END']
    open_tags = sorted(set(x['tag'] for x in starts)-set(x['tag'] for x in ends))
    assert len(starts) == 16 and len(ends) == 15 and open_tags == ['MS1-F5927-S0']
    assert not (RUN/'private_api/MS1-F5927-S0.raw.json').exists()
    assert not (PUBLIC/'responses/MS1-F5927-S0.json').exists()
    assert not (PUBLIC/'PREDICTIONS_SEALED.json').exists()
    published = sum(1 for _ in (PUBLIC/'PUBLISH_LEDGER.jsonl').open(encoding='utf-8'))
    assert published == 5914
    result = dict(status='ORIGINAL_PROCESS_INTERRUPTED_UNSEALED',
                  recorded_at_utc=datetime.now(timezone.utc).isoformat(),
                  inference_start_count=16,confirmed_end_count=15,
                  open_start_tags=open_tags,open_start_http_outcome='UNKNOWN',
                  no_retry_or_fabricated_end=True,
                  original_published_prefix_frames=published,
                  final_raw_response_exists=False,final_public_response_exists=False,
                  original_prediction_seal_exists=False,
                  freeze_sha256=sha(PUBLIC/'FREEZE.json'),call_ledger_sha256=sha(ledger),
                  recovery='run_development_v7_recovery; recorded responses only; zero new HTTP')
    target = PUBLIC/'INTERRUPTION_RECORD.json'
    with target.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('freeze_sha256','call_ledger_sha256')}))


if __name__ == '__main__':
    main()
