from common import *
import subprocess
def main():
 cpu=limit_cpu();save(P/'PIPELINE_STARTED.json',dict(at=now(),pid=os.getpid(),cpu=cpu,executable=sys.executable))
 for name in ['run_model','evaluate']:
  with (P/f'{name}_stdout.log').open('w',encoding='utf-8') as out,(P/f'{name}_stderr.log').open('w',encoding='utf-8') as err:
   child=subprocess.Popen([sys.executable,'-u',str(P/(name+'.py'))],cwd=P,stdout=out,stderr=err)
   save(P/f'{name}_process.json',dict(at=now(),pid=child.pid,parent_pid=os.getpid()))
   code=child.wait()
  (P/f'{name}_exit_code.txt').write_text(str(code),encoding='utf-8')
  if code:
   (P/'pipeline_exit_code.txt').write_text(str(code),encoding='utf-8');return code
 evaluation=read(P/'EVALUATION_ACCEPTANCE.json');assert evaluation['exit_code']==0
 for n,h in evaluation['hashes'].items():assert sha(P/n)==h,n
 save(P/'STATUS.json',dict(at=now(),stage='COMPLETED',total=144,completed=144,decision=evaluation['decision']))
 (P/'pipeline_exit_code.txt').write_text('0',encoding='utf-8');return 0
if __name__=='__main__':sys.exit(main())
