# DS8 最终代码隔离审查

**PASS：未发现本轮实现的阻断问题；结论限定为测量变量与代码隔离。** 本审查不判断跟踪收益。只新增审查文件，没有修改冻结源码、阈值或运行回放/评分。

## 已核对的实证

- association、controller、restored_source、launch 与 DS7 逐字节相同。共享关联/历史/质量常数保留：16点、比例0.2、尺度60mm、权重0.25、log9；CONFIG新增仅描述ROI规则。
- 四段 FREEZE 来源、扫描、派生输入、原始与v2深度、元数据记录和 DS7 完全一致。全部1471帧封存后逐条核对 old objects、full、restored_full、restored_source 不变；adaptive_full 与原 full 完全相同。最后706帧完成seal后再读取核对。SAM3_NATIVE与旧DS7、D2与旧DS7、P0与本轮native逐帧精确一致。
- 四份冻结code字典相同，各56项；224次当前摘要核对全部匹配。本项目执行/评分关键文件和独立matching/CLEAR辅助均覆盖，投影源码单列restored_sources。

## 唯一统计采样改变

先排除mask重叠，再对每个8连通片用零补边的精确L2距离，取 d≥max(1.5,min(3,0.5×dmax))，并合并所有保留下来的片。阈值只读当前mask与occupancy；不读深度或GT。piece记录几何连通片，samples记录ROI像素数，不能解释成有效深度数量或独立物理表面。

P1的独立state/likelihood绑定adaptive_raw，P2绑定同ROI的retained/inferred，D2/P0沿用原objects。原profiles、触发/二维项、银行质量、控制器、完整背景与缺测模型保持不变。宽片和不规则边界的采样也会改变，因为L2阈值与旧7×7方形腐蚀并不等价；这是全mask的ROI规则试验。

## 推断噪声与时间边界

actual_selected_mad_mm及cohorts.inferred.mad保留实际MAD。仅当选择inferred时，core.mad作为噪声适配代理=max(actualMAD,60/1.4826)，明确标EFFECTIVE_NOISE_ADAPTER。该60mm是单点假定sigma，不是测得精度；WLS拟合可压低forecast尺度，样本相关性未校准。retained/inferred的中位数分开，资格仍使用原来的实际统计规则。

候选只使用合法冻结pre与当前q首观测，cutoff=q；manager的mask索引是当前帧或上一group帧。完整assignments、扫描、时间索引及source哈希预加载，因此只能说决策不用q后观测，不能说未读取任何未来文件字节。v2读取当前H5图像，但已有上游RGB/未来帧清洗仍使P2属于离线曝光诊断。

## 封存与解释限制

评分检查实际DS8 evaluate/event_audit/score_checks，保留全部分支/段seal、source/code/access、旧D2逐帧等价、首次publisher及历史fact绑定。本次也核验了全四段产物seal、ALL与ACCESS摘要绑定、实际全量访问audit（含v3禁读标记）；所有q首post及冻结pre时间边界逐项通过。正式评分VERIFICATION另已生成，本审查没有运行GT评分或判断收益。

冻结launch实际禁止v3，slice访问记录也包含该项；scorer必需token集合没有独立强制restoration/v3/这一项，属于验证范围限制，没有观察到v3读取。ROOT外库实现没有全部逐文件冻结；ENVIRONMENT记录运行版本，不能称整个二进制环境按字节锁定。

事件审计的legacy piece字段可能为空，因为本轮连通片是roi_geometry中的几何片，不是合格深度surface。继承DS7_DEPTH_NUMERIC仅为机制来源标签；实际trial、arm、segment和facts仍属于DS8。

原始P1超过native、离线P2超过native和P2对P1增量必须分别按score_support_layers报告；严格P2增量规则不能代替所有比较。预RUN的10几何、5测量、13控制器、5计分synthetic PASS只验证工程性质；未取得独立surface/mm真值，不能据此称提点或物理准确。
