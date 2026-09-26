"""Index every source fact in already-frozen public episode facts."""
import argparse
import json
from pathlib import Path


def main(run):
    episodes=json.loads((run/'EPISODE_FACTS.json').read_text(encoding='utf-8'))
    facts=[]
    for p in episodes:
        case=p['request_id'].split('-')[-1]
        obs=[]
        for part in ('PRE_HISTORY','POST_HISTORY_TO_Q'):
            obs.extend(o for segment in p[part].values() for o in segment['observations'])
        for row in p['INTERACTION_OBSERVATIONS']:
            for o in row['anonymous_observations']:
                o={**o,'source_frame':row['frame'],'source_time_seconds':row['time_seconds']}
                obs.append(o)
        for o in obs:
            for source in o['source_fact_ids']:
                facts.append(dict(case=case,source_fact_id=source,observed_fact_id=o['fact_id'],
                                  frame=o['source_frame'],time_seconds=o['source_time_seconds'],
                                  source_mask_rle_sha256=o['source_mask_rle_sha256']))
    assert len({(x['case'],x['source_fact_id']) for x in facts})==len(facts)
    out=run/'SOURCE_FACT_MANIFEST.json'
    assert not out.exists()
    out.write_text(json.dumps(dict(status='SOURCE_FACTS_INDEXED_FROM_FROZEN_EPISODES',
        source='actual predicted observation and assignment streams checked by preflight and depth audit',
        facts=facts),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('source facts',len(facts))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run)
