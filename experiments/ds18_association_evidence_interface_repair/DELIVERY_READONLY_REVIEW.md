# DS18 冻结后交付与评分接口只读审查

审查时正式全段仍运行；本记录只读取源码、八段 FREEZE 元数据和已有项目忽略规则。未读取任何未封存预测、GT、参考匹配或本轮成绩。冻结代码与旧 seal 均未修改。

## 可执行接口

- 十个实际交付/评分/可视化脚本均成功解析，SHA 与八段冻结元数据一致。
- postseal_report 首先要求全预测封存与完整评分，核对全 seal、单段 seal 和必要产物；group 仅遍历真实 ARMS[2:]，不会读取 automatic_reconnect 汇总对象作为 group。
- scorer 提供了报告使用的 accepted/actual-reference/public-origin/durable 字段。自动预览 accepted、实际首次发布、持久 alias、被显式事务覆盖分别保留；literal endpoint 与 pre-fragment consensus、未提交与 UNKNOWN/UNSCORABLE 分列。
- 同源 native/Z4Q/DS16 parity 为完整逐帧与统一评分核验；Feeding 单独池化，不生成跨数据集整体提点表。全部 mask 和公开 ID 参与同一官方指标计算。

## 结论必须保留的边界

- build_report 的主 status gain/loss 只由 MIXED_ORDER−ACTIVITY_ORDER 的 IDF1 正负决定；标题中的 CONDITIONAL_DEPTH_GAIN 只能理解为固定已曝光队列内部分范围的条件 IDF1 增量，不能扩写成 HOTA/AssA 同时提高、超过同源 native/原 Z4Q 或普遍物理身份正确。完整差值表仍必须逐项读。
- MIXED_ORDER−ACTIVITY_ORDER 是同一修复接口上的混层/来源/质量筛选组合差值；MIXED_ORDER−MIXED_OFF 才是冻结顺序因子的条件贡献。对归档 DS17 或较弱旧状态的恢复只称止损。源码报告已经明确这两个边界。
- potential mixture/layer flags 是真实像素统计与来源质量线索，不是已认证鱼体数量或物理上下关系。L3/LW 弱预标注和重复曝光范围限制在报告中明示。

## 公开和受限产物

- 私有实际 mask/depth 可视化仅写 private/visuals；PRIVATE_VISUALS/FAILURE_VISUALS 公布路径、字节、SHA 与数字映射，图像本身保持受限。所有 private 与 slice* 路径由 .gitignore 和 manifest/index 路径检查排除。
- MIXED_DEPTH 分块是数字统计/ROI hash/source hash/binding；JSONL 引用与每个 part 均封存，读取端核查字节与 SHA，未以截断替代完整证据。
- RESTRICTED_ARTIFACTS 枚举实际源和工程 slice 的路径/字节/SHA，并列复现依赖；公共指标图仅基于聚合数字，可作为唯一明确的 PNG force-add 白名单。
- release_verify index 的已实现保证是路径排除和已列 manifest 文件的字节一致；它不是通用像素/凭据扫描。提交前仍须核对完整 staged 集合，拒绝未批准的像素文件、数据文件或敏感内容，不能仅据该布尔字段声称扫描全部内容。

## 收尾执行顺序约束

- 全评分、postseal 汇总、可视化、指标图、下一步规划、报告和所有会追加 EXECUTION_LOG 的 execute.py 调用应先完成。finalize_delivery 生成公共 manifest 后，若再通过 execute.py 包装它或 index/remote 检查，执行日志会改变，manifest 中日志 SHA 将失效。末次 manifest 和发布检查应直接执行，或在任何后续日志变化后重新生成独立完整快照；不得修改冻结评分/预测。
- remote 模式实际读取 origin/main ref、fetch ref 和关键 blob；REMOTE_VERIFICATION 自身随后提交会改变远端 SHA。因此最终 metadata push 后仍须独立实际读取最终 ref 和关键文件，不能仅复述 metadata push 前的 experiment_commit。
- FINAL_REVIEW/RESULTS/README 为本轮生成文件；终止情况仍应另有真实交付记录，不覆盖旧封存或把失败预测拼入新结果。

## 冻结字节核对

|文件|字节|SHA256|八段冻结绑定|
|---|---:|---|---:|
|build_report.py|9553|97c1907f35f3b3647be87acfb6eebb00449ec33f95d4fa38696be31e8e4d07f8|8|
|postseal_report.py|12099|a3f7021f8b1016dc45f1ce39106685af1d244cdfdec8b2da666ea1324b059044|8|
|finalize_delivery.py|4568|df13f11501ae77bc122079fa603937007b4006e1151505de41e03a88bedcfcc1|8|
|release_verify.py|2927|4ac30282953588d6ecfd83d0ee0cecfca5b2f9ff2b6c0b184f64f812fa0a32eb|8|
|score.py|45767|b0d14f4c89fde39544e992896445b85268238d9dd50dde1910a2cf19e0680a29|8|
|common.py|4318|99e53a84dba79c425777db43e88495709b34717282a679ac06c73d5945bdf79b|8|
|orchestrate.py|1321|afb1ef4e85ac5a38e5bf6857935decdf75c901efb04f3a4e6fdbafe56c20ffa0|8|
|visualize_postseal.py|4662|12ca004ee7c8f81ebe17b008d024d52a0c88cf5caba7486cdd24c16639dda2c5|8|
|failure_visuals.py|3906|b2d694e7120aec2255e27851c2e6f6d6114d0b6b4cb7cedfd49dee64a3a090fb|8|
|plot_results.py|1767|904c28f7ee965358c781607ebaccb2265a82b088f7b16db98f0535ee2bdef056|8|

结构审查未发现必须中止本轮回放或评分的具体容器错误。最终结果与动作物理正确性待全部封存、独立评分后再审；本记录不预报改善。
