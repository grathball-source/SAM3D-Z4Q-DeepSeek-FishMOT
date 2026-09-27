"""Postseal descriptive audit; never upgrades an invalid frozen response."""
import argparse
import json
from pathlib import Path

import score
from build import read, save, sha


def normalized_assessments(value):
    if isinstance(value,list):
        entries=value
        forms={next((k for k in ('id','hypothesis_id','hypothesis') if k in x),'missing')
               for x in entries if isinstance(x,dict)}
        shape='list_'+','.join(sorted(forms))
    elif isinstance(value,dict):
        entries=[dict(x,id=k) if isinstance(x,dict) else {} for k,x in value.items()]
        shape='dict_by_label'
    else:entries=[];shape=type(value).__name__
    return entries,shape


def main(root):
    root=Path(root);public=root/'public'
    logical={x['attempt_id']:x for x in read(public/'REQUESTS_LOGICAL.json')['requests']}
    scored={x['attempt_id']:x for x in read(public/'ATTEMPT_RESULTS.json')}
    bindings=read(public/'REFERENCE_BINDING.json')
    leaks=[]
    for case in sorted(bindings):
        p=json.loads(logical[case+'-E']['text'])
        for section,roles in (('PRE_HISTORY','AB'),('POST_HISTORY_TO_Q','XY')):
            for role in roles:
                segment=p[section][role];retained=[x['source_frame'] for x in segment['observations']]
                if segment.get('anchor_frame') not in retained:
                    leaks.append(dict(case=case,section=section,role=role,
                        stale_anchor_frame=segment['anchor_frame'],retained_endpoint_frame=retained[0]))
    assert len(leaks)==10 and all(x['section']=='POST_HISTORY_TO_Q' for x in leaks)
    save(public/'POSTSTOP_SOURCE_FAILURE_AUDIT.json',dict(status='ENGINEERING_FAILURE_STOP',
        issue='E_ENDPOINT_ANCHOR_LEAK',acceptance_false_positive=True,
        prior_acceptance_sha256=sha(public/'END_TO_END_ACCEPTANCE.json'),
        discovered_phase='postfreeze_readonly_audit',
        affected_E_requests=5,stale_post_role_fields=leaks,
        effect=('E carries an earlier post-fragment anchor while retaining only the q observation. '
                'The E-to-history ablation is not endpoint-only; no paired gain or method gate can be used.'),
        response_policy='stop new START; let sole in-flight request finish; retain all original bodies and responses'))
    rows=[]
    for attempt,request in logical.items():
        scored_row=scored[attempt];packet=json.loads(request['text'])
        path=public/'responses'/(attempt+'.json')
        if not path.exists():
            rows.append(dict(attempt_id=attempt,state='UNSENT',raw_choice=None,
                             reference_scoreable=bindings[request['case']]['reference_scoreable']))
            continue
        response=read(path);data=json.loads(response['content']);choice=data.get('preferred_hypothesis')
        assessments,shape=normalized_assessments(data.get('hypothesis_assessments'))
        allowed=score.fact_ids(packet);cited=[];malformed=[]
        for entry in assessments:
            if not isinstance(entry,dict):malformed.append('NOT_OBJECT');continue
            for field in ('supporting_fact_ids','conflicting_fact_ids'):
                values=entry.get(field)
                if not isinstance(values,list):malformed.append(field+'_NOT_LIST')
                else:cited.extend(values)
        invalid=sorted({x for x in cited if not isinstance(x,str) or x not in allowed},key=str)
        candidate=next((x['mapping'] for x in packet['hypotheses'] if x['id']==choice),None)
        correct=bindings[request['case']]['correct_physical_mapping']
        raw_alignment=None if candidate is None or correct is None else score.canonical(candidate)==score.canonical(correct)
        rows.append(dict(attempt_id=attempt,state='RETURNED',finish_reason=response['finish_reason'],
            raw_choice=choice,assessment_shape=shape,strict_scorer_status=scored_row['status'],
            strict_parseable=scored_row['parseable'],strict_usable=scored_row['usable'],
            cited_count=len(cited),invalid_fact_ids=invalid,malformed_citation_fields=malformed,
            citation_id_membership_only=('PASS' if not invalid and not malformed else 'FAIL'),
            raw_physical_choice=candidate,raw_alignment_to_posthoc_reference_ONLY_UNSCORED=raw_alignment,
            reference_scoreable=bindings[request['case']]['reference_scoreable'],
            semantic_support_review='NOT_FULLY_VERIFIED_NO_IDENTITY_CERTIFICATE'))
    save(public/'RAW_RESPONSE_AUDIT.json',dict(status='DESCRIPTIVE_POSTSEAL_NOT_A_SCORER_REPAIR',
        formal_returned=sum(x['state']=='RETURNED' for x in rows),strict_parseable=sum(x.get('strict_parseable',False) for x in rows),
        invalid_fact_citation_attempts=sum(bool(x.get('invalid_fact_ids')) for x in rows),
        rows=rows,notes=('Aliases such as hypothesis_id and dictionary assessments are recorded but not retroactively '
                          'accepted by the frozen scorer. Raw label alignment is not a valid method outcome.')))
    print(dict(stale_E_anchors=len(leaks),returned=sum(x['state']=='RETURNED' for x in rows),
               invalid_fact_citation_attempts=sum(bool(x.get('invalid_fact_ids')) for x in rows)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    main(parser.parse_args().root)
