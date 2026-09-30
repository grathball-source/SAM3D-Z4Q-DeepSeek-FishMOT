"""Record actual runtime and immutable old file bytes before the new prediction."""
import os,subprocess,platform
from common import *
import numpy as np,cv2,h5py,scipy
cfg=read(HERE/'CONFIG.json')
cfg['restored_fields']=['native_v2.depth_mm','original_depth_mm','filled_mask','invalidated_reason']
cfg['excluded_provenance']=[0]
cfg['scope']='EXPOSED_OFFLINE_V2_REPROJECTED; no annotation assistance; upstream RGB and future cleaning'
(HERE/'CONFIG.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
plan=(HERE/'PLAN.md').read_text(encoding='utf-8')
plan=plan.replace('现有恢复depth，来源分层core','真正native v2重投影，来源分层core')
plan=plan.replace('；4剔除','；不读取v3及其4类补孔')
plan=plan.replace('用户本轮允许已有修复深度。实际v2清洗用了i+1的depth与RGB，v3用了人工标注小孔；预测代码只读取depth_mm/provenance，禁读instance_id/fish_interior_mask/RGB/参考标签，不代表上游因果无泄漏。剔除p4未必复原v2光栅赢家。故P2全程标记已曝光开发集离线恢复诊断；不能证明仅过去帧无GT上线提点。原始P1单列。',
'用户本轮允许已有修复深度。使用真实full_v2三份native H5，按当前frame读取depth_mm/original_depth_mm/filled_mask/invalidated_reason并以记录标定重新投影；不使用v3及annotation补孔。实际v2清洗用了i+1的depth与RGB，故P2仍是已曝光开发集离线恢复诊断，不能证明仅过去帧上线提点。运行时禁读instance_id/fish_interior_mask/RGB/参考标签、v3与网络。原始P1单列。')
(HERE/'PLAN.md').write_text(plan,encoding='utf-8',newline='\n')
tracked=subprocess.check_output(['git','ls-files','experiments/ds1_depth_only','experiments/ds2_depth_transfer_validation','experiments/ds3_depth_foreground_filter','experiments/ds4_depth_quality_repair','experiments/ds5_surface_registration_audit','experiments/ds6_multifragment_depth_tracking'],cwd=ROOT,text=True).splitlines()
write_new(HERE/'OLD_READONLY_LOCK.json',dict(files={n:sha(ROOT/n) for n in tracked},count=len(tracked)))
write_new(HERE/'ENVIRONMENT.json',dict(python=sys.executable,platform=platform.platform(),
    numpy=np.__version__,opencv=cv2.__version__,h5py=h5py.__version__,scipy=scipy.__version__,
    local_cpu_only=True,new_model_http=0,cost_usd=0,
    runtime_thread_setting='launch.py sets OMP/OPENBLAS/MKL/NUMEXPR=1 and OpenCV.setNumThreads(1)',
    disk_free_bytes=__import__('shutil').disk_usage(HERE).free))
print('Locked',len(tracked),'old files')

