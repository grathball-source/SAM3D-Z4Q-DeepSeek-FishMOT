"""Record the root agent's actual local inspection, already performed via view_image."""
from common import *
from datetime import datetime, timezone

inventory = read(HERE/'PRIVATE_VISUALS.json')
contacts = read(HERE/'VISUAL_CONTACT_SHEETS.json')
assert len(inventory['cases']) == contacts['cases'] == 26
for entry in inventory['cases']:
    verify_item(entry['artifact'])
for pin in contacts['images']:
    verify_item(pin)
direct = [artifact(HERE/'private/cases'/f'{i:03d}.png') for i in (2,14,15,24)]
write_new(HERE/'VISUAL_ACCEPTANCE.json', dict(
    status='PASS_ACTUAL_LOCAL_VISUAL_INSPECTION', checked_utc=datetime.now(timezone.utc).isoformat(),
    all_26_cases_viewed_on_five_original_resolution_contact_sheets=contacts['images'],
    directly_viewed_original_resolution_cases=direct,
    actual_source_inventory=artifact(HERE/'PRIVATE_VISUALS.json'),
    observations=[
        'All three rows show actual Z4Q/WLS/LEVEL public identities on the same saved masks and raw depth; publication is identical as the sealed ledger states.',
        'Cases014/015 show actual F1422 reference n172→p126 and current F1465/F1466 n171→p171; edge veto did not produce a new persistent-ID restoration.',
        'Case002 shows native26→public16 first appears at global F159 in all three arms, retained as a wrong original action rather than hidden by the new branch.',
        'Some before columns show the whole actual frame because the target native mask is absent; no synthetic contour was added.',
        'Several target contours overlap raw-depth holes or background-like surfaces; visual inspection raises a purity risk, not a measured contamination fraction or certified body label.',
        'L3/LW cases remain UNSCORABLE; postseal display does not resolve missing physical reference.',
        'Colours use a separate 2–98 percentile range per frame crop; colour equality across columns is not equal depth. Numeric millimetres are in the bound facts/edge audit.',
        'The after column is postseal evidence only; no future frame entered the predictor or changed prior publication.'
    ], public_pixels_in_Git=False, RGB=False, GT_raster=False, result_only_code=artifact(__file__)))
print('ACTUAL_VISUAL_INSPECTION_RECORDED',26,flush=True)
