# B01 visual source check

The executor copied restricted images from the authorized source host to a private local preview directory and opened B01 endpoint RGB crops at frames 1314 (new A), 1317 (new B), and 1498 (X/Y), plus anonymous mask-token images at frames 1323 and 1483. The boxes and token labels point to visible regions in the fixed ROI; the 1323/1483 drawings show multiple distinct frame-local masks. This is executor quality assurance on exposed material, not an independent identity judgment or GT evidence.

Restricted local preview copies: `C:/Users/19430/AppData/Local/Temp/ehr1r_b01_visual_20260926/`. Their bytes and SHA-256 are inventoried in `ARTIFACT_MANIFEST.json`; no pixels are committed.
