"""An Actions comparison cannot promote missing or incomparable live evidence."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/playtech-family-live-compare.py'
spec = importlib.util.spec_from_file_location('playtech_family_live_compare', SCRIPT)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)

BASELINE = 'a' * 40
CANDIDATE = 'b' * 40
SOURCE = 'c' * 64
DEPENDENCIES = 'd' * 64


def manifest():
    return {
        'schema': 'tester-spin/playtech-family-live-manifest/v1',
        'baseline_sha': BASELINE, 'candidate_sha': CANDIDATE,
        'budget': {'spins': 1, 'timeout': 45, 'wall_timeout': 600},
        'cases': [
            {'code': f'gpas_fixture_{n}', 'family': ('quickspin-modern' if n == 0 else
                'corosin-legacy' if n == 1 else 'corosin-modern'), 'name': f'Fixture {n}'}
            for n in range(9)
        ],
    }


def payload(status='OK', *, unknown=0, pending=0):
    identifiers = ['00000000-0000-4000-8000-000000000001']
    identifiers += [f'00000000-0000-4000-8000-{n + 2:012d}' for n in range(unknown)]
    names = ['default'] + ['buyFeatureExtraBet', 'buyFeature2ExtraBet', 'buyFeature3ExtraBet'][:unknown]
    modes = [{'id': identity, 'name': name, 'kind': 'SPIN' if n == 0 else 'UNKNOWN_FEATURE',
              'selector': name, 'bet_type': 'default', 'validated': n == 0}
             for n, (identity, name) in enumerate(zip(identifiers, names))]
    return {
        'provider': 'playtech', 'symbol': 'gpas_fixture_0', 'slug': 'game-gpas_fixture_0',
        'game_name': 'Fixture 0', 'game_url': 'https://private.invalid/?token=never-publish',
        'status': status, 'requested_spins': 2, 'successful_spins': 2, 'failed_spins': 0,
        'elapsed_ms': 2000, 'error': 'UNBOUND_STAKE_MODE:buyFeatureExtraBet' if unknown else '',
        'discovered_modes': modes,
        'attempts': [
            {'number': n + 1, 'mode_id': identifiers[0], 'mode_kind': 'SPIN', 'ok': True,
             'terminal': True, 'wire_steps': 2, 'error': '', 'endpoint': 'https://private.invalid'}
            for n in range(2)
        ],
        'structural_map': {
            'return_to_base_verified': True,
            'execution_issues': ['UNBOUND_STAKE_MODE:buyFeatureExtraBet'] if unknown else [],
            'playtech_protocol': {'contract': {'command_family': 'quickspin-modern'},
                'source_sha256': [SOURCE]},
            'pending_choice_branches': {identifiers[0]: {'ChooseFG': list(range(pending))}} if pending else {},
            'operation_inventory': {
                'schema': 'tester-spin/gpas-operation-coverage/v1',
                'modes': [dict(m, discovered=True, executable=m['kind'] != 'UNKNOWN_FEATURE',
                    attempts=2 if n == 0 else 0, verified=n == 0 and not pending,
                    choice_coverage_complete=not pending, failed_attempts=0)
                    for n, m in enumerate(modes)],
                'declared_unknown': identifiers[1:], 'missing': identifiers[:1] if pending else [],
                'disabled_not_offered': [], 'all_declared_operations_verified': not unknown and not pending,
            },
        },
    }


def private_result(status='OK', *, unknown=0, pending=0):
    result = comparison._project_payload(payload(status, unknown=unknown, pending=pending), lambda x: x)
    return {'result': result, 'fingerprints': {
        'client_source_sha256': [SOURCE], 'client_source_origin': 'bootstrap',
        'monetary_configuration_sha256': 'e' * 64,
        'monetary_configuration_origin': 'scoped-server-rows',
        'manifest_sha256': 'f' * 64,
    }, 'issues': []}


def collect_fixture(tmp_path, monkeypatch, doc, version, code, *, status='OK', unknown=0,
                    pending=0, summary_changes=None, invocation_changes=None, head=None,
                    private=None):
    input_dir = tmp_path / 'private-input' / code / version
    input_dir.mkdir(parents=True, exist_ok=True)
    sha = doc[version + '_sha']
    summary = {'schema': 'tester-spin/playtech-actions-sample/v1', 'source_commit': sha,
        'fresh_data': True, 'dry_run': False, 'spins_per_mode': doc['budget']['spins'],
        'selected': [code], 'results': [{'symbol': code, 'status': status,
            'successful_spins': 2, 'failed_spins': 0, 'requested_spins': 2}]}
    summary.update(summary_changes or {})
    (input_dir / 'summary.json').write_text(json.dumps(summary), encoding='utf-8')
    invocation = {'schema': 'tester-spin/playtech-family-live-invocation/v1',
        'version': version, 'code': code, 'source_commit': sha, 'workflow_commit': '1' * 40,
        'budget': deepcopy(doc['budget']), 'exit_code': 0, 'python_version': '3.12.8',
        'dependency_sha256': DEPENDENCIES, 'started_at': '2026-10-26T01:00:00+00:00',
        'finished_at': '2026-10-26T01:00:10+00:00'}
    invocation.update(invocation_changes or {})
    (input_dir / 'invocation.json').write_text(json.dumps(invocation), encoding='utf-8')
    monkeypatch.setattr(comparison, '_git_head', lambda _: head if head is not None else sha)
    value = private if private is not None else private_result(status, unknown=unknown, pending=pending)
    monkeypatch.setattr(comparison, '_read_private', lambda *_: deepcopy(value))
    cell = comparison.collect_cell(doc, version, code, tmp_path / 'checkout',
                                   tmp_path / 'data', input_dir, 0)
    destination = tmp_path / 'cells' / code / (version + '.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(cell), encoding='utf-8')
    return cell, destination


def full_matrix(tmp_path, monkeypatch, *, baseline='PARCIAL', candidate='OK'):
    doc = manifest()
    for case in doc['cases']:
        for version, status in [('baseline', baseline), ('candidate', candidate)]:
            collect_fixture(tmp_path, monkeypatch, doc, version, case['code'], status=status)
    return doc


def run_compare(tmp_path, doc):
    source = tmp_path / 'manifest.json'
    source.write_text(json.dumps(doc), encoding='utf-8')
    output, markdown = tmp_path / 'comparison.json', tmp_path / 'comparison.md'
    code = comparison.main(['compare', '--manifest', str(source), '--input-dir', str(tmp_path / 'cells'),
        '--output', str(output), '--markdown', str(markdown)])
    return code, json.loads(output.read_text(encoding='utf-8')), markdown.read_text(encoding='utf-8')


def test_family_counts_and_compound_modes_are_visible(tmp_path, monkeypatch):
    doc = full_matrix(tmp_path, monkeypatch)
    collect_fixture(tmp_path, monkeypatch, doc, 'candidate', 'gpas_fixture_0',
                    status='PARCIAL', unknown=3, pending=2)
    code, report, markdown = run_compare(tmp_path, doc)
    assert code != 0
    assert report['summary']['expected_cells'] == report['summary']['received_cells'] == 18
    assert report['summary']['baseline']['statuses']['PARCIAL'] == 9
    assert report['summary']['candidate']['statuses']['OK'] == 8
    assert report['summary']['candidate']['statuses']['PARCIAL'] == 1
    assert report['summary']['transitions']['PARCIAL->OK'] == 8
    quickspin = next(f for f in report['families'] if f['family'] == 'quickspin-modern')
    assert quickspin['candidate']['metrics']['modes_unknown'] == 3
    assert quickspin['candidate']['metrics']['pending_choice_branches'] == 2
    assert quickspin['delta']['modes_unknown'] == 3
    assert quickspin['candidate']['metrics']['rounds_verified'] == 2
    assert report['games'][0]['candidate']['live_contract_family'] == 'quickspin-modern'
    assert 'buyFeature3ExtraBet' in markdown
    assert 'PARCIAL' in markdown and 'quickspin-modern' in markdown


def test_complete_valid_all_ok_matrix_can_pass(tmp_path, monkeypatch):
    doc = full_matrix(tmp_path, monkeypatch)
    code, report, _ = run_compare(tmp_path, doc)
    assert code == 0
    assert report['passed'] is True
    assert report['summary']['attribution_eligible_pairs'] == 9
    assert report['summary']['attributable_transitions']['PARCIAL->OK'] == 9


def test_missing_result_is_not_counted_as_ok_and_outputs_always_exist(tmp_path, monkeypatch):
    doc = full_matrix(tmp_path, monkeypatch)
    (tmp_path / 'cells/gpas_fixture_2/candidate.json').unlink()
    code, report, markdown = run_compare(tmp_path, doc)
    assert code != 0
    assert report['summary']['missing_cells'] == 1
    assert report['summary']['candidate']['statuses']['MISSING'] == 1
    assert report['games'][2]['candidate']['status'] == 'MISSING'
    assert 'MISSING' in markdown


def test_duplicate_cell_does_not_select_optimistic_result(tmp_path, monkeypatch):
    doc = full_matrix(tmp_path, monkeypatch)
    original = tmp_path / 'cells/gpas_fixture_2/candidate.json'
    (original.parent / 'second.json').write_bytes(original.read_bytes())
    code, report, _ = run_compare(tmp_path, doc)
    assert code != 0
    assert report['summary']['duplicate_cells'] == 1
    assert report['games'][2]['candidate']['status'] == 'ERROR'


@pytest.mark.parametrize('fingerprint', ['client_source_sha256', 'monetary_configuration_sha256', 'manifest_sha256'])
def test_different_live_sources_are_not_attributed_to_code(tmp_path, monkeypatch, fingerprint):
    doc = full_matrix(tmp_path, monkeypatch)
    path = tmp_path / 'cells/gpas_fixture_2/candidate.json'
    cell = json.loads(path.read_text())
    cell['fingerprints'][fingerprint] = ['9' * 64] if fingerprint == 'client_source_sha256' else '9' * 64
    path.write_text(json.dumps(cell))
    _, report, markdown = run_compare(tmp_path, doc)
    assert report['summary']['transitions']['PARCIAL->OK'] == 9
    assert report['summary']['attributable_transitions']['PARCIAL->OK'] == 8
    assert report['games'][2]['comparison']['attribution_eligible'] is False
    assert 'MISMATCH' in markdown


def test_different_configuration_origins_are_unknown_not_economic_drift(tmp_path, monkeypatch):
    doc = full_matrix(tmp_path, monkeypatch)
    path = tmp_path / 'cells/gpas_fixture_2/candidate.json'
    cell = json.loads(path.read_text())
    cell['fingerprints']['monetary_configuration_origin'] = 'resolved-default'
    cell['fingerprints']['monetary_configuration_sha256'] = '9' * 64
    path.write_text(json.dumps(cell))
    _, report, _ = run_compare(tmp_path, doc)
    assert report['games'][2]['comparison']['configuration_match'] == 'MISSING_EVIDENCE'
    assert report['games'][2]['comparison']['attribution_eligible'] is False


@pytest.mark.parametrize('candidate_status', ['PARCIAL', 'ERROR'])
def test_baseline_ok_to_any_non_ok_is_a_regression(tmp_path, monkeypatch, candidate_status):
    doc = full_matrix(tmp_path, monkeypatch, baseline='OK')
    collect_fixture(tmp_path, monkeypatch, doc, 'candidate', 'gpas_fixture_1', status=candidate_status)
    code, report, _ = run_compare(tmp_path, doc)
    assert code != 0
    assert report['summary']['regressions'] == 1
    assert report['games'][1]['regression'] is True


@pytest.mark.parametrize('changes', [
    {'source_commit': BASELINE}, {'spins_per_mode': 2}, {'selected': ['gpas_fixture_8']},
    {'fresh_data': False}, {'dry_run': True},
])
def test_collect_rejects_inconsistent_summary_provenance(tmp_path, monkeypatch, changes):
    cell, _ = collect_fixture(tmp_path, monkeypatch, manifest(), 'candidate', 'gpas_fixture_0',
                              summary_changes=changes)
    assert cell['validation']['valid'] is False
    assert cell['result']['status'] != 'OK'


def test_collect_rejects_mislabeled_checkout_and_budget(tmp_path, monkeypatch):
    doc = manifest()
    cell, _ = collect_fixture(tmp_path, monkeypatch, doc, 'candidate', 'gpas_fixture_0', head=BASELINE)
    assert 'CHECKOUT_SHA_MISMATCH' in cell['validation']['issues']
    cell, _ = collect_fixture(tmp_path, monkeypatch, doc, 'candidate', 'gpas_fixture_0',
        invocation_changes={'budget': dict(doc['budget'], wall_timeout=300)})
    assert 'INVOCATION_BUDGET_MISMATCH' in cell['validation']['issues']
    assert cell['result']['status'] == 'ERROR'


def test_compare_revalidates_ref_instead_of_trusting_valid_flag(tmp_path, monkeypatch):
    doc = full_matrix(tmp_path, monkeypatch)
    path = tmp_path / 'cells/gpas_fixture_4/candidate.json'
    cell = json.loads(path.read_text())
    cell['checkout_sha'] = BASELINE
    cell['validation']['valid'] = True
    path.write_text(json.dumps(cell))
    code, report, _ = run_compare(tmp_path, doc)
    assert code != 0
    assert report['summary']['invalid_cells'] == 1
    assert report['games'][4]['candidate']['status'] == 'ERROR'


def test_collect_missing_db_result_preserves_missing_status(tmp_path, monkeypatch):
    cell, _ = collect_fixture(tmp_path, monkeypatch, manifest(), 'candidate', 'gpas_fixture_0',
        private={'result': None, 'fingerprints': {}, 'issues': ['RESULT_MISSING']})
    assert cell['validation']['valid'] is False
    assert cell['result']['status'] == 'MISSING'


def test_projection_retains_mode_semantics_but_no_urls_or_original_identifiers():
    value = payload('PARCIAL', unknown=3, pending=2)
    identity = value['discovered_modes'][0]['id']
    value['attempts'][0]['error'] = 'CHOICE_BRANCHES_PENDING:' + identity + ' https://secret.invalid/a?token=canary'
    value['structural_map']['execution_issues'] += ['sessionId=private-canary', 'authorization: Bearer private-bearer']
    projected = comparison._project_payload(value, lambda x: x)
    serialized = json.dumps(projected)
    for secret in (identity, 'https://', 'private-canary', 'private-bearer', 'never-publish'):
        assert secret not in serialized
    assert 'buyFeature3ExtraBet' in serialized
    assert projected['attempts'][0]['mode_kind'] == 'SPIN'
    assert projected['pending_choice_branches'][0]['option_count'] == 2


def test_bootstrap_fingerprint_survives_missing_client_contract(tmp_path):
    value = payload('PARCIAL')
    value['structural_map'].pop('playtech_protocol')
    bootstrap = {'manifest': {'gameCode': 'gpas_fixture_0', 'env': {'glu6': True, 'game': '1.4.0'},
        'javascript': ['https://private.invalid/code.js?token=never']},
        'source_sha256': [SOURCE], 'contract': None}
    (tmp_path / 'bootstrap.json').write_text(json.dumps(bootstrap))
    rows = [{'scope': {'betType': 'default'}, 'content': {'game': {
        'baseCostMultipliers': [1, 25], 'defaultBaseCostMultiplier': 25,
        'costConfiguration': [{'uuid': 'private-one', 'name': 'default', 'cost': 4}]}}}]
    def write_har(data):
        frame = {'direction': 'received', 'payload': '3:::' + json.dumps({'data': {
            '_type': 'com.pt.gpas.config.GetGameConfigurationResponse', 'data': data}})}
        (tmp_path / 'session.har').write_text(json.dumps({'log': {'_warpWebSockets': [frame], 'entries': []}}))
    write_har(rows)
    first = comparison._fingerprints(value, tmp_path)
    assert first['client_source_sha256'] == [SOURCE]
    assert first['client_source_origin'] == 'bootstrap'
    assert first['monetary_configuration_origin'] == 'scoped-server-rows'
    assert len(first['monetary_configuration_sha256']) == 64
    rows[0]['content']['game']['costConfiguration'][0]['uuid'] = 'private-two'
    write_har(rows)
    second = comparison._fingerprints(value, tmp_path)
    assert first == second
    rows[0]['content']['game']['costConfiguration'][0]['cost'] = 5
    write_har(rows)
    assert comparison._fingerprints(value, tmp_path)['monetary_configuration_sha256'] != first['monetary_configuration_sha256']


def test_compare_runs_without_importing_project_dependencies(tmp_path):
    doc = manifest()
    code, report, markdown = run_compare(tmp_path, doc)
    assert code != 0
    assert report['summary']['missing_cells'] == 18
    assert 'MISSING' in markdown


def test_collect_never_copies_invalid_provenance_values_to_public_cell(tmp_path, monkeypatch):
    value = 'https://secret.invalid/session/private-canary'
    cell, _ = collect_fixture(tmp_path, monkeypatch, manifest(), 'candidate', 'gpas_fixture_0',
        summary_changes={'source_commit': value, 'selected': [value]},
        invocation_changes={'workflow_commit': value, 'dependency_sha256': value, 'started_at': value,
            'budget': {'spins': 1, 'timeout': 45, 'wall_timeout': 600, 'session': 'private-canary'}})
    assert cell['validation']['valid'] is False
    assert 'private-canary' not in json.dumps(cell)
    assert 'https://' not in json.dumps(cell)


def test_boolean_budget_is_not_equal_to_one_spin(tmp_path, monkeypatch):
    doc = manifest()
    cell, _ = collect_fixture(tmp_path, monkeypatch, doc, 'candidate', 'gpas_fixture_0',
        invocation_changes={'budget': dict(doc['budget'], spins=True)})
    assert cell['validation']['valid'] is False


def test_one_malformed_cell_does_not_erase_other_seventeen_results(tmp_path, monkeypatch):
    doc = full_matrix(tmp_path, monkeypatch)
    path = tmp_path / 'cells/gpas_fixture_4/candidate.json'
    cell = json.loads(path.read_text())
    cell['result'] = ['invalid-result']
    path.write_text(json.dumps(cell))
    code, report, _ = run_compare(tmp_path, doc)
    assert code != 0
    assert report['summary']['invalid_cells'] == 1
    assert report['summary']['candidate']['statuses']['OK'] == 8


def test_dependency_mismatch_is_separate_from_observed_improvement(tmp_path, monkeypatch):
    doc = full_matrix(tmp_path, monkeypatch)
    path = tmp_path / 'cells/gpas_fixture_4/candidate.json'
    cell = json.loads(path.read_text())
    cell['invocation']['dependency_sha256'] = '9' * 64
    path.write_text(json.dumps(cell))
    code, report, _ = run_compare(tmp_path, doc)
    assert code != 0
    assert report['games'][4]['comparison']['environment_match'] == 'MISMATCH'
    assert report['summary']['transitions']['PARCIAL->OK'] == 9
    assert report['summary']['attributable_transitions']['PARCIAL->OK'] == 8


def test_scope_and_actual_stake_are_preserved_without_private_declaration():
    value = payload('PARCIAL')
    mode = value['discovered_modes'][0]
    mode.update(cost=120, multiplier=50, declaration={'uuid': 'private-id'},
                configuration_context={'betType': 'default', 'featureType': 'buyFeature9', 'token': 'private-canary'})
    result = comparison._project_payload(value, lambda x: x)
    actual = result['discovered_modes'][0]
    assert actual['cost'] == 120 and actual['multiplier'] == 50 and actual['stake'] == 6000
    assert actual['configuration_context'] == {'betType': 'default', 'featureType': 'buyFeature9'}
    assert 'private-canary' not in json.dumps(result)
    assert 'declaration' not in actual


def test_real_checkout_storage_read_is_isolated_read_only_and_sanitized(tmp_path):
    data = tmp_path / 'data'
    run = data / 'providers/playtech/fixture/analysis/runs/run'
    run.mkdir(parents=True)
    value = payload('PARCIAL', unknown=3)
    value['run_dir'] = str(run)
    value['structural_map'].pop('playtech_protocol')
    (run / 'bootstrap.json').write_text(json.dumps({'source_sha256': [SOURCE],
        'contract': None, 'manifest': {'gameCode': 'gpas_fixture_0', 'env': {'game': '1.4.0'}}}))
    database = data / 'tester-spin.sqlite3'
    with sqlite3.connect(database) as connection:
        connection.executescript('CREATE TABLE test_results(id INTEGER PRIMARY KEY, provider TEXT, slug TEXT, payload_json TEXT);'
            'CREATE TABLE manual_validations(result_id INTEGER PRIMARY KEY, approved_at TEXT, note TEXT);')
        connection.execute('INSERT INTO test_results VALUES(1, ?, ?, ?)',
                           ('playtech', value['slug'], json.dumps(value)))
    original = database.read_bytes()
    before = set(data.rglob('*'))
    result = comparison._read_private(ROOT, data, 'gpas_fixture_0')
    assert result['result']['status'] == 'PARCIAL'
    assert result['result']['live_contract_family'] is None
    assert result['fingerprints']['client_source_sha256'] == [SOURCE]
    assert database.read_bytes() == original
    assert set(data.rglob('*')) == before
    assert 'https://' not in json.dumps(result)
    assert value['discovered_modes'][0]['id'] not in json.dumps(result)


@pytest.mark.parametrize('semantic_change', ['starting_mode', 'named_selector'])
def test_configuration_fingerprint_detects_semantic_binding_changes(semantic_change):
    configuration = {'game': {
        'baseCostMultipliers': [1, 25],
        'namedScopes': {'buyFeature1': {'betType': 'default', 'featureType': 'buyFeature1'}},
        'costConfiguration': [{'uuid': 'session-local-cost-id', 'name': 'buyFeature1', 'cost': 100,
                               'parameters': {'startingMode': 'Standard', 'startingPlays': '1'}}],
    }}
    original = comparison._hash(comparison._monetary_configuration(configuration))
    if semantic_change == 'starting_mode':
        configuration['game']['costConfiguration'][0]['parameters']['startingMode'] = 'Bonus'
    else:
        configuration['game']['namedScopes']['buyFeature1']['featureType'] = 'buyFeature2'
    assert comparison._hash(comparison._monetary_configuration(configuration)) != original
