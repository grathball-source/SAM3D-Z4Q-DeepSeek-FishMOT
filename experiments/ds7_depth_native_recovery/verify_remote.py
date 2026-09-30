"""Actual non-force remote ref and byte checks, not a local tracking-ref assertion."""
from common import *
import subprocess, urllib.request
BASE='49b06c521a7b9b9f261e6c852d6e366c17cc8fc2'
def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf-8').strip()
def main():
    head=git('rev-parse','HEAD')
    branch=git('branch','--show-current');assert branch=='main'
    actual=git('ls-remote','origin','refs/heads/main').split()[0];assert actual==head
    subprocess.run(['git','fetch','origin','main'],cwd=ROOT,check=True,capture_output=True)
    assert git('rev-parse','origin/main')==head
    files=git('diff','--name-only',BASE,head).splitlines()
    verified=[]
    for name in files:
        if not name:continue
        local=ROOT/name
        data=subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)
        assert local.read_bytes()==data,name
        verified.append(dict(path=name,bytes=len(data),sha256=__import__('hashlib').sha256(data).hexdigest()))
    required=['PLAN.md','RESULTS.md','run/METRICS.json','run/ALL_PREDICTIONS_SEALED.json',
              'controller.py','RESTORED_SOURCE_REVIEW.json']
    http=[]
    for rel in required:
        repo_path='experiments/ds7_depth_native_recovery/'+rel
        url='https://raw.githubusercontent.com/grathball-source/SAM3D-Z4Q-DeepSeek-FishMOT/'+head+'/'+repo_path
        with urllib.request.urlopen(url,timeout=30) as response:
            data=response.read();status=response.status
        assert status==200 and data==(HERE/rel).read_bytes(),repo_path
        http.append(dict(path=repo_path,status=status,bytes=len(data),sha256=__import__('hashlib').sha256(data).hexdigest()))
    proof=dict(main_SHA=head,actual_ls_remote_SHA=actual,origin_main_SHA=git('rev-parse','origin/main'),
        normal_push=True,all_changed_blobs_byte_equal=verified,key_raw_remote_files=http,
        git_status=git('status','--short'),new_model_http=0,cost_usd=0)
    if '--save' in sys.argv:write_new(HERE/'REMOTE_VERIFICATION.json',proof)
    print(__import__('json').dumps(dict(main_SHA=head,actual_remote_SHA=actual,verified_changed_files=len(verified),
        key_remote_files=len(http),git_status=proof['git_status'])))
if __name__=='__main__':main()

