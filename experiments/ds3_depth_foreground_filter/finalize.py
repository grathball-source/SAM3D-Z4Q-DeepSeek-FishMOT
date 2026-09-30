"""Postscore delivery docs and inventory; no changes to frozen measurements."""
import json
import subprocess
from datetime import datetime, timezone
from common import HERE, ROOT, artifact, write_new, verify


def finalize():
    report=HERE/'RESULTS.md'
    text=report.read_text(encoding='utf-8')
    explanation='''## 两个真实失败病例及评分边界

详见 FAILURE_CASE_AUDIT.json；以下是封存后的诊断，没有重跑或改参数。

- F704/o013：原mask与人工轮廓IoU0.6223；whole348个有效点中215个在匹配鱼体，
  旧core只有7点而不可用。筛选取得20点、主导率74.07%、背景差约69.18mm，
  但20点全在所有人工鱼体之外，纯度0。真实QA显示选中原mask的错误侧支。
  显著深度差、空间连通和样本数不能独自认证鱼体归属。
- F766/o012：旧core66点、median1141.7869mm、MAD2.7448mm；背景约1182mm。
  筛选选中了远侧57点、median12254.6191mm、MAD20.7900mm、主导率76%，
  背景差约−11073.18mm。全部是原始有限正值，没有补全或伪造；
  但密集且稳定的正深度仍可构成异常组件。55/57点在人工鱼体轮廓内，
  所以轮廓纯度竟为96.49%，不能当作深度正确率。缺设备量程/水体校准真值，
  物理正确性明确为UNKNOWN，不编造传感器根因。

同一配对对象旧core轮廓纯度99.6213%，已接近代理上限；冻结的提升≥10个百分点
门槛事后可见不可达到。本轮仍保留FAIL，不改门槛回写PASS；同时明确该门槛不能
判别用户指出的鱼体轮廓内部有效背景问题。F2纯度实际下降0.7049个百分点，
但有效采样约为旧core的3.49倍；不能只称扩大样本为改善，也不能把代理失败
扩展为任何深度前景筛选都无效。毫米深度准确、物理背景分离和跟踪增量均未获证实。

'''
    assert '## 两个真实失败病例' not in text
    report.write_text(text.replace('## 工程与封存证据',explanation+'## 工程与封存证据'),encoding='utf-8')
    inspected=json.loads((HERE/'VISUALIZATION_FILES.json').read_text())
    for item in inspected: verify(item['artifact'])
    write_new(HERE/'VISUALIZATION_INSPECTION.json',dict(status='ALL_THREE_ACTUALLY_OPENED_WITH_VIEW_IMAGE',
        time_utc=datetime.now(timezone.utc).isoformat(),files=inspected,
        observations=['F701/o001 coherent near-depth raw band.',
          'F701/o003 weak/small component refused with original evidence retained.',
          'F704/o013 wrong side branch outside manual outlines; retained failure.'],
        caution='Display clips800–1300mm; numeric audit including12254mm is authoritative.'))
    freeze=json.loads((HERE/'FREEZE.json').read_text())
    seal=json.loads((HERE/'MEASUREMENTS_SEALED.json').read_text())
    scored=json.loads((HERE/'SCORING_SEALED.json').read_text())
    write_new(HERE/'EXECUTION_LOG.json',dict(review_base=freeze['base'],checks='10/10 real F701',
        frozen_utc=freeze['clock_utc'],measurements_sealed_utc=seal['sealed_utc'],scoring_ended_utc=scored['ended_utc'],
        frames=1066,masks=28382,source_and_baseline_equivalence='ALL_EXACT',
        inference_http=0,smoke=0,cost_usd=0,rule_changes_after_freeze=0,
        postscore_only=['report.py','failure_audit.py','finalize.py'],
        commands=['python checks.py','python runner.py','python evaluate.py','python report.py','python failure_audit.py','python finalize.py'],
        measurement_or_scoring_failures=0,status='COMPLETE_PROXY_FAIL_PHYSICAL_UNKNOWN'))
    (HERE/'README.md').write_text((HERE/'README.md').read_text(encoding='utf-8')+'''

## Completed outcome

See RESULTS.md, SUMMARY.json, FAILURE_CASE_AUDIT.json and MEASUREMENT_SUMMARY.svg.
Engineering/input PASS. Fixed silhouette proxy FAIL:99.6213% core versus98.9165%
filtered,50.5329% fish retention and72.9140% old-core-usable coverage. No new
tracker result. The proxy misses a12254.6mm component inside a fish silhouette;
physical correctness remains UNKNOWN. Postscore reporting/failure/inventory
scripts do not re-run the filter or change scoring. Three private images were
actually viewed. Delivery proof: REMOTE_VERIFICATION.json (actual result push).
''',encoding='utf-8')
    intro='''Current result,2026-09-30: [DS3 foreground depth measurement](experiments/ds3_depth_foreground_filter/RESULTS.md) processed all28,382 saved SOURCE_OLD masks in1066 exposed DS2 frames. Local-background + significant depth contrast + connectivity filter is implemented:18,862 AVAILABLE/9,520 UNKNOWN; original masks/whole/core exactly reproduced;10 tests pass, seals precede reference scoring. **Fixed proxy FAIL / physical depth UNKNOWN**: core99.6213%→filter98.9165%, fish retention50.5329%, core-usable coverage72.9140%. F704 picks a wrong side branch; F766 accepts12254.6mm despite96.49% silhouette purity. No tracker change or new tracking/API/training/SAM3/completion result; cost0. [Current handoff](research/HANDOFF.md): one next step is an independent foreground/background/anomalous-depth pixel audit on these sealed selections.

'''
    index='''## DS3: foreground depth measurement — proxy FAIL / physical UNKNOWN

[Results](experiments/ds3_depth_foreground_filter/RESULTS.md), [freeze](experiments/ds3_depth_foreground_filter/FREEZE.json), [summary](experiments/ds3_depth_foreground_filter/SUMMARY.json), [failure cases](experiments/ds3_depth_foreground_filter/FAILURE_CASE_AUDIT.json).1066 exposed SOURCE_OLD frames,28,382 masks;18,862 AVAILABLE/9,520 UNKNOWN. Whole/core and masks exact;10 checks pass. Paired purity99.6213%→98.9165% (−0.7049pp), retention50.5329%, core-usable coverage72.9140%. Wrong side branch and stable12254.6mm component show significant connected contrast is not certified fish depth. No tracking/API/training/SAM3/completion; cost0. Old DS1/DS2 unchanged. Next: independent per-pixel foreground/background/anomaly audit without retuning this frozen rule.

'''
    for filename,section in [('README.md',intro),('EXPERIMENT_INDEX.md',index)]:
        original=subprocess.check_output(['git','show',f'HEAD:{filename}'],cwd=ROOT)
        first,rest=original.split(b'\n',1)
        if filename=='README.md': rest=rest.replace(b'Current result,2026-09-30:',b'Archived DS2 result,2026-09-30:',1)
        (ROOT/filename).write_bytes(first+b'\n\n'+section.encode('utf-8')+rest.lstrip(b'\r\n'))
    original=subprocess.check_output(['git','show','HEAD:research/HANDOFF.md'],cwd=ROOT)
    original=original.replace(b'# Active handoff',b'# Historical handoff',1)
    handoff='''# Active handoff — DS3 foreground depth measurement,2026-09-30

Read experiments/ds3_depth_foreground_filter/RESULTS.md, PLAN/CONFIG/SOURCE_CONTRACT,
CHECKS/FREEZE/SOURCE_INVENTORY/OLD_READONLY_LOCK, MEASUREMENTS_SEALED/SCORING_SEALED,
SUMMARY/OCCUPANCY_AUDIT, FAILURE_CASE_AUDIT, restricted/visualization/public inventories,
execution/timing/logs and actual remote proof. Base:b43a4ca62229e878b62ed81ea6c7327128636564.
Measurement development on reused, exposed DS2 frames701–1060/1201–1906; not new validation.

Engineering/input PASS; fixed silhouette proxy FAIL; physical depth and tracking
increment UNKNOWN.28,382 masks:18,862 AVAILABLE/9,520 UNKNOWN;28,088 scorable/294
unscorable.18,441 paired objects:99.6213% core→98.9165% F2 (−0.7049pp), retention
50.5329%, core-usable coverage72.9140%. Core proxy ceiling makes the frozen10pp
target unattainable; FAIL unchanged. This does not prove background inside a
fish silhouette absent. F704 picks20 wrong-side pixels; F766 selects57 raw pixels
at12254.619mm versus1141.787mm core, despite96.49% silhouette purity.

All original masks and whole/core exact;10 tests pass; extraction blocks network,
manual references and non-depth_mm keys; sealing precedes human labels. The
new stateless filter retains uncertainty/pixel provenance. DS1/DS2, tracking,
triggers/q/references/candidates/weights/publication unchanged. Three QA images
actually viewed; pixels private. API/smoke/training/SAM3/completion/cost0.
No new tracking score. Reporting/failure/inventory scripts are postscore only.

One next step: independent foreground/background/anomalous-depth per-pixel audit
on these sealed selections before deciding on DepthState integration.
Do not retune this frozen run or automatically add VLM.

'''
    (ROOT/'research/HANDOFF.md').write_bytes(handoff.encode('utf-8')+original)
    items=[artifact(path) for path in sorted(HERE.rglob('*')) if path.is_file()
           and 'private' not in path.parts and '__pycache__' not in path.parts
           and path.name not in ('ARTIFACT_MANIFEST.json','REMOTE_VERIFICATION.json')]
    write_new(HERE/'ARTIFACT_MANIFEST.json',dict(public_files=len(items),items=items,
        private_pixels_uploaded=False,old_outputs_overwritten=False))
    print('finalized report, byte-preserving root updates and public manifest')


if __name__=='__main__': finalize()
