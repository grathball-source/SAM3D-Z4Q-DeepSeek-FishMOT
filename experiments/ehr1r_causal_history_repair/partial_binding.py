"""Post-partial-seal GT audit of new reference meaning, with no trial score."""
import argparse
from pathlib import Path

from score import AO1,bind,read,save,sha


def main(run):
    seal=read(run/'PARTIAL_RESPONSES_SEALED.json')
    assert seal['status']=='PARTIAL_SOURCE_CONTRACT_FAILURE_STOP'
    assert seal['request_seal_sha256']==sha(run/'REQUESTS_SEALED.json')
    assert seal['call_ledger_sha256']==sha(run/'CALL_LEDGER.jsonl')
    key={x['case_alias']:x for x in read(AO1/'SCORE_KEY.json')['cases']}
    source={x['case_alias']:x for x in read(AO1/'SOURCE_MANIFEST.json')['cases']}
    episodes={x['request_id'].split('-')[-1]:x for x in read(run/'EPISODE_FACTS.json')}
    results={c:bind(p,source[c]['split'],key[c]) for c,p in episodes.items()}
    save(run/'CASE_SCORE_BINDING.json',dict(status='POST_PARTIAL_SEAL_REFERENCE_DIAGNOSTIC_ONLY',
         trial_scoring='NOT_PERFORMED_SOURCE_CONTRACT_FAILURE',cases=results))
    print([(c,r['score_answer'],r['old_answer_relation']) for c,r in results.items()])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run)
