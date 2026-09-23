# Causal episode registration

An episode begins at a newly observed pair of mutually neighboring native masks with two distinct B0 public identities. `sequence_id + pair + monotonic generation` is the unique event key. A pair cannot restart within six seconds; the generation increases only on a later new contact. History samples precede the trigger and do not use GT or future separation. The first separated B0-owner frame starts the 15-frame wait; renewed contact resets that wait. The query must occur within six seconds of the trigger. Events that expire or reach the split end remain in the audit.

The probe records generated whole-map swaps and their cloned stage outcomes before hash selection. This stage test is causal: it sees only the current preview and prior bank. Hash selection uses only events with at least one executable nonbaseline candidate. Every excluded event and reason remains in `EVENT_PROBE_V4_*.json`; selected episodes are in `EPISODES_*.jsonl`.
