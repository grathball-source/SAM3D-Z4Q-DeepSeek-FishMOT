"""Live local capacity before the one formal CPU replay; no remote/GPU job."""
from common import *
import subprocess,shutil,platform
from datetime import datetime,timezone


def main():
    command="$taskOS=Get-CimInstance Win32_OperatingSystem; $taskCPU=Get-CimInstance Win32_Processor; $taskProcesses=Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' }; $taskOwn=@($taskProcesses | Where-Object { $_.CommandLine -like '*ds19_protected_event_return*guard.py*' }); [pscustomobject]@{free_ram_kib=$taskOS.FreePhysicalMemory; total_ram_kib=$taskOS.TotalVisibleMemorySize; cpu_name=$taskCPU.Name; physical_cores=$taskCPU.NumberOfCores; logical_processors=$taskCPU.NumberOfLogicalProcessors; existing_python_process_count=@($taskProcesses).Count; own_replay_pids=@($taskOwn | Select-Object -ExpandProperty ProcessId)} | ConvertTo-Json -Compress"
    live=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',command],text=True))
    disk=shutil.disk_usage('E:/')
    assert not live['own_replay_pids'],'Wait for owned engineering slices to complete'
    assert disk.free>4*1024**3,'Insufficient free task output space'
    assert live['free_ram_kib']>3*1024**2,'Insufficient free memory'
    write_new(HERE/'ENVIRONMENT_FORMAL_START.json',dict(status='LIVE_LOCAL_CAPACITY_CHECK_PASS',
        time_utc=datetime.now(timezone.utc).isoformat(),python=sys.executable,version=platform.python_version(),
        live=live,disk_free_bytes=disk.free,max_jobs=6,threads_per_job=1,CUDA_VISIBLE_DEVICES='',
        unrelated_processes_untouched=True,server_contacted=False,model_http=0,cost_usd=0))
    print('Live local CPU capacity PASS',live['free_ram_kib'],'KiB free RAM;',disk.free,'bytes free disk')


if __name__=='__main__':main()
