"""Private contact sheets of all actual postseal depth/mask figures for QA."""
from common import *
from PIL import Image, ImageDraw, ImageFont

cases = read(HERE/'PRIVATE_VISUALS.json')['cases']
assert len(cases) == len(read(HERE/'VISUAL_CASES.json')['cases'])
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
paths = []
for offset in range(0, len(cases), 6):
    page = Image.new('RGB', (1760, 1740), 'white')
    pen = ImageDraw.Draw(page)
    for i, entry in enumerate(cases[offset:offset+6]):
        pin = entry['artifact']; verify_item(pin)
        case = entry['case']
        with Image.open(pin['path']) as raw:
            assert raw.size == (1760, 1100)
            thumb = raw.convert('RGB').resize((880, 550), Image.Resampling.LANCZOS)
        x, y = (i % 2)*880, (i // 2)*580
        pen.text((x+10, y+5), f"{offset+i+1:03d} | {case['segment']} | local F{case['frame']} | {case['grade']}", font=font, fill='black')
        page.paste(thumb, (x, y+30))
    path = HERE/'private'/f'CONTACT_{offset//6+1:02d}.png'
    assert not path.exists()
    page.save(path)
    paths.append(artifact(path))
write_new(HERE/'VISUAL_CONTACT_SHEETS.json', dict(
    images=paths, source_cases=artifact(HERE/'PRIVATE_VISUALS.json'), cases=len(cases),
    pixels_private=True, inspection_not_yet_claimed=True, result_only_code=artifact(__file__)))
print('CONTACT_SHEETS_READY',len(paths),len(cases),flush=True)
