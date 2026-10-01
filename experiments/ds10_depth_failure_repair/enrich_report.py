"""Add the sealed error decomposition and verified visualization links."""
from common import *


def main():
    review = read(HERE/'POSTRUN_REVIEW.json')
    assert review['status'] == 'POSTSEAL_DS10_ALL_Q_AND_SWITCH_REVIEW'
    for source in review['input_provenance']['numerical_inputs'].values():
        assert sha(source['path']) == source['sha256']
    for name in ('POSTRUN_REVIEW.md', 'POSTRUN_SOURCE_REVIEW.md',
                 'NEXT_STEP_PLAN.md', 'diagnosis/PUBLICATION_INVENTORY.json',
                 'diagnosis/PUBLICATION_ZOOM_INVENTORY.json',
                 'diagnosis/PUBLICATION_CALLOUT_INVENTORY.json'):
        assert (HERE/name).is_file(), name
    restored = [x for x in review['actual_changed_commits'] if x['arm']=='D10_RESTORED']
    wrong = [x for x in restored if x['first_public_reference_transition']=='CORRECT_TO_WRONG']
    right = [x for x in restored if x['first_public_reference_transition']=='WRONG_TO_CORRECT']
    assert len(wrong)==1 and len(right)==2
    error=wrong[0]
    section = '\n'.join([
        '## 本轮新增错误的封存后复盘', '',
        f"实际修复深度提交{len(restored)}次：正确恢复{len(right)}次，新增错改{len(wrong)}次。",
        f"新增错误在F{error['original_q']}：原生映射{error['native_pair_mapping']}，实际首次发布{error['first_public_mapping']}。",
        '这次交换影响34帧，增加2次CLEAR身份切换；原F1239、F1745各消除1次切换仍保留。因此IDSW为108−2+2=108，持平不能解释为没有新增错误。',
        f"错误交换的联合优势{error['margin']:.6f}超过冻结门槛{error['minimum_log_odds']:.6f}；其中二维部分{error['best_vs_h0']['geometry_log_lr']:.6f}，深度部分{error['best_vs_h0']['depth_log_lr']:.6f}。",
        '原始深度下post137不合格，配对深度回退为共同无信息，未越过门槛；v2仅inferred cohort可用。恢复补点也增加历史时间支持，使B预测scale由raw约99.475mm降至v2约31.793mm。同一个最后实测约1017.498mm更接近另一鱼post95约1027.832mm，错误交换因此得到支持。',
        '统计资格、更多样本、小MAD或更窄scale均不能认证鱼体表面和身份连续。现有GT只认证身份/掩码，真实表面归属和毫米准确性仍UNKNOWN。',
        '共同背景的对数分母在两条完整双射间抵消，但背景仍进入0.9·foreground+0.1·background混合内部，影响对比强度。本轮同时改均值与背景，只能报告联合版本的真实作用，不能拆成各模块独立贡献。',
        '四个原漏恢复F470/F764/F1390/F1805全部保留：缺失pre、短历史的大不确定性或不足的相对证据仍未被解决。未新增正确恢复，原始深度输出与旧F9全段完全相同。', '',
        '### 详细证据与实际发布可视化', '',
        '- [逐事件、逐边及完整切换复盘](POSTRUN_REVIEW.md)',
        '- [独立来源、因果和评分封存检查](POSTRUN_SOURCE_REVIEW.md)',
        '- [10个案例的三时刻四分支发布图清单](diagnosis/PUBLICATION_INVENTORY.json)',
        '- [F1027局部放大图清单](diagnosis/PUBLICATION_ZOOM_INVENTORY.json)',
        '- [F1027清晰标注的三时刻局部图清单](diagnosis/PUBLICATION_CALLOUT_INVENTORY.json)',
        '- [唯一下一步计划](NEXT_STEP_PLAN.md)', '',
        '像素图留在本机private/publication；三个清单列真实路径、字节和SHA。图只取合并前、首个group记录和q，显示当时实际公开ID，不回填历史、不读取q之后帧。',
        '首次生成发布图因Windows行末CRLF与publisher预写LF行摘要不一致而停止。原失败日志保留；追加图脚本分别验证实际磁盘行与预写行摘要，预测、账本、scorer和封存均未改变。', '',
        '下一步消除F1027仅叫止损；必须新增正确恢复且完整指标超过原生才算提点。本轮版本结果已固定，没有按评分滚动改门槛。', '',
    ])
    path=HERE/'RESULTS.md'
    text=path.read_text(encoding='utf-8')
    assert '## 本轮新增错误的封存后复盘' not in text
    path.write_text(text+'\n'+section,encoding='utf-8',newline='\n')
    print('Sealed actual failure decomposition and visualization evidence appended')


if __name__=='__main__':main()
