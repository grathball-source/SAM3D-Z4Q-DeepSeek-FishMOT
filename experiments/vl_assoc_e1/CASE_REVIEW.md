# Case review without E1 GT or model responses

- `P175d295a01799fe5` (validation query 2638): B0 C2, active N C1, and D/A/M-only each C1. This is the sole selected event where combined N differs from B0; it proves the numerical comparator can act, not that C1 is correct. The real temporal RGB sheet was visually examined. Blue lighting, nearby fish and predicted-mask dependence make visual association uncertain. L-T/V outputs and independent GT are pending.
- `P04c303d9612421d6` (validation query 377): B0 and N both C2, but M-only C1. The inspected sheet shows genuine fish, nearby animals and elongated crops with white padding. This is a possible appearance/geometry failure mode, not a scored success or failure; the model arms and GT are pending.
- `P188c6571ae22ff20` (validation query 2841): one historical node has no clean causal reference. The empty sample list is retained rather than replaced with a constant or later frame. This packet can still be staged and sent, but missing evidence may make its comparison unobservable. It is retained in all denominators.
- Historical `R000010`: the saved old request contained a null historical depth anchor despite a non-null depth value. The R0 repair cites the actual D1 bank source; the old response is not reused as if it answered the new provenance input. Old B0 remains byte-for-byte equivalent across 2888 rows.

No case is labeled E1 correct/incorrect, since no E1 decision seal exists and E1 GT has not been opened. The original historical TrackEval scores are distinct from this offline candidate-choice question.
