# Actual-pixel visual QA boundary

Before formal scoring, Work opened the **actual old sent** grayscale G006 and G007 PNG bytes (SHA-256 `f7a903f98bdc8c1ff18b9281edc6cab37d3dfcee89fb1db308f839a7222f9101`, 12,432 bytes; `d989683d867e891921cc4a14b36e2eb1c42deddd23b09a55e9564b6f2a4266fe`, 12,319 bytes). They show six gray predicted contours per frame with local `f006:` / `f007:` labels on a white ROI, not persistent identity labels. This is a pixel check, not an identity judgment.

After **all** outputs were sealed and scored, Work opened two private `POSTHOC_NOT_SENT` panels made from actual G image bytes; these panels were never a model input:

| Panel | Actual visual comparison | Restricted server artifact |
| --- | --- | --- |
| P05-REPEAT `f010:o03` | The model, mask-IoU baseline and exposed unique GT all point to `f011:o03`; center distance points to `f011:o04`. Crowded overlapping silhouettes are visible. This is a true single-token center-baseline error, not an increment over mask-IoU. | `/home/xiongxiong/m3l_local_correspondence_20260926/private_visual/P05_REPEAT_f010_o03_POSTHOC.png`, 52,353 bytes, SHA-256 `cf290072398cc73467bbe8018616cb6ac3060a70eda6ae3dbcd9d1b6f3ed6bf7` |
| P08-FIRST `f013:o03` | The model abstains; N-C and N-I both force `f014:o03`, while posthoc GT has no unique source match. The crowded shapes are visible, but the image itself does not resolve the GT ambiguity. | `/home/xiongxiong/m3l_local_correspondence_20260926/private_visual/P08_FIRST_f013_o03_POSTHOC.png`, 56,806 bytes, SHA-256 `dafcae7bc27baf6402c7cda8b897c09a39d6c516611675d49c25c90a4aca9a30` |

The two panels were `VISUALLY_INSPECTED` locally at `C:/Users/19430/AppData/Local/Temp/m3l_visual_20260926/`, with matching bytes and hashes, and remain off Git. Only the four opened local files are claimed as manually inspected; the other sent G pixels were SHA/readability checked, **not** individually viewed by Work. The post-score panel uses exposed GT as a green audit overlay and cannot be treated as a deployable model rationale or independent blind adjudication. Valid token citations in other answers were machine-checked for sent image/token membership, but their claimed semantic visual continuity was not independently certified.
