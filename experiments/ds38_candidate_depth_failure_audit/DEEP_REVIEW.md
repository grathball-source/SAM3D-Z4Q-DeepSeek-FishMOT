# DS38深度复盘

## 已确认的机制限制

17次错关联最终都没有合法的同物理旧参考边。7次缺少独立正确bank参考、5次在候选资格层被排除、5次正确列被旧边规则拒绝。这个结论只适用于本次曝光的Feeding错误队列。

D1原代码用`depth_residual/tolerance + 0.15*motion_cost`选择，dummy=1，运动只占小项，连续确认并未提供独立身份证据。深度接近的不同鱼会形成低成本错误边；正确鱼因深度变化、伙伴历史歧义或质量风险可能先被挡住。这里没有用GT修改原规则。

## 放回原有被拒列是否足够

{
  "whole": {
    "NO_CORRECT_COLUMN": 12,
    "OTHER_OR_TIED_MINIMUM": 4,
    "CORRECT_MINIMUM": 1
  },
  "core": {
    "NO_CORRECT_COLUMN": 12,
    "OTHER_OR_TIED_MINIMUM": 4,
    "CORRECT_MINIMUM": 1
  }
}

这是原矩阵列过滤前的分布诊断，不是改候选池后的新成绩。只在F1516，whole/core完整分布的最小距离是正确参考；另外四次含正确列的错误中，分布最小值仍落在错误身份上。不能把“取消门槛+换分布距离”当成已经得到解法。

F1516：正确p136的core W1=12.204mm，选中错误p119=23.103mm，正确边被partner_ambiguous拒绝。F522：正确p22=50.503mm，错误选中p73=8.328mm；F1390：错误p126=11.342mm，正确p136/p167=57.551/63.933mm。不同鱼的深度分布确实可能更接近当前观测。

## 历史生命周期与占用

BANK_REFERENCE_LIFECYCLE.json逐例区分：原来从未留下可评分独立anchor、曾有但bank删除、被其他物理来源覆盖、当前anchor不可评分、仍保留但被规则排除。以上是旧数字reference-match摘要的事后诊断，不把这些GT找到的历史作为新输入。

[
  {
    "action_id": "feeding_000000_000199/F160/n26-p16",
    "ever_same": false,
    "statuses": {}
  },
  {
    "action_id": "feeding_000000_000199/F191/n30-p8",
    "ever_same": true,
    "statuses": {
      "CURRENT_ANCHOR_UNSCORABLE": 1
    }
  },
  {
    "action_id": "feeding_000701_001060/F149/n119-p70",
    "ever_same": false,
    "statuses": {}
  },
  {
    "action_id": "feeding_000701_001060/F197/n127-p106",
    "ever_same": true,
    "statuses": {
      "ANCHOR_REPLACED_BY_OTHER_PHYSICAL_REFERENCE": 1
    }
  },
  {
    "action_id": "feeding_000701_001060/F269/n129-p91",
    "ever_same": false,
    "statuses": {}
  },
  {
    "action_id": "feeding_001201_001906/F551/n183-p125",
    "ever_same": false,
    "statuses": {}
  },
  {
    "action_id": "feeding_001201_001906/F693/n197-p167",
    "ever_same": false,
    "statuses": {}
  }
]

“occupied”保持一对一约束。OCCUPIED_REFERENCE_REVIEW.json另核当前占用观测；有同物理旧anchor也不能直接把两个现有mask写成同一public ID，不能把占用问题简化为放宽门槛。

## 混层、背景与质量

{
  "WRONG": {
    "current": {
      "core_n": {
        "n": 17,
        "median": 152.0,
        "min": 29,
        "max": 214
      },
      "core_scale_mm": {
        "n": 17,
        "median": 15.0,
        "min": 15.0,
        "max": 33.17625168457031
      },
      "whole_core_gap_mm": {
        "n": 17,
        "median": 13.5572509765625,
        "min": 0.61669921875,
        "max": 40.6339111328125
      },
      "patch_median_range_mm": {
        "n": 17,
        "median": 21.562255859375,
        "min": 5.127197265625,
        "max": 362.0885009765625
      },
      "supported": 16
    },
    "selected_reference": {
      "core_n": {
        "n": 17,
        "median": 168.0,
        "min": 124,
        "max": 260
      },
      "core_scale_mm": {
        "n": 17,
        "median": 18.647785180664062,
        "min": 15.0,
        "max": 38.812104382324215
      },
      "whole_core_gap_mm": {
        "n": 17,
        "median": 14.84405517578125,
        "min": 3.94696044921875,
        "max": 43.05828857421875
      },
      "patch_median_range_mm": {
        "n": 17,
        "median": 25.365966796875,
        "min": 10.08734130859375,
        "max": 68.73272705078125
      },
      "supported": 17
    }
  },
  "CORRECT": {
    "current": {
      "core_n": {
        "n": 8,
        "median": 164.0,
        "min": 90,
        "max": 259
      },
      "core_scale_mm": {
        "n": 8,
        "median": 23.482840228271485,
        "min": 15.0,
        "max": 37.22951213378906
      },
      "whole_core_gap_mm": {
        "n": 8,
        "median": 12.118560791015625,
        "min": 2.40411376953125,
        "max": 26.2852783203125
      },
      "patch_median_range_mm": {
        "n": 8,
        "median": 35.8843994140625,
        "min": 11.89947509765625,
        "max": 168.11798095703125
      },
      "supported": 8
    },
    "selected_reference": {
      "core_n": {
        "n": 8,
        "median": 164.0,
        "min": 156,
        "max": 211
      },
      "core_scale_mm": {
        "n": 8,
        "median": 19.045310925292966,
        "min": 15.0,
        "max": 44.60197229003906
      },
      "whole_core_gap_mm": {
        "n": 8,
        "median": 13.6510009765625,
        "min": 2.1212158203125,
        "max": 57.3353271484375
      },
      "patch_median_range_mm": {
        "n": 8,
        "median": 27.072235107421875,
        "min": 0.8753662109375,
        "max": 78.8045654296875
      },
      "supported": 8
    }
  },
  "UNSCORABLE": {
    "current": {
      "core_n": {
        "n": 2,
        "median": 45.5,
        "min": 30,
        "max": 61
      },
      "core_scale_mm": {
        "n": 2,
        "median": 17.11712777709961,
        "min": 15.0,
        "max": 19.23425555419922
      },
      "whole_core_gap_mm": {
        "n": 2,
        "median": 174.22247314453125,
        "min": 3.7149658203125,
        "max": 344.72998046875
      },
      "patch_median_range_mm": {
        "n": 2,
        "median": 186.6964569091797,
        "min": 10.26470947265625,
        "max": 363.1282043457031
      },
      "supported": 2
    },
    "selected_reference": {
      "core_n": {
        "n": 2,
        "median": 49.5,
        "min": 30,
        "max": 69
      },
      "core_scale_mm": {
        "n": 2,
        "median": 19.894294885253906,
        "min": 16.897694604492187,
        "max": 22.890895166015625
      },
      "whole_core_gap_mm": {
        "n": 2,
        "median": 7.43548583984375,
        "min": 2.3568115234375,
        "max": 12.51416015625
      },
      "patch_median_range_mm": {
        "n": 2,
        "median": 285.9869689941406,
        "min": 230.8385009765625,
        "max": 341.13543701171875
      },
      "supported": 2
    }
  }
}

这些量来自去重独立原始测量。whole/core和几何分区差只证明掩码内深度不均匀，不能区分鱼体倾斜、背景混入或上下鱼混合。原始depth的视角、配准误差与水下物理标定仍未知；当前core支持不能认证真实身体表面。

## 相对次序不能借用无关见证

全bank共有65条同版本、连续质量合格的次序比较，1244条UNKNOWN。但27条实际选中边的合格见证总数是0：不能把65条旧bank上的代理比较算成真实错误动作可被否决的证据。选择性放宽到命中也不能证明上下关系稳定。

## 性能和下一步边界

本轮只有原Z4Q逐帧一致的诊断回放，没有新跟踪策略或新指标涨跌。5项检查、实际入口/85条矩阵边与锚点核验、235个深度时刻/6289个观测、2019个分布比较、1309个次序记录均已保留。27张公开统计图和27组真实私有前后图覆盖全部提交。

下一步单一计划见NEXT_STEP.md；不在这批曝光错误上滚动找阈值，不自动启动下一实验。

## 原输入ROI补充核验与来源边界

主统计图使用DS36自适应core，与原Z4Q profiles固定腐蚀core不同。LEGACY_ROI_SUPPLEMENT_SEALED另封存原ROI：235时刻/6289观测的whole/core area/n/fraction/median/MAD/q25/q75逐列严格等于旧输入，原像素人口和独立去重人口分列。补充是在GT已曝光后的量测验真，不把其统计拼成新的盲输入或新成绩。原core下过滤前仍是12次无正确列、4次其他身份更近、1次正确最小，全部固定列保留。

错误当前原core样本数不足16的四例是F159、F897、F1404、F1751；不能把扩大ROI后的16/17测量支持率当成原core支持率。其他错误即使原core有足够有效点，深度接近也未证明同一身份。

source generation来自可见性连续性，epoch来自原Bridge；没有完整生产者reset元数据，不能认证一个连续native内部从未换鱼。REFERENCE_MATCHES不可评分的旧参考不能当成已证实不存在正确鱼，所以候选计数表的“正确”是可评分SAME定义。F468、F1681的同物理旧bank已被当前另一物理观测占用，事后只发现问题，不用GT释放占用或改动作。

最终真实图是FIXED_SCALE_PRIVATE_VISUALS：统一900–1400mm显示、洋红表示缺失；低值黑色不等于缺失。27组固定前后图与8张全案例联系图只在private中；17错误、8正确、2不可评分全部保留。公开27张自适应core统计SVG，像素、真实人口数组、凭据和GT raster未上传。

唯一下一步是NEXT_STEP.md的D1共同竞争门控试验，目前尚未启动；不等于推荐无条件放宽历史、深度或占用门槛。
