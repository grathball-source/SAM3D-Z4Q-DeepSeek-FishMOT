from pathlib import Path
import os, sys, json, gzip, hashlib, time, ctypes
from datetime import datetime
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
P=Path(__file__).resolve().parent
ROOT=next(parent for parent in P.parents if (parent/'AGENTS.md').exists())
DATA=ROOT/'data/AlignedDataset_v1'
STAGE=ROOT/'tools/sam3_interaction_stage_20260918'
BASE=ROOT/'tools/sam3_depth_return_guard_20260918/completion_evidence/experiment'
OPENED=[]
def now():return datetime.now().astimezone().isoformat(timespec='seconds')
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');q.replace(p)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def rows(p):
 with gzip.open(p,'rt',encoding='utf-8') as f:
  for l in f:yield json.loads(l)
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
 if any(s in p for s in ['/TRUTH.json','/labels/','/labels_original/','EVENTS_gap','offline_matches_','/TRUTH_SEALED.json']):raise PermissionError('Forbidden model-stage read: '+p)
 if p.endswith(('.json','.jsonl','.gz','.jpg','.png')):OPENED.append(p)
def alias(kind,key):return kind+hashlib.sha256(('SLR1:'+str(key)).encode()).hexdigest()[:8]
def pointer(obj,s):
 if not isinstance(s,str) or not s.startswith('/'):raise ValueError('JSON pointer required')
 for k in s[1:].split('/'):
  k=k.replace('~1','/').replace('~0','~');obj=obj[int(k)] if isinstance(obj,list) else obj[k]
 return obj
def validate(packet,out):
 if set(out)!={'state','matches','merged_groups','unresolved_tracks','action','evidence_refs'}:raise ValueError('keys')
 tracks=set(packet['focal_tracks']);obs={x['observation']:x for x in packet['current']}
 if not isinstance(out['matches'],list) or not isinstance(out['merged_groups'],list):raise ValueError('arrays')
 used_t=[];used_o=[]
 for m in out['matches']:
  if set(m)!={'track','observation'} or m['track'] not in tracks or m['observation'] not in obs:raise ValueError('unknown match')
  if obs[m['observation']]['area_px']<=0:raise ValueError('empty observation')
  used_t.append(m['track']);used_o.append(m['observation'])
 if len(set(used_t))!=len(used_t) or len(set(used_o))!=len(used_o):raise ValueError('duplicate assignment')
 unresolved=out['unresolved_tracks']
 if not isinstance(unresolved,list) or len(set(unresolved))!=len(unresolved) or set(unresolved)!=tracks-set(used_t):raise ValueError('unresolved mismatch')
 groups=[]
 for g in out['merged_groups']:
  if set(g)!={'observation','possible_members'} or g['observation'] not in obs or obs[g['observation']]['area_px']<=0:raise ValueError('group observation')
  members=g['possible_members']
  if len(members)<2 or len(set(members))!=len(members) or not set(members)<=tracks:raise ValueError('group membership')
  if g['observation'] in used_o or set(members)&set(used_t):raise ValueError('group conflicts')
  groups.append(g['observation'])
 if len(set(groups))!=len(groups):raise ValueError('duplicate groups')
 if out['state']=='MATCH':
  if set(used_t)!=tracks or groups or out['action']!='PROPOSE_MATCH':raise ValueError('incomplete match')
 elif out['state']=='POSSIBLE_MERGE':
  if used_t or not groups or out['action']!='WAIT':raise ValueError('merge state')
 elif out['state']=='UNRESOLVED':
  if used_t or groups or out['action']!='WAIT':raise ValueError('wait state')
 else:raise ValueError('state')
 if not isinstance(out['evidence_refs'],list) or not out['evidence_refs']:raise ValueError('no evidence')
 for s in out['evidence_refs']:
  value=pointer(packet,s)
  if value is None:raise ValueError('null-only evidence')
 return True
