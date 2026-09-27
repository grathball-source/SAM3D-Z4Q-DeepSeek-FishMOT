"""Two preregistered synthetic protocol fixtures, never research fish evidence."""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build import save, wire


def picture(path, shapes, row):
    image = Image.new('RGB', (320, 180), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((8, 6), 'SYNTHETIC TEST ONLY  t='+str(row), fill='black', font=ImageFont.load_default())
    for role, shape, center in shapes:
        x = center; box = (x-27, 76, x+27, 130)
        if shape == 'square':
            draw.rectangle(box, outline='black', width=5, fill=(175, 175, 175))
        elif shape == 'triangle':
            draw.polygon([(x, 70), (x-32, 132), (x+32, 132)], outline='black', fill=(175, 175, 175), width=5)
        else:
            draw.ellipse(box, outline='black', width=5, fill=(175, 175, 175))
        draw.text((x-5, 143), role, fill='black', font=ImageFont.load_default())
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format='PNG')


def packet(case, pre, post, image_meta):
    def obs(role, frame, center):
        return {'fact_id': f'{case}-{role}-F{frame}', 'source_frame': frame,
                'source_time_seconds': float(frame), 'source_stream_frame': frame,
                'coordinate_system': 'synthetic_320x180_px', 'unit': 'px',
                'bbox_center_px': [center, 103], 'bbox_px': [center-34, 69, center+34, 134],
                'area_px': 3500, 'neighbor_count': 0,
                'quality': {'presence': 1, 'risk': 'SYNTHETIC_CLEAN'}}
    groups = {'PRE_HISTORY': {}, 'POST_HISTORY_TO_Q': {}}
    for section, rows, frame in (('PRE_HISTORY', pre, 0), ('POST_HISTORY_TO_Q', post, 1)):
        for role, _, center in rows:
            groups[section][role] = {'role': role, 'observations': [obs(role, frame, center)]}
    index = []
    for frame, rows in ((0, pre), (1, post)):
        m = image_meta[frame]
        index.append({'image_id': f'{case}-F{frame}', 'frame': frame, 'time_seconds': float(frame),
                      'width': 320, 'height': 180, 'roi_full_mask_xyxy': [0, 0, 320, 180],
                      'full_to_image': 'identity', 'pixel_source': 'SYNTHETIC_TEST_ONLY',
                      'role_tokens': [{'role': role, 'token': f'{case}-F{frame}:{role}',
                                       'bbox_full_px': obs(role, frame, center)['bbox_px'],
                                       'bbox_image_px': obs(role, frame, center)['bbox_px'],
                                       'fact_id': obs(role, frame, center)['fact_id']}
                                      for role, _, center in rows], **m})
    return {'request_id': 'SYNTHETIC_TEST_ONLY-'+case, 'q_frame': 1, 'q_time_seconds': 1.0,
            'coordinate_system': 'synthetic_320x180_px',
            'role_contract': 'A/B are before the possible overlap; X/Y are the later observations.',
            **groups, 'hypotheses': [
                {'id': 'H1', 'mapping': {'X': 'B', 'Y': 'A', 'U1': 'K1'}, 'epistemic_type': 'HYPOTHESIS'},
                {'id': 'H2', 'mapping': {'X': 'A', 'Y': 'B', 'U1': 'K1'}, 'epistemic_type': 'HYPOTHESIS'}],
            'IMAGE_INDEX': index, 'unknowns': ['identity after possible overlap'],
            'condition': 'SYNTHETIC_TEST_ONLY',
            'fixture_note': 'Geometric shapes are artificial. Compare both complete mappings using visible images. '
                            'Cite actual packet fact IDs; abstain if identity is ambiguous.'}


def build(run):
    run = Path(run)
    fixtures = (
        ('S01', [('A', 'square', 80), ('B', 'triangle', 240)],
         [('X', 'triangle', 80), ('Y', 'square', 240)], 'H1'),
        ('S02', [('A', 'circle', 80), ('B', 'circle', 240)],
         [('X', 'circle', 135), ('Y', 'circle', 185)], 'DEFER'))
    requests = []
    expectations = {}
    for case, pre, post, expected in fixtures:
        media = []
        for frame, rows in ((0, pre), (1, post)):
            path = run/'private/media'/(case+f'-F{frame}.png')
            assert not path.exists()
            picture(path, rows, frame)
            raw = path.read_bytes()
            media.append({'media_file': path.name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
        p = packet(case, pre, post, media)
        requests.append({'attempt_id': case, 'case': case, 'arm': 'SYNTHETIC_TEST_ONLY',
                         'text': wire(p), 'images': [{'image_id': x['image_id'], **media[i]}
                                                       for i, x in enumerate(p['IMAGE_INDEX'])]})
        expectations[case] = {'expected_choice_diagnostic_only': expected,
                              'correct_physical_mapping': p['hypotheses'][0]['mapping'] if case == 'S01' else None,
                              'fixture_type': 'DISTINCT_SHAPES' if case == 'S01' else 'AMBIGUOUS_IDENTICAL_SHAPES'}
    save(run/'public/SMOKE_REQUESTS.json', {'requests': requests, 'expectations': expectations,
                                            'status': 'SYNTHETIC_TEST_ONLY'})
    print({'synthetic_smoke_requests': len(requests), 'images': 4})


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True)
    build(p.parse_args().run)
