"""Append actual engineering exception and attribution without changing any seal."""
from common import *

def main():
    m=read(RUN/'METRICS.json');audit=read(RUN/'EVENT_AUDIT.json')
    post=read(HERE/'ASSOCIATION_POSTRUN.json')
    acceptance=read(HERE/'FLOAT_SCORE_ADAPTER_ACCEPTANCE.json')
    assert acceptance['count']==281
    appendix=read(HERE/'APPENDED_SCORE_PROVENANCE_SEALED.json')
    verify_item(appendix['score_seal'])
    for item in appendix['append_only_provenance']:verify_item(item)
    for p in read(HERE/'OLD_READONLY_LOCK.json')['files']:
        assert sha(ROOT/p)==read(HERE/'OLD_READONLY_LOCK.json')['files'][p]
    staged=[e for e in audit['events'] if e['arm']=='J2_RESTORED_DEPTH' and e['status']=='COMMIT']
    images=read(HERE/'VISUALIZATION_INVENTORY.json')['private_figures']
    for item in images:verify_item(item['artifact'])
    bindings=[artifact(RUN/'SCORING_SEALED.json'),artifact(HERE/'APPENDED_SCORE_PROVENANCE_SEALED.json'),
        artifact(HERE/'ASSOCIATION_POSTRUN.json'),artifact(HERE/'POSTRUN_REVIEW.md'),artifact(HERE/'NEXT_STEP_PLAN.md')]
    write_new(HERE/'COMPLETION_EVIDENCE.json',dict(frames=1471,branches=6,
        actual_changed_v2_events=[dict(original_q=e['original_q'],first_public=e['first_public_mapping'],
            expected=e['expected_mapping'],physical=e['physical'],pre_entry_reference=e['pre_entry_reference']) for e in staged],
        private_images_actually_viewed=[x['artifact'] for x in images],bindings=bindings,
        original_strict_source_comparison='FAILED_INERT_FLOAT32_DIAGNOSTICS',
        appendix='281 one-ULP DT maximum diagnostics, all actual used facts/thresholds exact',
        depth_target_met=m['frozen_support_rule_met'],new_model_http=0,cost_usd=0))
    lines=['','## 封存后实际归因与工程例外','',
        '**微小收益属于共同几何机制，深度独立增量为0。** J0/J1/J2/ZERO完整发布逐帧相同（不仅指标相同）。IDF1与native相同；HOTA +0.047993、AssA +0.085265个百分点、IDSW 108→106。F1239把新source167接回旧ID136，F1745把190接回188，另一条边保持；两次实际首发布依原anchor参考为正确，进入前参考同anchor，无借旧错号偶然换回。',
        'F1239 depth只在已足够的geometry margin上附加raw约0.013296/v2约0.003422；F1745 depth边完全无信息。F434某深度候选虽被选择，却因残片写集guard不提交，且其参考不可评分，不能算恢复。',
        '错配控制在F519/F1027把原本正确的两个native ID双边交换成错误，额外损害使IDSW110。故错配有害，但原始/修复/置零/geometry都同效，不证明深度必要性。全部19q/枝与no-q事件保留，完整候选、风险、缺测与相同state比较见ASSOCIATION_POSTRUN.json。',
        '', '第一次冻结evaluate在读GT前因DS8逐字段严格metadata比较失败，原文件、预测与失败日志保持只读。随后全1471帧/39208对象审计仅有281个 dt_max_px 的float32 1 ULP差异（最大4.76837158203125e-7px）；全部双方值>6，实际ROI阈值都clamp3px。threshold、samples/n、median/MAD、资格、背景、来源和其它typed字段严格相同。未认证ROI bitmap字节相同，也未确定底层runtime浮点差异根因。',
        '新增独立score_float_adapter.py在读GT前另行封存，只在副本接纳上述无作用诊断值、最后全dict其余strict exact；原scorer、研究门槛、物理mapping真值、来源与预测全不改。5项最小检查拒绝实际中位数/threshold/大差异篡改。原严格验收FAIL与追加精度例外后评分成功分列，不能写成原严格比较PASS。当前281均经独立float32位距离认证为1；该adapter的spacing上界在未见的2次幂边界不作通用一ULP保证，下一新冻结版本可用nextafter精确邻点检查，本轮不改已seal代码。',
        '正式评分绑定：SOURCE_FLOAT_AUDIT、FLOAT_SCORE_ADAPTER_FROZEN/ACCEPTANCE、APPENDED_SCORE_PROVENANCE_SEALED。必要HOTA/Identity/CLEAR评分完整；可选BURST的tabulate导入提示不影响本轮三项，未安装依赖。',
        '', '工程链通过限定追加精度验收；输入为原始或含上游RGB/未来清理的离线v2；独立深度收益未建立，停止当前冻结版本。唯一下一步已经具体规划于NEXT_STEP_PLAN.md，未执行。新模型HTTP/训练/SAM3/补全服务与费用0；旧678 tracked文件保持字节不变。','']
    with (HERE/'RESULTS.md').open('a',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
    write_new(HERE/'REPRODUCTION_APPENDIX.json',dict(frozen_readme_retained=True,
        prediction_commands=['execute.py launch.py slice','execute.py check_real_slice.py','execute.py launch.py full'],
        actual_score_command='execute.py score_float_adapter.py',
        explanation='Original evaluate.py strict comparison failure preserved; explicit postprediction/preGT inert metadata exception sealed independently. No prediction regeneration or source/GT modification.',
        all_input_dependencies='RESTRICTED_INVENTORY.json',fresh_outputs_required=True))
    print('Actual attribution, engineering exception and completion evidence appended')
if __name__=='__main__':main()
