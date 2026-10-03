# 逐行文本SHA的换行规范

`ISOLATION_EFFECT_REVIEW.json` 中的 `source_row_sha256` 是真实gzip来源经
Python文本读取后、将CRLF规范化为LF的UTF-8完整JSON文本行SHA，含行尾LF。
验证helper读取同一真实来源并采用相同文本规范，因此64条行绑定可复现。
它不是解压后未规范化的物理CRLF字节行SHA。

实际检查 `TRANSACTIONS.part003.jsonl.gz` 的二进制首行以CRLF结束。
每个物理压缩来源文件的真实路径、字节数和SHA另在
`source_citations` 中记录，验证helper逐文件重新计算，未做换行转换。
报告中的“原始JSON行SHA”应按本规范解释为真实来源的规范化文本行SHA；
不表示来源gzip或物理行字节被改动。

本说明只限定哈希术语。来源内容、控制器、预测、评分、所选64行事实和
两次UNSCORABLE、实际IDSW新增1/消除0的结果均不变。
