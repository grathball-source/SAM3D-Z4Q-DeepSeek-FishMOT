"""Distinguish observed contact proxy from a verified online hard-event trigger."""
import argparse
import json
from pathlib import Path


def main(run):
    episodes=json.loads((run/'EPISODE_FACTS.json').read_text())
    rows=[]
    for p in episodes:
        t=p['trigger']
        rows.append(dict(case=p['request_id'].split('-')[-1],fixed_trigger_frame=t['frame'],
                         predicted_pair_contact_proxy=t['pair_contact_predicted'],
                         full_prediction_driven_difficult_trigger='NOT_VERIFIED',
                         analysis_role='OFFLINE_DIAGNOSTIC_CONTROL',
                         reason='No full online Z4Q hard-event gate was executed or logged for this frozen event package.'))
    out=run/'TRIGGER_SCOPE_AUDIT.json';assert not out.exists()
    out.write_text(json.dumps(dict(status='PROXY_ONLY_ALL_FIVE',cases=rows),indent=2)+'\n')
    print('proxy',sum(x['predicted_pair_contact_proxy'] for x in rows),'strict_trigger_verified',0)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run)
