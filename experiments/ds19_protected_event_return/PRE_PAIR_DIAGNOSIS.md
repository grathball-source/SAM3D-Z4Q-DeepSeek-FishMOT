# DS19：冻结 S0 历史配对失败的来源审查

## 范围与主结论

只读 `run/*/public` 全部已封存预测，检查 MIXED_RETURN 的 **50 个实际 S0 q**。不读取 GT、metrics、RGB 或修复深度，不生成新候选、选择、关联、预测或评分，新增模型 HTTP 与费用均为 0。此次源检查不改变本轮结果。

实际原因：18 个 `VALID_SOFT_ORDER_EVIDENCE`、16 个 `NO_SAME_FRAME_PRE_PAIR`、13 个 `INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING`、3 个 `INVALID_OR_MISSING_CURRENT_PAIRED_DEPTH`。有效证据不表示最终候选通过赔率门，也不表示物理恢复正确。

**13 个 INVALID_PRE 全部是深度历史点没有对应的被冻结几何点。** 逐列复查共 199 个失败历史点，只有 `GEOMETRY_FRAME_ABSENT` 一个失败字段；没有发现附带 native/public/generation/epoch、时间、fact_id 或量测质量篡改。在有几何点的历史上，原校验字段均通过。它们不是 13 次错误身份映射，也不能把缺失几何点补成 clean。

**16 个 NO_SAME_FRAME 是实际纳入的两条深度片段没有同帧交集。** 两角色单独的原检验通过，之后原程序才返回此原因。其中 14 个连冻结几何片段也没有共同帧；另 2 个几何有共同帧，实际过去也有合格共时深度，但各鱼后来的独立 `latest_fragment` 覆盖了共同证据。

## 实际生效的来源合同

`order_association.py:65–100` 依次核查版本头、每条 depth sample 对应的 geometry point、真实时间/深度/尺度、风险类别、来源和公共身份版本、质量及 fact_id。缺少任意一条几何点便停止，不能仅取剩余好点。`:103–105` 之后才取两条合格片段的同帧交集；本审查按这些原谓词拆字段，没有调用 `choose` 或 `evidence` 重新作选择。

几何和深度的保留逻辑当前不同：

- `merge_split_manager.py:341–389` 按几何质量、neighbors、事件类别更新 clean/last_clean；版本改变切断历史，`pending_clear` 删除 clean/last_clean/risk。
- `merge_split_manager.py:403–405` 在第一次 suspect 冻结两条独立的 clean 或 last_clean，最多 30 点。
- `depth_state.py:37–41` 的 `break_source` 只清活跃 samples，保留完成的 `latest_fragment`；`:47–76` 因 GROUP、POST、量测缺失或风险中断当前片段。
- `DS19 runner.py:34–57` 仅检查当前版本一致后取完整 `latest_fragment`，没有绑定其几何片段标识或事件清理生命周期。
- `DS19 runner.py:248–274` 先更新深度再调用 manager.after；几何 clean 可以成立而深度混合门拒绝同帧量测。

上述实际源码与 CONFIG 哈希已逐一对照八段 `FREEZE.json`，全部相同。controller 的冻结 SHA 为 `420aad60656d9084f7c7281c597d5039490a9f0aa3b221f02e855904b7241538`。

## 13 个 INVALID_PRE 的拆分

### 11 个：合法事件清理后，几何已为空、深度旧片段仍可冻结

JSON 每例保留原 frame/time/source/public/generation/epoch/fact/binding，实际深度状态转折以及此前结束的事件。以下 frame 均是 local 编号；original 编号按 `segment_start + local − 1` 转换。

| 片段 / 当前事件 | q | 缺几何的源 | 残留深度片段 | 已结束并清理该源的事件 |
| --- | ---: | ---: | --- | --- |
| Feeding 351–555 / F81 | 84 | 69 | 10–21 | F51，52 取消 |
| Feeding 701–1060 / F295 | 300 | 68 | 226–239 | F269，270 取消 |
| Feeding 1201–1906 / F152 | 159 | 88 | 36–41 | F71，80 局部回退完成 |
| FishSA dev / F4519 | 4524 | 1 | 4476–4477 | F4485，4501 局部回退完成 |
| FishSA dev / F5927 | 5939 | 7→public0 | 5229–5258 | F5303，5304 取消 |
| FishSA val / F2681 | 2689 | 5 | 2496–2525 | F2617，2620 局部回退完成 |
| L3 / F226 | 244 | 9，generation3 / epoch3 | 45–74 | F126，127 取消 |
| LW / F375 | 388 | 6 | 148–156 | F218，223 局部回退完成 |
| LW / F1274 | 1276 | 5 | 1261–1263 | F1269，1270 取消 |
| LW / F1277 | 1281 | 6 | 1234–1263 | F1274，1276 局部回退完成 |
| LW / F2157 | 2161 | 60 | 1814 | F1758，2029 局部回退完成，该源是 post |

真实风险之后没有新的 clean 几何能重新建立引用，当前严格拒绝正确。工程边界在于两个缓存对事件结束后的“旧片段仍可用”语义不同：相同 identity key 不能证明当前几何历史仍承认这条深度片段。不能恢复被合法清理的几何身份认证，也不能仅保留旧深度宣称已修好输入。

### 2 个：同版本风险中断后，新几何与旧深度不属于同一片段

| 当前事件 | 源 | 旧深度片段 | 当前几何片段 | 实际新片段深度原因 |
| --- | ---: | --- | --- | --- |
| Feeding 1201–1906 / F572，q605 | 151 | 508–537 | 557–563 | F557–563 全部 POTENTIAL_MIXTURE |
| LW / F2896，q2909 | 3 | 2845–2846 | 2866–2884 | F2866–2884 全部 POTENTIAL_MIXTURE |

这 26 帧的原始 core 均 `raw_core_usable=true`，实际混合证书均报告 `SUBSTANTIAL_MEASURED_LAYERS_HAVE_NOISE_SEPARATED_MEDIANS`、`eligible_single=false`。例如 Feeding F557 n151：227 点、MAD 11.26953125 mm；LW F2866 n3：736 点、MAD 36.012542724609375 mm。样本多或中位数稳定，仍不足以证明是单一身份表面。

几何通过 clean 门不代表混合深度可绑定个体。深度保留的是风险前结束的片段，几何冻结的是风险后重建的片段；generation/public/epoch 相同仍不能跨风险拼接。此处混合门的拒绝须保留，不能改为 qualified。

## 16 个 NO_SAME_FRAME 的拆分

14 个冻结几何本来就不共时：Feeding F59/F67/F71/F185/F191；FishSA dev F3863/F4057/F4485/F5399；FishSA val F2125/F2617；L3 F2802；LW F218/F932。这里是本次选入历史不提供同帧双鱼证据，不意味着整个视频从未有共同证据，也不能异步相减造出“上下关系”。逐帧范围、版本和真实量测事实见 JSON。

2 个有实际共时历史被各自后续独立片段覆盖：

| 事件 | 冻结 A 深度 | 冻结 B 深度 | 冻结几何共同帧 | 实际可引用的历史证据 |
| --- | --- | --- | --- | --- |
| Feeding 351–555 / F105，q120，n1/n24 | 65–73 | 88–94 | 68–73 | 68–71 与 73 双方原 core 及混合证书均合格；72 的 n24 是 POTENTIAL_MIXTURE，不能跨72拼接 |
| FishSA val / F457，q463，n3/n4 | 439 | 407–416 | 414–416 | 414–416 双方原 core 与混合证书均 SINGLE_COMPATIBLE_LAYER；n3 后来的单点439替代了它自己的较早片段 |

这两例支持“独立 latest 不等于最近共同证据”的机制诊断。此处只引用实际缓存，没有重新调用关联、判断应选哪个候选或预报增益。若未来保留共同片段，也仍须受来源版本、风险、真实 gap 和原赔率门约束。

附带的时限边界：FishSA dev F5927 中 B 的最后深度至 q 为 22.69 秒；F3863 中 A 为 13.658 秒，均超过原 12 秒窗。当前先因更早的绑定/同帧检查返回 UNKNOWN；不能把这些早停原因修掉便宣称证据会有效。未执行任何假想关联。

## 本轮 pending 隔离边界

独立审查还确认 `pending[native]` 是一个共享目标槽：保护边确认会覆盖同一新 source 正在确认的普通边。`controller.py:224–227` 将 routed native 从组外 pending 比对中排除，`:260–270` 直接运输该 native 的 proposal pending。因此 native 键范围保持局部，但**按目标公共身份划定的事件外确认进度没有隔离**。

- Feeding local193：普通 n38→public7 已 count3；保护 proposal n38→public16 count1 覆盖该槽。local196 又发生同样覆盖。ORDER 在195自然提交7，RETURN 到该段末仍没有提交7，实际发布195–200六帧不同。
- LW local949–952：保护 n32→public7 count1–4 覆盖普通 n32→public24 进度。ORDER 在952提交24，RETURN 到957才自然提交24，实际发布952–956五帧不同。

这些帧没有 protected return accepted/stage/commit；它们依然改变后续普通确认和实际发布。不能写成“零 return 就零副作用”，也不能用 source 键隔离 PASS 替代 target 级 pending 隔离 PASS。是否物理正确或指标损害由独立评分报告承担，本审查不读 GT 或重新评分。详见 `PENDING_COMPETITION_BOUNDARY.json/.md`。

## 唯一下一步

**分离保护边与普通边的 pending 确认状态，让未提交的事件 proposal 无法覆盖事件外目标的既有确认。** 本轮不修、不重跑。历史配对的生命周期错位、混合深度合法拒绝和共同证据被独立 latest 覆盖，作为下一步计划的明确研究边界保留。

## 证据与复现

- `PRE_PAIR_DIAGNOSIS.json`：全部50个实际 q、原原因、逐角色版本/帧/fact/绑定、199个字段失败、真实状态转折及事件生命周期。
- `PRE_PAIR_FOCUS_SOURCE_FACTS.json`：44条真实缓存量测/混合证书，含 source frame、原质量统计、证书 SHA、frame binding SHA。没有私有像素。
- `PENDING_COMPETITION_BOUNDARY.json`：两处普通确认、保护 pending、实际 stage 状态和发布映射的连续冻结 trace。
- 三个审查脚本仅读源记录；输出使用 `write_new` 拒绝覆盖。运行已存在的审查输出会拒绝写入，复现需在保留原产物的独立工作副本中运行。路径、字节数和 SHA 都在对应 JSON 中；依赖既有 D-MOT Python、只读 DS19/DS18 公共缓存与源码，不需要模型服务或密钥。
