"""Real-slice-discovered empty assessment has no modality weights; retain authority."""
from common import *
from association import gate,choose
assert not gate(dict(scores=[]))['eligible']
e=dict(q=3,suspect_frame=2,post_roles={10:[],20:[]},public_ids=[1,2])
d=choose(e,{'A':dict(samples=[]),'B':dict(samples=[])},{},True)
assert d['choice']=='DEFER' and d['mapping'] is None and d['original_evidence_reason']=='NO_PRE_HISTORY'
write_new(HERE/'CHECKS_EMPTY.json',dict(status='PASS',tests=2,empty_assessment_never_key_error_or_geometry_fallback=True,
    discovered_by_actual_development_slice=True,GT_opened=False,new_model_http=0,cost_usd=0))
