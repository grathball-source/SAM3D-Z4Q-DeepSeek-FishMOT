"""Postfreeze binding guard only; scoring logic remains frozen score.py."""
from common import *
import subprocess

receipt=read(HERE/'SCORE_IMPORT_ACCEPTANCE.json')
for key in ('scorer','adapter','math'):verify_item(receipt[key])
adapter=Path(receipt['adapter']['path'])
baseline=subprocess.check_output(['git','show',BASE+':'+adapter.relative_to(ROOT).as_posix()],cwd=ROOT)
assert hashlib.sha256(baseline).hexdigest()==receipt['adapter']['sha256']
clear_math=DS1/'postseal.py'
clear_baseline=subprocess.check_output(['git','show',BASE+':'+clear_math.relative_to(ROOT).as_posix()],cwd=ROOT)
clear_pin=artifact(clear_math)
assert clear_pin['sha256']==hashlib.sha256(clear_baseline).hexdigest()
for path,h in read(HERE/'RUNTIME_FREEZE.json')['code'].items():assert sha(path)==h,path
write_new(HERE/'SCORING_BINDING_ACCEPTANCE.json',dict(status='PASS_PRESTART_IMPORT_PINS_AND_FROZEN_BASE_ADAPTER',
    prestart_import_receipt=artifact(HERE/'SCORE_IMPORT_ACCEPTANCE.json'),adapter_at_frozen_git_BASE_sha256=hashlib.sha256(baseline).hexdigest(),
    dynamic_clear_math=clear_pin,dynamic_clear_math_at_frozen_git_BASE_sha256=hashlib.sha256(clear_baseline).hexdigest(),
    dynamic_clear_import_contract='Pinned DS14 evaluate.py AST-extracts only clear_step from DS1/postseal.py; source bytes verified against the already frozen Git BASE before import.',
    frozen_score=artifact(HERE/'score.py'),wrapper_changes_no_math_reference_or_prediction=True,
    runtime_dynamic_adapter_pin_gap='Adapter and AST-extracted clear_step source were not auto-enumerated in runtime.code; independent guard verifies them against the already frozen Git BASE. Adapter also had a preSTART import pin.',
    verified_before_GT_read=True,new_model_http=0,cost_usd=0))
import score
score.main()
