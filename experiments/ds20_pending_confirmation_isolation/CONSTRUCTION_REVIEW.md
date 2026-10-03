# DS20 冻结前确认来源合同复查

本记录仅描述冻结前工程调整。正式试验尚未冻结、尚未评分；此复查不读GT、不改深度、trigger、q、候选、矩阵、确认阈值或时间窗口。旧DS19目录只读。

## 私有proposal仍可能继承未绑定的普通确认

发现时源码位置：新controller.py的preview中，`trial = copy.deepcopy(self.engine)`，随后清空`trial.event_return_pending_versions`并加载`kept`中的事件确认（发现时约115–123行）。普通主clone不受这一步影响，但私有trial仍保留其余`self.engine.pending`。

原D1确认见`online/closed_loop_2888/z4q_source/source/sam3_depth_failure_repair_20260917/repair_controller_r3.py`约117–128行：只要pending目标相同、0.2秒/0.5秒窗口仍有效，当前候选会接着旧count累加。该pending没有事件generation、source/identity版本或精确旧anchor绑定。

因此需要检查：新事件或旧事件key因版本/anchor变化失效时，若普通pending恰指当前保护目标且count=4，私有事件proposal可能借用普通确认成为count=5。它未必污染普通主state，却可能绕过“新事件边只继承合格同key确认”的合同。此时“独立字典”本身不足以证明确认来源独立。

必要直接fixture：合法普通pending指保护目标、count=4、原时间窗口有效、无匹配事件key（另检查失效旧key）。应当普通主state保持原自然行为，受保护proposal本帧从新count=1开始；随后连续原资格观测仍按原5次确认，而非增加门槛。

最小修正建议仅作用私有trial：清除无合格事件key支持的保护目标普通pending，再加载已通过event/source/identity/精确anchor/target核验的事件确认。矩阵、dummy、阈值、窗口与普通clone不改。直接fixture与源码作者复核负责确认此风险，不以静态推断冒充真实完整实验结果。

## 其余真实控制流只读核验

通过正式runner导入并读取实际运行时MRO，而非只看同名下层方法：

| 实际方法 | 生效来源 |
|---|---|
| causal_view | DS17/controller.py约163行 |
| preview | DS20/controller.py |
| stage_event_return | DS20/controller.py |
| stage_group_restore | DS19/controller.py约448行 |
| local_fallback | DS17/controller.py约218行 |
| commit_once | DS19/controller.py约454行 |

DS17 local_fallback复制当前view.engine和view.trace、只释放本事件保护；它覆盖DS15更早的重跑causal_view实现。因此当前真实q回退不会因落到DS15方法而丢掉确认审计，未增加多余fallback override。联合stage同样继承当前view.trace；仍由直接状态测试检查成功/失败实际路径。

普通本帧accepted先在baseline形成实际alias/mapping；旧事件记录的合法性检查读取这个baseline，优先通过alias、版本或占用使其失效。同时accepted事件proposal若与ordinary accepted source重合会被阻断，原子stage还检查wanted映射等于proposal且组外状态一致。主ordinary pending只由普通clone产生；未accepted事件确认存入独立字典，不写回主pending。

取消/超时由原manager移除protected事件；下一preview用实际spec/context失效旧counter。首分离q使事件counter失效，不在该帧走单边返回；已提交alias按原真实分支继续，不因释放事件保护自动改回native。未发现需要改变这些政策的证据。

完整结论仍依赖真实Feeding/LW竞争切片、L3自然5次确认、正式封存后的actual engine/publisher审计；静态合同检查不能代替完整指标或物理正确性。

## 记录范围

复查不修改controller，不执行额外API或SAM3，不提交旧成绩。先前直接按模块名`controller`导入的只读MRO探针遇到旧基础模块同名循环导入；随后改用正式runner的唯一adapter模块名读取MRO，导入成功。正式runner导入策略未改变，这一探针失败不是正式试验故障。

发现与后续fixture/源修正日志一并保留。已启动的工程prefix若需停止，保留其partial输出与退出日志；在正式冻结前重新检查修改后的真实源码。

## 修复后源码复核

源作者已在私有trial中先移除目标属于当前保护身份的普通pending，再加载合法同key事件counter。普通主clone仍保持原pending；after_proposal取自实际baseline.engine.pending。旧DS19源码没有修改。修复后controller SHA256：`9f5266fa86e7c1473237df2321bd2624e66550cde2fd29cce2a101fa9bbf6167`。

直接fixture现通过真实D1观测产生普通count1/2/3/4，再进入新保护事件；无合格事件key时当前事件只count1。这一开发测试由源码作者直接运行，结果在工具返回中，尚无独立保存的stdout/stderr文件；本记录不伪造日志路径。正式checks.py将另生成实际CHECKS/执行日志，之后以其源码绑定与结果为冻结证据。

此修正关闭了未绑定普通确认被私有事件proposal借用的工程合同缺口；不改变完整矩阵、自然5次确认、0.2/0.5秒窗口或普通真实状态。真实prefix与完整性能仍待本轮正常流程核验，不能由单测PASS预报提点。

## R2真实前缀与审查工具修正

R2六列4190帧完成，四个归档控制逐帧精确；实际source→cache→候选→stage/commit→首次publisher检查通过。首次确认审查的实际8380条新分支状态检查通过，但报告FAIL：审查额外要求普通接受帧必须产生删除记录。Feeding源38的保护目标16计数已在194帧因原矩阵不再继续而失效，195普通接受时无旧key；LW源32在952普通接受之前未存入独立事件计数，不能要求删除一个不存在的key。实际普通接受时刻、mapping、alias与冻结无返回控制完全一致。

保留CONFIRMATION_SLICE_CHECKS_R1.json/md及首失败完整日志。只修审查谓词：普通接受后对应事件计数必须为空；接受前有精确旧key时才要求逐键失效记录。第二次审查因新输出路径变量被数值target遮蔽，在写文件时TypeError，未写新结果；完整退出日志保留。将输出变量独立命名后，第三次只读审查PASS，仍读取同一R2输出，不重放、不改controller/runner或科学政策。两窗自然接受为Feeding195→7与LW952→24；L3两新列保留3025自然5次确认返回。以上是工程与发布回归，不是物理正确性或深度提点。
