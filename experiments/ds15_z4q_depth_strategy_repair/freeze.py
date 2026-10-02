"""Freeze a single scientific version and protect all previous tracked depth work."""
from common import *
import subprocess


def main():
    assert read(HERE/'PREFIX_CHECKS.json')['status']=='PASS'
    old=read(DS14/'OLD_READONLY_LOCK.json')['files']
    paths=subprocess.check_output(['git','ls-files','experiments/ds14_raw_multidataset'],cwd=ROOT,text=True).splitlines()
    old=dict(old,**{p:sha(ROOT/p) for p in paths})
    for p,v in old.items():assert sha(ROOT/p)==v,p
    write_new(HERE/'OLD_READONLY_LOCK.json',dict(base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        count=len(old),files=old))
    for name in SEGMENTS:
        source=read(input_dir(name)/'SOURCE_MANIFEST.json')
        for item in source['derived_inputs'].values():verify_item(item)
        for key in ('scan','raw_sources','field_access'):verify_item(source[key])
    write_new(HERE/'EFFECTIVE_RUNTIME.json',dict(status='FIXED_BEFORE_FORMAL_PREDICTIONS',
        arms=list(ARMS),segments=SEGMENTS,frames=20098,scientific_strategy=read(HERE/'STRATEGY.json'),
        original_config=read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'),
        reused_raw_input_scope='DS14 immutable prepared raw masks/profiles/facts; actual source bindings unchanged',
        local_parallel=3,threads=1,GT_before_all_seals=False,model_http=0,cost_usd=0))
    import runner
    runner.freeze_inputs(RUN)
    print('FROZEN: five arms, eight segments,20098 frames; old protected files',len(old))

if __name__=='__main__':main()
