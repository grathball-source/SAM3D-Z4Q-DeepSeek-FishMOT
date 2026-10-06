"""Record actual postseal visual inspection; this does not certify tracking accuracy."""
from common import *
from PIL import Image
from datetime import datetime, timezone

first = read(HERE/'PRIVATE_VISUALS_INVENTORY.json')
extra = read(HERE/'POSTSEAL_EXTRA_PRIVATE_VISUALS.json')
inspected = [
    'private/visuals/feeding_000351_000555_MS1-F12_EVENT_RGB.png',
    'private/visuals/fishsa_development_8400_MS1-F1152_EVENT_RGB.png',
    'private/visuals/L3_MS1-F126_EVENT_RGB.png',
    'private/visuals/LW_MS1-F218_EVENT_RGB.png',
    'private/postseal_extra_cases/fishsa_development_8400_MS1-F3863_EVENT_RGBD.png',
    'private/postseal_extra_cases/fishsa_validation_2888_MS1-F2681_EVENT_RGBD.png',
    'private/svg_inspection/FULL_METRICS.png',
    'private/svg_inspection/EVENT_TIMELINE_TOP.png',
]
details = []
for relative in inspected:
    path = HERE/relative
    with Image.open(path) as picture:
        details.append(dict(artifact(path), dimensions=list(picture.size)))
for pin in read(HERE/'PUBLIC_VISUALS.json')['figures']:
    verify_item(pin)
write_new(HERE/'VISUAL_ACCEPTANCE.json', dict(
    status='PASS_ACTUAL_LOCAL_VISUAL_INSPECTION', inspected_utc=datetime.now(timezone.utc).isoformat(),
    manual_display='Actual view_image original contact sheets; installed Edge headless rendered the delivered SVGs.',
    inspected=details, inspection_scope='Six representative actual-source sheets plus full metrics and top of event timeline; not every image manually inspected.',
    observations=[
        'Actual Native/Z4Q/RGB/RGBD rows use the same acquired RGB, raw depth and original masks; overlays show published native-to-public mappings.',
        'Unknown pre-reference remains explicitly UNKNOWN; no-split L3 displays an empty UNKNOWN q panel.',
        'Feeding shows crowded masks and missing raw depth; raw depth holes and overlapping contours remain visible.',
        'Development q3902 and validation q2689 show the reported identity divergence between Z4Q and both event branches.',
        'All five numeric metric blocks and their negative/zero differences are legible; L3/LW weak-reference label is visible.',
        'Event timeline preserves no-q, fallback, DEFER and WRONG; only its top portion was raster-inspected.'
    ], first_source_inventory=artifact(HERE/'PRIVATE_VISUALS_INVENTORY.json'),
    extra_failure_inventory=artifact(HERE/'POSTSEAL_EXTRA_PRIVATE_VISUALS.json'),
    public_figures=artifact(HERE/'PUBLIC_VISUALS.json'), metrics=artifact(RUN/'METRICS.json'),
    helper=artifact(__file__), private_pixels_not_for_git=True,
    image_inspection_is_not_physical_identity_ground_truth=True, new_model_http=0, cost_usd=0))
print('Actual postseal visual inspection recorded', len(inspected), flush=True)
