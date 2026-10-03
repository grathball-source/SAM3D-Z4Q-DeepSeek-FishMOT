"""Necessary semantic checks on a real sealed source endpoint; no tracker or GT."""
import copy
import gzip
import json
from collections import Counter
import audit


def refused(fn):
    try:fn()
    except (AssertionError,KeyError,ValueError):return True
    raise AssertionError('semantic violation was accepted')


def main():
    name='feeding_000000_000199'
    base=audit.old.input_dir(name)
    row=next(audit.old.rows(base/'observations.jsonl.gz'))
    profiles=next(audit.old.rows(base/'profiles.jsonl.gz'))
    measured=next(audit.old.rows(base/'DEPTH_OBSERVATIONS.jsonl.gz'))
    packet=next(audit.old.rows(audit.old.DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz'))
    native=row['observations'][0]['id']
    profile=dict(next(x for x in profiles['observations'] if x['id']==native),frame=profiles['frame'])
    certificate=packet['objects'][str(native)]
    audit.validate_packet(name,row,measured,packet)
    bindings=audit.validate_endpoint(name,row,profile,measured,certificate,cutoff=row['frame'])
    count=1
    changed=copy.deepcopy(row)
    changed['observations'][0]['depth']['median']+=1
    # Recompute a self-consistent caller manifest: semantic source mismatch must still fail.
    new_manifest={'row_sha256':audit.digest(changed),'profile_sha256':audit.digest(profile)}
    assert new_manifest['row_sha256']==audit.digest(changed)
    assert refused(lambda:audit.validate_endpoint(name,changed,profile,measured,certificate));count+=1
    changed_profile=copy.deepcopy(profile);changed_profile['core']['median']+=1
    assert refused(lambda:audit.validate_endpoint(name,row,changed_profile,measured,certificate));count+=1
    future_profile=copy.deepcopy(profile);future_profile['frame']+=1
    self_consistent_profile_manifest={'profile_sha256':audit.digest(future_profile)}
    assert self_consistent_profile_manifest['profile_sha256']==audit.digest(future_profile)
    assert refused(lambda:audit.validate_endpoint(name,row,future_profile,measured,certificate));count+=1
    binding=copy.deepcopy(bindings['BIRTH_CORE'])
    binding['association_role']='D1_WHOLE'
    binding['binding_sha256']=audit.digest({k:v for k,v in binding.items() if k!='binding_sha256'})
    assert not audit.validate_bound_measurement(binding,profile['core'],'D1_WHOLE',certificate);count+=1
    assert refused(lambda:audit.validate_endpoint(name,row,profile,measured,certificate,cutoff=0));count+=1
    action={'native_id':native,'canonical_id':999,'history_depth':123.,'age':1.}
    assert audit.anchor_refs(name,action,row['frame'])=={}
    assert audit.quality_status(True,None)=='UNKNOWN_MISSING_EXACT_OLD_ANCHOR';count+=1
    assert audit.quality_status(True,False)=='CURRENT_ONLY_ELIGIBLE'
    assert audit.quality_status(False,True)=='ANCHOR_ONLY_ELIGIBLE'
    assert audit.quality_status(False,False)=='NEITHER_ELIGIBLE';count+=1
    unknowns=['UNSCORABLE','WRONG','CORRECT']
    assert Counter(unknowns)['CORRECT']==1
    assert sum(x=='CORRECT' for x in unknowns)==1
    assert all(x!='CORRECT' for x in unknowns[:2]);count+=1
    future={'native_id':native,'canonical_id':999,'old_anchor':dict(frame=row['frame'],native_id=native,
        mask=f'n:{native}',canonical_id=999)}
    assert refused(lambda:audit.anchor_refs(name,future,row['frame']));count+=1
    changed_packet=copy.deepcopy(packet)
    changed_packet['objects'][str(native)]['frame_binding_sha256']='0'*64
    changed_certificate=changed_packet['objects'][str(native)]
    changed_certificate['certificate_sha256']=audit.digest({k:v for k,v in changed_certificate.items() if k!='certificate_sha256'})
    self_consistent_manifest={'packet_sha256':audit.digest(changed_packet)}
    assert self_consistent_manifest['packet_sha256']==audit.digest(changed_packet)
    assert refused(lambda:audit.validate_packet(name,row,measured,changed_packet));count+=1
    import visualize
    visual_checks=visualize.selfcheck()
    source_paths=[base/name for name in ('observations.jsonl.gz','profiles.jsonl.gz','DEPTH_OBSERVATIONS.jsonl.gz')]
    source_paths+=audit.physical_files(audit.old.DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz')
    result=dict(status='PASS',semantic_checks=count,visual_checks=visual_checks,real_source=name,
        actual_check_sources=[audit.old.artifact(path) for path in source_paths],
        actual_check_code=[audit.old.artifact(audit.HERE/filename) for filename in ('audit.py','checks.py','visualize.py')],
        self_consistent_hash_does_not_bypass_semantics=True,GT_raster_read=False,
        new_model_http=0,cost_usd=0)
    audit.old.write_new(audit.HERE/'CHECKS.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
