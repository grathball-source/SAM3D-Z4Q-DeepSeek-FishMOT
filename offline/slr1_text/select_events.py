"""Offline selection boundary only. Sorted IDs discard the pairing order."""
from common import *
def main():
 assert not (P/'SELECTORS.json').exists(),'selectors already sealed'
 p=STAGE/'E0_event_audit/EVENTS_gap15.json'
 expected=read(STAGE/'FINAL_ACCEPTANCE.json')['hashes']['E0_event_audit/EVENTS_gap15.json']
 assert sha(p)==expected
 source=read(p)
 events=[e for e in source if e['eligible'] and e['merge_frames']]
 events.sort(key=lambda e:(e['split'],e['interaction_start'],sorted(e['pre_native_ids'])))
 selected=[]
 for i,e in enumerate(events):
  assert e['last_independent_frame']<e['merge_start']<=e['merge_end']<e['split_first_frame']
  selected.append(dict(key=alias('E',i),split=e['split'],pre=e['last_independent_frame'],
   historical_native_ids=sorted(e['pre_native_ids']),query_frames=[e['merge_start'],e['split_first_frame']]))
 assert len(selected)==18
 save(P/'SELECTORS.json',selected)
 save(P/'SELECTION_ACCEPTANCE.json',dict(at=now(),exit_code=0,count=18,source_sha256=expected,
  selectors_sha256=sha(P/'SELECTORS.json'),oracle_selection=True,GT_pairing_exported=False,
  fields=list(selected[0]),notes='Selection process sees offline E0; downstream reads only whitelist fields. Entire task is not blinded.'))
 print('18 fixed selectors sealed; GT correspondence excluded.',flush=True)
if __name__=='__main__':main()
