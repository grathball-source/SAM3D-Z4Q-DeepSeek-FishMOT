"""Fixed-population proxy summaries; no physical depth ground truth is assumed."""
from math import fsum, isfinite
from numbers import Integral


FIELDS = ('n', 'fish', 'other_fish', 'background')


def counts(value):
    if value is None:
        return dict.fromkeys(FIELDS, 0)
    result = {}
    for key in FIELDS:
        item = value[key]
        if not isinstance(item, Integral) or isinstance(item, bool) or item < 0:
            raise ValueError(f'invalid pixel count: {key}={item!r}')
        result[key] = int(item)
    if result['n'] != sum(result[key] for key in FIELDS[1:]):
        raise ValueError('occupancy counts do not partition selected pixels')
    return result


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize(rows, arm):
    """Use all SCORABLE rows for Q, and its reference-usable subset for R.

    UNKNOWN contributes zero selected pixels but stays in both denominators.
    UNSCORABLE occupancy is unavailable; its numeric selected_n can still count
    toward the complete source sample inventory. If selected_n is absent, use
    occupancy.n only when it exists, otherwise leave the source total unknown.
    """
    rows = list(rows)
    total = dict.fromkeys(FIELDS, 0)
    cross = {reference: dict.fromkeys(('AVAILABLE', 'UNKNOWN'), 0)
             for reference in ('SCORABLE', 'UNSCORABLE')}
    fixed = dict(n=0, compatible=0, discordant=0, unknown=0)
    q_n = accepted = fish_denom = available_q = source_n = unavailable_n = 0
    purities = []
    for row in rows:
        method = row['methods'][arm]
        status = method['status']
        if status not in ('AVAILABLE', 'UNKNOWN'):
            raise ValueError(f'invalid method status: {status!r}')
        scorable = row['reference_status'] == 'SCORABLE'
        cross['SCORABLE' if scorable else 'UNSCORABLE'][status] += 1
        accepted += status == 'AVAILABLE'
        occupancy = method['occupancy']
        selected_n = method.get('selected_n')
        if selected_n is None and occupancy is not None:
            selected_n = counts(occupancy)['n']
        if selected_n is None and status == 'UNKNOWN':
            selected_n = 0
        if selected_n is None:
            unavailable_n += 1
        else:
            if not isinstance(selected_n, Integral) or isinstance(selected_n, bool) or selected_n < 0:
                raise ValueError('invalid selected_n')
            if status == 'UNKNOWN' and selected_n != 0:
                raise ValueError('UNKNOWN must have zero selected samples')
            source_n += int(selected_n)
        if not scorable:
            if occupancy is not None or method['reference_compatible'] is not None or method['reference_abs_error_mm'] is not None:
                raise ValueError('UNSCORABLE matched quality must be null')
            continue
        q_n += 1
        if row['whole'] is None:
            raise ValueError('SCORABLE original whole counts are required')
        fish_denom += counts(row['whole'])['fish']
        current = counts(occupancy)
        if selected_n is not None and selected_n != current['n']:
            raise ValueError('selected_n differs from scorable occupancy.n')
        if status == 'AVAILABLE' and occupancy is None:
            raise ValueError('SCORABLE AVAILABLE occupancy is required')
        if status == 'UNKNOWN' and current['n']:
            raise ValueError('UNKNOWN occupancy must be empty')
        for key in FIELDS:
            total[key] += current[key]
        if status == 'AVAILABLE':
            available_q += 1
            if current['n']:
                purities.append(current['fish'] / current['n'])
        if row['reference_usable']:
            fixed['n'] += 1
            if status == 'UNKNOWN':
                if method['reference_compatible'] is not None or method['reference_abs_error_mm'] is not None:
                    raise ValueError('UNKNOWN reference quality must be null')
                fixed['unknown'] += 1
            else:
                compatible = method['reference_compatible']
                error = method['reference_abs_error_mm']
                if not isinstance(compatible, bool) or error is None or not isfinite(error) or error < 0:
                    raise ValueError('reference-usable AVAILABLE output requires its proxy quality')
                if not current['n'] or method['median_mm'] is None or not isfinite(method['median_mm']):
                    raise ValueError('reference-usable AVAILABLE output requires a measured median')
                fixed['compatible' if compatible else 'discordant'] += 1
        elif method['reference_compatible'] is not None or method['reference_abs_error_mm'] is not None:
            raise ValueError('unusable reference quality must be null')
    for key in ('compatible', 'discordant', 'unknown'):
        fixed[key + '_yield'] = ratio(fixed[key], fixed['n'])
    assert fixed['compatible'] + fixed['discordant'] + fixed['unknown'] == fixed['n']
    conditional = dict(objects=available_q, objects_with_samples=len(purities),
        micro_purity=ratio(total['fish'], total['n']),
        mean_purity=fsum(purities) / len(purities) if purities else None,
        selected_counts=dict(total))
    quality = dict(n=q_n, fish_denominator=fish_denom,
        fish_yield=ratio(total['fish'], fish_denom),
        nonfish_yield=ratio(total['other_fish'] + total['background'], fish_denom),
        selected_counts=dict(total))
    return dict(source_objects=len(rows), accepted=accepted, unknown=len(rows)-accepted,
        q_n=q_n, r_n=fixed['n'], unscorable=len(rows)-q_n, fixed_R=fixed, Q=quality,
        conditional_available=conditional, selected_counts=dict(total),
        selected_counts_population='SCORABLE',
        source_selected_n=source_n if not unavailable_n else None,
        source_selected_n_unavailable_objects=unavailable_n, cross_tab=cross)


def classify_primary(full, base):
    """A fixed-R proxy comparison, never a physical-depth success decision."""
    for key in ('source_objects', 'q_n', 'r_n'):
        if full[key] != base[key]:
            raise ValueError(f'comparison requires the same {key}')
    current, old = full['fixed_R'], base['fixed_R']
    if not full['r_n'] or not current['compatible'] + current['discordant']:
        return 'NO_PROXY_GAIN'
    # Equal R makes integer count comparisons exactly equivalent to yield
    # comparisons, without any new tolerance or significance threshold.
    if current['discordant'] < old['discordant']:
        return 'PROXY_GAIN_ONLY' if current['compatible'] >= old['compatible'] else 'TRADEOFF'
    return 'NO_PROXY_GAIN'
