"""Clarify measured-current versus predicted-target depth; preserve prior draft."""
from common import *
from datetime import datetime, timezone

validation = read(HERE / 'REPORT_VALIDATION.json')
report_pin = validation['report']
preserved_report = HERE / 'report_revisions/before_depth_wording_precision/FINAL_REVIEW.md'
assert (sha(report_pin['path']) == report_pin['sha256'] or
        (preserved_report.exists() and sha(preserved_report) == report_pin['sha256']))
verify_item(validation['results'])
changes = {}
base = HERE / 'report_revisions/before_depth_wording_precision'
replacements = (
    ('错误身份也可能处于近似深度。',
     '错误候选的当前实测深度也可接近目标预测均值；目标鱼在q的实际深度未据此认证。'),
    ('F159同时显示异鱼也能近深度。',
     'F159显示错误候选实测深度可接近目标预测均值，未认证两条鱼在q的真实深度相近。'),
)
for name in ('FINAL_REVIEW.md', 'INTERPRETATION.md', 'NEXT_STEP_PLAN.md', 'report.py',
             'interpretation.py', 'REPORT_VALIDATION.json'):
    path = HERE / name
    preserved = base / name
    preserved.parent.mkdir(parents=True, exist_ok=True)
    if not preserved.exists():
        preserved.write_bytes(path.read_bytes())
    before = preserved.read_bytes()
    old_pin = dict(path=str(path), bytes=len(before), sha256=hashlib.sha256(before).hexdigest())
    if name != 'REPORT_VALIDATION.json':
        content = before.decode('utf-8')
        assert name == 'report.py' or any(old in content for old, _ in replacements), name
        for old, new in replacements:
            content = content.replace(old, new)
        assert path.read_bytes() in (before, content.encode('utf-8')), name
        path.write_text(content, encoding='utf-8')
    changes[name] = dict(old=old_pin, preserved=artifact(preserved),
                         after_text_edit=artifact(path))

report = HERE / 'FINAL_REVIEW.md'
m = read(RUN / 'METRICS.json')
fields = ('IDF1', 'HOTA', 'AssA', 'IDSW', 'FP', 'FN')
parsed = [line.split('|')[1:-1] for line in report.read_text(encoding='utf-8').splitlines()
          if line.startswith('|')]
metric_rows = [row for row in parsed if len(row) == 8 and row[1] in ARMS]
delta_rows = [row for row in parsed if len(row) == 8 and row[1].startswith('Z4Q_DEPTH_VETO−')]
assert len(metric_rows) == 27 and len(delta_rows) == 10
def table(name):
    return m['feeding_pooled']['metrics'] if name == 'Feeding pooled 1471' else m['segments'][name]['metrics']
for name, arm, *values in metric_rows:
    for field, value in zip(fields, values):
        assert abs(float(value) - table(name)[arm][field]) <= 5.1e-7
for name, comparison, *values in delta_rows:
    arm = comparison.split('−')[1]
    for field, value in zip(fields, values):
        assert abs(float(value) - (table(name)[ARMS[2]][field] - table(name)[arm][field])) <= 5.1e-7
receipt = HERE / 'REPORT_DEPTH_WORDING_PRECISION.json'
write_new(receipt, dict(status='REPORTING_TEXT_CLARIFIED_NO_RESEARCH_CHANGE',
    utc=datetime.now(timezone.utc).isoformat(), changes=changes,
    reason='Current candidate measurement may agree with target forecast without certifying target actual depth at q.',
    numeric_rows_rechecked=37, prediction_score_seal_facts_results_unchanged=True,
    reporting_helper_initial_attempt='Assertion on report.py containing inline prose failed after two text edits. The report helper reads NEXT_STEP_PLAN instead. Prior bytes retained; resumed against exact before/expected-after bytes. No science file was touched.'))
validation.update(report=artifact(report), depth_wording_precision=artifact(receipt))
(HERE / 'REPORT_VALIDATION.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
verify_item(validation['results'])
for path, digest_value in read(HERE / 'RUNTIME_FREEZE.json')['code'].items():
    assert sha(path) == digest_value, path
print('POSTSEAL_DEPTH_WORDING_PRECISE_37_ROWS_UNCHANGED', flush=True)
