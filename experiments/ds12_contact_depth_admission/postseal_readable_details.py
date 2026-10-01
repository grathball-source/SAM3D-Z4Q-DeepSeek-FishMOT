"""Append readable numeric detail sheets from the sealed public inventory only.

No prediction rows, data pixels, GT, or research measurements are reopened.
Original SVGs, inventories, QA, and research artifacts remain unchanged.
"""
from pathlib import Path
from html import escape
import json
import subprocess
import textwrap
import xml.etree.ElementTree as ET
from common import HERE, artifact, read, write_new, verify_item

WIDTH, FONT, LINE = 1440, 20, 29
WRAP = 108
ARMS = ('SAM3_NATIVE', 'F9_RESTORED', 'R12_RAW', 'R12_RESTORED')


def value(item):
    if item is None:
        return 'NONE'
    if isinstance(item, bool):
        return str(item).upper()
    if isinstance(item, float):
        return f'{item:.6f}'
    return str(item)


def details(case):
    """Return bounded-width lines; no reason strings or ID maps are shortened."""
    lines = []

    def add(text='', kind='body'):
        for line in textwrap.wrap(str(text), WRAP, break_long_words=True,
                                  break_on_hyphens=False) or ['']:
            lines.append((line, kind))

    def section(text):
        add(); add(text, 'section')

    add(f'DS12 READABLE NUMERIC DETAILS | F{case["query_global_frame"]} '
        f'n{case["query_native"]} | {case["arm"]}', 'title')
    add('Postseal presentation repair. Sealed numbers only; no new experiment, pixels, GT, or predictions.')
    add('Source/native IDs and actual published IDs are different fields. No selected OLD ID is copied backward.')
    add('Eligible does not mean associated. No LR means not evaluated, never a zero score.')
    add('Numbers are displayed to 6 decimals; exact values and source hashes remain in the original inventory.')
    add(f'Segment: {case["segment"]}')
    add(f'Actual birth status={case["status"]}; native={case["query_native"]}; '
        f'FIRST PUBLIC={case["actual_first_public_id"]}; selected target={value(case["selected_target"])}')
    add(f'Numeric reason={value(case["numeric_reason"])}; group blocked={value(case["group_blocked"])}; '
        f'stage error={value(case["stage_error"])}')
    add(f'Case selection: {case["selection_reason"]}')
    add(f'Illustrated OLD reference source={case["reference_source"]}; rule={case["reference_rule"]}')
    add('Reference is NOT certified correct target. Physical fish ownership/background/calibration remain UNKNOWN.')

    section('1. ALL FOUR TIME ROLES AND ACTUAL PUBLICATION IDs')
    bindings = {item['role']: item for item in case['sample_bindings']}
    query_time = bindings['first_birth']['time']
    role_names = dict(joint_reference='LAST JOINT CLEAN REFERENCE',
                      first_anonymous_risk='FIRST ANONYMOUS RISK',
                      last_appearance='LAST APPEARANCE', first_birth='FIRST BIRTH / QUERY')
    for role, frame in case['sample_frames'].items():
        add(f'{role} -- {role_names[role]}', 'item')
        sample = bindings.get(role)
        if sample is None:
            assert frame is None
            add('  No recorded frame for this role; no ID or observation synthesized.')
            continue
        add(f'  global F{sample["global_frame"]}; local F{sample["frame"]}; '
            f'time={sample["time"]:.6f}; relative-to-query={sample["time"]-query_time:.6f}s')
        assert sample['frame'] == frame and sample['global_frame'] <= case['query_global_frame']
        for arm in ARMS:
            mapping = sample['actual_public_ids'][arm]
            old, born = str(case['reference_source']), str(case['query_native'])
            add(f'  {arm}: reference n{old} -> public {mapping.get(old,"ABSENT")}; '
                f'query n{born} -> public {mapping.get(born,"ABSENT")}')
            pairs = ', '.join(f'n{native}={public}' for native, public in sorted(
                mapping.items(), key=lambda item:int(item[0])))
            add(f'    ALL actual masks (native=published): {pairs or "NONE"}')
        add(f'  Publisher row SHA256: {sample["publisher_prewrite_LF_sha256"]}')
        add(f'  Disk prediction row SHA256: {sample["disk_prediction_line_sha256"]}')
    add(f'Complete raw joint history samples={len(case["complete_joint_history"])}; '
        f'anonymous risk observations={len(case["complete_anonymous_risk"])} (identity UNKNOWN, not fitted).')
    anchor = case['reference_anchor']
    add('Joint reference anchor: '+json.dumps(anchor, sort_keys=True, separators=(',', ':')))
    add('Actual mechanical bank anchor: '+json.dumps(case['actual_mechanical_bank_anchor'],
                                                    sort_keys=True, separators=(',', ':')))

    section('2. ALL CURRENT CORE COMPONENT STATISTICS (ACTUAL UNIQUE SENSOR n)')
    cert = case['current_certificate']
    weights = {piece['component_id']: piece['weight'] for piece in cert['qualified_components']}
    add(f'Source={cert["source"]}; mode={cert["mode"]}; eligible={value(cert["eligible"])}; '
        f'qualified={cert["qualified_component_count"]}/{len(cert["components"])}')
    add(f'Mask area={cert["mask_area"]}; mask-overlap pixels excluded={cert["shared_mask_pixels_excluded"]}; '
        f'core ROI area={cert["geometric_components"]["roi_area"]}')
    add('n counts actual selected unique source points; fraction denominator is actual geometric core-piece area.')
    add('MAD is actual measured MAD. Scale is the fixed noise adapter, not an observed MAD.')
    add('Inferred is forbidden; native-v2 admits retained provenance only. Weights fixed before all candidates.')
    add('Inferred/native-invalid exclusion counts can overlap; do not add them as independent losses.')
    for piece in cert['components']:
        add(f'Component {piece["component_id"]}', 'item')
        add(f'  qualified={value(piece["qualified"])}; fixed mixture weight={value(weights.get(piece["component_id"],0))}; '
            f'area={piece["area"]}; actual n={piece["n"]}; fraction={value(piece["valid_fraction"])}')
        add(f'  median_mm={value(piece["median_mm"])}; actual_MAD_mm={value(piece["actual_mad_mm"])}; '
            f'scale_mm={value(piece["scale_mm"])}')
        add('  Quantiles mm: '+', '.join(f'{key}={value(piece[key])}' for key in ('q10','q25','q75','q90')))
        add('  Pixel/source exclusions: '+', '.join(f'{key}={piece[key]}' for key in
            ('shared_source_pixels_excluded','duplicate_pixels_excluded','unmapped_pixels',
             'invalid_native_source_pixels','inferred_pixels_excluded')))
        add('  Reasons: '+('; '.join(piece['exclusion_reasons']) or 'NONE'))
        add(f'  >5000mm diagnostic count={piece["aligned_above_5000_mm_diagnostic_n"]}; '
            'SUSPECT ONLY, not sensor-range evidence or a new exclusion.')
    add(f'Certificate SHA256: {cert["certificate_sha256"]}')

    section('3. ALL ACTUALLY EVALUATED OLD + NEW LOG LIKELIHOODS')
    scores = case['all_evaluated_candidate_LR']
    add('geometry_logLR and depth_logLR are recorded factors; log_score includes the actual prior.')
    add('score_delta_vs_NEW below is a display-only subtraction of recorded log_scores.')
    if not scores:
        add('NONE: numerical selector was not evaluated for this query; no LR invented.')
    for name, score in scores.items():
        add(f'{name}: source={score["source"]}; public hypothesis={score["public"]}', 'item')
        add(f'  geometry_logLR={value(score["geometry_log_lr"])}; depth_logLR={value(score["depth_log_lr"])}; '
            f'log_score={value(score["log_score"])}')
        if 'NEW' in scores:
            add(f'  score_delta_vs_NEW={value(score["log_score"]-scores["NEW"]["log_score"])}')

    section(f'4. EVERY RECORDED OLD CANDIDATE: {len(case["all_recorded_candidates"])} SOURCES')
    add('All sources retained, including rejected sources and multiple sources sharing one public alias.')
    add('A public hypothesis LR is attributed only to its actual evaluated source, never to an alias sibling.')
    for number, candidate in enumerate(case['all_recorded_candidates'], 1):
        add(f'{number:02d}. OLD source={candidate["source"]}; public={candidate["public"]}; '
            f'eligible={value(candidate["eligible"])}', 'item')
        key = f'OLD:{candidate["public"]}'
        score = scores.get(key)
        if score and score['source'] == candidate['source']:
            add(f'  Evaluated: {key}; geometry_logLR={value(score["geometry_log_lr"])}; '
                f'depth_logLR={value(score["depth_log_lr"])}; log_score={value(score["log_score"])}')
        elif score:
            add(f'  No LR for this source; {key} was evaluated from source={score["source"]}.')
        else:
            add('  NO LR: this source was not evaluated. This is not zero evidence.')
        if candidate['reasons']:
            for reason in candidate['reasons']:
                add('  Recorded rejection reason: '+reason)
        else:
            add('  Recorded rejection reasons: NONE (eligibility still does not mean commitment).')
        add('  Recorded geometry local frames: '+json.dumps(candidate['geometry_frames']))
        add('  Reference anchor: '+json.dumps(candidate['reference_anchor'], separators=(',', ':')))
        add('  Bank anchor: '+json.dumps(candidate['bank_anchor'], separators=(',', ':')))

    section('5. IMMUTABLE SOURCE BINDING / INTERPRETATION')
    add(f'Original numeric SVG SHA256: {case["public_numeric_svg"]["sha256"]}')
    add('This supplement repairs text layout only. Original plots and original inventory remain unchanged.')
    add('All displayed observations are at or before q. No GT reference, new data pixel, or new decision used.')
    add('Native-v2 retains upstream RGB and next-frame cleaning support: offline diagnostic, causal equivalence UNKNOWN.')
    assert all(len(line) <= WRAP for line, _ in lines)
    return lines


def svg_document(lines):
    height = 72 + len(lines)*LINE
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
            f'viewBox="0 0 {WIDTH} {height}">',
            '<rect width="100%" height="100%" fill="#ffffff"/>',
            '<style>text{font-family:Consolas,\'DejaVu Sans Mono\',monospace;font-size:20px;'
            'white-space:pre} .title,.section,.item{font-weight:bold}</style>']
    for index, (line, kind) in enumerate(lines):
        color = '#173b66' if kind in ('title', 'section') else '#18232d'
        body.append(f'<text x="36" y="{44+index*LINE}" class="{kind}" fill="{color}">{escape(line)}</text>')
    body.append('</svg>')
    document = '\n'.join(body)+'\n'
    root = ET.fromstring(document)
    assert not root.findall('.//{http://www.w3.org/2000/svg}image')
    assert len(root.findall('{http://www.w3.org/2000/svg}text')) == len(lines)
    return document, height


def render(source, height, destination):
    node = Path('C:/Users/19430/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    sharp = Path('C:/Users/19430/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp')
    # Native-size windows, rather than shrinking a long page, preserve the actual 20px text for QA.
    windows = sorted(set((0, max(0, (height-1300)//2), max(0, height-1300))))
    script = ('const sharp=require(process.argv[1]); const top=+process.argv[4],h=+process.argv[5];'
              'sharp(process.argv[2],{density:72}).extract({left:0,top,width:1440,height:h})'
              '.png().toFile(process.argv[3]).catch(e=>{console.error(e);process.exit(1)});')
    result = []
    for index, top in enumerate(windows):
        target = destination/f'{source.stem}_QA_{index+1}.png'
        command = [str(node), '-e', script, str(sharp), str(source), str(target), str(top), str(min(1300,height-top))]
        completed = subprocess.run(command, text=True, capture_output=True)
        assert completed.returncode == 0, completed.stderr
        result.append(dict(source_svg=artifact(source), rendered_numeric_png=artifact(target),
                           top=top, height=min(1300,height-top), width=WIDTH,
                           command=command, exit_code=completed.returncode))
    return result


def main():
    source = HERE/'diagnosis/postseal_VISUALIZATION_INVENTORY.json'
    original_qa = HERE/'diagnosis/postseal_VISUALIZATION_QA.json'
    inventory = read(source)
    assert inventory['case_count'] == len(inventory['cases']) == 18
    for key in ('all_prediction_seal', 'scoring_seal', 'access_seal'):
        verify_item(inventory['bindings'][key])
    preserved = [artifact(source), artifact(original_qa)]
    preserved += [artifact(c['public_numeric_svg']['path']) for c in inventory['cases']]
    for case, actual in zip(inventory['cases'], preserved[2:]):
        assert actual == case['public_numeric_svg']
    destination = HERE/'diagnosis/readable_details'
    raster_destination = HERE/'private/readable_details_QA'
    destination.mkdir(); raster_destination.mkdir()
    cases, renders = [], []
    for case in inventory['cases']:
        lines = details(case)
        document, height = svg_document(lines)
        target = destination/f'postseal_F{case["query_global_frame"]:06d}_n{case["query_native"]}_{case["arm"]}_READABLE.svg'
        with target.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(document)
        cases.append(dict(query_global_frame=case['query_global_frame'], query_native=case['query_native'],
                          arm=case['arm'], status=case['status'], actual_first_public_id=case['actual_first_public_id'],
                          detail_svg=artifact(target), original_svg=case['public_numeric_svg'],
                          width=WIDTH,height=height,font_size=FONT,line_count=len(lines),
                          recorded_old_sources=len(case['all_recorded_candidates']),
                          evaluated_hypotheses=len(case['all_evaluated_candidate_LR']),
                          current_components=len(case['current_certificate']['components']),
                          wrapping='EVERY_FULL_STRING_WRAPPED_AT_108_MONOSPACE_CHARACTERS; AUTO_HEIGHT',
                          data_image_elements=0))
        if case['query_global_frame'] in (65,1886):
            renders.extend(render(target,height,raster_destination))
    assert preserved == [artifact(item['path']) for item in preserved]
    output = HERE/'diagnosis/postseal_READABLE_DETAILS_INVENTORY.json'
    write_new(output,dict(status='PASS_ALL_18_NUMERIC_DETAIL_SHEETS_GENERATED; ACTUAL_VIEW_PENDING',
                          code=artifact(__file__),source_inventory=artifact(source), original_QA=artifact(original_qa),
                          sealed_bindings={k:inventory['bindings'][k] for k in
                              ('all_prediction_seal','scoring_seal','access_seal')},
                          cases=cases, rendered_numeric_QA_windows=renders,original_artifacts_unchanged=True,
                          data_pixels_read=0,GT_reads=0,RGB_reads=0,prediction_rows_read=0,
                          new_research_measurements=0,new_decisions=0))
    print(json.dumps(dict(case_count=len(cases),QA_windows=len(renders),inventory=artifact(output))))


if __name__ == '__main__':
    main()
