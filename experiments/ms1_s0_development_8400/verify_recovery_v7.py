"""Check every previously published row against the completed offline replay."""
import json
from itertools import zip_longest
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE/'run_development_v7_paid/public'
NEW = HERE/'run_development_v7_recovery/public'


def main():
    seal = json.loads((NEW/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
    assert seal['mode'] == 'real_recovered' and seal['new_inference_http'] == 0
    assert seal['frames'] == seal['published_frames'] == 8400
    count = 0
    with (OLD/'PUBLISH_LEDGER.jsonl').open(encoding='utf-8') as old, \
         (NEW/'PUBLISH_LEDGER.jsonl').open(encoding='utf-8') as new:
        for a, b in zip_longest(old, new):
            if a is None:
                break
            assert b is not None
            a, b = json.loads(a), json.loads(b)
            count += 1
            assert a['frame'] == b['frame'] == count
            assert a['prediction_row_sha256'] == b['prediction_row_sha256'], count
            assert a['event_publish'] == b['event_publish'], count
    assert count == 5914, count
    out = dict(status='PASS',matching_original_published_prefix_frames=count,
               full_recovery_frames=seal['frames'],new_inference_http=0)
    with (NEW/'RECOVERY_PREFIX_CHECK.json').open('x', encoding='utf-8') as handle:
        json.dump(out, handle, indent=2)
        handle.write('\n')
    print(json.dumps(out))


if __name__ == '__main__':
    main()
