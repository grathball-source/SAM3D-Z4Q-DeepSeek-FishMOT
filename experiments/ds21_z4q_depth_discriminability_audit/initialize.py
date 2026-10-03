"""Freeze one read-only diagnostic and live local resources, not a tracker run."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, platform, shutil, subprocess, sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = '71e86e3daeca33b86497d002be8cc0894e4bd99f'
sys.dont_write_bytecode = True

def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def write(name, obj):
    with (HERE/name).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')

def main():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert head == BASE, (head, BASE)
    if len(sys.argv) > 1:
        assert sys.argv[1] == 'freeze'
        required = ('audit.py', 'checks.py', 'visualize.py', 'README.md', 'PLAN.md')
        assert all((HERE/f).exists() for f in required)
        checks = json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
        assert checks['status'] == 'PASS'
        for item in checks['actual_check_code'] + checks['actual_check_sources']:
            path = Path(item['path'])
            assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], path
        files = sorted(p for p in HERE.iterdir() if p.suffix in ('.py','.md') and p.is_file())
        write('FREEZE.json', dict(status='FROZEN_BEFORE_DIAGNOSTIC_FEATURES_AND_LABEL_JOIN',
            base_commit=head, frozen_utc=datetime.now(timezone.utc).isoformat(),
            code={str(p):dict(bytes=p.stat().st_size, sha256=sha(p)) for p in files},
            method='Existing DS18 measurement rules; no fitting, threshold selection or state replay',
            new_prediction=False, new_scoring=False, new_model_http=0, cost_usd=0))
        print('DS21 diagnostic extractor/plan frozen'); return
    command = "$taskOS=Get-CimInstance Win32_OperatingSystem; $taskCPU=Get-CimInstance Win32_Processor; $taskProcesses=Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' }; [pscustomobject]@{free_ram_kib=$taskOS.FreePhysicalMemory; total_ram_kib=$taskOS.TotalVisibleMemorySize; cpu_name=$taskCPU.Name; physical_cores=$taskCPU.NumberOfCores; logical_processors=$taskCPU.NumberOfLogicalProcessors; existing_python_process_count=@($taskProcesses).Count; own_pids=@($taskProcesses | Where-Object { $_.CommandLine -like '*ds21_z4q_depth_discriminability_audit*' } | Select-Object -ExpandProperty ProcessId)} | ConvertTo-Json -Compress"
    live = json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',command],text=True))
    disk = shutil.disk_usage(ROOT)
    assert disk.free > 1024**3 and live['free_ram_kib'] > 1024**2
    tracked = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')[:-1]
    write('OLD_TRACKED_BASE.json', dict(base_commit=head, paths=tracked,
        handoff=dict(bytes=(ROOT/'research/HANDOFF.md').stat().st_size, sha256=sha(ROOT/'research/HANDOFF.md')),
        gitignore=dict(bytes=(ROOT/'.gitignore').stat().st_size, sha256=sha(ROOT/'.gitignore')),
        note='Final git diff and additive suffix check must preserve every old tracked scientific file.'))
    write('ENVIRONMENT_INITIAL.json', dict(base_commit=head, checked_utc=datetime.now(timezone.utc).isoformat(),
        python=sys.executable, python_version=platform.python_version(), platform=platform.platform(),
        live=live, disk_free_bytes=disk.free, max_jobs=1, threads_per_library=1,
        GPU=False, server_contacted=False, unrelated_processes_untouched=True,
        new_model_http=0, smoke=0, cost_usd=0, new_prediction=False, new_scoring=False))
    print('DS21 initialized; read-only local diagnostic; model HTTP/cost0')

if __name__ == '__main__': main()
