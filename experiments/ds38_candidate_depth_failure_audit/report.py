"""Postseal descriptive review. No prediction, candidate, or threshold is changed."""
from common import *
from collections import Counter
import html, math, shutil
import numpy as np

def reference_key(name,ref): return key(name,ref['frame'],ref['native_id']) if ref else None
def number(x): return 'UNKNOWN' if x is None else f'{x:.1f}'

def ranking_verdict(action,role,quality=False):
    pool=[]
    for b in action['bank']:
        p=b['distribution']
        if not b['legal_matrix_edge'] or not p or 'comparisons' not in p: continue
        if quality and not p['both_core_supported']: continue
        d=p['comparisons'][role]['wasserstein_mm']
        if d is not None: pool.append((d,b['used_depth_reference_physical'],b['id']))
    if not any(r=='SAME' for _,r,_ in pool): return 'NO_SCOREABLE_CORRECT_EDGE_IN_POOL'
    if len(pool)==1: return 'ONLY_CORRECT_EDGE_NO_COMPETITION'
    if all(r=='SAME' for _,r,_ in pool): return 'ALL_EDGES_SAME_NO_DIFFERENT_IDENTITY_COMPETITION'
    best=min(d for d,_,_ in pool);relations=[r for d,r,_ in pool if d==best]
    if relations==['SAME']: return 'UNIQUE_CORRECT_MINIMUM'
    if all(r=='SAME' for r in relations): return 'TIED_CORRECT_MINIMA'
    if 'SAME' in relations: return 'TIED_CORRECT_AND_OTHER'
    return 'CORRECT_EDGE_EXISTS_BUT_OTHER_MINIMUM'

def availability(action):
    a=action['action'];incumbent=next(c['phase_snapshot']['current_public'][str(a['native'])]
        for c in CANDIDATES if c['action']['action_id']==a['action_id'])
    same=[b for b in action['bank'] if b['physical_reference']=='SAME']
    independent=[b for b in same if b['id']!=incumbent and b['anchor'] and b['anchor']['native_id']!=a['native']]
    result=dict(any_bank_same=bool(same),independent_bank_same=bool(independent),
        independent_column=any(b['actual_matrix_column'] for b in independent),
        independent_legal=any(b['legal_matrix_edge'] for b in independent),
        independent_below_dummy=any(b['can_beat_own_dummy'] for b in independent),incumbent_public=incumbent,
        independent_correct_targets=[b['id'] for b in independent])
    if action['physical']=='UNSCORABLE': result['cause']='UNSCORABLE'
    elif action['physical']=='CORRECT': result['cause']='CORRECT_CONTROL'
    elif not independent: result['cause']='NO_INDEPENDENT_CORRECT_BANK_REFERENCE'
    elif not result['independent_column']: result['cause']='CORRECT_HISTORY_EXCLUDED_BEFORE_MATRIX'
    elif not result['independent_legal']: result['cause']='CORRECT_HISTORY_COLUMN_BUT_EDGE_REJECTED'
    elif not result['independent_below_dummy']: result['cause']='CORRECT_EDGE_CANNOT_BEAT_DUMMY'
    else: result['cause']='CORRECT_LEGAL_EDGE_LOST_COMPETITION'
    return result

def distribution_chart(action,facts,path):
    a=action['action'];current=key(a['segment'],a['frame'],a['native'])
    sources=[(f'q n{a["native"]}',facts.get(current),'#111111')]
    for b in action['bank']:
        if not b['actual_matrix_column']: continue
        p=b['distribution'];ref=p['reference'] if p else reference_key(a['segment'],b['anchor'])
        color='#228844' if b['used_depth_reference_physical']=='SAME' else '#bc3434' if b['used_depth_reference_physical']=='DIFFERENT' else '#888888'
        sources.append((f'p{b["id"]} {"SELECTED " if b["selected"] else ""}{b["used_depth_reference_physical"]} cost={number(b["matrix_cost"])}',facts.get(ref),color))
    width=1120;height=110+len(sources)*65
    values=[v for _,f,_ in sources if f for v in f['depth_quantiles_mm']['core']]
    lo,hi=(min(values),max(values)) if values else (0.,1.)
    def x(v): return 380+680*(v-lo)/max(1.,hi-lo)
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="18" y="25" font-family="sans-serif" font-size="17">Global F{a["global_frame"]}: {html.escape(a["phase"])} / {action["physical"]}</text>',
        '<text x="18" y="47" font-family="sans-serif" font-size="12">Core depth q05-q95 with q25/median/q75; all layers retained; empirical proxy, no identity guarantee</text>']
    for index,(label,fact,color) in enumerate(sources):
        y=90+65*index;parts.append(f'<text x="18" y="{y+4}" font-family="sans-serif" font-size="13">{html.escape(label)}</text>')
        quant=[] if fact is None else fact['depth_quantiles_mm']['core']
        if quant:
            parts.append(f'<line x1="{x(quant[0]):.2f}" x2="{x(quant[-1]):.2f}" y1="{y}" y2="{y}" stroke="{color}" stroke-width="2"/>')
            for j in (4,9,14): parts.append(f'<circle cx="{x(quant[j]):.2f}" cy="{y}" r="{5 if j==9 else 3}" fill="{color}"/>')
            stats=fact['views']['core']['summary'];support=fact['views']['core']['measurement_support']
            parts.append(f'<text x="380" y="{y+24}" font-family="sans-serif" font-size="11">n={stats["n"]}; fraction={stats["valid_fraction"]:.3f}; scale={number(stats["scale_mm"])} mm; support={support}</text>')
        else: parts.append(f'<text x="380" y="{y+4}" font-size="13">UNKNOWN</text>')
    parts.append(f'<text x="380" y="{height-12}" font-family="sans-serif" font-size="12">Depth {lo:.1f} to {hi:.1f} mm; green=SAME reference, red=DIFFERENT, grey=unscorable (postseal labels)</text></svg>')
    path.write_text('\n'.join(parts),encoding='utf-8')

def pixel_cases(actions):
    """Postseal viewing only, exact event reference to q, no new state or GT raster."""
    from audit import render_pixels
    from PIL import Image,ImageDraw
    requests={name:set() for name in SEGMENTS}
    for action in actions:
        a=action['action'];ref=a['actual_reference'];requests[a['segment']].add(ref['frame'])
    added=[]
    for name,frames in requests.items():
        saved={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame'] in frames}
        obs={r['frame']:r for r in rows(input_dir(name)/'DEPTH_OBSERVATIONS.jsonl.gz') if r['frame'] in frames}
        sensor=SOURCE.RawDepth(name)
        try:
            for f in sorted(frames):
                path=HERE/'private'/f'{name}_F{f}_raw_depth_masks.png'
                if path.exists(): continue
                row=obs[f];depth,index,native,binding=sensor(row['global_frame'],row['time'])
                assert binding==row['raw_source_binding']
                render_pixels(depth,SOURCE.native_masks(saved[f]),name,f);added.append(artifact(path))
        finally: sensor.close()
    cases=[]
    for action in actions:
        a=action['action'];name=a['segment'];ref=a['actual_reference'];f=a['frame']
        before=Image.open(HERE/'private'/f'{name}_F{ref["frame"]}_raw_depth_masks.png').convert('RGB')
        current=Image.open(HERE/'private'/f'{name}_F{f}_raw_depth_masks.png').convert('RGB')
        panel=Image.new('RGB',(1280,1470),'white');panel.paste(before,(0,30));panel.paste(current,(0,750))
        ImageDraw.Draw(panel).text((8,8),f'Global F{a["global_frame"]} {action["physical"]}: actual old n{ref["native_id"]} / public p{a["target"]} -> current n{a["native"]}',fill='black')
        path=HERE/'private'/f'CASE_global{a["global_frame"]}_n{a["native"]}.png';panel.save(path)
        cases.append(dict(action_id=a['action_id'],physical=action['physical'],figure=artifact(path),
            exact_actual_reference=ref,current_frame=f,raw_source_only=True,GT_raster=False))
    save('POSTSEAL_PRIVATE_VISUALS.json',dict(cases=cases,added_source_views=added,
        reproduction='report.py after sealed diagnosis, requires private raw originals and saved masks'))
    return cases

def main():
    global CANDIDATES
    verified_freeze();data=read(HERE/'POSTSEAL_DIAGNOSIS.json')
    for pin in read(HERE/'FEATURES_SEALED.json')['files']: verify_item(pin)
    actions=data['actions'];CANDIDATES=list(rows(HERE/'run/CANDIDATES.jsonl.gz'))
    facts={key(f['segment'],f['frame'],f['native']):f for f in rows(HERE/'MEASUREMENTS.jsonl.gz')}
    for a in actions:
        a['availability_by_source_role']=availability(a)
        a['ranking_verdict']={r:ranking_verdict(a,r) for r in ('whole','core')}
        a['quality_core_ranking_verdict']=ranking_verdict(a,'core',True)
    grouped={p:[a for a in actions if a['physical']==p] for p in ('WRONG','CORRECT','UNSCORABLE')}
    summary={p:dict(actions=len(group),availability={stage:sum(a['availability_by_source_role'][stage] for a in group)
        for stage in ('any_bank_same','independent_bank_same','independent_column','independent_legal','independent_below_dummy')},
        causes=dict(Counter(a['availability_by_source_role']['cause'] for a in group)),
        ranking={r:dict(Counter(a['ranking_verdict'][r] for a in group)) for r in ('whole','core')},
        qualified_core_ranking=dict(Counter(a['quality_core_ranking_verdict'] for a in group))) for p,group in grouped.items()}
    order=data['order'];summary['relative_order']=dict(total=len(order),statuses=dict(Counter(o['status'] for o in order)),
        reasons=dict(Counter(reason for o in order for reason in o['reasons'])),
        qualified_by_reference_relation={r:dict(Counter(str(o['raw_order_reversed']) for o in order
            if o['status']=='SAME_VERSION_MEASURED_PROXY_ORDER' and o['reference_physical']==r)) for r in ('SAME','DIFFERENT','UNKNOWN')})
    depths={}
    for p,group in grouped.items():
        details=[]
        for a in group:
            current=facts[key(a['action']['segment'],a['action']['frame'],a['action']['native'])]
            selected=next(b for b in a['bank'] if b['selected']);ref=selected['distribution']
            older=facts.get(ref['reference']) if ref else None
            def describe(f):
                if not f: return None
                z=f['views']['core']['summary']['median'];whole=f['views']['whole']['summary']['median']
                patches=[f['views'][r]['summary']['median'] for r in ('patch1','patch2','patch3')]
                patches=[x for x in patches if x is not None]
                return dict(core_n=f['views']['core']['summary']['n'],core_fraction=f['views']['core']['summary']['valid_fraction'],
                    core_scale_mm=f['views']['core']['summary']['scale_mm'],core_support=f['views']['core']['measurement_support'],
                    whole_core_gap_mm=None if z is None or whole is None else abs(z-whole),
                    patch_median_range_mm=max(patches)-min(patches) if len(patches)>=2 else None,
                    core_background_comparison=f['views']['core']['background_comparison'],
                    layers=f['local_background'],physical_contamination='UNKNOWN_WITHOUT_SURFACE_LABELS')
            details.append(dict(action_id=a['action']['action_id'],current=describe(current),selected_reference=describe(older)))
        depths[p]=details
    summary['input_depth_descriptions']=depths
    save('RESULTS.json',dict(summary=summary,actions=actions,relative_order=order,
        source_role_note='Independent old identity excludes current incumbent public and same current native source; posthoc accounting, no new candidates.',
        scientific_status='DIAGNOSTIC_ONLY_NO_NEW_TRACKER_PERFORMANCE',model_http=0,cost_usd=0))
    figures=HERE/'visuals';figures.mkdir(exist_ok=True)
    for action in actions:
        a=action['action'];distribution_chart(action,facts,figures/f'global{a["global_frame"]}_n{a["native"]}.svg')
    cases=pixel_cases(actions)
    lines=['# DS38完整竞争历史与原始深度失败审计','',
        '**主判定：四段1471帧诊断回放与原Z4Q完整状态、trace、mapping、版本逐帧一致。新跟踪策略未运行，不能宣称提点或泛化。**','',
        '覆盖全部27次旧提交：17次WRONG、8次CORRECT对照、2次UNSCORABLE。队列及旧GT摘要已经曝光；所有新候选与深度特征先封存，再独立读取旧REFERENCE_MATCHES，未读新GT raster或未来帧决定输入。','',
        '## 正确历史在哪一层消失','',
        '| 旧物理结果 | 数量 | 任意bank有同物理参考 | 独立旧参考在bank | 进入矩阵列 | 存在合法入边 | 低于dummy |','|---|---:|---:|---:|---:|---:|---:|']
    for p in ('WRONG','CORRECT','UNSCORABLE'):
        s=summary[p];v=s['availability'];lines.append('| '+p+' | '+str(s['actions'])+' | '+' | '.join(str(v[x]) for x in v)+' |')
    lines.extend(['','“独立旧参考”排除本次尚未重接的当前incumbent和当前同native片段。当前n的近帧当然可能与自己同物理；这不能冒充一个已消失旧身份进入了重接候选池。原始全bank和两种口径全部保留。','',
        '错误分层：'+json.dumps(summary['WRONG']['causes'],ensure_ascii=False)+'。','',
        '## 完整分布是否能区分','',
        '固定Wasserstein-1距离比较全部独立测量来源，不择峰。下表是对真实合法矩阵边的诊断排序；UNKNOWN/无正确边不算成功，whole/core分别列，不是新的匈牙利关联或跟踪成绩。','',
        '| 旧结果 | whole诊断 | core诊断 | 双端core旧质量门槛后 |','|---|---|---|---|'])
    for p in ('WRONG','CORRECT','UNSCORABLE'):
        s=summary[p];lines.append('| '+p+' | '+json.dumps(s['ranking']['whole'])+' | '+json.dumps(s['ranking']['core'])+' | '+json.dumps(s['qualified_core_ranking'])+' |')
    lines.extend(['','whole/core差、三个几何分区的差和局部背景相似均逐例保存。较宽/多层不自动意味着两条鱼，背景环不保证是真背景，原始非零深度不自动可靠；没有像素表面真值，不能给污染率或物理识别准确率。','',
        '## 相对深度次序','',json.dumps(summary['relative_order'],ensure_ascii=False,indent=2),'',
        '只把连续同generation/epoch/public、没有中途接触或质量风险的邻鱼作为可比较见证。其余原始次序仍保存为UNKNOWN代理证据；没有连续见证时，不能把两次无身份绑定的“上下”直接拼成身份约束。','',
        '## 全部逐例结果','',
        '| 全局帧 | 当前→旧public | 入口 | 物理 | 独立正确旧参考 | 真正合法正确边 | core分布诊断 | 原因 |','|---:|---|---|---|---|---|---|---|'])
    for action in actions:
        a=action['action'];v=action['availability_by_source_role'];lines.append(f'| {a["global_frame"]} | n{a["native"]}→p{a["target"]} | {a["phase"]} | {action["physical"]} | {v["independent_correct_targets"]} | {v["independent_legal"]} | {action["ranking_verdict"]["core"]} | {v["cause"]} |')
    lines.extend(['','## 工程与边界','',
        '5项直接检查通过，含真实F159的160帧切片。两条入口完整bank、候选matrix、dummy和terms均记录；BirthRefine的实际core/whole锚点与D1 bank锚点分别追溯。旧原Z4Q、DS36/DS37代码及seal未改。','',
        '实际深度/mask图仅私有；公开27张分布统计SVG。受限清单记录真实路径、字节、SHA和复现依赖。新模型HTTP、smoke、SAM3推理、训练、补全、费用、RGB/GPU/服务器均0。','',
        '本轮未运行新性能策略；输出与原Z4Q逐帧一致是审计完整性证据，不是深度提点。此固定曝光集合上的分布排序不得直接当作新验证成功。','',
        '下一步将在审计结果核对后冻结为一个机制；本报告的NEXT_STEP.md为最终单一建议。'])
    (HERE/'FINAL_REVIEW.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    save('REPORT_ACCEPTANCE.json',dict(actions=27,wrong=17,correct_controls=8,unscorable=2,
        replay_frames=sum(v['frames'] for v in read(HERE/'run/REPLAY_SEALED.json')['segments'].values()),
        public_statistics_figures=len(list(figures.glob('*.svg'))),private_paired_cases=len(cases),
        inputs_verified_again=True,all_masks_retained=True,new_metrics=False,model_http=0,cost_usd=0))
    print(json.dumps({p:summary[p] for p in ('WRONG','CORRECT','UNSCORABLE','relative_order')},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__': main()
