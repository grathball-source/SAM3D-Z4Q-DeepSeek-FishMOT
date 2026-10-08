"""Final report boundaries and complete source/feature checks, no new experiment."""
from common import *
import numpy as np,cv2,scipy,PIL

def main():
    verified_freeze()
    for file in ('FEATURES_SEALED.json','LEGACY_ROI_SUPPLEMENT_SEALED.json'):
        for pin in read(HERE/file)['files']:verify_item(pin)
    for pin in read(HERE/'LEGACY_ROI_SUPPLEMENT_FREEZE.json')['files']:verify_item(pin)
    for pin in read(HERE/'run/REPLAY_SEALED.json')['files']:verify_item(pin)
    supplement=read(HERE/'LEGACY_ROI_COMPARISONS.json')
    low=[a['global_frame'] for a in supplement['actions'] if a['physical']=='WRONG'
        and a['current_original_profiles']['core']['original_profile']['n']<16]
    assert low==[159,897,1404,1751]
    for p in (HERE/'visuals').glob('*.svg'):
        text=p.read_text(encoding='utf-8')
        assert 'Core depth q05-q95' in text
        p.write_text(text.replace('Core depth q05-q95','DS36 adaptive core (distinct from original profile core): q05-q95'),encoding='utf-8')
    boundary=('\n## 原输入ROI补充核验与来源边界\n\n'
        '主统计图使用DS36自适应core，与原Z4Q profiles固定腐蚀core不同。LEGACY_ROI_SUPPLEMENT_SEALED另封存原ROI：'
        '235时刻/6289观测的whole/core area/n/fraction/median/MAD/q25/q75逐列严格等于旧输入，'
        '原像素人口和独立去重人口分列。补充是在GT已曝光后的量测验真，不把其统计拼成新的盲输入或新成绩。'
        '原core下过滤前仍是12次无正确列、4次其他身份更近、1次正确最小，全部固定列保留。\n\n'
        '错误当前原core样本数不足16的四例是F159、F897、F1404、F1751；不能把扩大ROI后的16/17测量支持率当成原core支持率。'
        '其他错误即使原core有足够有效点，深度接近也未证明同一身份。\n\n'
        'source generation来自可见性连续性，epoch来自原Bridge；没有完整生产者reset元数据，不能认证一个连续native内部从未换鱼。'
        'REFERENCE_MATCHES不可评分的旧参考不能当成已证实不存在正确鱼，所以候选计数表的“正确”是可评分SAME定义。'
        'F468、F1681的同物理旧bank已被当前另一物理观测占用，事后只发现问题，不用GT释放占用或改动作。\n\n'
        '最终真实图是FIXED_SCALE_PRIVATE_VISUALS：统一900–1400mm显示、洋红表示缺失；低值黑色不等于缺失。'
        '27组固定前后图与8张全案例联系图只在private中；17错误、8正确、2不可评分全部保留。'
        '公开27张自适应core统计SVG，像素、真实人口数组、凭据和GT raster未上传。\n\n'
        '唯一下一步是NEXT_STEP.md的D1共同竞争门控试验，目前尚未启动；不等于推荐无条件放宽历史、深度或占用门槛。\n')
    for filename in ('FINAL_REVIEW.md','DEEP_REVIEW.md'):
        p=HERE/filename;p.write_text(p.read_text(encoding='utf-8')+boundary,encoding='utf-8')
    save('DEPENDENCIES.json',dict(python=sys.executable,numpy=np.__version__,opencv=cv2.__version__,
        scipy=scipy.__version__,pillow=PIL.__version__,installed_dependency_path=str(LEGACY.DEPS),installation=False))
    save('FINAL_ACCEPTANCE.json',dict(status='COMPLETE_READ_ONLY_DIAGNOSTIC_WITH_EXACT_ORIGINAL_ROI_SUPPLEMENT',
        replay_frames=1471,actions=27,wrong=17,correct=8,unscorable=2,
        actual_evaluated_edges=85,
        actual_legal_edges=sum(b['legal_matrix_edge'] for a in read(HERE/'RESULTS.json')['actions'] for b in a['bank']),
        independent_correct_legal_edges_in_wrong_actions=0,
        source_generation_is_visibility_proxy_not_physical_ID_certificate=True,
        original_profile_objects_exact=6289,primary_features_unchanged=True,new_tracker_policy=False,
        new_performance_claim=False,GT_raster=False,model_http=0,cost_usd=0,next_trial_started=False))
    print('FINAL ACCEPTANCE PASS',flush=True)

if __name__=='__main__':main()
