# 数据与状态合同

原saved observation/profile/assignment/raw source/DS18 certificate逐帧绑定时间、全局帧、输入行SHA、实际mask和同ROI质量。来源原始容器与source_index依赖哈希验证；不读取annotation instance_id、v3、未曝光test或GT raster进行预测。关联无RGB读取，无颜色/纹理。

pre使用DS34不可变精确anchor registry：每个纳入观测都有native/generation/public/epoch版本，风险或丢失切断live片段，旧anchor不会随当前风险删除。进入前快照不跨风险。post同generation连续并匿名，位置和深度来自同一实际片段；速度不足三点UNKNOWN。所有风险mask仍由原Z4Q完整发布和评分，不制造临时公开个体ID。

模型侧HTTP=0。原DS31 core独立来源、whole/core混层、数量、覆盖、原始来源质量和DS1真实时间WLS不变。WLS记录斜率/尺度，不把深度差当运动。每个派生深度成本和几何事实保留原fact引用及实际观测行/ROI binding。

影子管理器无权写原Z4Q。原状态推进不因疑似、合并、pending或取消被截断。无新增事务时保留自身engine/previous/epochs/provenance的完整状态。新的成功事务在q自身检查点上重放全后缀，只更改事件写集；原持久映射不因下一帧强制native而丢失。重复目标、外部alias、native优先或原lifecycle veto拒绝后无状态污染。发布缓冲只能修正未首次发布帧；不回填已发布过去，不补画不可见鱼，不丢任何残片。

评分输入绑定实际预测、每个交易行、输入行、首次发布账本、START/END及seal。全部八段封存才打开参考。私有像素不提交，清单列实际路径、字节、SHA和复现环境；公开仅数值事实/预测token、代码、报告、无像素图表。
