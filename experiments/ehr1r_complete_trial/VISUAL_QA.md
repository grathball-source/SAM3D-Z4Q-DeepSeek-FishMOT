# Restricted image QA, 2026-09-27

The executor opened **five** B01 images from this run's 55 sealed source images. The 1314 A and 1317 B endpoint boxes cover visible fish regions in their fixed ROI; the 1498 X/Y endpoint boxes mark two visible regions. The anonymous G010/1323 and G031/1483 drawings display six distinct frame-local tokens each. This is an image/token placement check, not a fish identity judgment or GT review. All 55 files were hash checked by the sender preparation and final body gate; the other 50 were **not** visually opened in this run.

Restricted preview copies remain outside Git under `C:/Users/19430/AppData/Local/Temp/ehr1rc_visual_20260927/`. Opened files, bytes, and SHA-256 are:

| Frame / image | Bytes | SHA-256 |
| --- | ---: | --- |
| 1314 / B01-F1314 | 130041 | `61b73fcb3fca4687da33fa53d5b601c91cd8fd0fd3361d73a93f555e4e39ffd1` |
| 1317 / B01-F1317 | 131006 | `034e72088d89836db836bd2db4fbdf5c17723cf2f8f15f8bb4e5abdb065cf1a3` |
| 1323 / G010 | 12733 | `640b9dbf52a8d35c4c2f4fc4c3502ddbd735e6d7b73a890092777f5030692210` |
| 1483 / G031 | 12031 | `2f31e0646d22feb04f522195d17e18a1c7bb199f42f3cefb28c38219315f96e2` |
| 1498 / B01-F1498 | 137166 | `b04d322b2b50aa70ba0633a67d6930a17f7d90a930960d9f3084fca4bc6cd559` |

Each digest was recomputed from the downloaded bytes and equals its sealed media filename. No pixels are in the public repository.
