"""Stateless raw-depth filtering; no identity, candidate, GT or future input."""
from common import CFG, cv2, np, statistics


def dilate(mask, radius):
    return cv2.dilate(mask.astype('u1'), np.ones((2*radius+1, 2*radius+1), 'u1')).astype(bool)


def scale(values):
    return max(CFG['scale_floor_mm'], 1.4826*float(np.median(np.abs(values-np.median(values)))))


def measure(depth, region, other):
    """Return numeric facts plus local pixel regions and their global crop origin."""
    assert depth.ndim == 2 and depth.shape == region.shape == other.shape
    yy, xx = np.nonzero(region)
    if not len(xx):
        raise ValueError('empty source mask')
    pad = CFG['annulus_outer_px']+CFG['neighbor_margin_px']
    x0, x1 = max(0, int(xx.min())-pad), min(depth.shape[1], int(xx.max())+pad+1)
    y0, y1 = max(0, int(yy.min())-pad), min(depth.shape[0], int(yy.max())+pad+1)
    d = np.asarray(depth[y0:y1, x0:x1], dtype='f8')
    own, neighbor = region[y0:y1, x0:x1], other[y0:y1, x0:x1]
    exclusive = own & ~neighbor
    valid = np.isfinite(d) & (d > 0)
    ring = (dilate(own, CFG['annulus_outer_px']) & ~dilate(own, CFG['annulus_inner_px'])
            & ~dilate(neighbor, CFG['neighbor_margin_px']))
    empty = np.zeros(d.shape, bool)
    pixels = dict(annulus=ring, candidates=empty.copy(), support=empty.copy(), selected=empty.copy())
    facts = dict(status='UNKNOWN', reason=None, crop=[x0,y0,x1,y1],
                 annulus=statistics(d, ring), exclusive_area=int(exclusive.sum()),
                 exclusive_valid_n=int((exclusive & valid).sum()), plane=None,
                 components=[], significant_n=0, selected=statistics(d, empty),
                 support_raw_valid_fraction=None, selected_support_fraction=None,
                 dominance=None, raw_valid_retention=None, signed_contrast_median_mm=None)

    def finish(reason):
        facts['reason'] = reason
        return facts, pixels

    if facts['annulus']['n'] < CFG['background_min_n']:
        return finish('INSUFFICIENT_BACKGROUND_SAMPLES')
    if facts['annulus']['valid_fraction'] < CFG['background_min_fraction']:
        return finish('INSUFFICIENT_BACKGROUND_COVERAGE')
    gy, gx = np.indices(d.shape)
    cx, cy = (x0+x1-1)/2, (y0+y1-1)/2
    normalized_x = (gx+x0-cx)/CFG['annulus_outer_px']
    normalized_y = (gy+y0-cy)/CFG['annulus_outer_px']
    sample = ring & valid
    design = np.column_stack([np.ones(int(sample.sum())), normalized_x[sample], normalized_y[sample]])
    values = d[sample]
    condition = float(np.linalg.cond(design))
    if np.linalg.matrix_rank(design) < 3 or not np.isfinite(condition) or condition > CFG['background_max_condition']:
        return finish('DEGENERATE_BACKGROUND_GEOMETRY')
    beta = np.array([np.median(values), 0., 0.])
    for _ in range(CFG['irls_steps']):
        residual = values-design@beta
        weight = np.minimum(1., CFG['huber_c']*scale(residual)/np.maximum(np.abs(residual), 1e-12))
        weighted = design*np.sqrt(weight[:,None])
        beta = np.linalg.lstsq(weighted, values*np.sqrt(weight), rcond=None)[0]
    residual = values-design@beta
    sigma = scale(residual)
    threshold = max(CFG['contrast_floor_mm'], CFG['contrast_sigma']*sigma)
    predicted = beta[0]+beta[1]*normalized_x+beta[2]*normalized_y
    contrast = predicted-d
    facts['plane'] = dict(origin_px=[cx,cy], coordinate_scale_px=CFG['annulus_outer_px'],
                         beta_mm=beta.tolist(), residual_scale_mm=sigma,
                         residual_median_mm=float(np.median(residual)), condition=condition,
                         contrast_threshold_mm=threshold, sample_n=len(values))
    if sigma > CFG['max_scale_mm']:
        return finish('BACKGROUND_NOT_LOCALLY_SEPARABLE')
    candidate = exclusive & valid & (np.abs(contrast) >= threshold)
    pixels['candidates'] = candidate
    facts['significant_n'] = int(candidate.sum())
    if not candidate.any():
        return finish('NO_SIGNIFICANT_DEPTH_CONTRAST')
    components = []
    for sign, sign_mask in [('NEARER', contrast > 0), ('FARTHER', contrast < 0)]:
        seed = candidate & sign_mask
        support = cv2.morphologyEx(seed.astype('u1'), cv2.MORPH_CLOSE,
                                   np.ones((CFG['closing_size_px'],)*2, 'u1')).astype(bool) & exclusive
        count, labels = cv2.connectedComponents(support.astype('u1'), connectivity=8)
        for label in range(1, count):
            area = labels == label
            selected = seed & area
            stat = statistics(d, selected)
            support_n = int(area.sum())
            sigma_component = scale(d[selected]) if stat['n'] else None
            qualified = (stat['n'] >= CFG['foreground_min_n'] and
                         stat['n']/max(1,support_n) >= CFG['foreground_min_support_fraction'] and
                         sigma_component <= CFG['max_scale_mm'])
            entry = dict(sign=sign, label=label, n=stat['n'], support_area=support_n,
                         raw_scale_mm=sigma_component, qualified=bool(qualified))
            facts['components'].append(entry)
            if qualified:
                components.append((stat['n'], sign, label, area, selected))
    if not components:
        return finish('NO_QUALIFIED_CONNECTED_COMPONENT')
    components.sort(key=lambda item: (-item[0], item[1], item[2]))
    n, sign, label, support, selected = components[0]
    dominance = n/facts['significant_n']
    facts['dominance'] = dominance
    if dominance < CFG['dominant_fraction']:
        return finish('AMBIGUOUS_MULTIPLE_DEPTH_COMPONENTS')
    pixels.update(support=support, selected=selected)
    facts.update(status='AVAILABLE', selected=statistics(d, selected), selected_sign=sign,
                 selected_component_label=label, support_area=int(support.sum()),
                 support_raw_valid_fraction=float((valid & support).sum()/support.sum()),
                 selected_support_fraction=n/int(support.sum()),
                 raw_valid_retention=n/max(1,facts['exclusive_valid_n']),
                 signed_contrast_median_mm=float(np.median(contrast[selected])))
    return finish('QUALIFIED_DOMINANT_DEPTH_COMPONENT')
