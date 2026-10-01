# DS12 交付、工程记录与复现边界

本轮在主仓库main上非破坏性追加，基点d3c0fe5c287c9fbe54004b3d7ef74380fc001569。所有DS1–DS11已跟踪实验文件由OLD_READONLY_LOCK的1107项字节摘要保护；没有覆盖旧源码、预测、评分或seal。main普通提交/推送，远端实际核验记录由REMOTE_VERIFICATION保存。

## 已保留的工程失败

1. 正式全段前的attempt1真实切片：OpenCV精确L2的float32最大距离元数据1 ULP不稳定，严格source重算失败。ENGINEERING_ATTEMPT1记录旧源码、检查和切片快照；私有真实路径/字节/SHA进入RESTRICTED_INVENTORY。原日志和公开检查记录以ATTEMPT1后缀保留。当前证书使用精确最近零像素整数平方距离，全部出生帧2715个实际mask核心零像素变化；未放宽scorer，未修改旧测量缓存。只运行一次正式全段和一次独立正式评分。
2. 事后绘图首轮：二维axes迭代把ndarray当作轴，检查ax.images时失败。原脚本、日志及首图另存私有工程目录；只修后处理axes.flat并重新生成诊断图，不改预测、评分或研究seal。18组最终图的inventory仍标QA_PENDING作为生成时状态，独立事后QA绑定实际图hash，不回写原inventory。

原公开SVG中的长候选文字有溢出，独立QA如实保留该发现。另从原公开inventory数值生成18张自动高度的readable_details SVG附页，完整时点、实际ID、所有候选、拒绝理由及片统计均可读，并追加附页inventory/实际渲染QA。没有重读数据像素、GT或预测，没有研究重测；原图、原QA与封存仍不变。

## 冻结文字勘误

runner.freeze_inputs中的branch_policy静态字符串残留“R11 arms”。实际ARMS、控制分支、模块来源、证书、事务、发布和scorer均为R12。正式冻结后未改运行代码或此字符串，现追加澄清；未发现同类错误执行分支。研究结果以实际代码SHA、四分支预测与绑定记录为依据。

## 数据及公开范围

SOURCE_OLD四段1471帧，同源SAM3 mask/raw depth与保存native-v2。已有历史/group测量逐字复用，当前101个非初始出生帧的所有mask重新提取证书；不是对39208个全段mask逐像素重新计算深度。实际NPZ字段仅depth_mm/source_index；预测不直接读GT/RGB/v3/未来二维数组、不联网。v2上游RGB/后帧清理属于已曝光离线诊断，原始深度为因果输入，物理表面归属与毫米精度未知。

公开代码、参数、检查、数值fact、各分支ID到mask token映射、日志、逐事件审计、指标、纯数值SVG及报告；原mask像素、深度数组、GT raster、图像和真实切片保留私有路径。受限清单包含真实路径、字节和SHA，复现需原保存源、现有Python/依赖、已记录相机几何与native-v2；不需要任何API key。没有公开凭据或provider file IDs。

## 成果阅读顺序

- RESULTS.md：全部主表、差值、四段成绩、成功及失败原因、费用与耗时。
- POSTRUN_COMPONENT_REVIEW.json/.md：210出生、所有候选与拒绝原因、五个代表性未提交例、切换分解。
- POSTRUN_EVALUATION_REVIEW.json/.md：独立指标、真实发布、身份来源与因果归因边界复核。
- postseal_SOURCE_REVIEW.json、diagnosis/postseal_VISUALIZATION_INVENTORY.json及独立QA：真实测量覆盖、18组实际前中后图与纯数值SVG。
- run/*SEALED*、VERIFICATION、BIRTH_AUDIT、EVENT_AUDIT、SWITCH_LEDGER：正式封存、严格端到端验收与事后统一评分。
- RESTRICTED_INVENTORY、POSTRUN_ACCEPTANCE、ARTIFACT_MANIFEST、REMOTE_VERIFICATION：本地受限库存、旧字节保护、公开库存、正常main远端核验。

完整目标在本四段满足，但只有1次新增正确身份恢复，不声称统计显著性、独立深度必要性、修复深度独有增益或跨录像泛化。唯一下一步见NEXT_STEP_PLAN，当前仅规划，不自动启动。
