# DS19 封存后控制图读取顺序修复

第一次只读绘图执行退出 1。真实深度读取器要求原帧单调；集合遍历导致先读较晚帧再读早帧，从而触发 previous_frame 检查。没有修改或重新生成任何预测、评分、触发、关联、深度参数。

唯一修复为 visualize_control 中将 `for frame in frames` 改成 `for frame in sorted(frames)`。重跑退出 0，产物为未恢复控制图和封存 order 汇总。初次及重跑日志保留，均绑定真实字节数、SHA、exit 和耗时。

初次耗时 15.73761089995969 秒；重跑耗时 127.48539309995249 秒。
当前 helper SHA：d7c056b95c7d925810e2d7a8e5cac5ea37f2afcc8f75e5b77cd1912c6b8da5b1。

只读 archive 是依据记录中的唯一一行改动精确反向构建，并验证再次应用修复逐字节等于实际当前 helper。其 SHA 是现在对 archive 的测量，不冒称第一次执行前独立记录过的旧版本 SHA。真实路径与 SHA 见 DIAGNOSTIC_RENDER_REPAIR.json。

本修复仅属于封存后的图/解释，不是新性能试验。新增模型 HTTP=0、费用=0。
