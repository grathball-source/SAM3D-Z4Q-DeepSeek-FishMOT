"""Append final engineering receipts from executed checks; never run a formal trial."""
from common import *
import ast
import argparse
import copy
import re
import subprocess
from datetime import datetime, timezone


def verified(path):
    value = read(path)
    assert value['status'].startswith('PASS'), path
    for key in ('code', 'checker', 'scorer', 'source_fixture', 'transaction'):
        pin = value.get(key)
        if isinstance(pin, dict) and {'path', 'bytes', 'sha256'} <= pin.keys():
            verify_item(pin)
    for pin in value.get('scoring_dependencies', []):
        verify_item(pin)
    assert not value.get('GT_opened', False), path
    assert not value.get('new_model_http', 0), path
    return value


def logged_check(name):
    executions = [e for e in rows_plain(HERE/'EXECUTION_LOG.jsonl')
                  if Path(e['command'][1]).name == name and e['exit_code'] == 0]
    assert executions, 'Missing executed check: ' + name
    execution = executions[-1]
    for key in ('stdout', 'stderr'):
        verify_item(execution[key])
    stdout = Path(execution['stdout']['path']).read_text(encoding='utf-8')
    stderr = Path(execution['stderr']['path']).read_text(encoding='utf-8')
    try:
        result = json.loads(stdout)
        assert result['status'].startswith('PASS')
        checks = result.get('count', result.get('checks'))
        count = len(checks) if isinstance(checks, list) else checks
    except json.JSONDecodeError:
        count = int(re.search(r'Ran (\d+) tests? in', stderr).group(1))
        assert re.search(r'\nOK\s*$', stderr), 'Tests did not finish successfully'
        result = dict(status='PASS', checks=count, scope='Actual unittest exit/log')
    assert type(count) is int and count > 0
    return dict(checker=artifact(HERE/name), count=count, result=result, execution=execution)


def rows_plain(path):
    with Path(path).open(encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


def evidence_check():
    receipt = HERE/'EVIDENCE_CHECKS_READY.json'
    if receipt.exists():
        value = verified(receipt)
        verify_item(value['evidence']); verify_item(value['tests'])
        return value
    executed = subprocess.run([sys.executable, '-B', str(HERE/'checks_evidence.py')],
                              cwd=HERE, capture_output=True, text=True, encoding='utf-8')
    assert executed.returncode == 0, executed.stderr
    value = json.loads(executed.stdout)
    assert value['status'].startswith('PASS') and value['source_dataset_reads'] == value['GT_reads'] == 0
    verify_item(value['evidence']); verify_item(value['tests'])
    write_new(receipt, value)
    return value


def current_code():
    import runner, score
    paths = set(HERE.glob('*.py')) | {HERE/'CONFIG.json', HERE/'PLAN.md', HERE/'README.md',
                                     HERE/'DATA_CONTRACT.md', CONFIG_PATH}
    for value in list(sys.modules.values()):
        filename = getattr(value, '__file__', None)
        if filename and filename.endswith('.py'):
            path = Path(filename).resolve()
            if path.is_relative_to(ROOT) or path.is_relative_to(WORK/'tools'):
                paths.add(path)
    paths |= {Path(pin['path']) for pin in score.scoring_dependencies()}
    for path in paths:
        if path.suffix == '.py':
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    return [artifact(path) for path in sorted(paths, key=str)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--real-slice', default='REAL_INPUT_SLICE_OWNER_READY.json')
    parser.add_argument('--real-access', default='REAL_INPUT_SLICE_ACCESS_OWNER_READY.json')
    parser.add_argument('--publication-checks', default='REAL_PUBLICATION_CHECKS_OWNER_READY.json')
    parser.add_argument('--flow-checks', default='SCORER_REAL_FLOW_CHECKS_OWNER_READY.json')
    parser.add_argument('--score-checks', default='SCORE_CHECKS_FROZEN_CANDIDATE.json')
    parser.add_argument('--qualified', default='QUALIFIED_CONTINUITY_REVIEW_CASCADE_READY.json')
    parser.add_argument('--enabled-prefix', default='slice_owner_acceptance205')
    parser.add_argument('--disabled-prefix', default='slice_owner_disabled60')
    args = parser.parse_args()
    for name in vars(args).values():
        assert Path(name).name == name, 'Use a direct append-only receipt name'
    targets = [HERE/name for name in ('INTEGRATED_CONTRACT_REVIEW_READY.json',
                                     'CHECKS_FINAL.json', 'REAL_ACCEPTANCE.json')]
    assert not any(path.exists() for path in targets), 'Final receipts are append-only'
    assert not (HERE/'RUNTIME_FREEZE.json').exists(), 'Assemble before runtime freeze'
    # A known actual event-related original conflict assertion must be resolved, not hidden by
    # a successful earlier two-frame replay or by replacing published outputs.
    cascade = verified(HERE/'NATIVE_RETURN_CASCADE_REVIEW_READY.json')
    assert cascade['engineering_only'] and cascade['return_after_publication_checked']
    scorer = verified(HERE/args.score_checks)
    publication = verified(HERE/args.publication_checks)
    flow_check = verified(HERE/args.flow_checks)
    history = verified(HERE/'HISTORY_CHECKS.json')
    evidence = evidence_check()
    qualified = verified(HERE/args.qualified)
    suite = {'score':dict(count=len(scorer['checks']), receipt=artifact(HERE/args.score_checks)),
             'history':dict(count=len(history['checks']), receipt=artifact(HERE/'HISTORY_CHECKS.json')),
             'evidence':dict(count=len(evidence['checks']), receipt=artifact(HERE/'EVIDENCE_CHECKS_READY.json'))}
    for name in ('state', 'lag', 'flow'):
        suite[name] = logged_check('checks_' + name + '.py')
    real = read(HERE/args.real_slice)
    assert real['status'] == 'PASS' and real['engineering_only'] and real['no_GT']
    assert real['mock_choice'] == 'H2' and real['not_a_method_result']
    assert real['frames'] == 78 and (real['q'], real['cutoff']) == (48, 50)
    assert not real['staged'] and real['error'] == 'UNSELECTED_MEMBER_OWNERSHIP'
    assert real['published_once'] and real['complete_selected_state_continues']
    assert not real['future_measurement_written_to_q'] and real['all_masks_and_residuals_retained']
    unique_pairs = {(p['pre_frame'], p['post_frame']) for p in real['actual_flow_pairs']}
    assert len(unique_pairs) == len(real['actual_flow_pairs']) == flow_check['actual_pairs'] == 9
    assert flow_check['actual_endpoints'] == len(real['actual_sensor_bindings']) == 6
    for name, expected in real['code'].items():
        assert sha(HERE/name) == expected, 'Real slice source changed: ' + name
    assert publication['frames'] == 265
    runtime_names = ('common.py', 'manager.py', 'runner.py', 'transaction.py', 'history.py',
                     'lag.py', 'sensor.py', 'flow.py', 'evidence.py')
    actual_artifacts = [artifact(HERE/name) for name in
        (args.real_slice, args.real_access, args.publication_checks,
         args.flow_checks, args.qualified,
         'NATIVE_RETURN_CASCADE_REVIEW_READY.json')]
    for directory, expected_frames in ((args.enabled_prefix, 205), (args.disabled_prefix, 60)):
        public = HERE/directory/'feeding_000351_000555/public'
        seal = read(public/'PREDICTIONS_SEALED.json'); freeze = read(public/'PREFIX_FREEZE.json')
        assert seal['frames'] == expected_frames
        for name in runtime_names:
            assert freeze['code'][str(HERE/name)] == sha(HERE/name), 'Fresh slice required: ' + name
        assert freeze['configuration'] == artifact(HERE/'CONFIG.json')
        actual_artifacts.extend(artifact(public/name) for name in
            ('PREDICTIONS_SEALED.json', 'PREFIX_FREEZE.json', 'ACCESS.json', 'RUN_SUMMARY.json'))
    code = current_code()
    review = copy.deepcopy(read(HERE/'INTEGRATED_CONTRACT_REVIEW.json'))
    review.update(schema='DS34_INTEGRATED_CONTRACT_REVIEW_READY_V1', status='PASS',
        created_utc=datetime.now(timezone.utc).isoformat(), code=code,
        prior_review=artifact(HERE/'INTEGRATED_CONTRACT_REVIEW.json'),
        current_code_revalidated=True, freeze_and_reporting_sources_bound=True,
        actual_validation=dict(publication_frames=265, actual_flow_pairs=9, actual_endpoints=6,
            real_mock_frames=78, q=48, cutoff=50, stage_rejected='UNSELECTED_MEMBER_OWNERSHIP',
            actual_fallback_continues=True, method_result=False, artifacts=actual_artifacts),
        later_native_return_cascade=cascade)
    review['resolved_findings'].append(dict(id='CURRENT_ORIGINAL_CONFLICT_EVENT_ALIAS_CASCADE',
        correction=cascade['correction'], receipt=artifact(HERE/'NATIVE_RETURN_CASCADE_REVIEW_READY.json')))
    write_new(targets[0], review)
    check_artifacts = [artifact(HERE/args.score_checks),
                       artifact(HERE/'HISTORY_CHECKS.json'), artifact(HERE/'EVIDENCE_CHECKS_READY.json'),
                       artifact(targets[0]), artifact(HERE/'NATIVE_RETURN_CASCADE_REVIEW_READY.json')]
    for name in ('state', 'lag', 'flow'):
        check_artifacts.extend(suite[name]['execution'][key] for key in ('stdout', 'stderr'))
    write_new(targets[1], dict(status='PASS', suites=suite, total_checks=sum(x['count'] for x in suite.values()),
        artifacts=check_artifacts, code=code, GT_opened=False, new_model_http=0, cost_usd=0,
        scope='Engineering/source/arithmetic only; not performance or physical identity qualification'))
    write_new(targets[2], dict(status='PASS', frames=265, real_mock_frames=78, actual_flow_pairs=9,
        actual_raw_endpoints=6, method_result=False, selected_state_continues=True,
        mock_H2_stage_rejection='UNSELECTED_MEMBER_OWNERSHIP', artifacts=actual_artifacts+[artifact(targets[0])],
        GT_opened=False, new_model_http=0, cost_usd=0,
        scope='Actual saved input, conditional flow, state/publication contracts; no method correctness claim'))
    print(json.dumps(dict(status='PASS', total_checks=sum(x['count'] for x in suite.values()),
        outputs=[artifact(path) for path in targets], formal_trials_run=False, GT_opened=False)))


if __name__ == '__main__':
    main()
