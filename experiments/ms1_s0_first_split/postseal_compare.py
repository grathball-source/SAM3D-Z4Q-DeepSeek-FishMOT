"""Read-only comparison with the separately sealed fifth-frame MS1-R run."""
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
CURRENT=HERE/'run_ms1s0_20260928/public'
OLD=HERE.parent/'ms1r_observation_state_repair/run_ms1r_20260928/public'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as handle:
        yield from map(json.loads,handle)


def check(public):
    seal=read(public/'PREDICTIONS_SEALED.json')
    raw=(public/'predictions_validation.jsonl.gz').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==seal['predictions_sha256']


def main():
    check(CURRENT)
    check(OLD)
    changed=Counter()
    first={}
    for new,old in zip(rows(CURRENT/'predictions_validation.jsonl.gz'),
                       rows(OLD/'predictions_validation.jsonl.gz'),strict=True):
        assert new['frame']==old['frame']
        for n,o in (('B-HOLD-S0','B-HOLD-R'),('B-VLM-S0','B-VLM-R')):
            if new['variants'][n]!=old['variants'][o]:
                changed[n]+=1
                first.setdefault(n,new['frame'])
    output=dict(status='POSTSEAL_READ_ONLY',old_prediction_sha256=read(OLD/'PREDICTIONS_SEALED.json')['predictions_sha256'],
                new_prediction_sha256=read(CURRENT/'PREDICTIONS_SEALED.json')['predictions_sha256'],
                changed_frames=dict(changed),first_changed_frame=first,
                old_q=read(OLD/'EVENTS.json')['B-VLM-R'][0]['q'],
                new_q=read(CURRENT/'EVENTS.json')['B-VLM-S0'][0]['q'])
    target=CURRENT/'OLD_MS1R_COMPARISON.json'
    assert not target.exists()
    target.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(output))


if __name__=='__main__':
    main()
