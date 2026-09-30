"""Postaudit delivery only; never alters frozen computation or old results."""
import json
import subprocess
from pathlib import Path
from audit import HERE,ROOT,DS4,ARMS,artifact,verify,write_new,check_old


def sync(path, transform):
    original=subprocess.check_output(['git','show',f'HEAD:{path}'],cwd=ROOT)
    p=ROOT/path
    assert p.read_bytes()==original,'refuse overwrite unrelated edits'
    p.write_bytes(transform(original))


def run():
    assert not (HERE/'RESULTS.md').exists(),'refuse overwrite'
    check_old()
    for filename in ('POSTAUDIT_REVIEW.json','POSTAUDIT_SOURCE_REVIEW.json','POSTAUDIT_FAILURE_REVIEW.json'):
        assert (HERE/filename).is_file(),filename
    for filename in ('AUDIT_SEALED.json','REPORT_SEALED.json'):
        for item in json.loads((HERE/filename).read_text(encoding='utf-8'))['artifacts']: verify(item)
    summary=json.loads((HERE/'SUMMARY.json').read_text(encoding='utf-8'))
    figures=json.loads((HERE/'VISUALIZATION_CAPTION_REPAIR.json').read_text(encoding='utf-8'))['new_figures']
    assert len(figures)==9
    for item in figures: verify(item['artifact'])
    write_new(HERE/'VISUALIZATION_INSPECTION.json',dict(status='ALL_NINE_CAPTION_V2_FIGURES_ACTUALLY_VIEWED',
        images=figures,original_clipped_figures_preserved=True,GT_raster_public=False,
        findings=['F1821 two raw-value clusters and weight reversal visible',
        'F747 within-silhouette gradient and changed sampling visible',
        'F1044/F1385 source/reference mismatches preserved; physical ownership not fabricated',
        'F766/F1319 SUSPECT points explicit red; missing depths remain missing']))
    restricted={}
    def add(item):
        verify(item); restricted[str(Path(item['path']))]=item
    for item in json.loads((HERE/'OLD_READONLY_LOCK.json').read_text(encoding='utf-8')):
        if 'private' in Path(item['path']).parts: add(item)
    oldsource=json.loads((DS4/'SOURCE_INVENTORY.json').read_text(encoding='utf-8'))
    for source in oldsource['original'].values():
        for r in source:
            for key in ('prediction','depth'): add(dict(path=r[key+'_path'],bytes=r[key+'_bytes'],sha256=r[key+'_sha256']))
    for item in oldsource['native']: add({k:v for k,v in item.items() if k in ('path','bytes','sha256')})
    newsource=json.loads((HERE/'SOURCE_INVENTORY.json').read_text(encoding='utf-8'))
    for row in newsource['cohort']:
        for item in row['artifacts'].values(): add(item)
    for p in sorted((HERE/'private').rglob('*')):
        if p.is_file(): add(artifact(p))
    inventory=list(restricted.values()); total=sum(i['bytes'] for i in inventory)
    write_new(HERE/'RESTRICTED_INVENTORY.json',dict(files=inventory,total_files=len(inventory),total_bytes=total,
        uploaded=False,scope='Bound source pixels, old private read-only verification dependencies and new private QA',
        reproduction='Original SOURCE_OLD raw polygons, raw depth/source_index/native and current RGB/labels at these paths; retain DS1-DS4 code/seals; fresh sibling DS5 directory; no API/key/GPU/v3',
        physical_labels='No certified per-pixel depth-surface labels available'))
    pooled=summary['groups']['POOLED']; lines=[]; shadow=[]; grids=[]
    for arm in ARMS:
        v=pooled[arm]
        for gap in (30,60):
            g=v['depth_graphs'][str(gap)]
            lines.append(f"|{arm}|{gap}|{v['available']}|{v['unknown']}|{v['selected_fragments_more_than_one']}|{g['multiple_pieces']}|{g['multiple_qualified_pieces']}|")
        old=v['depth_graphs']['30']['old_fixed_R_reference_status']
        shadow.append(f"|{arm}原选择|—|{old.get('C',0)}|{old.get('D',0)}|{old.get('U',0)}|")
        for gap in (30,60):
            s=v['depth_graphs'][str(gap)]['largest_piece_shadow_R_reference_status']
            shadow.append(f"|{arm}最大匿名片段影子|{gap}|{s.get('C',0)}|{s.get('D',0)}|{s.get('U',0)}|")
    for group in ('registration_cases','registration_controls'):
        for arm in ARMS:
            g=summary[group][arm]
            grids.append(f"|{group}|{arm}|{g['zero']['fish_fraction']*100:.4f}%|{g['nonzero_fraction_range'][0]*100:.4f}%–{g['nonzero_fraction_range'][1]*100:.4f}%|")
    text=f'''# DS5 完整复盘与实验报告

## 主判定与实际执行

**AUDIT_COMPLETE；物理表面归属与物理配准正确性仍UNRESOLVED。**
实际完成深度片段与坐标敏感性实验，未产生新的提取器或跟踪成绩。
预冻结详细方案见PLAN.md、CONFIG、三份独立*_REVIEW；FREEZE绑定代码/样本/来源。
main基点56c2ea61682edea71328976c4fed27230f334c2a；旧DS1–DS4全只读。
全部1066开发帧、28382原mask完成。原Q28088/R21817和294不可评分不变。
73诊断病例、59去重稳定对照，共132；14病例无合格同参考可用性对照仍保留。
44新增冲突、9零匹配鱼体、每段最早8低保留、9旧哨兵全部入列，重合去重不挑好例。
8直接相关检查通过；正式完整审计一次，耗时{summary['runtime_seconds']:.3f}s。
本地现有D-MOT Python/NumPy/OpenCV/SciPy，原生数学线程1、GPU0，无服务器安装。
模型HTTP/smoke/训练/SAM3/补全/跟踪运行/费用均0；不读future像素、instance_id或v3。
时序和cohort为已曝光诊断资料，不能称盲测泛化。

## 1. 失败归因需要分开

掩码内有效深度只证明存在测量，不认证来自指定鱼。空间连通、小MAD也不认证单一表面。
但不能把全部失败都归背景：44新增冲突有13例选点100%位于匹配RGB轮廓；
39个原兼容→冲突病例均扩采、median均向较大深度变化，位移中位11.535mm。
鱼体姿态/梯度、取样空间位置变化、另一鱼占用、源异常与参考污染须分别记录。
RGB人工轮廓不是独立深度表面真值；SOURCE_OLD上游SAM3批内lookahead仍UNKNOWN。

F1821旧F2同片段已有低/高簇20/14点，簇median约823.000/1117.647mm。
原值排序最大gap254.875mm；F6变20/66点，52新增点全部进高簇，
高簇占比41.18%→76.74%。整体median838.139→1136.486，
MAD17.673→10.727反而下降。与840.761mm共识参考发生冲突，
但低簇也未获独立物理认证。不能把“更贴近旧参考”称真正鱼体。
混合分布压成一个代表值会掩盖解释歧义；多数投票、小MAD不能解决来源归属。

## 2. 全量连通与深度片段

原F2/F6全部选点不变。30/60mm来自旧contrast/foreground尺度，只作影子诊断，
不是认证的邻域噪声阈值。空间8邻与真实选点深度约束图分开，无补孔/插值/重选。

|原臂|边差mm|可用|UNKNOWN|真实点多空间片|深度图多片|至少两个n≥16且占比≥20%片段|
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(lines)}

F6有8891/21586（41.19%）实际点集多片，而原closed support单片。
这证明闭运算连接稀疏/缺测片段，不表示8891个错误或8891个物理表面合并。
多个qualified深度片也可能是同深度的空间断裂：F6的782/741组片段最大median差
中位仅12.553/12.036mm，q90约77.364/80.235mm。不能将每个多片叫多层或多鱼。
完整逐对象片段n/比例/median/MAD、最大gap、q90−q10在CENSUS；
POSTAUDIT_FAILURE_REVIEW独立BFS及连续片段差分布完整保留。

## 3. 最大匿名片段有代价，不直接升级

仅对固定R21817做数值反事实；并列最大或最大不足16点/20%保持UNKNOWN。
没有新测量或状态回放；C/D仅为原raw RGB轮廓共识兼容/冲突。

|描述|边差mm|C|D|U|
|---|---:|---:|---:|---:|
{chr(10).join(shadow)}

F6最大30mm片段影子相对原F6：C−92、D−14、U+106；
60mm影子C−103、D不变、U+103。30mm的旧44局部结果16C/25D/3U，
60mm为7C/35D/2U，不能把局部恢复兼容当全人口收益。
独立逐对象转移还确认30mm全R新增7个C→D、101个C→U。

F1821最大簇仍是66点高簇1138.850mm，靠最大簇无法恢复原参考解释。
F747原/新全部在轮廓内；30mm主片314点median1062.859，
相对参考1017.662误差45.197，仍略超45mm容差。取样位置/鱼体梯度可能改变代表值，
不能直接判物理错误或背景污染。
F1044新19点全在其他鱼RGB轮廓；30mm分成12/7点，两者不足16。
F1385新59点全在其他鱼，仍共识兼容；其53点主片MAD3.389不认证身份。
因此本轮没有部署“取最大簇”提取器，也没有挑选30mm影子作为新成绩。

## 4. 空间配准与来源

SOURCE_REVIEW核验1907对原帧均为唯一最近时间戳，1471包内时序一致：
RGB早1ms1050帧、早2ms857帧。它不能排除运动造成的局部视差。
5固定帧原RGB SHA、缩小图逐像素INTER_AREA、native来源SHA、
整个depth_mm/source_index重投影精确复现。
POSTAUDIT_SOURCE_REVIEW独立核cohort同源投影；POSTAUDIT_REVIEW核全1066来源事后SHA。
这支持软件来源/投影合同可复现，不能判水下物理标定已正确。

recorded R的det=0.993885946、max|RᵀR−I|=0.012190667，
singular values约[1,1,0.99388594]。SDK/BAG同源记录不构成独立物理校准。
固定同native来源、原生Z、t/K/畸变，仅以nearest properSO3替R做连续uv影子；
不重zbuffer、不重采样、不变输入。源审计5帧全部≤5m winner影子位移中位约0.75px、
q90约1.38px、最大1.738px；cohort全量逐对象位移/Z差/raster舍入误差见REGISTRATION。
矩阵结构问题应披露，但其物理正确性和具体失败因果仍UNKNOWN，不自动SVD修正。

49格整数平移（−9至9、步3）固定原匹配/点数/值，出界仍在原n分母且单列，
不绕回、不插值。零移位每对象精确复现DS4；病例和稳定对照都是曝光诊断。

|队列|原臂|零移位匹配RGB轮廓占比|全部非零格占比范围|
|---|---|---:|---:|
{chr(10).join(grids)}

两固定队列、两臂均无统一非零格优于零移位；该格网未支持“大范围统一平移”解释。
不表示所有个体都已对齐，也没检验亚像素、局部非线性折射、真实表面或时间校正。
F701/F1044/F1385个別非零格改善占用，只说明局部坐标敏感，不能据GT挑warp。
最近depth jump距离可能来自邻鱼/背景/稀疏投影，不是物理配准准确率。

## 5. 独立验收、图像与交付

POSTAUDIT_REVIEW独立复核完整28382键、113528图资格分区、132cohort，
12936 shift分区、264零shift绑定、汇总及3749文件/2.62GB SHA通过；
其中包括345旧只读文件及全1066帧3200项预测/depth/native事后绑定。
POSTAUDIT_FAILURE_REVIEW用独立BFS回算44×2×2原选点图；
POSTAUDIT_SOURCE_REVIEW核同native投影和有限/正Z，不借用GT矫正。

9固定案例的当前RGB/来源轮廓/人工RGB轮廓、原深度、F2/F6实际点、
共同直方图和49格都已实际打开。首版长标题左边裁切，原图/冻结代码保留；
新caption脚本只换行/tight保存重绘，9新图全实际核查。
所有RGB、depth、GT栅格、RLE留private；公开SVG仅封存计数。
受限依赖和QA共{len(inventory)}文件、{total}字节，真实path/bytes/SHA在RESTRICTED_INVENTORY，
包括旧只读核验依赖，不把文件数当新增测量数。
重现需README所列原来源和旧代码/seal，在新同层目录运行，不覆盖旧输出。
原完整BAG的历史摘要证据沿用DS4，本轮未重新hash整段BAG，不伪称独立硬件验证。

代码、配置、测试、公开日志、全S数值、cohort完整曲线、独立review、
完整报告与数字图正常提交并push main，实际远端ref/关键文件核验见REMOTE_VERIFICATION。
commit/main实际SHA在最终交付给出；正文不预猜。
物理表面/距离独立标注、水下标定认证、盲测泛化、新DepthState/跟踪增量未完成，
UNKNOWN/未运行均保留，没有借用旧IDF1/HOTA或伪造逐像素物理认证。

## 一个下一步

开发保留空间位置和来源的多深度片段观测，用同版本因果历史消解歧义；
无法区分保持UNKNOWN。冻结后与单median输入同源对照，
不按最大/最近簇认证鱼体，不自动加大模型。当前只规划此项，不继续滚动调参。
'''
    with (HERE/'RESULTS.md').open('x',encoding='utf-8') as out: out.write(text)
    write_new(HERE/'EXECUTION_LOG.json',dict(base=summary['base'],status=summary['status'],formal_audit_runs=1,
        objects=28382,frames=1066,cohort_n=132,checks=8,runtime_seconds=summary['runtime_seconds'],
        inference_http=0,smoke=0,training=0,sam3_inference=0,completion_service=0,cost_usd=0,
        tracker_runs=0,old_files_changed=0,input_transform_applied=False,postseal_caption_repairs=1,
        physical_pixel_labels_completed=False,private_pixels_uploaded=False))
    lead='''Current result,2026-09-30: [DS5 depth-piece and spatial-registration audit](experiments/ds5_surface_registration_audit/RESULTS.md) completed1066 exposed frames/28382 masks and132fixed diagnostic objects. **AUDIT_COMPLETE; physical surface/registration UNRESOLVED.**8checks;0API/tracking/training/cost. F1821 already had two depth clusters; expansion changed their weights. Largest30mm depth-piece shadow loses92compatible references and adds106UNKNOWN overall, so it is not promoted. Full49-cell grids support no uniform nonzero shift improvement in either case/control queue. Recorded R has a disclosed nonorthogonal structure; same-native SO3 shadow is sensitivity only. Old seals preserved, private RGB/raw-depth QA actually viewed. [Current handoff](research/HANDOFF.md): one next step is provenance-bound multiple depth pieces with causal same-version history; ambiguity staysUNKNOWN.

'''.encode('utf-8')
    sync('README.md',lambda old:old.replace(b'Current result,2026-09-30:',b'Archived DS4 result,2026-09-30:',1).replace(b'Archived DS4 result,2026-09-30:',lead+b'Archived DS4 result,2026-09-30:',1))
    index=b'## DS5: sealed depth-piece/spatial audit - AUDIT_COMPLETE / physical UNKNOWN\n\n'+lead+b'\n'
    sync('EXPERIMENT_INDEX.md',lambda old:old.replace(b'## DS4:',index+b'## DS4:',1))
    handoff='''# Active handoff — DS5 surface/spatial observational audit,2026-09-30

Read experiments/ds5_surface_registration_audit/RESULTS.md, PLAN/CONFIG/FREEZE,
COHORT/SOURCE_INVENTORY/OLD_READONLY_LOCK, three initial independent reviews,
CHECKS/AUDIT_SEALED/REPORT_SEALED, CENSUS/REGISTRATION, SUMMARY/KNOWN_CASES,
three POSTAUDIT reviews, actual caption-v2 QA inspection, restricted inventory,
EXECUTION_LOG and REMOTE_VERIFICATION. Base56c2ea61682edea71328976c4fed27230f334c2a.
All1066frames/28382objects,73cases+59uniquecontrols;14missingcontrols retained.
Engineering/source-contract PASS; physical surfaces/water calibration UNKNOWN.
No extractor/tracker/model/DepthState intervention; HTTP/training/SAM3/completion/cost0.
Largest30mm depth-piece shadow not promoted: C−92/D−14/U+106 vs original F6;
multiple pieces may be spatial fragments at same depth, not different surfaces.
F1821 old20/14 depth clusters become20/66; median flips while MAD falls.
No uniform nonzero shift improves either fixed aggregate queue; local/subpixel
misregistration/refraction/physical ownership unresolved.
recordedR nonorthogonal; SO3 shadow is no certified correction/data substitution.
DS1–DS4 files/seals and source hashes preserved; pixels private.
One next step: multiple provenance-bound depth pieces and causal same-version
history disambiguation; uncertain choice staysUNKNOWN. Not yet implemented.
Do not retune DS5, select GT warps or automatically add VLM/tracking.

'''.encode('utf-8')
    sync('research/HANDOFF.md',lambda old:handoff+old.replace('# Active handoff — DS4'.encode(), '# Historical handoff — DS4'.encode(),1))


if __name__=='__main__': run()

