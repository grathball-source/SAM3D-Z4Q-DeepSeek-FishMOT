# DS18 immutable record copy profile

**11.2x refers only to synthetic `copy.deepcopy(engine)`, not whole-experiment speed.**

## Measurements

| Store | Before seconds/copy | After seconds/copy |
|---|---:|---:|
| engine | 0.167788138 | 0.014925237 |
| bank | 0.008607513 | 0.009690962 |
| view_bank | 0.002303850 | 0.002742200 |
| reference_bindings | 0.018857238 | 0.001815300 |
| depth_history_bindings | 0.095635725 | 0.001158712 |
| ema_evidence | 0.005198763 | 0.000060987 |
| source_activity | 0.032220262 | 0.000060800 |
| pending_birth | 0.000002388 | 0.000001750 |
| certificates | 0.000005050 | 0.000004525 |

## Exact scope and procedure

Generate three masked depth objects (1, 2, 9) on a 64x200 plane, warm the real controller for 50 generated frames, then copy one source fact table to keys 20-119 to create a 103-object bank shape with 15 historical contributions each. Retain original source labels. The expanded engine is a storage-shape benchmark and was never stepped or scored.

Copy each listed store eight times, then the full engine eight times. Report mean time.perf_counter elapsed seconds, with one process per revision. JSON contains the exact reproduction program, interpreter, cwd and tool output identifiers. No dataset pixels, GT or API was used.

Only past reference/whole-history/EMA/received-observation fact values become readonly. Their outer maps and bank/view_bank/alias/pending/source_versions/identity_versions remain mutable and independently cloned. No scientific values, candidates or thresholds change.

## Source provenance

- controller.py: 42385 bytes; SHA256 `966ddf22e4ac41fccd3105b1d49036c666ee0a0de074541152c126c2e96c3d1a`.
- test_controller.py: 17122 bytes; SHA256 `05b59e50a8f31f017a77f2d98c117b755745bf7da3909f0d6d8e03029e32e7bb`.
- mixed_depth.py: 16681 bytes; SHA256 `12b7564afb69690dd85be60c2af88744c784e97d62ad5dcbacbb9c2458abfbb7`.

Before controller: 42289 bytes, SHA256 `d195bdc2f29e47ab0f7a675c6589ec603785b783f46dcaef4433a29e1f238365`. Reversing only four readonly-record wrappers from current source bytes while preserving CRLF reproduces this exact digest. Before test_controller SHA is `bc2cc34c684f2d828a60d56bd98b43dfb75367986a07ce4178e5c17e59502342`; adjacent source proof is CHECKS_R4. The copy benchmark did not capture its mixed_depth runtime digest, so the adjacent review is not presented as in-process evidence.

Before output: tool chunk 2771fe; after: 67f8c6; both exited 0. This report only saves those existing measurements; no additional benchmark, test, prediction or evaluation was run.

## Interpretation limits

Depth history and received-observation facts dominated copying in this generated state. Mean engine copy fell from 0.167788 to 0.014925 seconds. Complete data replay also includes I/O, depth measurement, source signatures, serialization and scoring; this profile does not claim 11.2x acceleration of any complete experiment. Eight repeated copies do not support a confidence interval or cross-scene performance claim.
