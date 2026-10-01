"""Write the complete tracking table from sealed scientific outputs."""
from common import *


def table(values):
    keys=('IDF1','HOTA','AssA','IDSW','FP','FN')
    lines=['| 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        lines.append('| '+arm+' | '+' | '.join(
            f'{values[arm][key]:.6f}' if key in keys[:3] else str(values[arm][key]) for key in keys)+' |')
    return '\n'.join(lines)


def main():
    for name,digest in read(RUN/'SCORING_SEALED.json')['artifacts_sha256'].items():
        assert sha(RUN/name)==digest
    metrics=read(RUN/'METRICS.json');births=read(RUN/'BIRTH_AUDIT.json')
    assert births['frozen_support_rule_met']
    assert all(births['certified_physical_restore_count'][a]==1 for a in ARMS[2:])
    lines=['# DS12 完整结果：本冻结版本小幅超过同源原生', '',
        '## 主判定与分层边界', '',
        '**工程、输入、实际发布与独立评分通过；四分支1471帧完成，本轮预先冻结的联合目标满足。**', '',
        '- 两个R12分支各新增1次正确出生重接；query→clean、actual bank→clean、旧source首次身份→clean均为同一RGB身份参考。新增错误/不可评分提交均0。',
        '- 全段IDF1、HOTA、AssA均严格超过同源SAM3，IDSW减少；这是已曝光四段开发数据的小幅收益，只有一个新增物理身份恢复案例。',
        '- 原始深度与native-v2修复深度的1471帧实际发布完全相同，未证实修复深度相对原始深度的增量。v2含上游RGB及后帧清理，仅为离线诊断。',
        '- 四分支同时引入接触出生准入和深度关联，不能单独识别深度的因果贡献。F1886几何log LR自身已大于log9；正深度LR不等于深度是必要证据。',
        '- 无鱼体深度表面/物理毫米GT、无独立录像盲测；UNKNOWN、未提交和全部残片保留。不把旧群组收益算作新出生收益。', '',
        '## 改了什么', '',
        '当前接触出生以真实独占core测量证书进入窄原子事务，保留真实neighbors及匿名风险。读取当前原始depth_mm/source_index与native来源，v2仅retained可颁证；实际逐片n、fraction、MAD、源点共享/去重与像素hash可追溯。所有合格片固定等权，所有候选使用同一片权重与共同背景，不按候选挑片。证书不认证鱼体表面。', '',
        '历史版本、连续joint clean、完整风险间隔、30帧/10点、二维OLS、深度预测/尺度、候选与NEW、log9、群组q、目标占用和发布政策保持冻结。风险观测不入pre，先stage/commit再唯一首次发布，之后继续真实自身状态；没有改预测文件或永久锁ID。', '',
        '工程首切片因OpenCV float32距离最大值1 ULP波动被严格验收拒绝，保留attempt1源快照、切片与日志。仅当前证书以精确最近零像素整数平方距离实现原公式；2715真实出生帧mask/3143组件/40211等号边界点核对，核心ROI零像素变化。旧历史与scorer未改，不添加容差。新F65切片选择NEW并通过严格source→selection→firstpub验收。', '',
        '## 完整同源主表', '',table(metrics['pooled_metrics']), '',
        '合并评分为四段独立ID命名空间的直接TrackEval，非百分比平均。39208个预测mask全部保留，GT对象39706；FP/FN相同，差异仅身份关联。', '',
        '### 相对差值（率为百分点）', '',
        '| 比较 | ΔIDF1 | ΔHOTA | ΔAssA | ΔIDSW | ΔFP | ΔFN |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for pair,d in metrics['pooled_delta'].items():
        lines.append('| '+pair+' | '+' | '.join(f'{d[k]:+.6f}' if k in ('IDF1','HOTA','AssA') else f'{d[k]:+d}'
            for k in ('IDF1','HOTA','AssA','IDSW','FP','FN'))+' |')
    for segment,values in metrics['segment_metrics'].items():
        lines.extend(['',f'### {segment}','',table(values)])
    lines.extend(['', '## 提交、真实身份与首次发布', '',
        '旧F9群组恢复仍为2次，F1239与F1745，两支R12保持。新出生恢复仅F1886（local686）：native198→public176；实际bank与clean参考均F1857（local657）。当前查询与两锚点均唯一匹配RGB参考ID4，原native176首次身份也同参考；不是原公共ID已错后偶然换回。', '',
        'F1886当前area388、真实neighbors[157]仍保留。两片等权0.5：n/area=28/34与45/54，median=1142.852661/1148.069458mm，MAD=7.947266/7.514526mm。old176真实历史跨度0.299秒，完整间隔0.964秒，预测深度mu=1154.723572mm、scale=52.809143mm。此scale是关联概率尺度，不称实测物理准确度。', '',
        '几何log LR=3.816346；深度log LR raw=0.235870、v2=0.281580；相对runner（NEW）的margin=4.052215/4.097925。query retained片与原始片相同，差异来自共同深度背景密度。每支105个非初始出生中47活动组阻断、57保留native、1 COMMIT；102段首初始ID另列。未提交不能算正确恢复。', '',
        '## 工程、费用与耗时', '',
        '13发布/状态、11预测、11测量（含独立几何穷举）及真实源、15关联/实际事务、5评分语义检查通过；自洽重封存的违规输入仍按语义拒绝。全段严格验收包含实际当前证书重建、历史fact、选择body、真实stage/commit与首次发布绑定；精度例外为空，SAM3与F9逐帧复现旧冻结输出。', '',
        '本地CPU单数学/OpenCV线程。正式预测258.997秒，独立评分485.906秒；新真实切片19.164秒、验收13.536秒。既有历史测量缓存复用，新增当前出生帧像素测量及v2重投影真实执行；不是实时部署耗时。', '',
        '新模型HTTP=0、smoke=0、训练=0、SAM3推理=0、补全服务=0、GPU/服务器作业=0、费用=$0。未调用任何大模型或服务；不需要key。未安装依赖，TrackEval无关BURST/tabulate提示保留，不影响HOTA/Identity/CLEAR评分。', '',
        '## 未完成边界与一个下一步', '',
        '本轮完整试验、评分、逐例复盘与交付完成；独立数据复现、深度的单独因果归因、真实表面归属及物理毫米标定尚未完成。只有一次新增恢复，不能扩大为普遍超越结论。', '',
        '**下一步仅做冻结R12_RAW的时间非重叠开发验证**：按来源元数据选最早完整、获准且未参与调参的保存片段，与同源SAM3直接全段比较；不按覆盖/结果选样本、不调参数、不读sealed test，不自动加大模型。选择与运行须先确认新数据可用性，本轮不启动。见NEXT_STEP_PLAN.md。', ''])
    with (HERE/'RESULTS.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
    print('Sealed complete report table and layered conclusion written')


if __name__=='__main__':main()
