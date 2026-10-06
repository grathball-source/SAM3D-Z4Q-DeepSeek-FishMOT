"""Resume delivery after an interrupted, unscored engineering JSON hit EOF.

Preserve every original byte. Closing containers is only for privacy inspection;
the resulting value is never saved or accepted as a prediction/scoring input.
"""
import delivery as d
from common import *
from datetime import datetime, timezone

from verify_inputs import verify_all
verify_all()
assert d.git('rev-parse','HEAD').decode().strip() == BASE
assert read(HERE/'REPORT_VALIDATION.json')['status'] == 'PASS'
assert read(HERE/'VISUAL_ACCEPTANCE.json')['status'] == 'PASS_ACTUAL_LOCAL_VISUAL_INSPECTION'
for path, expected in read(HERE/'RUNTIME_FREEZE.json')['code'].items():
    assert sha(path) == expected
for value in read(HERE/'HANDOFF_UPDATE.json').values():
    verify_item(value['new'])
assert set(d.git('diff','--name-only').decode().splitlines()) == {'.gitignore','research/HANDOFF.md'}

def inspect_eof_prefix(path, error):
    assert path.relative_to(HERE).parts[0] == 'slice_real_v1'
    assert not (path.parent/'PREDICTIONS_SEALED.json').exists()
    raw = path.read_text(encoding='utf-8')
    assert error.pos == len(raw) and raw.rstrip().endswith('{')
    stack, quoted, escaped = [], False, False
    for char in raw:
        if quoted:
            if escaped: escaped = False
            elif char == '\\': escaped = True
            elif char == '"': quoted = False
        elif char == '"': quoted = True
        elif char in '{[': stack.append('}' if char == '{' else ']')
        elif char in '}]': assert stack.pop() == char
    assert not quoted
    d.numeric(json.loads(raw + ''.join(reversed(stack))))
    return dict(artifact(path), parse_error=str(error), unsealed_engineering_attempt=True,
        added_only_closing_delimiters_for_memory_only_privacy_inspection=True,
        original_bytes_unchanged=True, never_scored=True)

records, partial = 0, []
for path in d.files():
    assert path.suffix.lower() not in {'.png','.jpg','.jpeg','.npy','.npz','.h5','.mp4'}
    assert path.stat().st_size < 95*1024*1024
    if path.suffix == '.json':
        try: d.numeric(read(path)); records += 1
        except json.JSONDecodeError as error: partial.append(inspect_eof_prefix(path,error))
    elif path.name.endswith('.jsonl.gz') or path.suffix == '.jsonl':
        try:
            for value in rows(path): d.numeric(value); records += 1
        except (EOFError,gzip.BadGzipFile,json.JSONDecodeError):
            assert any(p.startswith('slice_') for p in path.relative_to(HERE).parts)
            partial.append(artifact(path))
    elif path.suffix == '.partial': partial.append(artifact(path))

write_new(HERE/'PUBLIC_CONTENT_REVIEW.json',dict(status='PASS',numeric_records=records,
    private_outputs=len(read(HERE/'PRIVATE_INVENTORY.json')['private_outputs']),
    incomplete_engineering_attempts=partial,incomplete_engineering_attempts_never_scored=True,
    old_seals_readonly=True,new_model_http=0,cost_usd=0))
write_new(HERE/'DELIVERY_PREPARE_REPAIR.json',dict(status='PUBLIC_INVENTORY_RESUMED_WITH_ORIGINAL_FAILED_ATTEMPT_PRESERVED',
    observed_utc=datetime.now(timezone.utc).isoformat(),original_prepare_exit_code=1,
    original_error='JSONDecodeError at unsealed slice_real_v1 EVENTS.json EOF, line7755 column9 char219421',
    original_prepare=artifact(HERE/'delivery.py'),resume_helper=artifact(__file__),
    formal_predictions_or_scores_or_frozen_code_changed=False,
    original_handoff_and_ignore_update_not_repeated=True,restricted_pixels_excluded=True,
    new_model_http=0,cost_usd=0))
write_new(HERE/'PUBLIC_ARTIFACT_MANIFEST.json',dict(
    files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix()) for p in d.files()],
    repository_files=[dict(artifact(p),relative_path=p.relative_to(ROOT).as_posix())
        for p in (ROOT/'.gitignore',ROOT/'research/HANDOFF.md')],private_pixels_excluded=True))
print('Public delivery inventory complete; interrupted engineering bytes preserved',records,len(partial),flush=True)
