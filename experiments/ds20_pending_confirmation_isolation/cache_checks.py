"""Real source-to-cache contracts, including re-signed semantic corruption."""
from common import *
from runner import validate_cached_frame
from bridge import stream
from mixed_depth import _seal, _digest
import copy
import argparse


def signed(packet, ledger):
    packet=copy.deepcopy(packet);ledger=copy.deepcopy(ledger)
    shared={k:packet[k] for k in ('segment','frame','global_frame','time','source_binding',
        'actual_depth_binding','actual_source_index_binding','native_depth_binding')}
    packet['frame_binding_sha256']=_digest(shared)
    for c in packet['objects'].values():
        c['frame_binding_sha256']=packet['frame_binding_sha256']
        _seal(c)
    ledger['mixed_row_sha256']=hashlib.sha256((json.dumps(packet,separators=(',',':'),
        allow_nan=False)+'\n').encode()).hexdigest()
    return packet,ledger


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='CACHE_CHECKS.json');args=parser.parse_args()
    target=HERE/args.output
    assert target.resolve().parent==HERE.resolve() and not target.exists()
    checks={};negative={};example=None
    for name in SEGMENTS:
        reference=cache_reference(name)
        base=input_dir(name)
        src=stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz',reference['frames'])
        measured=rows(base/'DEPTH_OBSERVATIONS.jsonl.gz')
        assignment=rows(base/'assignments.jsonl.gz')
        packets=rows(reference['source']['path']);ledgers=rows(reference['source_ledger']['path'])
        verified=[]
        for _ in range(3):
            row,profiles=next(src);m=next(measured);a=next(assignment);p=next(packets);l=next(ledgers)
            facts,digest=validate_cached_frame(p,l,row,m,profiles,a)
            verified.append(dict(frame=row['frame'],objects=len(facts),mixed_row_sha256=digest))
            if example is None:example=(row,profiles,m,a,p,l)
        checks[name]=dict(cache=reference,actual_source_checks=verified)
    row,profiles,m,a,p,l=example
    def reject(label,mutate):
        altered=copy.deepcopy(p);mutate(altered)
        altered,ledger=signed(altered,l)
        assert ledger['mixed_row_sha256']!=l['mixed_row_sha256']
        try:validate_cached_frame(altered,ledger,row,m,profiles,a)
        except (AssertionError,KeyError,ValueError) as e:
            negative[label]=dict(status='REJECTED',self_consistent_new_row_hash=True,
                signed_container_and_certificates=True,reason=type(e).__name__+': '+str(e))
        else:raise AssertionError('semantic corruption accepted: '+label)
    reject('future_time',lambda x:x.update(time=x['time']+1))
    reject('different_frame',lambda x:x.update(frame=x['frame']+1))
    reject('wrong_actual_depth_source',lambda x:x['actual_depth_binding'].update(sha256='0'*64))
    first=next(iter(p['objects']))
    reject('wrong_native_certificate',lambda x:x['objects'][first].update(native=99999))
    reject('missing_real_quality',lambda x:x['objects'][first]['whole']['inclusive_summary'].pop('n'))
    # Expected actual mask changes on a test copy, while the valid old cache hash stays intact.
    changed=copy.deepcopy(a)
    from source import native_masks
    actual=native_masks(changed)
    if actual:
        profiles_changed=copy.deepcopy(profiles)
        profiles_changed[int(first)]['frame']+=1
        try:validate_cached_frame(p,l,row,m,profiles_changed,a)
        except AssertionError:
            negative['wrong_actual_profile_frame']=dict(status='REJECTED',original_valid_cache_hash=True)
        else:raise AssertionError('wrong current profile accepted')
    write_new(target,dict(status='PASS',segments=checks,semantic_negative_tests=negative,
        GT_read=False,model_http=0,cost_usd=0,actual_test_sources={str(path):sha(path) for path in (
            HERE/'cache_checks.py',HERE/'common.py',HERE/'runner.py',HERE/'controller.py',DS18/'mixed_depth.py')}))
    print('PASS eight sealed caches; 24 actual frame contracts; six semantic corruptions rejected')


if __name__=='__main__':main()
