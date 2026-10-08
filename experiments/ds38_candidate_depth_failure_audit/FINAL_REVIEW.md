# DS38完整竞争历史与原始深度失败审计

**主判定：四段1471帧诊断回放与原Z4Q完整状态、trace、mapping、版本逐帧一致。新跟踪策略未运行，不能宣称提点或泛化。**

覆盖全部27次旧提交：17次WRONG、8次CORRECT对照、2次UNSCORABLE。队列及旧GT摘要已经曝光；所有新候选与深度特征先封存，再独立读取旧REFERENCE_MATCHES，未读新GT raster或未来帧决定输入。

## 正确历史在哪一层消失

| 旧物理结果 | 数量 | 任意bank有同物理参考 | 独立旧参考在bank | 进入矩阵列 | 存在合法入边 | 低于dummy |
|---|---:|---:|---:|---:|---:|---:|
| WRONG | 17 | 14 | 10 | 5 | 0 | 0 |
| CORRECT | 8 | 8 | 8 | 8 | 8 | 8 |
| UNSCORABLE | 2 | 1 | 0 | 0 | 0 | 0 |

“独立旧参考”排除本次尚未重接的当前incumbent和当前同native片段。当前n的近帧当然可能与自己同物理；这不能冒充一个已消失旧身份进入了重接候选池。原始全bank和两种口径全部保留。

错误分层：{"NO_INDEPENDENT_CORRECT_BANK_REFERENCE": 7, "CORRECT_HISTORY_EXCLUDED_BEFORE_MATRIX": 5, "CORRECT_HISTORY_COLUMN_BUT_EDGE_REJECTED": 5}。

## 完整分布是否能区分

固定Wasserstein-1距离比较全部独立测量来源，不择峰。下表是对真实合法矩阵边的诊断排序；UNKNOWN/无正确边不算成功，whole/core分别列，不是新的匈牙利关联或跟踪成绩。

| 旧结果 | whole诊断 | core诊断 | 双端core旧质量门槛后 |
|---|---|---|---|
| WRONG | {"NO_SCOREABLE_CORRECT_EDGE_IN_POOL": 17} | {"NO_SCOREABLE_CORRECT_EDGE_IN_POOL": 17} | {"NO_SCOREABLE_CORRECT_EDGE_IN_POOL": 17} |
| CORRECT | {"ONLY_CORRECT_EDGE_NO_COMPETITION": 6, "UNIQUE_CORRECT_MINIMUM": 2} | {"ONLY_CORRECT_EDGE_NO_COMPETITION": 6, "UNIQUE_CORRECT_MINIMUM": 2} | {"ONLY_CORRECT_EDGE_NO_COMPETITION": 6, "UNIQUE_CORRECT_MINIMUM": 2} |
| UNSCORABLE | {"NO_SCOREABLE_CORRECT_EDGE_IN_POOL": 2} | {"NO_SCOREABLE_CORRECT_EDGE_IN_POOL": 2} | {"NO_SCOREABLE_CORRECT_EDGE_IN_POOL": 2} |

whole/core差、三个几何分区的差和局部背景相似均逐例保存。较宽/多层不自动意味着两条鱼，背景环不保证是真背景，原始非零深度不自动可靠；没有像素表面真值，不能给污染率或物理识别准确率。

## 相对深度次序

{
  "total": 1309,
  "statuses": {
    "UNKNOWN": 1244,
    "SAME_VERSION_MEASURED_PROXY_ORDER": 65
  },
  "reasons": {
    "WITNESS_CONTACT_OR_QUALITY_RISK": 1159,
    "WEAK_MEASUREMENT": 185,
    "SOURCE_OR_PUBLIC_VERSION_BREAK": 39,
    "NOT_INDEPENDENT_WITNESS": 19,
    "VISIBILITY_BREAK": 34
  },
  "qualified_by_reference_relation": {
    "SAME": {
      "False": 9
    },
    "DIFFERENT": {
      "True": 23,
      "False": 32
    },
    "UNKNOWN": {
      "True": 1
    }
  }
}

只把连续同generation/epoch/public、没有中途接触或质量风险的邻鱼作为可比较见证。其余原始次序仍保存为UNKNOWN代理证据；没有连续见证时，不能把两次无身份绑定的“上下”直接拼成身份约束。

## 全部逐例结果

| 全局帧 | 当前→旧public | 入口 | 物理 | 独立正确旧参考 | 真正合法正确边 | core分布诊断 | 原因 |
|---:|---|---|---|---|---|---|---|
| 159 | n26→p16 | D1_DELAYED | WRONG | [] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | NO_INDEPENDENT_CORRECT_BANK_REFERENCE |
| 190 | n30→p8 | D1_DELAYED | WRONG | [] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | NO_INDEPENDENT_CORRECT_BANK_REFERENCE |
| 194 | n38→p7 | D1_DELAYED | UNSCORABLE | [] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | UNSCORABLE |
| 374 | n70→p67 | D1_DELAYED | UNSCORABLE | [] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | UNSCORABLE |
| 468 | n80→p21 | BIRTH_REFINE | WRONG | [67] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | CORRECT_HISTORY_EXCLUDED_BEFORE_MATRIX |
| 522 | n83→p73 | D1_DELAYED | WRONG | [22] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | CORRECT_HISTORY_COLUMN_BUT_EDGE_REJECTED |
| 834 | n118→p99 | D1_DELAYED | WRONG | [100] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | CORRECT_HISTORY_EXCLUDED_BEFORE_MATRIX |
| 849 | n119→p70 | D1_DELAYED | WRONG | [] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | NO_INDEPENDENT_CORRECT_BANK_REFERENCE |
| 897 | n127→p106 | D1_DELAYED | WRONG | [] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | NO_INDEPENDENT_CORRECT_BANK_REFERENCE |
| 905 | n123→p117 | D1_DELAYED | CORRECT | [70, 117] | True | ONLY_CORRECT_EDGE_NO_COMPETITION | CORRECT_CONTROL |
| 969 | n129→p91 | D1_DELAYED | WRONG | [] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | NO_INDEPENDENT_CORRECT_BANK_REFERENCE |
| 1043 | n132→p120 | D1_DELAYED | CORRECT | [106, 120] | True | ONLY_CORRECT_EDGE_NO_COMPETITION | CORRECT_CONTROL |
| 1360 | n170→p167 | D1_DELAYED | CORRECT | [136, 167] | True | ONLY_CORRECT_EDGE_NO_COMPETITION | CORRECT_CONTROL |
| 1390 | n172→p126 | BIRTH_REFINE | WRONG | [136, 167] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | CORRECT_HISTORY_COLUMN_BUT_EDGE_REJECTED |
| 1404 | n168→p136 | D1_DELAYED | WRONG | [162] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | CORRECT_HISTORY_COLUMN_BUT_EDGE_REJECTED |
| 1463 | n177→p158 | D1_DELAYED | CORRECT | [158] | True | UNIQUE_CORRECT_MINIMUM | CORRECT_CONTROL |
| 1466 | n174→p163 | D1_DELAYED | CORRECT | [163] | True | UNIQUE_CORRECT_MINIMUM | CORRECT_CONTROL |
| 1466 | n176→p167 | D1_DELAYED | CORRECT | [126, 167] | True | ONLY_CORRECT_EDGE_NO_COMPETITION | CORRECT_CONTROL |
| 1516 | n178→p119 | D1_DELAYED | WRONG | [136, 162, 173] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | CORRECT_HISTORY_COLUMN_BUT_EDGE_REJECTED |
| 1615 | n181→p166 | D1_DELAYED | CORRECT | [135, 166] | True | ONLY_CORRECT_EDGE_NO_COMPETITION | CORRECT_CONTROL |
| 1681 | n188→p125 | D1_DELAYED | WRONG | [135, 166] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | CORRECT_HISTORY_EXCLUDED_BEFORE_MATRIX |
| 1712 | n186→p166 | D1_DELAYED | WRONG | [132] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | CORRECT_HISTORY_COLUMN_BUT_EDGE_REJECTED |
| 1751 | n183→p125 | D1_DELAYED | WRONG | [] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | NO_INDEPENDENT_CORRECT_BANK_REFERENCE |
| 1799 | n187→p164 | D1_DELAYED | WRONG | [136, 162, 173] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | CORRECT_HISTORY_EXCLUDED_BEFORE_MATRIX |
| 1821 | n194→p149 | D1_DELAYED | CORRECT | [149] | True | ONLY_CORRECT_EDGE_NO_COMPETITION | CORRECT_CONTROL |
| 1888 | n193→p158 | D1_DELAYED | WRONG | [132] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | CORRECT_HISTORY_EXCLUDED_BEFORE_MATRIX |
| 1893 | n197→p167 | D1_DELAYED | WRONG | [] | False | NO_SCOREABLE_CORRECT_EDGE_IN_POOL | NO_INDEPENDENT_CORRECT_BANK_REFERENCE |

## 工程与边界

5项直接检查通过，含真实F159的160帧切片。两条入口完整bank、候选matrix、dummy和terms均记录；BirthRefine的实际core/whole锚点与D1 bank锚点分别追溯。旧原Z4Q、DS36/DS37代码及seal未改。

实际深度/mask图仅私有；公开27张分布统计SVG。受限清单记录真实路径、字节、SHA和复现依赖。新模型HTTP、smoke、SAM3推理、训练、补全、费用、RGB/GPU/服务器均0。

本轮未运行新性能策略；输出与原Z4Q逐帧一致是审计完整性证据，不是深度提点。此固定曝光集合上的分布排序不得直接当作新验证成功。

下一步将在审计结果核对后冻结为一个机制；本报告的NEXT_STEP.md为最终单一建议。

## 原输入ROI补充核验与来源边界

主统计图使用DS36自适应core，与原Z4Q profiles固定腐蚀core不同。LEGACY_ROI_SUPPLEMENT_SEALED另封存原ROI：235时刻/6289观测的whole/core area/n/fraction/median/MAD/q25/q75逐列严格等于旧输入，原像素人口和独立去重人口分列。补充是在GT已曝光后的量测验真，不把其统计拼成新的盲输入或新成绩。原core下过滤前仍是12次无正确列、4次其他身份更近、1次正确最小，全部固定列保留。

错误当前原core样本数不足16的四例是F159、F897、F1404、F1751；不能把扩大ROI后的16/17测量支持率当成原core支持率。其他错误即使原core有足够有效点，深度接近也未证明同一身份。

source generation来自可见性连续性，epoch来自原Bridge；没有完整生产者reset元数据，不能认证一个连续native内部从未换鱼。REFERENCE_MATCHES不可评分的旧参考不能当成已证实不存在正确鱼，所以候选计数表的“正确”是可评分SAME定义。F468、F1681的同物理旧bank已被当前另一物理观测占用，事后只发现问题，不用GT释放占用或改动作。

最终真实图是FIXED_SCALE_PRIVATE_VISUALS：统一900–1400mm显示、洋红表示缺失；低值黑色不等于缺失。27组固定前后图与8张全案例联系图只在private中；17错误、8正确、2不可评分全部保留。公开27张自适应core统计SVG，像素、真实人口数组、凭据和GT raster未上传。

唯一下一步是NEXT_STEP.md的D1共同竞争门控试验，目前尚未启动；不等于推荐无条件放宽历史、深度或占用门槛。
