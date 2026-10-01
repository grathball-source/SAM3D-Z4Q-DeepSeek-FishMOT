"""Actual local resources and previous immutable bytes, before prediction."""
from common import *
import platform,os,shutil,importlib.metadata,datetime

def main():
    assert not RUN.exists()
    lock=read(HERE/'OLD_READONLY_LOCK.json')
    for p,h in lock['files'].items():assert sha(ROOT/p)==h,p
    disk=shutil.disk_usage(ROOT)
    env=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        interpreter=sys.executable,python=sys.version,platform=platform.platform(),cpu_count=os.cpu_count(),
        native_math_threads=1,opencv_threads=1,cuda_visible_devices='',
        versions={n:importlib.metadata.version(n) for n in ('numpy','scipy','opencv-python','h5py')},
        disk=dict(total_bytes=disk.total,used_bytes=disk.used,free_bytes=disk.free),
        execution='LOCAL_CPU_EXISTING_DEPS_NO_SERVER_JOBS_INSTALL_OR_INFERENCE',
        new_model_http=0,cost_usd=0,old_immutable_files=lock['count'])
    (HERE/'ENVIRONMENT.json').write_text(json.dumps(env,indent=2)+'\n',encoding='utf-8')
    write_new(HERE/'PREFLIGHT_REVIEW.json',dict(status='PASS',environment=artifact(HERE/'ENVIRONMENT.json'),
        old_immutable_lock=artifact(HERE/'OLD_READONLY_LOCK.json'),original_source_inventory=artifact(HERE/'SOURCE_INVENTORY.json'),
        input_review=artifact(HERE/'INPUT_REVIEW.json'),
        endpoint_contract=artifact(HERE/'ENDPOINT_CONTRACT.json'),
        no_GT_read=True,GT_free_source_opportunity_is_not_branch_eligibility=True))
    print('Old artifacts locked',lock['count'],'disk free bytes',disk.free)
if __name__=='__main__':main()
