"""Public, pixel-free figures from independently scored sealed numeric results."""
from common import *
from html import escape

COLORS = {'SAM3_NATIVE':'#6b7280', 'Z4Q_FROZEN':'#2563eb', 'RGB_LAG':'#b45309', 'RGBD_LAG':'#15803d'}
NAMES = {'SAM3_NATIVE':'Native', 'Z4Q_FROZEN':'Z4Q', 'RGB_LAG':'RGB lag', 'RGBD_LAG':'RGB-D lag'}


def _text(x, y, value, size=13, fill='#111827'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}">{escape(str(value))}</text>'


def _svg(width, height, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="white"/>'
        '<g font-family="Arial, sans-serif">' + ''.join(body) + '</g></svg>\n')


def metric_table(result):
    """All fixed sources and every arm, including weak references and zeros."""
    sections = [(name, s['metrics']) for name, s in result['segments'].items()]
    sections.append(('Feeding pooled (identities namespaced by segment)', result['feeding_pooled']['metrics']))
    body = [_text(20, 28, 'DS33: actual full-sequence mask tracking metrics', 20),
        _text(20, 50, 'L3/LW references are weak preannotation; do not pool them into an accuracy headline.'),
        _text(20, 70, 'RGB / RGB-D delay first publication by at most 30 frames. No masks are added, removed or inpainted.')]
    y = 102
    fields = ('IDF1', 'HOTA', 'AssA', 'IDSW', 'FP', 'FN')
    xs = (360, 450, 540, 630, 740, 855)
    for name, values in sections:
        body.append(_text(20, y, name, 15)); y += 24
        body.extend(_text(x, y, field, 12, '#374151') for x, field in zip(xs, fields))
        y += 22
        for arm in ARMS:
            body.append(_text(38, y, NAMES[arm], 13, COLORS[arm]))
            for x, field in zip(xs, fields):
                value = values[arm][field]
                body.append(_text(x, y, f'{value:.4f}' if field in ('IDF1', 'HOTA', 'AssA') else str(value)))
            y += 22
        body.append(f'<path d="M20 {y - 8} H940" stroke="#e5e7eb"/>'); y += 14
    return _svg(960, y + 12, body)


def depth_increment(result):
    body = [_text(20, 28, 'Reliable-depth increment: RGB-D lag minus identical RGB lag', 20),
        _text(20, 52, 'Percentage points for IDF1/HOTA/AssA; integer difference for IDSW. Lower IDSW is better.')]
    fields, xs = ('IDF1', 'HOTA', 'AssA', 'IDSW'), (440, 555, 670, 810)
    y = 88
    body.extend(_text(x, y, field, 13) for x, field in zip(xs, fields)); y += 28
    sections = [(name, s['metrics']) for name, s in result['segments'].items()]
    sections.append(('Feeding pooled', result['feeding_pooled']['metrics']))
    for name, values in sections:
        body.append(_text(20, y, name))
        for x, field in zip(xs, fields):
            delta = values['RGBD_LAG'][field] - values['RGB_LAG'][field]
            benefit = delta < 0 if field == 'IDSW' else delta > 0
            color = '#15803d' if benefit else '#b91c1c' if delta else '#6b7280'
            body.append(_text(x, y, f'{delta:+.4f}' if field != 'IDSW' else f'{int(delta):+d}', fill=color))
        y += 30
    return _svg(960, y + 12, body)


def event_table(result):
    body = [_text(20, 28, 'Every request and its actual first publication', 20),
        _text(20, 52, 'Physical preanchor correctness uses actual published reconnect actions; public-label origin is scored separately.'),
        _text(20, 72, 'UNKNOWN, EOF, deadlines, out-of-scope and shadow requests remain visible. A new label is not identity recovery.')]
    y = 100
    values = [(name, arm, event) for name, audit in result['event_audits'].items()
        for arm, events in audit['event_arms'].items() for event in events]
    if not values:
        body.append(_text(20, y, 'No requests in the fixed sources.'))
    for name, arm, event in values:
        body.append(_text(20, y, f"{name} | {NAMES[arm]} | q={event['global_frame']} | delay={event['decision_to_first_publication_delay_frames']} frames", 14))
        y += 21
        changed = '; '.join(f"n:{n}: {v['before']} → {v['after']}" for n, v in event['actual_changes'].items()) or 'No publication change'
        body.append(_text(36, y, f"{event['original_status']} | {event['submitted_option']} | physical={event['physical_preanchor']} | {changed}", 12))
        y += 21
        origins = '; '.join(f"n:{s['source']}: {s['public_reference_correctness']}" for s in event['selected_sources']) or 'No selected source'
        body.append(_text(36, y, f"Public origin: {origins} | {event['outcome_role']}", 12, '#4b5563'))
        y += 29
    return _svg(1340, y + 16, body)


def main():
    result = read(RUN / 'METRICS.json')
    assert result['status'] == 'SCORED_AFTER_ALL_EIGHT_FORMAL_PREDICTION_AND_ACCESS_SEALS'
    assert result['frames'] == 20098 and tuple(result['arms']) == ARMS
    assert result['all_seal'] == artifact(RUN / 'ALL_PREDICTIONS_SEALED.json')
    assert read(RUN / 'SCORE_PROVENANCE.json')['original_controls_exact']
    directory = HERE / 'visuals'
    directory.mkdir(exist_ok=True)
    outputs = []
    for name, render in (('FULL_METRICS.svg', metric_table), ('DEPTH_INCREMENT.svg', depth_increment), ('ALL_EVENTS.svg', event_table)):
        path = directory / name
        with path.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(render(result))
        outputs.append(artifact(path))
    write_new(directory / 'SOURCES.json', dict(status='SCORED_NUMERIC_ONLY_NO_PRIVATE_PIXELS',
        metrics=artifact(RUN / 'METRICS.json'), scoring_provenance=artifact(RUN / 'SCORE_PROVENANCE.json'),
        renderer=artifact(__file__), figures=outputs, RGB_pixels=False, depth_rasters=False, GT_rasters=False,
        weak_references=['L3', 'LW'], all_fixed_sources_and_events_included=True))
    print('Numeric figures sealed:', len(outputs), flush=True)


if __name__ == '__main__':
    main()
