# PX-A main sync verification — 2026-09-29

The experiment's 50 public files were committed as `8c726cd3b560c46252c5d08dba0c969cc3c90baa` and pushed non-force from review base `85f71d854f8d9b0bcc6d7bf1d200d1a01dd8de08`. `git fetch origin main` followed by `git ls-remote origin refs/heads/main`, local `HEAD`, and fetched `origin/main` all returned `8c726cd3b560c46252c5d08dba0c969cc3c90baa` at this verification point. The working tree was clean.

Fetched `origin/main:<path>` blob IDs were compared to hashes of the local files and all matched:

| Key file | Remote/local Git blob |
| --- | --- |
| `FINAL_REVIEW.md` | `0f908c571b8e5739dd3dcf75656a67426ad110b7` |
| `public/METRICS.json` | `361c1cd58a901e920dbeaeaa17fd98ff198b75a6` |
| `public/SOURCE_AUDIT.json` | `ac54f842c023ec386433b4fa5215fde9ac78e8d6` |
| `public/SOURCE_OLD/feeding_000000_000199/SEAL.json` | `e7989b8bf506335734981a2ee7dff6ccf5ab1739` |
| `source/co_visibility_exclusion.py` | `917fd4843971d95cfd81020d762397ac986e8fad` |
| `research/HANDOFF.md` | `04f3c85ad7d509eb6210586237ded96738b82beb` |

This record is a documentation-only follow-up to the sealed result and changes no rule, prediction, metric, input or old artifact. The final remote `main` SHA after this record is delivered is verified separately in the task response.
