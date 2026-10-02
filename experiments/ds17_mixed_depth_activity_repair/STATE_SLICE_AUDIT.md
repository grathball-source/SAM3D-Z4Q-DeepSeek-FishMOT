# DS17 真实 L3 状态来源切片验收

## 执行与边界

实际执行3025帧source-only前缀，耗时61.259421秒、退出0。未读取GT/GT raster/RGB，未评分，新增API与费用为0。所有S0固定H0释放，仅验证状态读写链，不作为完整深度关联成绩，也不评判物理身份正确性。

首次执行已成功，stdout此前只返回工具。依明确要求，代码不变再执行一次以保存完整实际stdout、来源与耗时；这是工程落盘验收，不是科研重复、模型重问或择优。

复现命令：

```text
"E:\researchsoftware\anaconda3\envs\D-MOT\python.exe" -B "E:\CAU\SAM3D-Z4Q-DeepSeek-FishMOT\experiments\ds17_mixed_depth_activity_repair\test_controller.py" --real-l3
```

## 实际状态与首次发布

| 状态 | local2890 bank9活动last_frame | local3025 native47发布ID | local3025 bank9 clean anchor | 目标9竞争 |
|---|---:|---:|---:|---|
| 原Z4Q | 2890 | 9 | 3025 | alternatives空，真实D1提交 |
| 旧DS16保护 | 2872 | 47 | 2712 | partner5 margin -4.926819，拒绝 |
| 新DS17状态分离 | 2890 | 9 | 2712 | alternatives空，真实D1提交 |

新版本将来源native9的last_seen/last_frame/contact/partners按实际观测推进至2890；不替失踪member增加时间。local3021–3025目标边累计五次确认，新版本在local3025/global3024实际自动提交n47→9并第一次发布9。新版本目标身份参考仍为2712，不把组测量或当前匿名片段写成进入前参考。原D1边cost0.748384、深度/运动门槛未改；过期partner5移除来自真实活动时钟恢复。

## 合同检查

必要合成测试此前PASS：无事件原状态等价、真实活动和缺失时钟、clean/view/recentcore冻结、匿名当前深度禁用于个体关联、真实clean/view篡改拒绝、generation守卫、stage原子性、局部fallback保住组外alias、新post无虚构参考、陈旧接触竞争复现。此处不额外声明深度性能。

JSON封存完整原始stdout、解析结果（2872/2890/3021/3025三条状态的实际slice）、源码和输入字节/SHA、运行命令/耗时/退出。输入hash匹配旧冻结DS14来源链，controller/test文件前后不变。

完整六分支性能尚未由本审计产生，随后正式冻结回放独立决定结果。
