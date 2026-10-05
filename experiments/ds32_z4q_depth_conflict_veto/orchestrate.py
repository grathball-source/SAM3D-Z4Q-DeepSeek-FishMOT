"""Two single-thread workers, then one no-GT selected edge counterfactual."""
from common import *
from concurrent.futures import ThreadPoolExecutor
import subprocess,sys
schedule=['LW','L3','fishsa_development_8400','fishsa_validation_2888',*[n for n in SEGMENTS if n.startswith('feeding_')]]
def call(mode,name):
    p=subprocess.run([sys.executable,str(HERE/'execute_unique.py'),'guard.py',mode,name],cwd=HERE,capture_output=True,text=True)
    print(mode,name,p.returncode,p.stdout[-1400:],p.stderr[-1400:],flush=True);assert p.returncode==0
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda n:call('run',n),schedule))
for n in SEGMENTS:verify_seal(n)
selected=None
for n in SEGMENTS:
    hit=read(RUN/n/'public/FIRST_LEGAL_VETO.json')
    if 'edge' in hit:
        edge=hit['edge'];selected=dict(hit,allow_edge=[hit['frame'],edge['phase'],edge['native_id'],edge['canonical_id']]);break
write_new(HERE/'COUNTERFACTUAL_SELECTION.json',selected or dict(status='NO_ACTUAL_CONFLICT',no_threshold_relaxation=True,no_GT_selection=True))
counter={}
if selected:
    for mode in ('counter_allow','counter_veto'):
        p=HERE/mode/selected['segment']/'public'
        write_new(p/'CF_FREEZE.json',dict(status='FROZEN_BEFORE_COUNTERFACTUAL',mode=mode,segment=selected['segment'],
            formal_freeze=artifact(RUN/selected['segment']/'public/FREEZE.json'),selection=artifact(HERE/'COUNTERFACTUAL_SELECTION.json'),
            formal_prediction_seal=artifact(RUN/selected['segment']/'public/PREDICTIONS_SEALED.json'),
            allow_edge=selected['allow_edge'] if mode=='counter_allow' else None,source_and_code_same_as_formal=True,no_GT_selection=True))
        call(mode,selected['segment'])
        counter[mode]=dict(seal=artifact(p/'PREDICTIONS_SEALED.json'),access=artifact(p/'ACCESS.json'))
write_new(RUN/'ALL_PREDICTIONS_SEALED.json',dict(status='ALL_FORMAL_AND_AVAILABLE_COUNTERFACTUAL_PREDICTIONS_ACCESS_SEALED',frames=20098,arms=ARMS,
    seals={n:artifact(RUN/n/'public/PREDICTIONS_SEALED.json') for n in SEGMENTS},
    access_seals={n:artifact(RUN/n/'public/ACCESS.json') for n in SEGMENTS},counterfactual=counter,
    selection=artifact(HERE/'COUNTERFACTUAL_SELECTION.json'),model_http=0,cost_usd=0))
print('All formal/counterfactual predictions sealed; independent score may now read exposed references.',flush=True)
