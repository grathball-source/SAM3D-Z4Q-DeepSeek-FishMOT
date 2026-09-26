"""Per-event separation of raw choices, missing calls, and invalid trial score."""
import argparse
import json
from pathlib import Path


def read(p):return json.loads(Path(p).read_text())


def main(run):
    audit=read(run/'RAW_RESPONSE_AUDIT.json');binding=read(run/'CASE_SCORE_BINDING.json')['cases']
    numeric=read(run/'NUMERIC_REFERENCE.json');scope={x['case']:x for x in read(run/'TRIGGER_SCOPE_AUDIT.json')['cases']}
    episodes={x['request_id'].split('-')[-1]:x for x in read(run/'EPISODE_FACTS.json')}
    rows=[]
    for case in sorted(episodes):
        p=episodes[case];arms={x['arm']:x for x in audit if x['case']==case}
        rows.append(dict(case=case,source_contract_v5='FAIL_ANONYMOUS_DEPTH_QUALITY',
             predicted_pair_contact_proxy=scope[case]['predicted_pair_contact_proxy'],
             strict_prediction_driven_hard_trigger=scope[case]['full_prediction_driven_difficult_trigger'],
             analysis_role=scope[case]['analysis_role'],
             old_to_new_reference=p['old_to_new_reference'],
             posthoc_new_reference_answer=binding[case]['score_answer'],
             posthoc_old_answer_relation=binding[case]['old_answer_relation'],
             N_H2D=numeric[case]['N_H2D']['choice'],N_HD=numeric[case]['N_HD']['choice'],
             N_HD_depth_mode=numeric[case]['N_HD']['depth_mode'],
             arms={a:dict(transport=v['status'],raw_choice=v['raw_choice'],parseable=v['parseable'],
                          citation_legal=v['citation_legal'],evidence_errors=v['evidence_errors'],
                          correct=None,wrong=None,abstention_as_valid_trial=None,
                          score_bucket='UNSCORABLE_SOURCE_CONTRACT') for a,v in arms.items()}))
    out=run/'EVENT_RESULTS.json';assert not out.exists()
    out.write_text(json.dumps(dict(status='NO_VALID_PAIRED_TRIAL_SCORE',cases=rows),ensure_ascii=False,indent=2)+'\n')
    print('event results',len(rows))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run)
