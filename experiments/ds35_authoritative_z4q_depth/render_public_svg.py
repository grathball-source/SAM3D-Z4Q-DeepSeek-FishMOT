"""Postseal inspection render only; no changes to science, scores or public SVGs."""
from common import *
from datetime import datetime, timezone
from PIL import Image
import subprocess, tempfile

edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
assert edge.is_file()
pins = {Path(p['path']).name: p for p in read(HERE/'PUBLIC_VISUALS.json')['figures']}
destination = HERE/'private/svg_inspection'
destination.mkdir(parents=True, exist_ok=False)
rendered = []
for source_name, target_name, width, height in [
    ('FULL_METRICS.svg', 'FULL_METRICS.png', 1280, 1100),
    ('EVENT_TIMELINE.svg', 'EVENT_TIMELINE_TOP.png', 1700, 1000),
]:
    pin = pins[source_name]
    verify_item(pin)
    output = destination/target_name
    with tempfile.TemporaryDirectory(prefix='ds35_edge_', dir=destination) as temporary:
        # Temporary cleanup is restricted to this newly created renderer directory.
        assert Path(temporary).resolve().is_relative_to(destination.resolve())
        command = [str(edge), '--headless', '--disable-gpu', '--no-first-run',
            '--disable-background-networking', '--disable-extensions', '--hide-scrollbars',
            '--user-data-dir='+temporary, f'--window-size={width},{height}',
            '--screenshot='+str(output), Path(pin['path']).as_uri()]
        completed = subprocess.run(command, capture_output=True, timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW)
        assert completed.returncode == 0 and output.is_file(), completed.stderr[-2000:]
        with Image.open(output) as picture:
            dimensions = list(picture.size)
        rendered.append(dict(source=pin, output=artifact(output), dimensions=dimensions,
            renderer=artifact(edge), command=command, exit_code=completed.returncode,
            stderr_sha256=hashlib.sha256(completed.stderr).hexdigest()))
write_new(HERE/'SVG_RENDER_RECORD.json', dict(status='RENDERED_FOR_ACTUAL_LOCAL_INSPECTION',
    created_utc=datetime.now(timezone.utc).isoformat(), rendered=rendered,
    public_svg_unchanged=True, predictions_and_scores_unchanged=True,
    new_model_http=0, cost_usd=0))
print('Public SVG inspection rasters ready', len(rendered), flush=True)
