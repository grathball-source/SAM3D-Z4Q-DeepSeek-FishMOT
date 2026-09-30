"""Read the actual remote ref and key remote file bytes after a normal push."""
from common import *
import subprocess,urllib.request,hashlib
BASE='a56e3cae72caffc34a19318a786c42649bbe16af'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf-8').strip()
def main():
    head=git('rev-parse','HEAD');assert git('branch','--show-current')=='main'
    actual=git('ls-remote','origin','refs/heads/main').split()[0];assert actual==head
    subprocess.run(['git','fetch','origin','main'],cwd=ROOT,check=True,capture_output=True)
    assert git('rev-parse','origin/main')==head
    changed=git('diff','--name-only',BASE,head).splitlines();verified=[]
    for name in changed:
        blob=subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)
        assert (ROOT/name).read_bytes()==blob,name
        verified.append(dict(path=name,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest()))
    key_paths=['experiments/ds9_joint_h0_depth/PLAN.md', 'experiments/ds9_joint_h0_depth/CONFIG.json', 'experiments/ds9_joint_h0_depth/association.py', 'experiments/ds9_joint_h0_depth/RESULTS.md', 'experiments/ds9_joint_h0_depth/run/METRICS.json', 'experiments/ds9_joint_h0_depth/run/ALL_PREDICTIONS_SEALED.json', 'experiments/ds9_joint_h0_depth/run/SCORING_SEALED.json', 'experiments/ds9_joint_h0_depth/RESTRICTED_INVENTORY.json', 'experiments/ds9_joint_h0_depth/ARTIFACT_MANIFEST.json', 'research/HANDOFF.md']
    http=[]
    for path in key_paths:
        url='https://raw.githubusercontent.com/grathball-source/SAM3D-Z4Q-DeepSeek-FishMOT/'+head+'/'+path
        with urllib.request.urlopen(url,timeout=30) as response:data=response.read();status=response.status
        assert status==200 and data==(ROOT/path).read_bytes(),path
        http.append(dict(path=path,status=status,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    proof=dict(main_SHA=head,actual_ls_remote_SHA=actual,origin_main_SHA=git('rev-parse','origin/main'),
        all_changed_blobs_byte_equal=verified,key_raw_remote_files=http,normal_push=True,
        git_status=git('status','--short'),new_model_http=0,cost_usd=0)
    if '--save' in sys.argv:write_new(HERE/'REMOTE_VERIFICATION.json',proof)
    print(json.dumps(dict(main_SHA=head,actual_remote_SHA=actual,verified_changed_files=len(verified),
        key_remote_files=len(http),git_status=proof['git_status'])))
if __name__=='__main__':main()
