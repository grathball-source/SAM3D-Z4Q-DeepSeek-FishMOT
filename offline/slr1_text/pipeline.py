"""Background wrapper records exits and evaluates only sealed model outputs."""
from common import *
import subprocess,traceback
def main():
 limit_cpu();code=1
 try:
  for name in ['run_model.py','evaluate.py']:
   rc=subprocess.call([sys.executable,'-u',str(P/name)],cwd=P)
   (P/(Path(name).stem+'_exit_code.txt')).write_text(str(rc)+'\n')
   if rc:raise RuntimeError(name+' failed')
   if name=='run_model.py' and not (P/'MODEL_ACCEPTANCE.json').exists():raise RuntimeError('model not completed')
  code=0
 except Exception:
  traceback.print_exc()
 finally:(P/'pipeline_exit_code.txt').write_text(str(code)+'\n')
 return code
if __name__=='__main__':sys.exit(main())
