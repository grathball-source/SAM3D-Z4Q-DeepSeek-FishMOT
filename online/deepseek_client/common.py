from pathlib import Path
import os, sys, json, hashlib, ctypes, gzip
from datetime import datetime
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
P=Path(__file__).resolve().parent
ROOT=next(x for x in P.parents if (x/'AGENTS.md').exists())
PREV=ROOT/'tools/sam3_spatial_llm_stage1_20260920/engineering_r3'
STAGE=ROOT/'tools/sam3_interaction_stage_20260918'
OPENED=[]
def now():return datetime.now().astimezone().isoformat(timespec='seconds')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');q.replace(p)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def rows(p):
 with gzip.open(p,'rt',encoding='utf-8') as f:
  for line in f:yield json.loads(line)
def limit_cpu():
 if os.name=='nt':
  k=ctypes.windll.kernel32;k.GetCurrentProcess.restype=ctypes.c_void_p
  k.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
  k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
  p=k.GetCurrentProcess();a=ctypes.c_size_t();s=ctypes.c_size_t()
  assert k.GetProcessAffinityMask(p,ctypes.byref(a),ctypes.byref(s))
  chosen=[i for i in range(64) if a.value&(1<<i)][:4]
  assert k.SetProcessAffinityMask(p,sum(1<<i for i in chosen));return chosen
 chosen=sorted(os.sched_getaffinity(0))[:4];os.sched_setaffinity(0,chosen);return chosen
def guard(event,args):
 if event!='open' or not isinstance(args[0],(str,bytes)):return
 p=os.fsdecode(args[0]).replace('\\','/')
 forbidden=['/TRUTH.json','/labels/','/labels_original/','EVENTS_gap','offline_matches_','/TRUTH_SEALED.json', '/audit_decisions/', '/audit_inputs/', '/EVENT_RESULTS.json','/SUMMARY.json','/REVIEW.md']
 if any(s in p for s in forbidden):raise PermissionError('Forbidden inference-stage read: '+p)
 if p.endswith(('.json','.jsonl','.gz','.jpg','.png')):OPENED.append(p)
REASONS={'appearance','depth','motion','lineage','ambiguity','poor_measurement','missing_evidence'}
def validate(packet,out):
 if not isinstance(out,dict) or set(out)!={'option_id','evidence_ids','reason_codes'}:raise ValueError('output keys')
 options={x['option_id']:x for x in packet['options']}
 if not isinstance(out['option_id'],str) or out['option_id'] not in options:raise ValueError('unknown option')
 refs=out['evidence_ids'];reasons=out['reason_codes']
 if not isinstance(refs,list) or not refs or not all(isinstance(x,str) and x in packet['evidence'] for x in refs) or len(set(refs))!=len(refs):raise ValueError('evidence IDs')
 if not isinstance(reasons,list) or not reasons or not all(isinstance(x,str) and x in REASONS for x in reasons) or len(set(reasons))!=len(reasons):raise ValueError('reason codes')
 return True
