"""Wait for the installed Edge launcher's asynchronous local screenshot output."""
from common import *
from PIL import Image
from datetime import datetime,timezone
import subprocess,time

edge=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
pins={Path(p['path']).name:p for p in read(HERE/'PUBLIC_VISUALS.json')['figures']}
destination=HERE/'private/svg_inspection_v2'
destination.mkdir(parents=True,exist_ok=False)
rendered=[]
for source_name,target_name,width,height in [
    ('FULL_METRICS.svg','FULL_METRICS.png',1280,1100),
    ('EVENT_TIMELINE.svg','EVENT_TIMELINE_TOP.png',1700,1000)]:
    pin=pins[source_name];verify_item(pin)
    output=destination/target_name
    profile=destination/('profile_'+Path(source_name).stem)
    assert profile.resolve().is_relative_to(destination.resolve())
    command=[str(edge),'--headless','--disable-gpu','--no-first-run',
        '--disable-background-networking','--disable-extensions','--hide-scrollbars',
        '--user-data-dir='+str(profile),f'--window-size={width},{height}',
        '--screenshot='+str(output),Path(pin['path']).as_uri()]
    began=time.perf_counter()
    completed=subprocess.run(command,capture_output=True,timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW)
    assert completed.returncode==0,completed.stderr[-2000:]
    while time.perf_counter()-began<45:
        try:
            with Image.open(output) as picture:
                picture.load();dimensions=list(picture.size)
            break
        except (FileNotFoundError,OSError):time.sleep(.25)
    else:raise AssertionError('Renderer did not produce a complete PNG')
    assert dimensions==[width,height]
    verify_item(pin)
    rendered.append(dict(source=pin,output=artifact(output),dimensions=dimensions,
        renderer=artifact(edge),command=command,exit_code=completed.returncode,
        screenshot_seconds=time.perf_counter()-began,
        stderr_sha256=hashlib.sha256(completed.stderr).hexdigest()))
write_new(HERE/'SVG_RENDER_RECORD_V2.json',dict(status='ACTUAL_ASYNC_RENDER_OUTPUT_VERIFIED',
    created_utc=datetime.now(timezone.utc).isoformat(),rendered=rendered,
    failed_renderer_preserved=artifact(HERE/'render_public_svg.py'),
    public_svg_unchanged=True,predictions_and_scores_unchanged=True,new_model_http=0,cost_usd=0))
print('Actual local SVG inspection renders verified',len(rendered),flush=True)
