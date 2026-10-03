# DS20 实际确认状态隔离核验

PASS_ACTUAL_PENDING_VERSION_ANCHOR_AND_PUBLICATION_ISOLATION

全部八段、两个新分支，共40196分支帧；检查的是实际提交后engine字典、精确版本/anchor与实际首次发布，不以自报布尔字段代替实值。

| 片段/分支 | 帧 | 实际独立确认记录 | 普通接受并发布 | 局部提交 | 帧间入口变化 |
|---|---:|---:|---:|---:|---:|
| feeding_000000_000199/ACTIVITY_ISOLATED | 200 | 1 | 2 | 0 | 0 |
| feeding_000000_000199/MIXED_ISOLATED | 200 | 0 | 2 | 0 | 0 |
| feeding_000351_000555/ACTIVITY_ISOLATED | 205 | 0 | 4 | 0 | 0 |
| feeding_000351_000555/MIXED_ISOLATED | 205 | 0 | 4 | 0 | 0 |
| feeding_000701_001060/ACTIVITY_ISOLATED | 360 | 0 | 6 | 0 | 0 |
| feeding_000701_001060/MIXED_ISOLATED | 360 | 0 | 5 | 0 | 0 |
| feeding_001201_001906/ACTIVITY_ISOLATED | 706 | 0 | 12 | 0 | 0 |
| feeding_001201_001906/MIXED_ISOLATED | 706 | 0 | 10 | 0 | 0 |
| fishsa_development_8400/ACTIVITY_ISOLATED | 8400 | 0 | 3 | 0 | 0 |
| fishsa_development_8400/MIXED_ISOLATED | 8400 | 0 | 3 | 0 | 0 |
| fishsa_validation_2888/ACTIVITY_ISOLATED | 2888 | 0 | 3 | 0 | 0 |
| fishsa_validation_2888/MIXED_ISOLATED | 2888 | 0 | 3 | 0 | 0 |
| L3/ACTIVITY_ISOLATED | 3710 | 7 | 9 | 1 | 0 |
| L3/MIXED_ISOLATED | 3710 | 7 | 8 | 1 | 0 |
| LW/ACTIVITY_ISOLATED | 3629 | 20 | 39 | 1 | 0 |
| LW/MIXED_ISOLATED | 3629 | 0 | 41 | 0 | 0 |

失效理由、全部实值来源和入口变化保存在CONFIRMATION_AUDIT.json。
显式事务只允许事件写集内变化；组外pending与发布精确等于同分支普通preview。全部非pending bank/alias内部字段仍由冻结原子validator和状态测试核验，本日志不伪造未保存的完整快照。
此PASS仅指确认隔离工程；物理正确性与完整性能在独立评分/结果报告分列。
