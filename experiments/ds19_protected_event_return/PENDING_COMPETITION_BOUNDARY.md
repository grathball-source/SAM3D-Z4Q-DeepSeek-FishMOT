# DS19 pending 确认隔离边界

只读已封存 trace，不读 GT 或 metrics，不修改本轮 controller，不重新关联或评分。冻结 controller SHA：`420aad60656d9084f7c7281c597d5039490a9f0aa3b221f02e855904b7241538`。

## 根因

`controller.py:224–227` 用 native 键过滤组外状态；`:260–270` 运输原 proposal 的未接受 pending。`pending[native]` 仅有一个 target 槽，没有事件/普通目标两条确认状态。

因此新 source 被纳入 event route 后，其普通事件外 public 目标的 pending 也被列为源内允许写集。保护 pending 覆盖这一槽既不写 alias 也不写 bank，但会重置普通边确认，随后改变普通自动提交与真实发布。source 键隔离成立，不足以证明 target 范围隔离。

## 两个真实连续切片

### Feeding 0–199：事件 F155，受保护 public2/16

- 191、192、193：普通 n38→public7 count1、2、3。
- 193：private proposal 原矩阵选 n38→public16 count1，运输时覆盖普通 pending；未 accepted、未 stage。
- 194、195：RETURN 普通7重新 count1、2；ORDER 在195自然 count5提交7。
- 196：RETURN 普通7 count3再次被保护16 count1覆盖。
- 197、198、200：RETURN 普通7再次从1开始，到段末仍未提交；195–200首次实际发布均 public38，ORDER 为7。

### LW：事件 F932，受保护 public3/7

- 普通 n32→public24 从948开始 count1。
- 949–952：保护 n32→public7 count1–4，逐帧覆盖普通24同源 pending。普通24的计数反复变成1。
- ORDER 在952自然提交24；RETURN 在957才自然提交24。实际发布差异为952–956五帧。
- 未发生保护边 accepted、stage 或 event local return commit；迟来的24仍是普通自动提交。

原始保护边假设不等同真实身份，不能按 GT 判定哪条该赢。本审查确认的是相同普通源的确认状态被未提交保护 proposal 干扰，实际因果链可直接从冻结 trace 复核。

## 判定与下一步

本轮源/accepted事务局部写集检查，未覆盖 target 级确认隔离，工程边界未通过。**零 event return 不等于零副作用。** 同时不得称发生了整套 baseline 状态复制或组外鱼 bank 被覆盖；实际写入是同 native 的 pending 槽。

唯一下一步：分离保护边与普通边的 pending 确认状态，保留本轮完整结果与代码，不把此修复追写进本轮。

完整 frame/original frame、ordinary event、proposal checks、carry、stage、actual public/alias 与来源文件哈希见 `PENDING_COMPETITION_BOUNDARY.json`；复现脚本 `review_pending_competition.py` 不调用跟踪器或新关联。
