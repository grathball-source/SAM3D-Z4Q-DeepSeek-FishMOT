"""Verify actual normal origin/main ref and required remote file bytes."""
from common import *
import subprocess,urllib.request,hashlib
BASE='c33bfbc630c8ccbcbc73276c491775e58f846d8b'
PROXY='http://127.0.0.1:7897'
def git(*args):
    return subprocess.check_output(['git','-c','http.proxy='+PROXY,*args],cwd=ROOT).decode('utf-8').strip()
def main():
    head=git('rev-parse','HEAD');assert git('branch','--show-current')=='main'
    remote=git('ls-remote','origin','refs/heads/main').split()[0];assert remote==head
    subprocess.run(['git','-c','http.proxy='+PROXY,'fetch','origin','main'],cwd=ROOT,check=True,capture_output=True)
    assert git('rev-parse','origin/main')==head
    changed=[]
    for name in git('diff','--name-only',BASE,head).splitlines():
        data=subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)
        assert data==(ROOT/name).read_bytes(),name
        changed.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    keys=('PLAN.md','CONFIG.json','reconnect.py','birth_memory.py','runner.py','RESULTS.md',
          'run/METRICS.json','run/BIRTH_AUDIT.json','run/ALL_PREDICTIONS_SEALED.json',
          'run/SCORING_SEALED.json','RESTRICTED_INVENTORY.json','ARTIFACT_MANIFEST.json')
    remote_files=[]
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':PROXY}))
    for name in ['experiments/ds11_depth_birth_reconnect/'+x for x in keys]+['research/HANDOFF.md']:
        url='https://raw.githubusercontent.com/grathball-source/SAM3D-Z4Q-DeepSeek-FishMOT/'+head+'/'+name
        with opener.open(url,timeout=30) as response:data=response.read();status=response.status
        assert status==200 and data==(ROOT/name).read_bytes(),name
        remote_files.append(dict(path=name,status=status,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    proof=dict(main_SHA=head,actual_ls_remote_SHA=remote,origin_main_SHA=git('rev-parse','origin/main'),
        changed_blobs_byte_equal=changed,key_raw_remote_files=remote_files,normal_push=True,
        git_status=git('status','--short'),new_model_http=0,cost_usd=0)
    if '--save' in sys.argv:write_new(HERE/'REMOTE_VERIFICATION.json',proof)
    print(json.dumps(dict(main_SHA=head,actual_remote_SHA=remote,verified_changed_files=len(changed),
        key_remote_files=len(remote_files),git_status=proof['git_status'])))
if __name__=='__main__':main()
