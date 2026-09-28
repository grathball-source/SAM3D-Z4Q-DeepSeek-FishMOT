"""Bind the frozen source, actual bodies, sealed responses and scores."""
import hashlib
import json
import shutil
from pathlib import Path

from provider import PRICE_INPUT,PRICE_OUTPUT,write_new
from replay import HERE,OBS,PROFILES,ARCHIVED,rows,read,sha


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()


def inventory_file(path):
    path=Path(path).resolve()
    return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))


def main():
    output=HERE/'run_ms1r_20260928'
    public=output/'public'
    freeze=read(public/'FREEZE.json')
    seal=read(public/'PREDICTIONS_SEALED.json')
    assert freeze['status']=='FROZEN_BEFORE_FIRST_REQUEST'
    assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
    for name,expected in freeze['code_sha256'].items():
        assert sha(HERE/name)==expected,name
    for path,info in freeze['source_sha256'].items():
        assert sha(path)==info['sha256'] and Path(path).stat().st_size==info['bytes']
    for name,key in [('predictions_validation.jsonl.gz','predictions_sha256'),
                     ('TRANSACTIONS.jsonl.gz','transactions_sha256'),('EVENTS.json','events_sha256'),
                     ('CALL_LEDGER.jsonl','call_ledger_sha256')]:
        assert sha(public/name)==seal[key]
    ledger=[json.loads(x) for x in (public/'CALL_LEDGER.jsonl').read_text().splitlines()]
    assert [x['phase'] for x in ledger]==['START','END','START','END']
    assert len({x['tag'] for x in ledger})==2 and seal['http_attempts']==2
    charges=[]
    reference_audit={}
    copied=[]
    episode=read(public/'EVENTS.json')['B-VLM-R'][0]
    target=public/'model_geometry'
    target.mkdir(exist_ok=False)
    for start,end in ((ledger[0],ledger[1]),(ledger[2],ledger[3])):
        tag=start['tag']
        packet=read(public/'requests'/f'{tag}.json')
        body=read(output/'private_api'/f'{tag}.body.json')
        response=read(public/'responses'/f'{tag}.json')
        raw=output/'private_api'/f'{tag}.raw.json'
        assert digest(canonical(packet))==start['public_packet_sha256']
        assert digest(canonical(body))==start['body_sha256']
        assert body['messages'][0]['content']==packet['system']
        assert body['messages'][1]['content'][0]['text']==packet['user']
        assert len(body['messages'][1]['content'])-1==len(packet['images'])
        assert all(part['type']=='file' and part['file_id'].startswith('file-api-')
                   for part in body['messages'][1]['content'][1:])
        assert all(x not in packet['user'] for x in ('file-api-','gt_grid','native_id','public_id'))
        assert sha(raw)==response['raw_private_sha256']
        assert sha(public/'responses'/f'{tag}.json')==end['response_sha256']
        assert response['finish_reason']=='stop'
        usage=response['usage']
        upper=(usage['prompt_tokens']*PRICE_INPUT+usage['completion_tokens']*PRICE_OUTPUT)/1_000_000
        assert abs(upper-response['peak_charge_upper_usd'])<1e-10
        charges.append(upper)
        for image in packet['images']:
            episode_id,stage=tag.rsplit('-',1)
            assert image['frame'] <= (episode['confirm_frame'] if stage=='M' else episode['q'])
            source=Path(output/'private_source/geometry'/f'{episode_id}_{stage}_{image["phase"]}_{image["frame"]}.png')
            assert source.is_file() and sha(source)==image['sha256']
            dest=target/source.name
            shutil.copyfile(source,dest)
            assert sha(dest)==image['sha256']
            copied.append(dict(file=str(dest.relative_to(public)),bytes=dest.stat().st_size,
                               sha256=image['sha256'],frame=image['frame'],phase=image['phase'],
                               bindings=image['bindings']))
        if tag.endswith('-S'):
            try:
                obj=json.loads(response['content'])
                refs=obj.get('evidence_refs') or [] if isinstance(obj,dict) else []
            except (TypeError,ValueError):
                refs=[]
            reference_audit=dict(citations=refs,all_exist=all(x in packet['user'] for x in refs),
                                 missing=[x for x in refs if x not in packet['user']],
                                 note='Reference existence does not establish the interpretation or physical correctness.')
    assert sum(charges)==seal['peak_charge_upper_usd'] and sum(charges)<freeze['budget_usd']
    score=read(public/'METRICS.json')
    assert score['source_prediction_sha256']==seal['predictions_sha256']
    provenance=read(public/'SCORE_PROVENANCE.json')
    assert provenance['scorer_sha256']==sha(HERE/'score.py')
    assert provenance['original_scorer_sha256']==sha(HERE.parents[1]/'online/closed_loop_2888/score.py')
    assert provenance['scored_after_seal']
    write_new(public/'MODEL_GEOMETRY_MANIFEST.json',dict(images=copied,geometry_only=True,
                                                          no_rgb_no_gt=True))
    write_new(public/'RESPONSE_REFERENCE_AUDIT.json',reference_audit)
    private=[]
    for path in sorted(HERE.rglob('*')):
        if not path.is_file():
            continue
        rel=path.relative_to(HERE).as_posix()
        if 'private_source/' in rel or 'private_api/' in rel:
            private.append(inventory_file(path))
    private.extend(inventory_file(p) for p in (OBS,PROFILES,ARCHIVED,
        HERE.parent/'merge_split_identity_memory/private_source/assignments.jsonl.gz',
        HERE.parent/'merge_split_identity_memory/private_source/scan.json',
        HERE.parent/'merge_split_identity_memory/private_source/offline_matches_validation.jsonl.gz'))
    write_new(public/'RESTRICTED_INVENTORY.json',dict(local_restricted=private,
        remote_scoring_dependencies='See REMOTE_RESTRICTED_INVENTORY.json',
        reproduction='Run source_scan.py and test_ms1r.py with listed prediction-only inputs; replay.py real is single-use and must not be rerun; score.py requires sealed predictions and exposed validation GT only after seal.'))
    report=dict(status='PASS_SEALED_CHAIN_AND_SCORE',source_files=len(freeze['source_sha256']),
                calls=2,peak_charge_upper_usd=sum(charges),images_sent=len(copied),
                unique_image_sha256=len({x['sha256'] for x in copied}),
                response_refs=reference_audit,restricted_local_files=len(private),
                prediction_sha256=seal['predictions_sha256'],metrics_sha256=sha(public/'METRICS.json'))
    write_new(public/'ACCEPTANCE.json',report)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    main()
