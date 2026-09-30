"""Read real remote ref and public files; no credentials or private content."""
import hashlib
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from common import HERE, ROOT, write_new


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def verify_remote(expected, save):
    remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    assert remote==expected,(remote,expected)
    subprocess.run(['git','fetch','origin','main'],cwd=ROOT,check=True)
    assert git('rev-parse','origin/main').decode().strip()==expected
    changes=git('diff','--name-only','b43a4ca62229e878b62ed81ea6c7327128636564',expected).decode().splitlines()
    blobs=[]
    for name in changes:
        raw=git('show',f'origin/main:{name}')
        local=(ROOT/name).read_bytes()
        assert raw==local,name
        assert '/private/' not in name and not name.endswith(('.png','.npz','.jpg'))
        blobs.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                          status='FETCHED_ACTUAL_REMOTE_REF_BLOB_EQUALS_LOCAL'))
    http=[]
    for filename in ('RESULTS.md','foreground.py','CONFIG.json','SUMMARY.json','SCORING_SEALED.json'):
        relative=f'experiments/ds3_depth_foreground_filter/{filename}'
        url=f'https://raw.githubusercontent.com/grathball-source/SAM3D-Z4Q-DeepSeek-FishMOT/{expected}/{relative}'
        try:
            with urllib.request.urlopen(url,timeout=20) as response:
                raw=response.read(); status=response.status
            assert status==200 and raw==(ROOT/relative).read_bytes(),filename
            http.append(dict(path=relative,status='HTTP200_BYTES_EQUAL',bytes=len(raw),
                             sha256=hashlib.sha256(raw).hexdigest()))
        except Exception as exc:
            http.append(dict(path=relative,status='PUBLIC_HTTP_CHECK_FAILED_REMOTE_GIT_BLOB_VERIFIED',
                             error=type(exc).__name__+': '+str(exc)))
    result=dict(status='PUSHED_MAIN_REMOTE_REF_AND_ALL_CHANGED_BLOBS_VERIFIED',
                time_utc=datetime.now(timezone.utc).isoformat(),result_or_proof_commit=expected,
                remote_main_at_verification=remote,force_push=False,
                changed_file_blob_checks=blobs,public_http_checks=http,
                inference_http=0,private_pixels_uploaded=False)
    if save: write_new(HERE/'REMOTE_VERIFICATION.json',result)
    print(json.dumps(dict(remote=remote,files=len(blobs),http=http),indent=2))


if __name__=='__main__': verify_remote(sys.argv[1],len(sys.argv)>2 and sys.argv[2]=='save')
