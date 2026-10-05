"""Repair postseal CRCRLF display only, retaining exact prior draft bytes."""
from common import *
from datetime import datetime, timezone

validation = read(HERE / 'REPORT_VALIDATION.json')
verify_item(validation['report'])
verify_item(validation['results'])
changes = {}
base = HERE / 'report_revisions/before_line_ending_repair'
for name in ('FINAL_REVIEW.md', 'INTERPRETATION.md', 'NEXT_STEP_PLAN.md',
             'report.py', 'interpretation.py', 'REPORT_VALIDATION.json'):
    path = HERE / name
    prior = path.read_bytes()
    preserved = base / name
    assert not preserved.exists()
    preserved.parent.mkdir(parents=True, exist_ok=True)
    old = artifact(path)
    preserved.write_bytes(prior)
    assert preserved.read_bytes() == prior
    if name != 'REPORT_VALIDATION.json':
        normalized = prior.replace(b'\r\r\n', b'\n').replace(b'\r\n', b'\n')
        assert b'\r' not in normalized
        path.write_bytes(normalized)
    changes[name] = dict(old=old, preserved=artifact(preserved),
                         after_line_ending_repair=artifact(path))
for name in ('FINAL_REVIEW.md', 'INTERPRETATION.md'):
    lines = (HERE / name).read_text(encoding='utf-8').splitlines()
    for i, line in enumerate(lines):
        if line.startswith('|') and i + 2 < len(lines):
            assert not (not lines[i + 1] and lines[i + 2].startswith('|')), (name, i)

m = read(RUN / 'METRICS.json')
fields = ('IDF1', 'HOTA', 'AssA', 'IDSW', 'FP', 'FN')
parsed = [line.split('|')[1:-1] for line in (HERE / 'FINAL_REVIEW.md').read_text(encoding='utf-8').splitlines()
          if line.startswith('|')]
metrics = [row for row in parsed if len(row) == 8 and row[1] in ARMS]
deltas = [row for row in parsed if len(row) == 8 and row[1].startswith('Z4Q_DEPTH_VETO−')]
assert len(metrics) == 27 and len(deltas) == 10
def table(name):
    return m['feeding_pooled']['metrics'] if name == 'Feeding pooled 1471' else m['segments'][name]['metrics']
for name, arm, *values in metrics:
    for field, value in zip(fields, values):
        assert abs(float(value) - table(name)[arm][field]) <= 5.1e-7
for name, comparison, *values in deltas:
    arm = comparison.split('−')[1]
    for field, value in zip(fields, values):
        assert abs(float(value) - (table(name)[ARMS[2]][field] - table(name)[arm][field])) <= 5.1e-7
receipt = HERE / 'REPORT_FORMAT_ACCEPTANCE.json'
write_new(receipt, dict(status='PASS_POSTSEAL_LINE_ENDING_REPAIR_ONLY',
    utc=datetime.now(timezone.utc).isoformat(), changes=changes, numeric_rows_rechecked=37,
    markdown_table_rows_contiguous=True, prediction_score_seals_facts_results_unchanged=True))
validation.update(report=artifact(HERE / 'FINAL_REVIEW.md'), line_ending_repair=artifact(receipt))
(HERE / 'REPORT_VALIDATION.json').write_bytes((json.dumps(validation, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
verify_item(validation['results'])
for path, expected in read(HERE / 'RUNTIME_FREEZE.json')['code'].items():
    assert sha(path) == expected, path
print('REPORT_FORMAT_PASS_37_NUMERIC_ROWS_CONTIGUOUS_TABLES', flush=True)
