"""Minimal read-only E1C shared-edge grounding counterexample."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "vl_assoc_e1c"))
from contract import validate_response  # noqa: E402

packet = dict(schema="VL_ASSOC_RECOVERY_V1", packet_id="SHARED_EDGE_MINIMAL",
              snapshot_version=1, history=[dict(label="A"), dict(label="K")],
              candidates=[dict(id="C1", mapping={"X": "A", "Y": "K"}),
                          dict(id="C2", mapping={"X": "A", "Y": "B"})],
              evidence={"shared": dict(pair="A:X", applicable=True)})
response = dict(schema=packet["schema"], packet_id=packet["packet_id"],
                snapshot_version=1,
                comparisons=[dict(left="C1", right="C2", relation="LEFT_BETTER",
                                  evidence_ids=["shared"])])
formatted, grounded, reason = validate_response(packet, response)
assert (formatted, grounded, reason) == (True, True, "VALID")
assert packet["candidates"][0]["mapping"]["X"] == packet["candidates"][1]["mapping"]["X"]
result = dict(status="REPRODUCED_PRIOR_CONTRACT_DEFECT", accepted_as_grounded=grounded,
              cited_edge="A:X", changed_edge="Y:K versus Y:B", API_calls=0,
              note="Synthetic counterexample, not a new model failure; old decoder left unchanged.")
out = HERE / "PRIOR_CONTRACT_REGRESSION.json"
assert not out.exists()
out.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
