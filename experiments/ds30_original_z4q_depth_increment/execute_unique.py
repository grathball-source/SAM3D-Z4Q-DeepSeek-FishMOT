"""Record real sequential diagnostic exits; never append to an old run."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, subprocess, sys, time, uuid

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True

def main():
    name = sys.argv[1]
    path = (HERE / name).resolve()
    assert path.parent == HERE and path.suffix == '.py' and path.is_file()
    assert name not in ('execute.py', 'initialize.py', 'delivery.py')
    logdir = HERE / 'logs'; logdir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'_'+uuid.uuid4().hex
    stdout = logdir / f'{stamp}_{path.stem}.stdout.txt'
    stderr = logdir / f'{stamp}_{path.stem}.stderr.txt'
    started = datetime.now(timezone.utc).isoformat(); began = time.perf_counter()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    command = [sys.executable, str(path), *sys.argv[2:]]
    with stdout.open('xb') as out, stderr.open('xb') as err:
        result = subprocess.run(command, cwd=HERE, env=env, stdout=out, stderr=err)
    def item(p):
        with p.open('rb') as f: digest = hashlib.file_digest(f, 'sha256').hexdigest()
        return dict(path=str(p), bytes=p.stat().st_size, sha256=digest)
    record = dict(command=command, started_utc=started, ended_utc=datetime.now(timezone.utc).isoformat(),
                  elapsed_seconds=time.perf_counter()-began, exit_code=result.returncode,
                  stdout=item(stdout), stderr=item(stderr), new_model_http=0, cost_usd=0)
    with (HERE / 'EXECUTION_LOG.jsonl').open('a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(record, separators=(',', ':'))+'\n')
    print(json.dumps(record, separators=(',', ':')), flush=True)
    if result.returncode:
        print(stderr.read_text(encoding='utf-8', errors='replace')[-10000:])
    sys.exit(result.returncode)

if __name__ == '__main__': main()
