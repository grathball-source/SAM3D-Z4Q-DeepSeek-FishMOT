"""Postseal remote scorer dependency inventory; metadata only."""
import hashlib
import json
from pathlib import Path

ROOT=Path('/home/xiongxiong/ms1r_20260928_score')
RUN=ROOT/'run_ms1r_20260928'
FILES=[
    Path('/home/data2/xiongxiong/d-mot/experiments/sam3_i3_validation_cpu16_20260915/run_validation_2888/assignments.jsonl.gz'),
    Path('/home/data2/xiongxiong/d-mot/experiments/sam3_i1_validation_20260915/truth.jsonl.gz'),
    Path('/home/xiongxiong/dmot-experiments/sam3_depth_return_guard_20260918/experiment/offline_matches_validation.jsonl.gz'),
    ROOT/'original_score.py',ROOT/'score.py',
    RUN/'public/predictions_validation.jsonl.gz',RUN/'public/METRICS.json',
    RUN/'private_api/MS1-F2586-S.bindings.json',
]


def info(path):
    with path.open('rb') as handle:
        digest=hashlib.file_digest(handle,'sha256').hexdigest()
    return dict(path=str(path),bytes=path.stat().st_size,sha256=digest)


def main():
    target=RUN/'public/REMOTE_RESTRICTED_INVENTORY.json'
    assert not target.exists()
    value=dict(host='xiongxiong@10.2.212.110',purpose='Postseal exposed-validation scoring; metadata only',
               files=[info(path) for path in FILES],
               reproduction='Run frozen score.py with original_score.py in lab annotation environment after prediction seal; private S token binding verifies physical mapping against actual mask order.')
    target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':
    main()
