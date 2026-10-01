# DS13 frozen R12 source availability

本目录保存2026-10-01用户“开始”后的实际来源核查；实验尚未运行。

阅读`RESULTS.md`、`INPUT_AVAILABILITY.json`、`FROZEN_R12_LOCK.json`、`SOURCE_METADATA_INVENTORY.json`及`OLD_READONLY_LOCK.json`。本轮新增指标为空，不能借用DS12成绩。

本机已有Python环境，无需新增依赖。只读复核：

```powershell
& 'E:/researchsoftware/anaconda3/envs/D-MOT/python.exe' -B experiments/ds13_frozen_validation/checks.py
& 'E:/researchsoftware/anaconda3/envs/D-MOT/python.exe' -B experiments/ds13_frozen_validation/preflight.py --verify
```

`preflight.py`默认以独占新文件方式记录审计；原目录重复生成会拒绝覆盖。复现完整审计须复制代码到新目录并保留同一项目目录结构。源审查只解析metadata和科学代码；原预测/参考文件只核文件名，NPY只核路径存在。旧产物复核另外逐字节哈希全部DS1–DS12已跟踪文件，包括旧公开预测压缩流和图表，但不解压、解析或显示它们，不解码原始像素或读取参考内容。检查不构成方法效果试验。本轮公开文件不含像素、参考多边形、密钥或模型响应。
