"""Record completed actual local image inspection; not identity ground truth."""
from common import *
from PIL import Image
from datetime import datetime,timezone

inspected=[
    'private/visuals/feeding_000351_000555_MS1-F12_DEPTH_OVERRIDE.png',
    'private/visuals/fishsa_development_8400_MS1-F3863_DEPTH_OVERRIDE.png',
    'private/visuals/fishsa_validation_2888_MS1-F2125_DEPTH_OVERRIDE.png',
    'private/visuals/fishsa_validation_2888_MS1-F2681_DEPTH_OVERRIDE.png',
    'private/visuals/L3_MS1-F126_DEPTH_OVERRIDE.png',
    'private/visuals/LW_MS1-F218_DEPTH_OVERRIDE.png',
    'private/postseal_depth_gate_cases/fishsa_development_8400_MS1-F7997_DEPTH_OVERRIDE.png',
    'private/postseal_depth_gate_cases/fishsa_validation_2888_MS1-F2584_DEPTH_OVERRIDE.png',
    'private/postseal_depth_gate_cases/LW_MS1-F2979_DEPTH_OVERRIDE.png',
    'private/postseal_depth_gate_cases/LW_MS1-F3101_DEPTH_OVERRIDE.png',
    'private/svg_inspection_v2/FULL_METRICS.png',
    'private/svg_inspection_v2/EVENT_TIMELINE_TOP.png']
details=[]
for name in inspected:
    path=HERE/name
    with Image.open(path) as picture:dimensions=list(picture.size)
    details.append(dict(artifact(path),dimensions=dimensions))
for pin in read(HERE/'PUBLIC_VISUALS.json')['figures']:verify_item(pin)
write_new(HERE/'VISUAL_ACCEPTANCE.json',dict(status='PASS_ACTUAL_LOCAL_VISUAL_INSPECTION',
    inspected_utc=datetime.now(timezone.utc).isoformat(),inspected=details,
    manual_display='Actual view_image contact sheets and installed Edge rendered delivered SVG files.',
    inspection_scope='Six source sheets, all four common-depth gate cases, full metric plot and top of timeline; '
        'not every source sheet or every timeline row manually inspected.',
    observations=[
        'Original Z4Q/depth-off/depth-override actual published rows remain equal. Raw masks and residual contours are retained.',
        'Development q3902 and validation q2188 original reconnections remain in the actual source panels and numeric first-publication records.',
        'UNKNOWN pre-reference labels remain UNKNOWN; a displayed old diagnostic anchor is not certified usable history. No-split L3 has an explicit empty UNKNOWN q panel.',
        'Crowded Feeding masks and missing raw depth remain visible; global color range is explicitly0..3000mm, not an estimated fish depth.',
        'Four common-depth gate cases show real pre/group/q/post context, not invented missing-body masks or certified physical identities.',
        'All five metric blocks show zero depth increment; Native/Z4Q differences, full IDSW/FP/FN and weak L3/LW reference label are legible.',
        'Timeline preserves no-q, missing evidence, DEFER and no-stage cases; only the top was raster inspected.'
    ],source_inventory=artifact(HERE/'PRIVATE_VISUALS_INVENTORY.json'),
    depth_gate_inventory=artifact(HERE/'POSTSEAL_DEPTH_GATE_PRIVATE_VISUALS.json'),
    public_figures=artifact(HERE/'PUBLIC_VISUALS.json'),renderer=artifact(HERE/'SVG_RENDER_RECORD_V2.json'),
    metrics=artifact(RUN/'METRICS.json'),helper=artifact(__file__),
    failed_async_renderer_log_preserved=True,private_pixels_not_for_git=True,
    image_inspection_is_not_physical_identity_ground_truth=True,new_model_http=0,cost_usd=0))
print('Actual local visual inspection recorded',len(inspected),flush=True)
