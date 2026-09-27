"""Real-source B01 slice and synthetic transport/scorer metamorphic regressions."""
import argparse
import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import score
import sender
import validate
from build import read, save, sha


def reject(fn):
    try:fn()
    except (AssertionError,ValueError,KeyError,FileNotFoundError):return True
    raise AssertionError('negative fixture unexpectedly accepted')


def response(packet,choice='H1',support=None):
    fact=support or packet['PRE_HISTORY']['A']['observations'][-1]['fact_id']
    assessments=[dict(id=h,supporting_fact_ids=[fact] if h==choice else [],
                      conflicting_fact_ids=[] if h==choice else [fact],
                      unresolved_assumptions=['contact identity is unresolved']) for h in ('H1','H2')]
    return dict(request_id=packet['request_id'],hypothesis_assessments=assessments,
        preferred_hypothesis=choice,uncertainty_reason='insufficient evidence' if choice=='DEFER' else '')


def fixture_chain(run,tmp):
    """No paid call: 25 real B01+negative bodies use synthetic file IDs."""
    tmp=Path(tmp);public=tmp/'public';send=tmp/'send';public.mkdir();send.mkdir()
    for name in ('REQUESTS_LOGICAL.json','REQUEST_MANIFEST.json','SOURCE_TO_BODY_AUDIT.json',
                 'PLAN.json','SENDER_GATE.json','BUDGET.json'):
        shutil.copyfile(run/'public'/name,public/name)
    logical=read(public/'REQUESTS_LOGICAL.json')['requests']
    digests=sorted({image['sha256'] for request in logical for image in request['images']})
    ids={digest:'file-api-TEST-FIXTURE-'+str(i) for i,digest in enumerate(digests)}
    upload=[]
    for digest in digests:
        upload += [dict(phase='START',sha256=digest),dict(phase='END',sha256=digest,file_id=ids[digest])]
    (send/'UPLOAD_LEDGER.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in upload))
    (send/'bodies').mkdir()
    records=[]
    for request in logical:
        data=sender.wire(sender.body(request,ids));attempt=request['attempt_id']
        (send/'bodies'/(attempt+'.json')).write_bytes(data)
        records.append(dict(attempt_id=attempt,payload_sha256=hashlib.sha256(data).hexdigest(),payload_bytes=len(data)))
    save(public/'BODY_GATE.json',dict(bodies=dict(status='BODY_GATE_PASS',records=records)))
    code={x:sha(Path(__file__).parent/x) for x in ('build.py','validate.py','sender.py','score.py','freeze.py','test_acceptance.py')}
    names=('REQUESTS_LOGICAL.json','REQUEST_MANIFEST.json','SOURCE_TO_BODY_AUDIT.json',
           'PLAN.json','SENDER_GATE.json','BUDGET.json','BODY_GATE.json')
    save(public/'CODE_AND_INPUT_LOCK.json',dict(code_sha256=code,input_sha256={x:sha(public/x) for x in names}))
    save(public/'REQUESTS_SEALED.json',dict(status='ALL_25_BODIES_FROZEN_BEFORE_FORMAL',
        at='2026-09-27T00:00:00+00:00',logical_sha256=sha(public/'REQUESTS_LOGICAL.json'),
        manifest_sha256=sha(public/'REQUEST_MANIFEST.json'),lock_sha256=sha(public/'CODE_AND_INPUT_LOCK.json'),
        body_gate_sha256=sha(public/'BODY_GATE.json'),records=records))
    request=next(x for x in logical if x['attempt_id']=='B01-H-D');packet=json.loads(request['text'])
    synthetic=dict(attempt_id='B01-H-D',transport_valid=True,finish_reason='stop',
        content=json.dumps(response(packet)),usage={'prompt_tokens':1,'completion_tokens':1},charged_upper_usd=.000001)
    save(public/'responses/B01-H-D.json',synthetic)
    ledger=[dict(phase='START',at='2026-09-27T00:00:01+00:00',attempt_id='B01-H-D',
                 payload_sha256=next(x['payload_sha256'] for x in records if x['attempt_id']=='B01-H-D')),
            dict(phase='END',at='2026-09-27T00:00:02+00:00',attempt_id='B01-H-D',
                 transport_valid=True,response_sha256=sha(public/'responses/B01-H-D.json'))]
    (public/'CALL_LEDGER.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in ledger))
    save(public/'PARTIAL_RESPONSES_SEALED.json',dict(status='PARTIAL_STOP',
        request_seal_sha256=sha(public/'REQUESTS_SEALED.json'),ledger_sha256=sha(public/'CALL_LEDGER.jsonl')))
    return packet


def main(run):
    run=Path(run);source=Path(read(run/'private/SOURCE_LOCATION.json')['source'])
    old={x['request_id'].split('-')[-1]:x for x in read(source/'EPISODE_FACTS.json')}
    case={x['case_alias']:x for x in read(validate.AO1)['cases']}['B01']
    observed,depth,records=validate.check_source_episode(old['B01'],case['split'])
    assert old['B01']['PRE_HISTORY']['A']['velocity']['epistemic_type']=='UNKNOWN'
    assert len(old['B01']['PRE_HISTORY']['A']['observations'])==1
    assert old['B01']['q_frame']==1498 and len(records)>1000
    logical=read(run/'public/REQUESTS_LOGICAL.json')['requests']
    b01=[x for x in logical if x['case']=='B01'];assert len(b01)==5
    assert all(x['arm'] in ('E','H-2D','H-D','H-D-REPEAT','H-D-PERMUTE') for x in b01)
    checks=['B01_REAL_SOURCE_ROLE_FRAGMENT_CONDITION']
    with tempfile.TemporaryDirectory(prefix='ehr1rc_fixture_') as name:
        tmp=Path(name);packet=fixture_chain(run,tmp)
        old_root=score.OLD;score.OLD=source
        try:
            chain=score.verify_chain(tmp);assert chain['full'] is False
            binding=dict(reference_scoreable=True,correct_physical_mapping=packet['hypotheses'][0]['mapping'])
            normal=dict(transport_valid=True,finish_reason='stop',content=json.dumps(response(packet)))
            assert score.classify(normal,packet,binding)['status']=='CORRECT'
            swapped=copy.deepcopy(packet)
            for h in swapped['hypotheses']:h['id']='H2' if h['id']=='H1' else 'H1'
            swapped['hypotheses'].reverse()
            same=dict(normal,content=json.dumps(response(swapped,'H2')))
            assert score.classify(same,swapped,binding)['status']=='CORRECT'
            assert score.classify(normal,swapped,binding)['status']=='WRONG'
            reordered=copy.deepcopy(packet);reordered['hypotheses'].reverse()
            assert score.classify(normal,reordered,binding)['status']=='CORRECT'
            u=copy.deepcopy(packet);u['hypotheses'][0]['mapping']['U1']='B'
            assert score.classify(normal,u,binding)['status']=='WRONG'
            assert score.classify(dict(normal,content=json.dumps(response(packet,'DEFER'))),packet,binding)['status']=='DEFER'
            bad=response(packet);bad['hypothesis_assessments'][0]['supporting_fact_ids']=['NONEXISTENT']
            assert score.classify(dict(normal,content=json.dumps(bad)),packet,binding)['status']=='INVALID_EVIDENCE'
            assert score.classify(dict(normal,content='{broken'),packet,binding)['status']=='UNPARSEABLE'
            assert score.classify(dict(normal,finish_reason='length'),packet,binding)['status']=='TRUNCATED'
            assert score.classify(normal,packet,dict(reference_scoreable=False,correct_physical_mapping=None))['status']=='UNSCORABLE_NEW_REFERENCE'
            checks += ['SYNTHETIC_BODY_START_RESPONSE_END_SEAL_SCORER','PHYSICAL_PERMUTE_REPEAT_REORDER_U',
                       'DEFER_BAD_CITATION_UNPARSEABLE_TRUNCATED_UNSCORABLE']
            public=tmp/'public';body_path=tmp/'send/bodies/B01-H-D.json'
            original=body_path.read_bytes();body_path.write_bytes(original+b' ')
            assert reject(lambda:score.verify_chain(tmp));body_path.write_bytes(original)
            original=(public/'CALL_LEDGER.jsonl').read_text()
            forged=original.replace(chain['starts']['B01-H-D']['payload_sha256'],'0'*64)
            (public/'CALL_LEDGER.jsonl').write_text(forged)
            assert reject(lambda:score.verify_chain(tmp));(public/'CALL_LEDGER.jsonl').write_text(original)
            original=(public/'REQUESTS_LOGICAL.json').read_bytes()
            (public/'REQUESTS_LOGICAL.json').write_bytes(original+b' ')
            assert reject(lambda:score.verify_chain(tmp));(public/'REQUESTS_LOGICAL.json').write_bytes(original)
            original=(public/'responses/B01-H-D.json').read_bytes()
            (public/'responses/B01-H-D.json').write_bytes(original+b' ')
            assert reject(lambda:score.verify_chain(tmp));(public/'responses/B01-H-D.json').write_bytes(original)
            assert score.verify_chain(tmp)['starts']['B01-H-D']['phase']=='START'
            checks.append('SCORE_REJECTS_BODY_START_LOGICAL_RESPONSE_TAMPER')
        finally:score.OLD=old_root
    # The independent preflight must reject actual logical-body mutations, not merely a producer copy.
    with tempfile.TemporaryDirectory(prefix='ehr1rc_mutation_') as name:
        tmp=Path(name);(tmp/'public').mkdir();(tmp/'private').symlink_to(run/'private',target_is_directory=True)
        for filename in ('REQUESTS_LOGICAL.json','REQUEST_MANIFEST.json'):
            shutil.copyfile(run/'public'/filename,tmp/'public'/filename)
        request_path=tmp/'public/REQUESTS_LOGICAL.json';original=request_path.read_text()
        for mutate in ('missing_depth_quality','wrong_fact_reference','post_q_image','changed_median'):
            requests=json.loads(original);request=next(x for x in requests['requests'] if x['attempt_id']=='B01-H-D')
            p=json.loads(request['text'])
            if mutate=='missing_depth_quality':
                index=p['INTERACTION_TABLE']['columns'].index('depth_core_mad')
                p['INTERACTION_TABLE']['columns'].pop(index)
                for row in p['INTERACTION_TABLE']['rows']:row.pop(index)
            elif mutate=='wrong_fact_reference':p['IMAGE_INDEX'][2]['anonymous_tokens'][0]['fact_id']='NONEXISTENT'
            elif mutate=='post_q_image':p['IMAGE_INDEX'][0]['frame']=p['q_frame']+1
            else:
                index=p['INTERACTION_TABLE']['columns'].index('depth_median_pipeline_mm')
                p['INTERACTION_TABLE']['rows'][0][index]=123456.0
            request['text']=json.dumps(p,ensure_ascii=False,separators=(',',':'))
            request_path.write_text(json.dumps(requests))
            assert reject(lambda:validate.check_projection(tmp)),mutate
        checks.append('SENDER_PREFLIGHT_REJECTS_DEPTH_REFERENCE_POST_Q_AND_VALUE_TAMPER')
    # Gates are keyed by case names, never event order, and reject every invalid negative state.
    bindings={f'B{i:02d}':dict(reference_scoreable=True) for i in range(1,6)}
    attempts=[dict(case=f'B{i:02d}',arm=arm,status='CORRECT',transport_valid=True,
                   finish_reason='stop',parseable=True,usable=True)
              for i in range(1,6) for arm in ('E','H-2D','H-D','H-D-REPEAT','H-D-PERMUTE')]
    for row in attempts:
        if row['case']=='B01' and row['arm']=='E':row['status']='DEFER'
    assert score.summary(attempts,bindings,True)['limited_exposed_signal']
    assert score.summary(list(reversed(attempts)),bindings,True)['limited_exposed_signal']
    for change in (dict(status='UNPARSEABLE',parseable=False),dict(status='UNSCORABLE_NEW_REFERENCE'),
                   dict(status='INVALID_EVIDENCE',usable=False),dict(status='HTTP_UNKNOWN',transport_valid=False),
                   dict(status='TRUNCATED',finish_reason='length'),dict(status='UNSENT',transport_valid=False)):
        altered=copy.deepcopy(attempts)
        next(x for x in altered if x['case']=='B03' and x['arm']=='H-D').update(change)
        assert score.summary(altered,bindings,True)['negative_HD_safe'] is False,change
    checks.append('NEGATIVE_GATE_INVALID_UNSCORABLE_UNKNOWN_UNSENT_REORDER')
    tests=dict(status='PASS',fixture='TEST_FIXTURE_NO_MODEL_CALL',checks=checks)
    test_path=run/'public/SCORER_METAMORPHIC_TESTS.json'
    if test_path.exists():assert read(test_path)==tests
    else:save(test_path,tests)
    acceptance=dict(status='PASS',fixture='TEST_FIXTURE_NO_MODEL_CALL',
        B01=dict(q=1498,A_pre_frames=1,A_velocity='UNKNOWN',source_observations=len(records),
                 arms=[x['arm'] for x in b01]),all_cases=5,logical_requests=25,
        source_audit_sha256=sha(run/'public/SOURCE_TO_BODY_AUDIT.json'),
        scorer_tests_sha256=sha(test_path))
    accept_path=run/'public/END_TO_END_ACCEPTANCE.json'
    if accept_path.exists():assert read(accept_path)==acceptance
    else:save(accept_path,acceptance)
    print(dict(status='PASS',tests=len(checks),cases=5,requests=25))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True)
    main(parser.parse_args().run)
