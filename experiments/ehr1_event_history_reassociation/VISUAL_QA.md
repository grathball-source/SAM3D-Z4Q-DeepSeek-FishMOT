# Answer-exposed private input QA

Four actual B01 old M2-T fixed-ROI grayscale predicted-mask PNGs were downloaded only to `C:/Users/19430/Downloads/ehr1_private_qa/` and opened before formal requests: G006 at frame 1300, G010 near the contact window, G017 later in the interaction, and G034 at q. They visibly contain distinct frame-local mask tokens, multiple fish and changing adjacency. This confirms actual private pixels existed and were viewed; it is **not** an independent identity adjudication because the reviewer knew the older exposed B01 outcome. The sample was used to check input representation, never to pick a candidate, trigger, model response or score.

| Private file | Bytes | SHA-256 |
| --- | ---: | --- |
| `B01_G006.png` | 12432 | `f7a903f98bdc8c1ff18b9281edc6cab37d3dfcee89fb1db308f839a7222f9101` |
| `B01_G010.png` | 12733 | `640b9dbf52a8d35c4c2f4fc4c3502ddbd735e6d7b73a890092777f5030692210` |
| `B01_G017.png` | 13059 | `21afc4500839fca13c9ad5c6bf7976f06a526e0792b88e070fc05fbf10cc23da` |
| `B01_G034.png` | 12453 | `7a4e70ba72f22aec265d68d256c6e2bc6a1baf92c1ffa2e4b9c7a9426cdddbc7` |

The pixels are not in Git. Exact remote path/bytes/hash inventory for all 181 copied G PNGs is in `ARTIFACT_MANIFEST.json`.
