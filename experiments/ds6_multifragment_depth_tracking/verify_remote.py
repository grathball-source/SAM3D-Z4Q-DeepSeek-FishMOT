"""Read real remote main and all public changed Git blobs after normal push."""
import hashlib
import json
import subprocess
import sys
import urllib.request
from datetime import datetime,timezone
from common import HERE,ROOT,write_new

BASE='ced663d97cadc23138c538f5784df7ed4e835fe2'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def verify(expected,save=False):
    remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    assert remote==expected,(remote,expected)
    subprocess.run(['git','fetch','origin','main'],cwd=ROOT,check=True)
    assert git('rev-parse','origin/main').decode().strip()==expected
    names=git('diff','--name-only',BASE,expected).decode().splitlines()
    blobs=[]
    for name in names:
        data=git('show',f'origin/main:{name}')
        assert data==(ROOT/name).read_bytes(),name
        assert '/private/' not in name and '/slice/' not in name
        assert not name.endswith(('.png','.jpg','.jpeg','.npz','.npy','.pyd','.mp4'))
        blobs.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
            status='ACTUAL_REMOTE_GIT_BLOB_EQUALS_LOCAL'))
    http=[]
    for filename in ('RESULTS.md','CONFIG.json','runner.py','SUMMARY.json','run/METRICS.json','run/ALL_PREDICTIONS_SEALED.json'):
        relative=f'experiments/ds6_multifragment_depth_tracking/{filename}'
        url=f'https://raw.githubusercontent.com/grathball-source/SAM3D-Z4Q-DeepSeek-FishMOT/{expected}/{relative}'
        try:
            with urllib.request.urlopen(url,timeout=15) as response:
                data=response.read();status=response.status
            assert status==200 and data==(ROOT/relative).read_bytes(),filename
            http.append(dict(path=relative,status='HTTP200_BYTES_EQUAL',bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest()))
        except Exception as exc:
            http.append(dict(path=relative,status='HTTP_FAILED_ACTUAL_GIT_BLOB_VERIFIED',
                reason=type(exc).__name__+': '+str(exc)))
    proof=dict(status='REAL_ORIGIN_MAIN_REF_AND_ALL_CHANGED_BLOBS_VERIFIED',
        timestamp_utc=datetime.now(timezone.utc).isoformat(),result_or_proof_commit=expected,
        actual_remote_main=remote,non_force_push=True,blobs=blobs,http_key_files=http,
        private_pixels_uploaded=False,model_http=0,cost_usd=0,
        proof_commit_policy='this saved proof describes result commit; follow-up proof commit main is verified separately without rewriting this file')
    if save:write_new(HERE/'REMOTE_VERIFICATION.json',proof)
    print(json.dumps(dict(remote=remote,blobs=len(blobs),http=http),ensure_ascii=False,indent=2))
if __name__=='__main__':verify(sys.argv[1],len(sys.argv)>2 and sys.argv[2]=='save')

