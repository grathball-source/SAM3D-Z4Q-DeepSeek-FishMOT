# DS18 大日志的完整字节交付

这是全部预测封存后、评分过程中增加的交付包装。冻结科学代码、原 gzip、预测和 seal 均不改变。

`run/LW/public/TRANSACTIONS.jsonl.gz` 为 179086513 字节，SHA256 为
`e3392913270a477a45d5f4848637ffdb180d59b01bef8a72040dd5d35e874b2c`。
三个公开 raw-byte part 大小依次为 62914560、62914560、53257393 字节。
`LARGE_RECORD_PACKAGING.json` 绑定完整顺序、偏移、大小、分块 SHA 和原 sealed SHA。
这不是重新压缩、逻辑截断或修改日志内容。

## 复现封存文件

在有全部公开 part 的新 checkout 中，用已有 Python 执行：

```text
python experiments/ds18_association_evidence_interface_repair/reconstruct_large_records.py
```

重建前验证所有 part，并核对连续偏移和完整拼接 SHA。
只创建缺失的原文件；已有相同文件只验证；已有不同文件拒绝，不覆盖。
写入使用同目录临时文件与 exclusive atomic link，完成 SHA 核对后才出现原路径。
正常评分/分析脚本随后仍按原路径读取完整原日志。

本机真实 roundtrip 保存于 `private/package_check`，包括完整重组文件及
`ROUNDTRIP_CHECK.json`；该受限目录不进入 Git。

## 发布顺序

所有会追加执行日志的操作和最终报告先完成，直接执行 `finalize_delivery.py`。
原 `PUBLIC_ARTIFACT_MANIFEST.json` 继续描述包括原大日志在内的全部逻辑产物。
随后直接执行以下命令，不通过会追加执行日志的 `execute.py` 包装：

```text
python experiments/ds18_association_evidence_interface_repair/packaged_release_verify.py manifest
```

该命令生成 `GIT_DELIVERY_MANIFEST.json`，用全部公开 parts 交付原大文件，
并列入逻辑 manifest、`.gitignore` 和本轮 HANDOFF。原大 gzip 单一路径被 Git 忽略。
暂存全部实际交付文件后执行：

```text
python experiments/ds18_association_evidence_interface_repair/packaged_release_verify.py index
```

检查全部实际 staged 路径与所有预期 index blob 的字节/SHA。
禁止 private、slice、原大文件和未列入清单的路径；公开 PNG 只允许聚合数字指标图。
该阶段的新增核验元数据须另明确暂存或在最终提交后核验。
本轮不使用冻结旧 `release_verify.py index` 对原大文件的暂存假设。

非 force push 后执行：

```text
python experiments/ds18_association_evidence_interface_repair/packaged_release_verify.py remote
```

实际读取 origin/main、fetch ref、所有交付 blobs 与全部 parts。
远端原始字节拼接须等于远端原 seal 的 SHA，原大 gzip 不必在 Git 中存在。
如果核验元数据随后提交并再次 push，必须再实际读取最终远端 ref 与关键 blobs；
不可把元数据提交前的 commit 称作最终 main。

无需额外推理、服务、数据权限或科学实验；模型 HTTP/费用均为 0。

新 checkout 必须先执行 `reconstruct_large_records.py`，再核对恢复的大 gzip
与原 `PREDICTIONS_SEALED.json` 中 `artifacts_sha256` 的字节/SHA。
完成这一步后才能按原路径校验封存记录；parts 本身不是新的科学日志或评分输入。
