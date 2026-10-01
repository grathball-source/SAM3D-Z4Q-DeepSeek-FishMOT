"""Actual normal-main push verification: remote ref and key HTTP file bytes."""
from common import *
import subprocess,urllib.request,hashlib
BASE='fd1dad5b164c40e8889c4951c47a475af0c1cd6c'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf-8').strip()
def main():
    head=git('rev-parse','HEAD');assert git('branch','--show-current')=='main'
    remote=git('ls-remote','origin','refs/heads/main').split()[0];assert remote==head
    subprocess.run(['git','fetch','origin','main'],cwd=ROOT,check=True,capture_output=True)
    assert git('rev-parse','origin/main')==head
    verified=[]
    for name in git('diff','--name-only',BASE,head).splitlines():
        data=subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)
        assert data==(ROOT/name).read_bytes(),name
        verified.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    keys=['PLAN.md','CONFIG.json','forecast.py','association.py','RESULTS.md','run/METRICS.json',
          'run/ALL_PREDICTIONS_SEALED.json','run/SCORING_SEALED.json','diagnosis/FAILURE_ANALYSIS.md',
          'RESTRICTED_INVENTORY.json','ARTIFACT_MANIFEST.json']
    http=[]
    for name in ['experiments/ds10_depth_failure_repair/'+x for x in keys]+['research/HANDOFF.md']:
        url='https://raw.githubusercontent.com/grathball-source/SAM3D-Z4Q-DeepSeek-FishMOT/'+head+'/'+name
        with urllib.request.urlopen(url,timeout=30) as response:data=response.read();status=response.status
        assert status==200 and data==(ROOT/name).read_bytes(),name
        http.append(dict(path=name,status=status,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    proof=dict(main_SHA=head,actual_ls_remote_SHA=remote,origin_main_SHA=git('rev-parse','origin/main'),
        changed_blobs_byte_equal=verified,key_raw_remote_files=http,normal_push=True,git_status=git('status','--short'),new_model_http=0,cost_usd=0)
    if '--save' in sys.argv:write_new(HERE/'REMOTE_VERIFICATION.json',proof)
    print(json.dumps(dict(main_SHA=head,actual_remote_SHA=remote,verified_changed_files=len(verified),key_remote_files=len(http),git_status=proof['git_status'])))
if __name__=='__main__':main()
