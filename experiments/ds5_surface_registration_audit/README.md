# DS5 surface / spatial registration audit

Read PLAN.md and CONFIG.json first. This is an exposed observational diagnosis,
not a new depth extractor, physical label set or tracker trial. Reuses sealed
DS4 F2/F6 samples over 1066 frames / 28382 original masks, preserving UNKNOWN.
Current RGB/manual RGB contours are local diagnostic evidence only.

Interpreter: E:/researchsoftware/anaconda3/envs/D-MOT/python.exe.
Existing NumPy/OpenCV/SciPy/Matplotlib/pycocotools, one native math thread, no GPU.
Run checks.py, audit.py, report.py sequentially. All outputs refuse overwrite.
Three independently produced *_REVIEW.json files are required before freeze.
Use a fresh sibling checkout/output copy for regeneration; retain original
parent-relative DS1–DS4 dependency layout and source paths listed in inventories.
Never delete old seals or run again inside this completed directory.

audit.py freezes original sources/cohort/code, computes full selected-point
connectivity census, fixed 49-cell coordinate sensitivity and same-native-point
SO3 projection sensitivity. No original sample values/coordinates or masks are
changed. report.py verifies seals/old locks before post-audit summarization.
Boundary and RGB occupancy are geometry proxies, never measured surface truth.
No LLM/VLM/API/key, training, SAM3 inference, restoration or tracking is used.

Private QA RGB/depth images and all raster dependencies remain outside Git.
Final restricted inventory records paths, bytes, SHA and reproduction dependencies.
Public census contains per-object numerical statistics only. Main delivery and
remote proof are appended after execution, without changing frozen files.
