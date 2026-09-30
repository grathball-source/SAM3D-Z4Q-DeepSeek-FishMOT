"""Append-only experiment delivery and public/private inventory; no prediction changes."""
from __future__ import annotations
import gzip
import json
import subprocess
from pathlib import Path
from common import HERE,ROOT,RUN,DATA,SEGMENTS,ARMS,input_dir,read,rows,sha,write_new,artifact,verify_item

BASE='ced663d97cadc23138c538f5784df7ed4e835fe2'

def sync(path,prefix,replace_header=False):
    original=subprocess.check_output(['git','show',f'{BASE}:{path}'],cwd=ROOT)
    target=ROOT/path
    assert target.read_bytes()==original,'unrelated edits: '+path
    if replace_header:
        original=original.replace(b'# Active handoff',b'# Historical handoff',1)
    target.write_bytes(prefix.encode('utf-8')+original)

def json_safe(value,path='$'):
    if isinstance(value,dict):
        assert not ('size' in value and isinstance(value.get('counts'),str)),'public RLE: '+path
        for k,v in value.items():
            assert k.lower() not in ('api_key','authorization','provider_file_id','gt_raster','source_index_array'),path
            if k.lower() in ('rgb_pixels','depth_pixels','instance_id'):
                raise AssertionError('public pixel/GT field: '+path+'.'+k)
            json_safe(v,path+'.'+k)
    elif isinstance(value,list):
        for index,v in enumerate(value):
            json_safe(v,f'{path}[{index}]')

def main():
    summary=read(HERE/'SUMMARY.json');metrics=read(RUN/'METRICS.json')
    audit=read(RUN/'EVENT_AUDIT.json')
    assert (HERE/'VISUALIZATION_INSPECTION.json').exists()
    for name in ('POSTRUN_SOURCE_REVIEW.json','POSTRUN_DEPTH_REVIEW.json','POSTRUN_SCORE_REVIEW.json'):
        assert (HERE/name).exists(),name
    for item in read(HERE/'OLD_READONLY_LOCK.json')['artifacts']:verify_item(item)
    for filename,digest in read(RUN/'SCORING_SEALED.json')['artifacts_sha256'].items():
        assert sha(RUN/filename)==digest
    assert summary['frames']==1471 and summary['objects']==39208
    restricted={}
    def add(path):
        path=Path(path)
        if path.is_file():restricted[str(path.resolve())]=artifact(path)
    for name,(start,stop) in SEGMENTS.items():
        base=input_dir(name)
        for path in base.iterdir():add(path)
        for item in read(base/'sources.json'):
            add(item['prediction_path']);add(item['depth_path'])
        for f in range(start,stop+1):
            add(DATA/'depth_native_mm'/f'{f:06d}.npy')
            add(DATA/'labels_640x360'/f'{f:06d}.json')
    for root in (HERE/'private',HERE/'slice'):
        for path in root.rglob('*'):add(path)
    # Old RLE source binding used only by postseal exact-F6 verification/QA.
    for name,(start,stop) in SEGMENTS.items():
        if start>=701:
            add(ROOT/'experiments/ds4_depth_quality_repair/private'/f'{name}_pixels.jsonl.gz')
    inventory=list(restricted.values())
    write_new(HERE/'RESTRICTED_INVENTORY.json',dict(
        files=inventory,total_files=len(inventory),total_bytes=sum(x['bytes'] for x in inventory),
        uploaded=False,private_pixels=True,
        dependencies='SOURCE_OLD raw SAM3 polygons + aligned raw depth/source_index/native + original cache assignment RLE; human labels only after all seals for scoring; existing local deps from ENVIRONMENT',
        reproduce='fresh sibling DS6 output layout retaining parent code/paths; preflight, tests, score_checks, launch slice then full, evaluate, postrun; never rerun into an existing seal directory',
        public_exclusions='No raw/GT raster, RGB, mask RLE or credential uploaded; original masks are referenced by n: frame-local tokens in public predictions'))

    pooled=metrics['pooled_metrics'];table=[];segments=[]
    for arm in ARMS:
        v=pooled[arm]
        table.append('|'+arm+'|'+('|'.join(f'{v[k]:.4f}' for k in ('IDF1','HOTA','AssA')))+
                     '|'+('|'.join(str(v[k]) for k in ('IDSW','FP','FN')))+'|')
    for name,values in metrics['segment_metrics'].items():
        for arm in ARMS:
            v=values[arm]
            segments.append('|'+name+'|'+arm+'|'+('|'.join(f'{v[k]:.4f}' for k in ('IDF1','HOTA','AssA')))+
                '|'+('|'.join(str(v[k]) for k in ('IDSW','FP','FN')))+'|')
    diffs=[]
    for other in ('SAM3_NATIVE','D0_GEOMETRY','D2_CORE_FROZEN','D4_F6_SCALAR'):
        d=metrics['pooled_delta']['D5_MULTIFRAGMENT_vs_'+other]
        diffs.append(f"|D5−{other}|{d['IDF1']:+.4f}|{d['HOTA']:+.4f}|{d['AssA']:+.4f}|{d['IDSW']:+d}|")
    causal=read(HERE/'CAUSAL_EVIDENCE_ANALYSIS.json')
    restores=[];action_table=[]
    for arm in ARMS[1:]:
        counts=audit['summary'][arm];first=audit['first_public_summary'][arm]
        restores.append(f"|{arm}|{counts['CORRECT']}|{counts['WRONG']}|{counts['NOT_STAGED']}|{counts['UNSCORABLE_OR_NO_BIJECTION']}|{counts['NO_SPLIT']}|{counts['UNCONFIRMED']}|{first['CORRECT']}|{first['WRONG']}|{first['UNSCORABLE_OR_NO_BIJECTION']}|")
        a=causal['real_state_actions'][arm]
        action_table.append(f"|{arm}|{a.get('COMMIT',0)}|{a.get('RESOLVE_NO_ID_CHANGE',0)}|{a.get('LOCAL_FALLBACK_COMMITTED',0)}|{a['changed_sources']}|")
    cover=[]
    totals={}
    for name,v in summary['coverage'].items():
        c=v['counts']
        for key,value in c.items():totals[key]=totals.get(key,0)+value
        cover.append(f"|{name}|{v['objects']}|{c.get('raw_core_available',0)}|{c.get('f6_filter_AVAILABLE',0)}|{c.get('history_available',0)}|{c.get('multi_qualified',0)}|")
    shadow=summary['same_state_shadow']
    status=summary['depth_increment']
    # One evidence-driven next step only; this experiment itself is frozen.
    next_step='在固定四段上只消融“必须四边全部可用”的缺测门，验证候选一致的缺测边际化能否保留有效单身份深度证据；触发、历史资格、权重与事务保持冻结。'
    write_new(HERE/'NEXT_STEP.json',dict(next_step=next_step,automatic_execution=False,automatic_model_addition=False))
    text=f"""# DS6 多深度片段：完整跟踪性能试验

## 主判定

**TRACKING_TRIAL_COMPLETE；工程与原始输入合同PASS；深度增量：{status}。**
四段1471帧、39208原mask全部完成五个独立分支。预测全体封存后才读取人工参考评分。
这些片段均已开发曝光，同录像结果不构成盲测或泛化。表面物理归属、毫米深度真值仍UNKNOWN；本轮没有将它们作为性能试验启动门。

## 冻结设计与实际修改

复用NE1原生优先/S0-P、原扫描规则/q/二维项/权重/参考/原mask/事务。
D2真实调用原DepthState/dynamic_choice。新D4/D5复用F6旧函数体但在隔离globals执行；
原native>5m只作为SUSPECT质量策略。新表示保留F6实际selected原始点上的30mm图所有匿名片，
n≥16、占比≥.2、scale≤60才纳入似然；closing从不补测量值。
只有唯一合格片进入同版本风险隔离的pre历史；多片UNKNOWN仍完整留在事实表。
q D4整体scalar与D5等权归一多片似然，共同四边缺测模型、权重.25。
各支实际更新自己的bank/public/epochs并延续，不修改最终输出冒充状态改变。

D5−D4的同状态影子隔离q表示；全段分支分叉包含后续状态效应。
D4−D2同时改变选点、历史资格与共同缺测规则，不能称纯滤波收益。
D0仍有共用controller的旧深度质量规则，并非端到端无深度系统。

## 完整总体指标

|分支|IDF1|HOTA|AssA|IDSW|FP|FN|
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(table)}

所有原mask均评分；公开ID同帧一对一，负ID不忽略、不改正数绕过切换。
总体使用官方TrackEval直接评分全部帧，段间身份命名空间隔离，不平均分段率。
完整来源、原字段和所有逐帧新增/消除切换见run/METRICS、SCORE_PROVENANCE、SWITCH_LEDGER。

|对照|ΔIDF1 pp|ΔHOTA pp|ΔAssA pp|ΔIDSW|
|---|---:|---:|---:|---:|
{chr(10).join(diffs)}

## 分段结果

|片段|分支|IDF1|HOTA|AssA|IDSW|FP|FN|
|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(segments)}

## 全部事件与首次发布

|分支|接受映射正确|接受映射错误|未stage/回退|接受映射不可评分|无分离|未确认|首发正确|首发错误|首发不可评分|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(restores)}

|分支|实际COMMIT|无ID变化resolve|局部fallback|改动source数|
|---|---:|---:|---:|---:|
{chr(10).join(action_table)}

D5的8次正确接受中，1次实际COMMIT、7次无ID变化；5次错误接受全部无ID变化。
D2的10次正确接受中，3次COMMIT、7次无ID变化；3次错误接受全部无ID变化。
各支5次fallback中，首发1次正确、4次不可评分；不能把18个q都写成可评分。
上述“正确”按实际bank anchor与当前post的RGB轮廓对应事后核验，
不把整数ID偶然换回算作物理恢复，不把人工轮廓当深度表面真值。
原公共ID进入前已错/与anchor物理身份不同、缺失、冲突、无联合bijection均分列，
全部事件、首发映射与片段事后共识见EVENT_AUDIT及FRAGMENT_REFERENCE_AUDIT。
未提交、不可评分、UNKNOWN不能算保护通过。

## 深度覆盖与实际增量

|片段|原对象|原core可用|F6选点可用|新历史单片可用|多个合格片|
|---|---:|---:|---:|---:|---:|
{chr(10).join(cover)}

新历史规则可用{totals.get('history_available',0)}/{39208}对象；
多片{totals.get('multi_qualified',0)}对象的匿名事实保留，不认证为pre单值。
同状态首分离影子{shadow['events']}个，其中共同四边证据可用{shadow['joint_available']}个，
scalar→multi原始选择变化{shadow['scalar_vs_multi_choice_changes']}个。
两次current多合格片的q（F415/F419）均不满足joint证据；没有多片歧义场景实际参与完整深度决策。
5个joint可用q的两个post都只有1个合格片。因此本轮对多片表示的有效身份增量仍证据不足，
不能把零作用结论推广为多片/完整历史关联无效。

### 负结果的具体来源

- F419：新pre B无合格历史，另一个post被F6判多connected-component歧义；joint全归零，旧core H2变回几何H1。
- F519：pre A的F508 F6无合格component；F510虽有深度但处于neighbors风险，保持隔离。新joint归零，旧core H2变H1。
- 两处丢失旧core正确提交使D5相对D2下降0.4714pp IDF1、0.3869pp HOTA、0.6795pp AssA，IDSW+4。
- F1280也出现core H2→新H1，但两支都有残片阻止联合提交并走局部fallback，不算深度实际身份贡献。
- 18个q中2个没有数值候选对，另11个缺joint证据，5个joint可用；未知与不可提交全保留。

工程来源与数据读写已通过；当前无收益主要来自本轮保守历史资格/四边共同缺测门抑制了旧有效信息，
以及实际事件缺乏可用的多片歧义配对。未观察到多片模块额外制造错误状态动作，
也不能把D0相对native的旧共用底座损害计为多片模块独有损害。
逐q完整预测/缺失原因、old core比较及真实事务见CAUSAL_EVIDENCE_ANALYSIS。
不能把选点proxy改善、宽尺度覆盖或事实缓存数量称作跟踪提升。
新旧预测各对照实际改变帧数见METRICS.changed_frames；用这些和真提交区分未起作用与起作用但错误。
后1066帧全部{summary['f6_exact_old_objects']}对象F6 selector逐事实精确复现DS4，
旧core/几何/原生三支全1471帧逐条精确复现，未换源掩盖损害。

## 工程验收、技术尝试与计时

16项实际测量/状态单测＋11项评分合成检查通过，不代替实际成绩。
首个合法真实source→测量→score→stage→首次publish切片在F415 q(local65)跑通。
首轮路径guard误用substring挡住depth_rgb目录，在任何FREEZE/measurement之前0帧退出；
仅改为精确RGB目录段检查，失败日志与空尝试保留。静态漏判在独立修复review明确纠正。
正式冻结后未改算法、阈值或受试源码。
旧347个DS1–DS5公开文件逐SHA复核，原输入/旧seal只读。

四段五支顺序循环计时合计{summary['branch_independent_elapsed_seconds']:.3f}秒，
含循环内原NPZ/native加载、quality hash、原core/F6共算、四状态和公开输出；
不含启动读assignments/manifest/scan及输入freeze hash，不含原SAM3推理。
共算测量时间不是每支独立运行的速度，未证明实时部署。逐q评分/每帧发布延迟见PERFORMANCE/PUBLISH_LEDGER。
预测期路径和实际NPZ字段审计仅depth_mm/source_index，禁止RGB/人工参考/v3与socket连接。
新增模型HTTP/smoke/训练/SAM3推理/补全服务/费用全部0，不需要DeepSeek key。

## 交付、未完成边界与复现

代码、固定方案/常量、单测、评分验收、公开预测/状态/事件/日志、
全指标与纯数字图全部在本目录。实际原深度/mask QA在private，已实际查看；
原pixels/RLE/GT raster/密钥未公开。受限{len(inventory)}个文件、
{sum(x['bytes'] for x in inventory)}字节，逐路径/大小/SHA及复现依赖见RESTRICTED_INVENTORY。
旧DS1–DS5均保留。本轮commit与actual origin/main SHA、每个新增Git blob及关键远端文件读取证明见REMOTE_VERIFICATION。
main正常推送，不force。没有新VLM成绩或模型付费调用。

仍未完成：独立录像验证、物理表面标签/毫米校准、SAM3前端未知批次未来支持的认证。
本轮完整性能试验已完成，以上边界不用于隐去任何失败或弃权。

## 一个下一步

{next_step}
"""
    with (HERE/'RESULTS.md').open('x',encoding='utf-8',newline='\n') as handle:handle.write(text)
    brief=(f"Current result,2026-09-30: [DS6 complete multi-fragment depth tracking trial]"
        f"(experiments/ds6_multifragment_depth_tracking/RESULTS.md) completed all1471 exposed SOURCE_OLD frames "
        f"and39208 masks, five independent branches. **{status}.** "
        f"D5 IDF1/HOTA/AssA={pooled['D5_MULTIFRAGMENT']['IDF1']:.4f}/"
        f"{pooled['D5_MULTIFRAGMENT']['HOTA']:.4f}/{pooled['D5_MULTIFRAGMENT']['AssA']:.4f}, "
        f"IDSW{pooled['D5_MULTIFRAGMENT']['IDSW']}; normalized multi-piece q representation changes"
        f"{shadow['scalar_vs_multi_choice_changes']}/{shadow['events']} same-state choices. "
        f"Old native/geometry/core controls exact; all seals precede GT scoring. "
        f"27necessary synthetic checks pass; physical depth/surface ownership UNKNOWN. "
        f"NoAPI/training/SAM3/completion/cost. Private QA stays local. "
        f"[Current handoff](research/HANDOFF.md) provides one next step.\n\n")
    sync('README.md', '# DeepSeek + Z4Q Fish MOT research archive\n\n'+brief,
         False) if False else None
    original=subprocess.check_output(['git','show',f'{BASE}:README.md'],cwd=ROOT)
    assert (ROOT/'README.md').read_bytes()==original
    header=b'# DeepSeek + Z4Q Fish MOT research archive\r\n\r\n'
    if not original.startswith(header):header=b'# DeepSeek + Z4Q Fish MOT research archive\n\n'
    (ROOT/'README.md').write_bytes(header+brief.encode()+original[len(header):].replace(b'Current result,2026-09-30:',b'Archived result,2026-09-30:',1))
    sync('EXPERIMENT_INDEX.md','# DS6 complete multi-fragment tracking trial\n\n'+brief)
    sync('research/HANDOFF.md',f"""# Active handoff — DS6 full performance trial,2026-09-30

Read experiments/ds6_multifragment_depth_tracking/RESULTS.md/PLAN/CONFIG,
INPUT_REVIEW/old lock/effective settings,16unit+11scoring checks, all four segment
FREEZE/PREDICTIONS_SEALED and ALL_PREDICTIONS_SEALED/access audit,
METRICS/actual EVENT_AUDIT/SWITCH_LEDGER/FRAGMENT_REFERENCE_AUDIT,
SUMMARY/postrun reviews, private QA inspection/restricted inventory/remote proof.
Base{BASE}; complete1471 exposed frames/five branches/39208 masks.
Engineering/source PASS; depth increment {status}. Surface identity UNKNOWN.
Scalar vs multi shared-history same-state q choices changed{shadow['scalar_vs_multi_choice_changes']}/{shadow['events']}.
Old three controls fully exact; all prediction seals precede GT scoring.
No model/API/training/SAM3/completion/cost. No private pixel or old seal change.
One next step: {next_step}
Not started automatically; do not retune this frozen version or add models.

""",True)
    public=[]
    for path in sorted(HERE.rglob('*')):
        if not path.is_file() or any(p in ('private','slice','__pycache__') for p in path.relative_to(HERE).parts):continue
        assert path.suffix not in ('.png','.jpg','.npz','.npy','.pyd','.mp4')
        if path.suffix=='.json':
            json_safe(read(path))
        elif path.name.endswith('.jsonl.gz') or path.suffix=='.jsonl':
            for value in rows(path):json_safe(value)
        public.append(artifact(path))
    write_new(HERE/'ARTIFACT_MANIFEST.json',dict(public=public,total_files=len(public),
        total_bytes=sum(x['bytes'] for x in public),private_pixels_uploaded=False,
        restricted_inventory=artifact(HERE/'RESTRICTED_INVENTORY.json'),
        remote_proof='REMOTE_VERIFICATION appended after first commit; final proof commit separately verified'))
    print(json.dumps(dict(public_files=len(public),public_bytes=sum(x['bytes'] for x in public),
        restricted_files=len(inventory),restricted_bytes=sum(x['bytes'] for x in inventory)),ensure_ascii=False))

if __name__=='__main__':main()

