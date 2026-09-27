# 事后复盘执行记录（2026-09-27）

## 范围与环境

- 审查起点：`4bc02d737250907515d527642b6af73f80832f7d`，原 `main` 工作区干净。旧 `experiments/direct_history_replay/public/` 及其响应、预测、seal、ledger、指标只读。
- 新目录：本仓库 `experiments/direct_history_replay/posthoc/`；实验室服务器独立目录 `/home/xiongxiong/direct_history_posthoc_20260927`，原评分目录 `/home/xiongxiong/direct_history_replay_20260927` 只读。
- 本地解释器：`E:\CAU\D-MOT\tools\X-AnyLabeling\runtime\Scripts\python.exe`，Python 3.12.14。服务器解释器：`/home/data2/xiongxiong/dmot-annotation/env/bin/python`，原 TrackEval 固定路径由 `online/closed_loop_2888/score.py` 指定。
- 作业前实时检查：主机 `ps-ESC8000-G4`、用户 `xiongxiong`；`/home` 余量 56 GB、可用内存约 45 GiB；核对了八张卡实时状态。本轮全部 CPU，只读 GT 评分，不占用 GPU；`CUDA_VISIBLE_DEVICES=`，OMP/OpenBLAS/MKL 各 1 线程。发现另一个已有 Screen 会话，未接管或停止。没有环境安装、服务重启或清理旧产物。
- 模型 HTTP **0**，新费用 **USD 0**；没有使用旧预算或 API key。

## 顺序与核验

1. 本地先验证旧预测 seal 和原观测/深度 SHA，再运行 `replay_b03_only.py`。第 377 帧用原 B03 `{1:5,5:1}` 经 `Bridge.stage`/`commit_once`，B04 不执行。`no_truth` 审计钩拒绝读取评分/GT 路径。退出码 0；前 2,637 帧与原 B1 精确相同，全部 2,888 帧掩码相同，B04 后 251 帧 ID 不同。新预测封存 SHA-256 `d32ac30845a57fbdf5399fc435c071517e11dda47d2bfece778378011cee38e6`，seal SHA-256 `dea4866dfaa4e7f2b84d48658ad1e963e8428e276b6132b6df1a5d6615d1d6d9`。
2. 使用 SSH 主机密钥检查和现有专用密钥路径，把新预测、seal、`EVENTS.json`、`score_ablation.py` 复制到独立服务器目录。逐项核对本地/服务器 SHA。原远端 scorer SHA-256 `6cb2b7e438e2e98367b86f39e36ac220f90a6036c3f522b0558cec9123a8d811`，原预测 `33b0f11d07502ce8a256426a32cfcf7b5500c9a6e43171ea1b88feddcc50d671`，原指标 `9da9a8c36a9b03e1b7546666d64437af4e6c80f0fefa1228ca3a2c910cd07371`。
3. `score_ablation.py` 先检查新旧预测 seal、事件 SHA、原 scorer SHA 及 assignments/truth/matches 的固定 SHA，再读取 GT。服务器运行退出码 0；B0/B1 七项官方指标均与旧 `METRICS.json` 在 `1e-8` 内一致，三个分支和三个窗口完整输出。TrackEval 导入时提示可选 BURST 模块缺 `tabulate`；原 CLEAR/Identity/HOTA 路径正常执行，与旧指标完全复现。远端与下载后的 `COUNTERFACTUAL_METRICS.json` SHA-256 均为 `fa02136ddd84c8cb2b5471d16946aeab9f991ec42f89f00243d5af69c36a1c43`。
4. `matched_id_counts.py` 再次核对双预测 seal 和 matches SHA，服务器退出码 0，窗口帧数为 376/2261/251；`MATCHED_ID_COUNTS.json` 服务器与本地 SHA-256 均为 `6789a064a815f6301a52b528211fb3aae97ddb51afcfd0a63fe05a36833d10ba`。只输出按公开 ID/物理 ID 汇总的匹配次数，不输出 GT raster。
5. 本地 `audit_claims.py` 把四个实际请求中的 H1/H2 映射、端点测量和原回答绑定到评分后紧凑 GT 结果。断言 B03/B01/B04 局部解释错、B05 对；逐帧断言中窗 `1↔5` 和尾窗 `4↔5` 的置换关系。退出码 0；`CLAIM_AND_MAPPING_AUDIT.json` SHA-256 `294c120926421980b937a34371277ed9e380798cdf6630bb1c09d7bf79993659`。

服务器评分命令（已执行，且输出已下载校验）：

```sh
cd /home/xiongxiong/direct_history_posthoc_20260927
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/data2/xiongxiong/dmot-annotation/env/bin/python score_ablation.py \
  --old /home/xiongxiong/direct_history_replay_20260927/public \
  --scorer /home/xiongxiong/direct_history_replay_20260927/original_score.py
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/data2/xiongxiong/dmot-annotation/env/bin/python matched_id_counts.py \
  --old /home/xiongxiong/direct_history_replay_20260927/public \
  --matches /home/xiongxiong/dmot-experiments/sam3_depth_return_guard_20260918/experiment/offline_matches_validation.jsonl.gz
```

输入 SHA（沿用原实验）：观测 `3fc24d623ca3af22520dc7333ba07ad1479bc766425a2c548b1a13aa922a2e87`，特征 `91a154246748146896ac846f0bdd934bb67be874fe823124263650e88ad62f0e`，assignments `ea468964e4b287a3879dfb83b304dd64c83f055e9649d3155fa62c41b717a0fc`，truth `55d88b7edae92c993c4ed0a4340307e696bf7cdbcf853c38cd805d9ec50b6057`，matches `5c557ab0dd833e00b4b0d3a6eeec3cdd6e0669f11da4f5e6611619fe5928cbd1`。后两者只在封存后由评分脚本读取。完整新文件大小与哈希见 `POSTHOC_MANIFEST.json`。

## 未执行事项

没有额外模型请求、调提示词、训练、DAA/E2、从 GT 挑案例或动作、未曝光测试集评估、B04 从 B0 独立启动的反事实。最后一项若今后需要，应作为另一个明确标注的分支实验，不能由本次顺序消融推断。
