# DS19 交付前只读工程审查

审查时间：2026-10-03 08:26–08:32 UTC。正式八段六分支运行期间完成；本记录是工程观察，不能代替最终完整性、评分或远端验收。

## 审查边界

- 不修改冻结的代码、配置、请求结构、前缀检查或旧封存产物；只新增本记录。
- 不读取 GT、GT raster、性能指标或未关闭的 GZ；不新增资格测试、不重跑预测。
- 文件体积检查仅做当时文件系统快照。结构检查只读取已有前缀工程记录，以及先通过 `PREDICTIONS_SEALED.json` SHA 绑定的已完成公共文件。

## 冻结与旧封存

| 检查 | 实际范围 | 观察 |
| --- | --- | --- |
| 旧封存 SHA | `OLD_READONLY_LOCK.json` 所列旧文件中 207 个 seal 命名 JSON，排除 metric 路径 | 0 个改变 |
| 本轮科学依赖 | L3 `FREEZE.json` 的 82 个代码/依赖哈希 | 0 个改变 |
| 工程检查来源 | CHECKS / CACHE_CHECKS / PREFIX_CHECKS / REAL_PREFIX_SOURCE_CHECKS 的来源绑定，分别 6 / 5 / 5 / 5 个哈希 | 均与当前文件一致 |
| 旧 tracked 差异 | 当时 `git diff --name-only` | 只有 `.gitignore`；DS19 是新目录 |

旧只读锁共列 5,618 个 tracked 文件；本次未声称独立重算全部 5,618 项。全部旧锁、所有新 seal 和最终公开清单仍由完成后的 finalizer 逐项核验。

## 控制关闭与发布链证据

`PREFIX_CHECKS.json` 覆盖 L3 3,030 帧、FishSA 开发 3,970 帧、FishSA 验证 2,250 帧、Feeding 0–199 的 200 帧，共 9,450 个工程前缀帧。

- SAM3_NATIVE、Z4Q_FROZEN、ACTIVITY_ORDER、MIXED_ORDER 对 DS18 的逐帧发布 parity 记录完整；来源与帧号对齐。
- 六分支都保留全部 native mask token，同帧 public ID 一对一。
- 已设置 q 的事件，`evidence_cutoff_frame == q`，首 post 观测帧等于 q。
- `REAL_PREFIX_SOURCE_CHECKS.json` 四项 source→自然候选→commit→唯一 publisher 独立绑定均 PASS，预测/ledger/order/birth/transaction 绑定均真，`GT_read=false`。
- 此处 L3 的两个来源提交只代表两个 RETURN 分支各一次真实工程提交，不代表物理恢复正确或性能提升。

## 像素、RLE 与编码内容检查

结构级检查完成于 08:30:30 UTC。共检查 43 个 JSON / JSONL / GZ 文件：四个本轮工程检查 JSON，以及当时已封存的 Feeding 0–199、Feeding 351–555、FishSA 验证 2,888 帧各 13 个非评分公共文件。正式文件在解析前均与 seal SHA 一致，0 个 SHA 阻断。

检查递归键名、字符串和数值列表形态，不只依据扩展名；没有发现 RLE `counts`、图像 base64、二维稠密像素矩阵或公开 depth/mask/RGB raster。

`PREFIX_CHECKS.json` 的关键内容：

- `pre_geometry_history` 保存中心、bbox、面积、邻居、时间/版本，以及 whole/core 深度的标量分布和质量摘要；没有像素数组。
- 296 个 `mask` 与 4,162 个 `mask_token` 字段全部为 `n:<native>` 符号引用。
- 4,162 个 `selected_pixel_binding` 仅包含 `dtype`、`shape`、`sha256`，没有被选择的像素值或坐标列表。
- 检出的长度超过 64 的数值列表均为 `group_frames` 帧号序列。

完成片段的命中项是 `sample_counts` 统计、`overlap_pixels` 计数、`valid_pixels` 计数、`RGB_read`/`no_RGB` 布尔及 `selected_pixel_binding` 摘要；不是 RLE、RGB 或深度像素。`MIXED_DEPTH.jsonl.gz` 是完整 DS18 缓存的封存外部引用，不复制像素数组。

这次结构审查没有读取还在写入的 L3、LW、FishSA 开发及另外两个 Feeding 段的 GZ。全段完成后必须对最终公共产物重新检查；后续真实 mask/depth 可视化应留在受限目录。

## 凭据、体积与交付实现

- 非 run 公共代码/JSON/文本的凭据、Bearer、API key、provider file ID 字面模式扫描无命中。此为有限模式检查，不是对任意编码秘密的形式证明。
- 文件快照中有 146 个非 private/slice/__pycache__ 公共候选，没有常见 raster/media 扩展产物，也没有单文件达到 100 MiB。
- 最大稳定公共文件是 `PREFIX_CHECKS.json`：47,851,796 bytes，SHA256 `04b88d39fd78993f0e9a10fdbb1b59b1661c4c16e2102d44e00c31b7b0ff2080`。
- `TRANSACTIONS` 已在正式冻结前采用压缩分块，目标约 70 MiB；检查在每行写入后发生，理论上可能有一行的超额，最终仍需实际核单文件大小。
- `.gitignore` 明确排除本轮 `private/` 和 `slice*/`；publisher 公开输出仅是 public ID 与 native mask token。
- 已读取 delivery finalizer 和远端核验实现：最终清单绑定公开 bytes/SHA，staging 校验 Git index 内容并排除受限目录；远端流程读取实际 ref 与每个必要文件，不能以本记录代替 push 或远端成功。

## 尚待完成后的验收

等待八段全部预测封存后，核验全部新封存、旧只读锁、最终公开文件内容及大小；完成独立评分、受限产物真实路径/bytes/SHA 清单、公开清单、暂存内容和实际 origin/main 核验。本轮科学版本与已有 seal 保持原样。
