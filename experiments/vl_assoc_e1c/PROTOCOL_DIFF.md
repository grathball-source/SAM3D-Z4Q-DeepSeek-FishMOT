# Old E1 versus E1C-A diagnostic path

| Component | Frozen old E1 | E1C-A diagnostic | Status |
| --- | --- | --- | --- |
| Query owner requirement | Both historical IDs currently owned (`event_probe.py:122-125`) | One owner may remain | Implemented in `probe.py`, prediction-only |
| Nonbaseline candidates | Current-owner swaps (`event_probe.py:47-58`) | Also native-to-missing-public-ID reattachment | Clone-stage tested; no true reachable recovery confirmed |
| Current temporal segment | Three sampled frames, no intervening continuity proof | Separate observation key and tracklet epoch in `contract.py` | Contract tested synthetically; no new real packet freeze |
| Applicability | Global field validated but ignored by old decoder (`e1_protocol.py:65-94`) | Cited evidence must be applicable for directional comparison | Synthetic contract tests only |
| Numeric N | Last history/current sample for D/A and final current point for M (`build_packets.py:66-89`) | Median over all clean causal samples, explicit null cost and missingness | Synthetic only; no real paired E1C model comparison |
| Visual evidence | Old source crops, no pixel IDs in response | New packet-local visual evidence location required | Not completed because A gate failed; old four harm sheets verified, not new pilot inputs |

The E1C-A probe exposed seven recovery events with **three** selected current tracklets (one owner plus two alternatives), violating the specified maximum of two. Its frozen output is retained as an engineering failure, not silently rewritten or treated as an approved candidate protocol. Four of the six executable recovery events are within the cap; no confirmed correct recovery exists even in the broader diagnostic output. No prompt, three-vote gate, five-frame rule or episode budget was loosened in the old experiment.
