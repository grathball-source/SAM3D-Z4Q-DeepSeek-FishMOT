# DS6 状态损害复盘

同源四段1471帧、39208对象，D0/D4/D5公开预测逐帧完全一致。相对native：新增10条、消除4条IDSW，净+6；104条同帧同参考身份共有切换中，7条from/to公开ID还受到此前alias的持久影响。

## 根因与全部新增损害

F419、F519、F1027、F1263、F1719各交换两条此前连续native来源，恰好贡献全部10条新增切换。它们都被旧账本记为RESOLVE_NO_ID_CHANGE，因为changes比较内部q预览；预览本身已经按旧numeric临时H1猜配。被接受的预览随后建立持久event alias，实际q发布确实改变此前公开ID。旧D2在F419/F519的两个COMMIT反而保持前帧/native ID，只修正内部猜配。这些旧状态名称与封存原件保持不变。

F1263四边深度都可用，H1/H2 depth cost为1.934416/1.934515，基本无区分，geometry仍选错。不能把available等同于有支持的改号证据。F419/519新四边门还删去了旧D2有效支持；F1027/1719旧D2虽有部分深度仍未胜过错误geometry。

## 恢复、回退和代价

四条消除IDSW为F764(118→100)、F1239(167→136)、F1390(172→170)、F1745(190→188)。其中三例旧标NO_ID_CHANGE仍实际让新native继承旧公开身份，另一例COMMIT。不能把所有非native输出都归为损害。

五个fallback实际首次发布中1个RGB锚点对应正确、4个不可联合评分，且包含2个无数值候选。它们未贡献这10条新增切换；不能把数值choice当作已提交映射。F1280即使core/new选项不同，均因可见残片走fallback，当前发布未按数字候选提交。

## 最小修复

保护bank/pre/group继续收集匿名证据；public及q预览使用本分支当前合法event alias/native，缺测或DEFER局部释放也从本分支预帧取消保护后完整causal step取得合法engine和mapping。明确获准的候选才经过原原子stage。缺深度仍强制接受geometry permutation会保留上述损害，单改preview不够。

必须保留组外alias、public/native键域及native-return占用规则，未选候选不得污染发布。动作记录分baseline差、连续来源相对前帧差、新来源公开ID、native override；不再用一个旧COMMIT/NOCHANGE标签概括。

用完整1471帧验证无事件写入分支是否与native精确一致，再隔离深度支持改号及已有修复深度的贡献。可能失去四个有效重接，必须全量计入代价。这里没有预测新修复成绩，也没有按GT设提取或写入阈值。

## 证据边界

本报告只读真实事件/事务/公开切换账本，未重新运行tracker/评分，未读GT raster。RGB轮廓锚点对应只解释身份边，不认证像素深度表面或毫米真值。全部72个实际q、每条新增/消除/受影响共有切换及持续alias计数见POSTMORTEM_STATE.json。
