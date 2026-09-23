"""One-time freeze, after all local checks and before the first formal API call."""
from common import *
def main():
 limit_cpu();assert not (P/'MODEL_RUN_STARTED.json').exists()
 for filename in ['PREPARATION_ACCEPTANCE.json','INPUT_CHECKS.json','CONTRACT_CHECKS.json','EVALUATION_CHECKS.json','BASELINE_ACCEPTANCE.json','SMOKE_ACCEPTANCE.json']:
  assert read(P/filename)['exit_code']==0,filename
 preparation=read(P/'PREPARATION_ACCEPTANCE.json')
 for n,h in preparation['hashes'].items():assert sha(P/n)==h,n
 for n,h in preparation['source_hashes'].items():assert sha(n)==h,n
 paths=[*P.glob('*.py')]+[P/n for n in ['PLAN.md','README.md','PROMPT.txt','MODEL_CONFIG.json','PREPARATION_ACCEPTANCE.json','INPUT_CHECKS.json','CONTRACT_CHECKS.json','EVALUATION_CHECKS.json','BASELINE_ACCEPTANCE.json','BASELINE_DECISIONS.json','SMOKE_ACCEPTANCE.json','SMOKE_RESPONSE.json','smoke_stimulus.png']]
 paths += [P/n for n in preparation['hashes']]
 paths += [ROOT/'tools/sam3_depth_only_reconnect_20260916/rle_decode.py']
 if (P/'FINAL_INPUT_QA.json').exists():
  assert read(P/'FINAL_INPUT_QA.json')['exit_code']==0
  paths.append(P/'FINAL_INPUT_QA.json')
 freeze={str(path.resolve()):sha(path) for path in paths}
 save(P/'MODEL_FREEZE.json',freeze)
 save(P/'FREEZE_ACCEPTANCE.json',dict(at=now(),exit_code=0,files=len(freeze),freeze_sha256=sha(P/'MODEL_FREEZE.json'),source_hashes_checked=len(preparation['source_hashes'])))
 print('Frozen',len(freeze),'files',flush=True)
if __name__=='__main__':main()
