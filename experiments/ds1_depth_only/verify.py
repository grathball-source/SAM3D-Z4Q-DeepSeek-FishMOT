"""Verify full native/legacy equality and actual first publication before scoring."""
import hashlib
import json
from pathlib import Path

import score

HERE=Path(__file__).resolve().parent
NE1=HERE.parent/'ne1_native_first_event_association'


def verify():
    run=HERE/'run'
    checked=[]
    q_checks=0
    group_violations=deleted=group_checks=0
    for name,(start,stop) in score.SEGMENTS.items():
        score.verify_seal(run,name,start,stop)
        actual=list(score.records(run/name/'public/predictions.jsonl.gz'))
        old=list(score.records(NE1/'run'/name/'public/predictions.jsonl.gz'))
        assert len(actual)==len(old)==stop-start+1
        for current,archive in zip(actual,old,strict=True):
            assert current['frame']==archive['frame'] and current['global_frame']==archive['global_frame']
            assert current['variants']['SAM3_NATIVE']==archive['variants']['SAM3_NATIVE']
            assert current['variants']['D1_STATIC_LEGACY']==archive['variants']['EVENT_NUM'],(name,current['frame'])
            native=current['variants']['SAM3_NATIVE']
            for arm in score.ARMS[1:]:
                objects=current['variants'][arm]
                deleted+=max(0,len(native)-len(objects))
                assert [x['mask'] for x in objects]==[x['mask'] for x in native]
                assert len(objects)==len(set(x['id'] for x in objects))
        public=run/name/'public'
        events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8'))
        ledger={x['frame']:x for x in map(json.loads,(public/'PUBLISH_LEDGER.jsonl').read_text(encoding='utf-8').splitlines())}
        states={(x['frame'],x['arm']):x for x in score.records(public/'DEPTH_STATES.jsonl.gz')}
        for arm in score.ARMS[1:]:
            for e in events[arm]:
                for group in e['group_observations']:
                    live=states[(group['frame'],arm)]['live'].get(str(group['source']))
                    group_violations+=bool(live and group['frame'] in live['sample_frames'])
                    group_checks+=1
                for frozen in e['depth_frozen'].values():
                    samples=frozen['samples']
                    assert all(s['frame']<e['suspect_frame'] for s in samples)
                    assert all(b['frame']==a['frame']+1 and b['time']>a['time'] for a,b in zip(samples,samples[1:]))
                if e['q'] is None:
                    continue
                q=e['q']
                assert e['evidence_cutoff_frame']==q
                assert all(x['frame']==q for x in e['post_first_observations'].values())
                published=ledger[q]['event_publish'][arm]
                assert published['q']==q and published['post_sample_count']==1
                mapping={int(x['mask'][2:]):x['id'] for x in actual[q-1]['variants'][arm]}
                assert {int(n):k for n,k in published['first_public_pair'].items()}=={
                    int(n):mapping[int(n)] for n in e['post_first_observations']}
                if not e['restore']['status'].startswith('LOCAL_FALLBACK'):
                    assert {int(n):k for n,k in e['restore']['mapping'].items()}=={
                        int(n):mapping[int(n)] for n in e['post_first_observations']}
                    for n in e['post_first_observations']:
                        live=states[(q,arm)]['live'].get(n)
                        assert not live or all(f>=q for f in live['sample_frames'])
                q_checks+=1
        def normalized(branch):
            encoded=json.dumps([x['variants'][branch] for x in actual],separators=(',',':')).encode()
            return hashlib.sha256(encoded).hexdigest()
        checked.append(dict(segment=name,frames=len(actual),native_exact=True,legacy_exact=True,
                            normalized_predictions_sha256={arm:normalized(arm) for arm in score.ARMS}))
    assert group_violations==deleted==0
    result=dict(status='PASS_BEFORE_GT_SCORING',frames=405,segments=checked,
                first_publication_checks=q_checks,group_observation_checks=group_checks,
                group_to_individual_write_violations=group_violations,
                invalid_depth_detection_deletions=deleted,new_model_http=0,model_cost_usd=0)
    score.write_new(run/'VERIFICATION.json',result)
    print(json.dumps(result))


if __name__=='__main__':
    verify()
