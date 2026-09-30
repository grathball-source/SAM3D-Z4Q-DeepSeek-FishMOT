"""Verify real origin/main and every changed public Git blob."""
import hashlib
import json
import subprocess
import sys
import urllib.request
from datetime import datetime,timezone
from audit import HERE,ROOT,write_new

BASE='56c2ea61682edea71328976c4fed27230f334c2a'


def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)


def verify_remote(expected,save):
    remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    assert remote==expected,(remote,expected)
    subprocess.run(['git','fetch','origin','main'],cwd=ROOT,check=True)
    assert git('rev-parse','origin/main').decode().strip()==expected
    changes=git('diff','--name-only',BASE,expected).decode().splitlines()
    blobs=[]
    for name in changes:
        raw=git('show',f'origin/main:{name}')
        assert raw==(ROOT/name).read_bytes(),name
        assert '/private/' not in name and not name.endswith(('.png','.npz','.jpg','.npy'))
        blobs.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                          status='ACTUAL_REMOTE_BLOB_EQUALS_LOCAL'))
    http=[]
    for filename in ('RESULTS.md','audit.py','CONFIG.json','SUMMARY.json','AUDIT_SEALED.json'):
        relative=f'experiments/ds5_surface_registration_audit/{filename}'
        url=f'https://raw.githubusercontent.com/grathball-source/SAM3D-Z4Q-DeepSeek-FishMOT/{expected}/{relative}'
        try:
            with urllib.request.urlopen(url,timeout=20) as response:
                raw=response.read(); status=response.status
            assert status==200 and raw==(ROOT/relative).read_bytes(),filename
            http.append(dict(path=relative,status='HTTP200_BYTES_EQUAL',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        except Exception as exc:
            http.append(dict(path=relative,status='HTTP_FAILED_GIT_BLOB_VERIFIED',error=type(exc).__name__+': '+str(exc)))
    result=dict(status='PUSHED_MAIN_REF_AND_ALL_CHANGED_BLOBS_VERIFIED',time_utc=datetime.now(timezone.utc).isoformat(),
        result_or_proof_commit=expected,remote_main_at_verification=remote,force_push=False,
        changed_file_blob_checks=blobs,public_http_checks=http,model_http=0,private_pixels_uploaded=False)
    if save: write_new(HERE/'REMOTE_VERIFICATION.json',result)
    print(json.dumps(dict(remote=remote,files=len(blobs),http=http),indent=2))


if __name__=='__main__': verify_remote(sys.argv[1],len(sys.argv)>2 and sys.argv[2]=='save')

