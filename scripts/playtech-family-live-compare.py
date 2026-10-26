"""Collect private Actions results and compare the fixed GPAS family cohort.

This script never launches a game. ``compare`` uses only the standard library;
``collect`` imports the tested checkout's Storage and publication sanitizer in
an isolated child interpreter, opens its existing database read-only, and emits
an allowlisted projection. Cohort labels are historical, not client bindings.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import threading


MANIFEST_SCHEMA = 'tester-spin/playtech-family-live-manifest/v1'
CELL_SCHEMA = 'tester-spin/playtech-family-live-cell/v1'
REPORT_SCHEMA = 'tester-spin/playtech-family-live-compare/v1'
INVOCATION_SCHEMA = 'tester-spin/playtech-family-live-invocation/v1'
SAMPLE_SCHEMA = 'tester-spin/playtech-actions-sample/v1'
VERSIONS = ('baseline', 'candidate')
STATUSES = ('OK', 'PARCIAL', 'ERROR', 'MISSING')
KINDS = ('SPIN', 'ANTE_BET', 'PURCHASE', 'UNKNOWN_FEATURE')
EXECUTABLE = frozenset(KINDS[:3])
METRICS = ('modes_discovered', 'modes_recognized', 'modes_verified', 'modes_unknown',
           'modes_pending', 'pending_choice_branches', 'rounds_requested',
           'rounds_attempted', 'rounds_verified', 'rounds_failed', 'wire_steps')
SHA40 = re.compile(r'[0-9a-f]{40}\Z')
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
URL = re.compile(r'(?i)\b(?:https?|wss?)://[^\s<>"\']+')
UUID = re.compile(r'(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b')
OPAQUE = re.compile(r'(?i)\b[0-9a-f]{24,}\b|\b(?=[A-Za-z0-9_+/-]{32,}\b)(?=[A-Za-z0-9_+/-]*\d)[A-Za-z0-9_+/-]+\b')
SECRET = re.compile(r'(?i)(?:authorization\s*[:=]\s*(?:bearer|basic)\s+\S+|'
                    r'(?:[\w-]*(?:token|session|password|cookie|secret)[\w-]*|'
                    r'correlationId|username|userId|connectionId|gamecycle|sid|api[_-]?key)\s*[:=]\s*[^\s;,]+)')


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _load(path, maximum=16 * 1024 * 1024):
    if path.stat().st_size > maximum:
        raise ValueError('INPUT_TOO_LARGE')
    return json.loads(path.read_text(encoding='utf-8'),
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def _text(value, aliases=None):
    if not isinstance(value, str):
        return ''
    for identity, alias in (aliases or {}).items():
        if len(identity) >= 8:
            value = value.replace(identity, alias)
    value = URL.sub('[URL]', value)
    value = SECRET.sub('[REDACTED]', value)
    value = UUID.sub('[ID]', value)
    value = OPAQUE.sub('[ID]', value)
    return ' '.join(value.split())[:1000]


def _number(value, default=0):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else default


def _count(value):
    return value if type(value) is int and value >= 0 else 0


def _rows(value):
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _strings(value):
    return [_text(item) for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _budget_matches(value, expected):
    return (isinstance(value, dict) and set(value) == set(expected)
            and all(type(value[key]) is int and value[key] == expected[key] for key in expected))


def _public_provenance(value):
    """Invalid metadata is useful as a diagnostic, never as arbitrary text."""
    output = {}
    patterns = {
        'source_commit': SHA40, 'workflow_commit': SHA40, 'dependency_sha256': SHA256,
        'python_version': re.compile(r'\d+\.\d+\.\d+\Z'),
        'code': re.compile(r'gpas_[A-Za-z0-9_]+\Z'),
        'started_at': re.compile(r'\d{4}-\d{2}-\d{2}T[0-9:.]+(?:Z|[+-][0-9:]+)\Z'),
        'finished_at': re.compile(r'\d{4}-\d{2}-\d{2}T[0-9:.]+(?:Z|[+-][0-9:]+)\Z'),
    }
    for key, item in value.items():
        if key in patterns:
            output[key] = item if isinstance(item, str) and patterns[key].fullmatch(item) else None
        elif key == 'schema':
            output[key] = item if item in (SAMPLE_SCHEMA, INVOCATION_SCHEMA) else None
        elif key == 'version':
            output[key] = item if item in VERSIONS else None
        elif key in ('fresh_data', 'dry_run'):
            output[key] = item if type(item) is bool else None
        elif key in ('spins_per_mode', 'exit_code'):
            output[key] = item if type(item) is int else None
        elif key == 'selected':
            output[key] = [x for x in item if isinstance(x, str) and patterns['code'].fullmatch(x)] if isinstance(item, list) else None
        elif key == 'budget':
            output[key] = {k: v if type(v) is int else None for k, v in _mapping(item).items()
                           if k in ('spins', 'timeout', 'wall_timeout')}
    return output


def _stake_fields(row):
    cost = row.get('cost') if type(row.get('cost')) is int and row['cost'] > 0 else None
    multiplier = row.get('multiplier') if type(row.get('multiplier')) is int and row['multiplier'] > 0 else None
    context = _mapping(row.get('configuration_context'))
    return {'cost': cost, 'multiplier': multiplier,
            'stake': cost * multiplier if cost is not None and multiplier is not None else None,
            'configuration_context': {key: _text(context[key]) for key in ('betType', 'featureType')
                                      if isinstance(context.get(key), str)}}


def _validate_manifest(value):
    if not isinstance(value, dict) or value.get('schema') != MANIFEST_SCHEMA:
        raise ValueError('MANIFEST_SCHEMA_INVALID')
    if any(not isinstance(value.get(v + '_sha'), str) or not SHA40.fullmatch(value[v + '_sha']) for v in VERSIONS):
        raise ValueError('MANIFEST_REF_INVALID')
    if value['baseline_sha'] == value['candidate_sha']:
        raise ValueError('MANIFEST_REFS_IDENTICAL')
    budget = value.get('budget')
    if (not isinstance(budget, dict) or set(budget) != {'spins', 'timeout', 'wall_timeout'}
            or any(type(n) is not int or n < 1 for n in budget.values())):
        raise ValueError('MANIFEST_BUDGET_INVALID')
    cases = value.get('cases')
    if not isinstance(cases, list) or len(cases) != 9:
        raise ValueError('MANIFEST_REQUIRES_NINE_CASES')
    for case in cases:
        if (not isinstance(case, dict)
                or not re.fullmatch(r'gpas_[A-Za-z0-9_]+', str(case.get('code', '')))
                or not re.fullmatch(r'[a-z][a-z0-9-]{0,79}', str(case.get('family', '')))
                or not isinstance(case.get('name'), str) or not case['name']
                or _text(case['name']) != case['name']):
            raise ValueError('MANIFEST_CASE_INVALID')
    if len({case['code'] for case in cases}) != 9:
        raise ValueError('MANIFEST_CASE_DUPLICATE')
    return value


def _manifest_hash(manifest):
    return _hash({key: manifest[key] for key in ('schema', 'baseline_sha', 'candidate_sha', 'budget', 'cases')})


def _project_payload(payload, public_value):
    """Publish names and kinds; turn opaque mode keys into per-result aliases."""
    structural = payload.get('structural_map') or {}
    inventory = structural.get('operation_inventory') or {}
    discovered = _rows(payload.get('discovered_modes'))
    inventory_rows = _rows(inventory.get('modes'))
    attempts = _rows(payload.get('attempts'))
    pending = structural.get('pending_choice_branches') or {}
    aliases, names = {}, {}

    def alias(identity):
        if not isinstance(identity, str) or not identity:
            return 'mode-unbound'
        if identity not in aliases:
            aliases[identity] = f'mode-{len(aliases) + 1:03d}'
        return aliases[identity]

    for row in discovered + inventory_rows:
        alias(row.get('id'))
        if isinstance(row.get('id'), str):
            names[row['id']] = _text(row.get('name'))
    for attempt in attempts:
        alias(attempt.get('mode_id'))
    if isinstance(pending, dict):
        for identity in pending:
            alias(identity)

    def mode(row):
        return {'mode': alias(row.get('id')), 'name': _text(row.get('name'), aliases),
                'kind': row.get('kind') if row.get('kind') in KINDS else 'UNKNOWN_FEATURE'}

    safe_modes = [dict(mode(row), **_stake_fields(row), selector=_text(row.get('selector'), aliases),
                       bet_type=_text(row.get('bet_type'), aliases), validated=row.get('validated') is True)
                  for row in discovered]
    safe_inventory = [dict(mode(row), executable=row.get('executable') is True,
        attempts=_count(row.get('attempts')), verified=row.get('verified') is True,
        choice_coverage_complete=row.get('choice_coverage_complete') is True,
        failed_attempts=_count(row.get('failed_attempts'))) for row in inventory_rows]
    safe_pending = []
    if isinstance(pending, dict):
        for identity, phases in pending.items():
            if not isinstance(phases, dict):
                continue
            for phase, options in phases.items():
                if isinstance(options, list):
                    safe_pending.append({'mode': alias(identity), 'name': names.get(identity, ''),
                        'phase': _text(phase, aliases), 'option_count': len(options)})
    protocol = structural.get('playtech_protocol') or {}
    contract = protocol.get('contract') or {}
    family = contract.get('command_family')
    live_family = family if isinstance(family, str) and re.fullmatch(r'[a-z][a-z0-9-]{0,79}', family) else None
    result = {
        'status': payload.get('status') if payload.get('status') in STATUSES else 'ERROR',
        'reported_status': payload.get('status') if payload.get('status') in STATUSES + ('DETENIDO', 'PENDIENTE') else 'UNRECOGNIZED',
        'requested_spins': _count(payload.get('requested_spins')),
        'successful_spins': _count(payload.get('successful_spins')),
        'failed_spins': _count(payload.get('failed_spins')),
        'elapsed_ms': _number(payload.get('elapsed_ms')),
        'error': _text(payload.get('error'), aliases),
        'execution_issues': [_text(x, aliases) for x in structural.get('execution_issues', []) if isinstance(x, str)],
        'return_to_base_verified': structural.get('return_to_base_verified') is True,
        'live_contract_family': live_family,
        'discovered_modes': safe_modes,
        'attempts': [{'number': _count(row.get('number')), 'mode': alias(row.get('mode_id')),
            'name': names.get(row.get('mode_id'), ''),
            'mode_kind': row.get('mode_kind') if row.get('mode_kind') in KINDS else 'UNKNOWN_FEATURE',
            'ok': row.get('ok') is True, 'terminal': row.get('terminal') is True,
            'wire_steps': _count(row.get('wire_steps')), 'error': _text(row.get('error'), aliases),
            'warning': _text(row.get('warning'), aliases)} for row in attempts],
        'operation_inventory': {
            'schema': 'tester-spin/gpas-operation-coverage/v1', 'modes': safe_inventory,
            'expected_by_kind': {kind: sum(row['executable'] and row['kind'] == kind for row in safe_inventory) for kind in KINDS[:3]},
            'verified_by_kind': {kind: sum(row['verified'] and row['kind'] == kind for row in safe_inventory) for kind in KINDS[:3]},
            'declared_unknown': [row['mode'] for row in safe_inventory if row['kind'] == 'UNKNOWN_FEATURE'],
            'missing': [row['mode'] for row in safe_inventory if row['executable'] and not row['verified']],
            'disabled_not_offered': _strings(inventory.get('disabled_not_offered')),
            'all_declared_operations_verified': inventory.get('all_declared_operations_verified') is True,
        },
        'pending_choice_branches': safe_pending,
    }
    return public_value(result)


def _metrics(result):
    result = _mapping(result)
    modes = _rows(result.get('discovered_modes'))
    inventory = _rows((result.get('operation_inventory') or {}).get('modes'))
    attempts = _rows(result.get('attempts'))
    return {
        'modes_discovered': len(modes),
        'modes_recognized': sum(row.get('kind') in EXECUTABLE for row in modes),
        'modes_verified': sum(row.get('verified') is True for row in inventory),
        'modes_unknown': sum(row.get('kind') == 'UNKNOWN_FEATURE' for row in modes),
        'modes_pending': sum(row.get('verified') is not True for row in inventory),
        'pending_choice_branches': sum(_count(row.get('option_count')) for row in _rows(result.get('pending_choice_branches'))),
        'rounds_requested': _count(result.get('requested_spins')),
        'rounds_attempted': len(attempts),
        'rounds_verified': sum(row.get('ok') is True and row.get('terminal') is True for row in attempts),
        'rounds_failed': sum(row.get('ok') is not True for row in attempts),
        'wire_steps': sum(_count(row.get('wire_steps')) for row in attempts),
    }


def _empty_result(status='MISSING'):
    return _project_payload({'status': status}, lambda x: x)


def _source_hashes(value):
    if isinstance(value, list) and value and all(isinstance(x, str) and SHA256.fullmatch(x) for x in value):
        return list(value)
    return []


def _monetary_configuration(configuration):
    """No UUID, player balance, session, or personal settings enter this hash."""
    if not isinstance(configuration, dict):
        return {}
    selected = {}
    game = configuration.get('game')
    if isinstance(game, dict):
        fields = ('baseCostMultipliers', 'defaultBaseCostMultiplier', 'coinSizes', 'defaultCoinSize',
                  'minBet', 'maxBet', 'featureBetEnabled', 'extraBetEnabled', 'powerPlayEnabled',
                  'activeBetOptions', 'namedScopes')
        selected['game'] = {key: game[key] for key in fields if key in game}
        if isinstance(game.get('costConfiguration'), list):
            selected['game']['costConfiguration'] = [
                {key: row[key] for key in ('name', 'cost', 'parameters') if key in row}
                for row in _rows(game['costConfiguration'])]
    if isinstance(configuration.get('limits'), dict):
        selected['limits'] = {key: configuration['limits'][key] for key in
                              ('minBet', 'maxBet', 'currency', 'currencyCode', 'decimalPlaces')
                              if key in configuration['limits']}
    return selected


def _har_configurations(path):
    document = _load(path, 256 * 1024 * 1024)
    log = document.get('log', {})
    frames = list(log.get('_warpWebSockets') or [])
    for entry in _rows(log.get('entries')):
        frames.extend(entry.get('_webSocketFrames') or entry.get('_webSocketMessages') or [])
    configurations = []
    for frame in _rows(frames):
        if frame.get('direction', 'received') not in ('received', 'recv', 'in'):
            continue
        raw = frame.get('payloadData', frame.get('payload', frame.get('data')))
        if not isinstance(raw, str):
            continue
        try:
            packet = json.loads(raw[4:] if raw.startswith('3:::') else raw)
        except ValueError:
            continue
        data = packet.get('data') if isinstance(packet, dict) else None
        if not isinstance(data, dict) or not str(data.get('_type', '')).endswith('GetGameConfigurationResponse'):
            continue
        if not isinstance(data.get('data'), list):
            continue
        rows = []
        for row in _rows(data['data']):
            scope = row.get('scope') or {}
            content = _monetary_configuration(row.get('content'))
            if content and isinstance(scope, dict):
                rows.append({'scope': {key: scope[key] for key in ('betType', 'featureType') if key in scope},
                             'content': content})
        if rows:
            configurations.append(rows)
    return configurations


def _fingerprints(payload, run):
    protocol = (payload.get('structural_map') or {}).get('playtech_protocol') or {}
    bootstrap = {}
    if run is not None and (run / 'bootstrap.json').is_file():
        try:
            bootstrap = _load(run / 'bootstrap.json')
        except (OSError, ValueError):
            pass
    if not isinstance(bootstrap, dict):
        bootstrap = {}
    source_hashes = _source_hashes(protocol.get('source_sha256'))
    origin = 'protocol' if source_hashes else None
    boot_hashes = _source_hashes(bootstrap.get('source_sha256'))
    consistent = not source_hashes or not boot_hashes or source_hashes == boot_hashes
    if not source_hashes and boot_hashes:
        source_hashes, origin = boot_hashes, 'bootstrap'
    raw_configurations = []
    if run is not None:
        for har in sorted(run.rglob('session.har'))[:128]:
            if not har.resolve().is_relative_to(run.resolve()):
                continue
            try:
                raw_configurations.extend(_har_configurations(har))
            except (OSError, ValueError, TypeError, AttributeError):
                continue
    configuration_hash, configuration_origin = None, None
    if raw_configurations:
        # A retry count is not a configuration change. Scope order and economic
        # arrays are retained, while byte-identical declarations are deduplicated.
        configuration_hash = _hash(sorted({_hash(value) for value in raw_configurations}))
        configuration_origin = 'scoped-server-rows'
    else:
        resolved = _monetary_configuration(bootstrap.get('configuration', protocol.get('configuration')))
        if resolved:
            configuration_hash, configuration_origin = _hash(resolved), 'resolved-default'
    manifest = bootstrap.get('manifest')
    manifest_projection = {}
    if isinstance(manifest, dict):
        for key in ('gameCode', 'version', 'supportedContexts'):
            if key in manifest:
                manifest_projection[key] = manifest[key]
        for section, keys in {
            'env': ('glu6', 'glu', 'game', 'cli'),
            'setup': ('useExtendedBetApi', 'usesLegacyBalanceApi', 'useLegacyBoot',
                      'usesScopedConfiguration', 'supportsFs2Bonus', 'handlesGameCycleEnd', 'gameSuite'),
        }.items():
            if isinstance(manifest.get(section), dict):
                manifest_projection[section] = {key: manifest[section][key] for key in keys if key in manifest[section]}
    return {'client_source_sha256': source_hashes, 'client_source_origin': origin,
            'client_sources_consistent': consistent,
            'monetary_configuration_sha256': configuration_hash,
            'monetary_configuration_origin': configuration_origin,
            'manifest_sha256': _hash(manifest_projection) if manifest_projection else None,
            'projection_schema': 'tester-spin/live-fingerprints/allowlist-v1'}


def _read_private_local(checkout, data_root, code):
    """Called only in the isolated interpreter, with the tested checkout first."""
    from tester_spin.storage import Storage
    from tester_spin.run_result_publisher import _public_value
    for name in ('tester_spin.storage', 'tester_spin.run_result_publisher'):
        if not Path(sys.modules[name].__file__).resolve().is_relative_to(checkout.resolve()):
            raise ValueError('CHECKOUT_IMPORT_MISMATCH')
    database = data_root / 'tester-spin.sqlite3'
    if not database.is_file():
        return {'result': None, 'fingerprints': {}, 'issues': ['RESULT_MISSING']}

    class ReadOnlyStorage(Storage):
        def __init__(self, path):
            self.path, self._lock = path, threading.RLock()

        @contextmanager
        def _connect(self):
            connection = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True)
            connection.row_factory = sqlite3.Row
            try:
                yield connection
            finally:
                connection.close()

    rows = ReadOnlyStorage(database).latest_results('playtech')
    matching = [row for row in rows if row.get('symbol') == code and row.get('provider') == 'playtech']
    if len(matching) != 1:
        return {'result': None, 'fingerprints': {}, 'issues': ['RESULT_MISSING' if not matching else 'RESULT_DUPLICATE']}
    payload = matching[0]
    issues = ['DATA_ROOT_NOT_ISOLATED'] if len(rows) != 1 else []
    run = None
    if isinstance(payload.get('run_dir'), str) and payload['run_dir']:
        candidate = Path(payload['run_dir']).resolve()
        if candidate.is_relative_to(data_root.resolve()) and candidate.is_dir():
            run = candidate
        else:
            issues.append('RUN_DIRECTORY_INVALID')
    return {'result': _project_payload(payload, _public_value),
            'fingerprints': _fingerprints(payload, run), 'issues': issues}


def _read_private(checkout, data_root, code):
    runner = (
        'import importlib.util,json,sys; from pathlib import Path; '
        'spec=importlib.util.spec_from_file_location("family_compare",sys.argv[1]); '
        'module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); '
        'sys.path.insert(0,sys.argv[2]); '
        'print(json.dumps(module._read_private_local(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4]),allow_nan=False))'
    )
    completed = subprocess.run([sys.executable, '-I', '-B', '-c', runner, str(Path(__file__).resolve()),
        str(checkout.resolve()), str(data_root.resolve()), code], capture_output=True, text=True,
        timeout=120, check=False)
    if completed.returncode:
        raise ValueError('PRIVATE_RESULT_READ_FAILED')
    return json.loads(completed.stdout)


def _git_head(checkout):
    completed = subprocess.run(['git', '-C', str(checkout), 'rev-parse', 'HEAD'],
                               capture_output=True, text=True, timeout=15, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else ''


def _invocation_issues(invocation, manifest, version, code, exit_code):
    invocation = _mapping(invocation)
    issues = []
    expected = {'schema': INVOCATION_SCHEMA, 'version': version, 'code': code,
                'source_commit': manifest[version + '_sha'], 'budget': manifest['budget'], 'exit_code': exit_code}
    for key, value in expected.items():
        if invocation.get(key) != value or type(invocation.get(key)) is not type(value):
            issues.append('INVOCATION_' + key.upper() + '_MISMATCH')
    if not _budget_matches(invocation.get('budget'), manifest['budget']):
        issues.append('INVOCATION_BUDGET_MISMATCH')
    if not isinstance(invocation.get('dependency_sha256'), str) or not SHA256.fullmatch(invocation['dependency_sha256']):
        issues.append('INVOCATION_DEPENDENCIES_MISSING')
    if not isinstance(invocation.get('workflow_commit'), str) or not SHA40.fullmatch(invocation['workflow_commit']):
        issues.append('INVOCATION_WORKFLOW_REF_INVALID')
    if not re.fullmatch(r'\d+\.\d+\.\d+', str(invocation.get('python_version', ''))):
        issues.append('INVOCATION_PYTHON_INVALID')
    try:
        started = datetime.fromisoformat(invocation['started_at'].replace('Z', '+00:00'))
        finished = datetime.fromisoformat(invocation['finished_at'].replace('Z', '+00:00'))
        if started.tzinfo is None or finished.tzinfo is None or finished < started:
            raise ValueError('invalid time')
    except (KeyError, TypeError, ValueError, AttributeError):
        issues.append('INVOCATION_TIMING_INVALID')
    return issues


def _result_issues(result):
    issues = []
    if not isinstance(result, dict) or result.get('status') not in STATUSES:
        return ['RESULT_INVALID']
    if (any(not isinstance(result.get(key), list) for key in
            ('discovered_modes', 'attempts', 'pending_choice_branches', 'execution_issues'))
            or not isinstance(result.get('operation_inventory'), dict)):
        return ['RESULT_INVALID']
    if result['status'] == 'MISSING':
        return ['RESULT_MISSING']
    metrics = _metrics(result)
    if (result.get('successful_spins') != metrics['rounds_verified'] or
            (metrics['rounds_attempted'] and result.get('failed_spins') != metrics['rounds_failed'])):
        issues.append('RESULT_ROUND_COUNTS_INCONSISTENT')
    if result['status'] == 'OK' and (
            not metrics['rounds_verified'] or metrics['rounds_failed'] or metrics['modes_unknown']
            or metrics['modes_pending'] or metrics['pending_choice_branches']
            or result.get('return_to_base_verified') is not True or result.get('error')
            or result.get('execution_issues')
            or (result.get('operation_inventory') or {}).get('all_declared_operations_verified') is not True):
        issues.append('RESULT_OK_EVIDENCE_INCOMPLETE')
    return issues


def collect_cell(manifest, version, code, checkout, data_root, input_dir, exit_code):
    _validate_manifest(manifest)
    case = next((case for case in manifest['cases'] if case['code'] == code), None)
    if case is None or version not in VERSIONS:
        raise ValueError('CELL_NOT_IN_MANIFEST')
    expected_sha = manifest[version + '_sha']
    issues = []
    try:
        checkout_sha = _git_head(checkout)
    except (OSError, subprocess.SubprocessError):
        checkout_sha = ''
    if checkout_sha != expected_sha:
        issues.append('CHECKOUT_SHA_MISMATCH')
    try:
        summary = _load(input_dir / 'summary.json')
        if not isinstance(summary, dict):
            raise ValueError('invalid summary')
    except (OSError, ValueError):
        summary = {}
        issues.append('SAMPLE_SUMMARY_MISSING_OR_INVALID')
    summary_proof = {key: summary.get(key) for key in ('schema', 'source_commit', 'spins_per_mode', 'selected', 'fresh_data', 'dry_run')}
    expected_summary = {'schema': SAMPLE_SCHEMA, 'source_commit': expected_sha,
        'spins_per_mode': manifest['budget']['spins'], 'selected': [code], 'fresh_data': True, 'dry_run': False}
    for key, value in expected_summary.items():
        if summary_proof[key] != value or type(summary_proof[key]) is not type(value):
            issues.append('SAMPLE_' + key.upper() + '_MISMATCH')
    matches = [row for row in _rows(summary.get('results')) if row.get('symbol') == code]
    if len(matches) != 1 or len(_rows(summary.get('results'))) != 1:
        issues.append('SAMPLE_RESULT_MISSING_OR_DUPLICATE')
    try:
        invocation = _load(input_dir / 'invocation.json')
        if not isinstance(invocation, dict):
            raise ValueError('invalid invocation')
    except (OSError, ValueError):
        invocation = {}
    issues.extend(_invocation_issues(invocation, manifest, version, code, exit_code))
    safe_invocation = {key: invocation.get(key) for key in ('schema', 'version', 'code', 'source_commit',
        'workflow_commit', 'budget', 'started_at', 'finished_at', 'exit_code', 'python_version', 'dependency_sha256')}
    private = {'result': None, 'fingerprints': {}, 'issues': []}
    if checkout_sha == expected_sha:
        try:
            private = _read_private(checkout, data_root, code)
        except (OSError, ValueError, subprocess.SubprocessError):
            issues.append('PRIVATE_RESULT_READ_FAILED')
    issues.extend(private.get('issues', []))
    result = private.get('result') or _empty_result()
    issues.extend(_result_issues(result))
    if matches and private.get('result'):
        if any(matches[0].get(key) != result.get(key) for key in ('status', 'requested_spins', 'successful_spins', 'failed_spins')):
            issues.append('SAMPLE_DATABASE_RESULT_MISMATCH')
    result['cli_exit_code'] = (matches[0]['cli_exit_code'] if matches and
        type(matches[0].get('cli_exit_code')) is int else None)
    fingerprints = private.get('fingerprints') or {}
    if fingerprints.get('client_sources_consistent') is False:
        issues.append('CLIENT_SOURCE_CONFLICT')
    if exit_code != 0 and result['status'] == 'OK':
        issues.append('PROCESS_EXIT_NONZERO_WITH_OK')
    issues = sorted(set(issues))
    if issues and result['status'] != 'MISSING':
        result['status'] = 'ERROR'
    return {'schema': CELL_SCHEMA, 'manifest_sha256': _manifest_hash(manifest),
        'version': version, 'case': {key: case[key] for key in ('code', 'family', 'name')},
        'expected_sha': expected_sha, 'checkout_sha': checkout_sha if SHA40.fullmatch(checkout_sha) else None,
        'budget': dict(manifest['budget']), 'exit_code': exit_code,
        'summary_proof': _public_provenance(summary_proof), 'invocation': _public_provenance(safe_invocation),
        'validation': {'valid': not issues, 'issues': issues},
        'result': result, 'metrics': _metrics(result), 'fingerprints': fingerprints}


def _cell_issues(cell, manifest, case, version):
    issues = []
    if not isinstance(cell, dict):
        return ['CELL_INVALID']
    if any(not isinstance(cell.get(key), dict) for key in
           ('case', 'budget', 'summary_proof', 'invocation', 'validation', 'result', 'metrics', 'fingerprints')):
        return ['CELL_INVALID']
    for key, expected in {'schema': CELL_SCHEMA, 'manifest_sha256': _manifest_hash(manifest),
        'version': version, 'case': {key: case[key] for key in ('code', 'family', 'name')},
        'expected_sha': manifest[version + '_sha'], 'checkout_sha': manifest[version + '_sha'],
        'budget': manifest['budget']}.items():
        if cell.get(key) != expected:
            issues.append('CELL_' + key.upper() + '_MISMATCH')
    if not _budget_matches(cell.get('budget'), manifest['budget']):
        issues.append('CELL_BUDGET_MISMATCH')
    proof = cell.get('summary_proof') or {}
    for key, expected in {'schema': SAMPLE_SCHEMA, 'source_commit': manifest[version + '_sha'],
        'spins_per_mode': manifest['budget']['spins'], 'selected': [case['code']], 'fresh_data': True, 'dry_run': False}.items():
        if proof.get(key) != expected or type(proof.get(key)) is not type(expected):
            issues.append('CELL_SAMPLE_' + key.upper() + '_MISMATCH')
    if type(cell.get('exit_code')) is not int:
        issues.append('CELL_EXIT_CODE_INVALID')
    issues.extend(_invocation_issues(cell.get('invocation') or {}, manifest, version, case['code'], cell.get('exit_code')))
    validation = cell.get('validation') or {}
    if validation.get('valid') is not True or validation.get('issues'):
        issues.extend(_strings(validation.get('issues')) or ['CELL_VALIDATION_FAILED'])
    result = cell.get('result') or {}
    issues.extend(_result_issues(result))
    if cell.get('metrics') != _metrics(result):
        issues.append('CELL_METRICS_INCONSISTENT')
    if cell.get('exit_code') != 0 and result.get('status') == 'OK':
        issues.append('PROCESS_EXIT_NONZERO_WITH_OK')
    return sorted(set(issues))


def _comparison(baseline, candidate, valid):
    left, right = (_mapping(cell.get('fingerprints')) for cell in (baseline, candidate))

    def match(key, *, origin=None):
        a, b = left.get(key), right.get(key)
        if not a or not b or (origin and (not left.get(origin) or left.get(origin) != right.get(origin))):
            return 'MISSING_EVIDENCE'
        return 'MATCH' if a == b else 'MISMATCH'

    source_match = match('client_source_sha256')
    if not _source_hashes(left.get('client_source_sha256')) or not _source_hashes(right.get('client_source_sha256')):
        source_match = 'MISSING_EVIDENCE'
    if left.get('client_sources_consistent') is False or right.get('client_sources_consistent') is False:
        source_match = 'MISMATCH'
    config = match('monetary_configuration_sha256', origin='monetary_configuration_origin')
    manifest = match('manifest_sha256')
    invocations = [_mapping(cell.get('invocation')) for cell in (baseline, candidate)]
    environment = 'MATCH'
    for key in ('dependency_sha256', 'python_version', 'workflow_commit'):
        a, b = (inv.get(key) for inv in invocations)
        if not a or not b:
            environment = 'MISSING_EVIDENCE'
            break
        if a != b:
            environment = 'MISMATCH'
    checks = {'source_match': source_match, 'configuration_match': config,
              'manifest_match': manifest, 'environment_match': environment}
    return dict(checks, attribution_eligible=valid and all(value == 'MATCH' for value in checks.values()),
                causality_proven=False)


def _brief(cell, issues=None, missing=False):
    result = _mapping(cell.get('result')) or _empty_result('ERROR' if issues else 'MISSING')
    metrics = _metrics(result)
    issues = issues or []
    status = 'MISSING' if missing or result.get('status') == 'MISSING' else 'ERROR' if issues else result.get('status', 'ERROR')
    inventory = _rows(_mapping(result.get('operation_inventory')).get('modes'))
    return {'status': status, 'reported_status': result.get('reported_status'),
            'metrics': metrics, 'error': _text(result.get('error')),
            'execution_issues': _strings(result.get('execution_issues')), 'validation_issues': issues,
            'live_contract_family': _text(result.get('live_contract_family')) or None,
            'cli_exit_code': result.get('cli_exit_code') if type(result.get('cli_exit_code')) is int else None,
            'discovered_modes': [dict(name=_text(row.get('name')), kind=_text(row.get('kind')),
                                     **_stake_fields(row)) for row in _rows(result.get('discovered_modes'))],
            'pending_modes': [{'name': _text(row.get('name')), 'kind': row.get('kind')}
                              for row in inventory if row.get('verified') is not True],
            'pending_choice_branches': result.get('pending_choice_branches') or [],
            'attempts_by_kind': dict(Counter(row.get('mode_kind') for row in _rows(result.get('attempts')))),
            'return_to_base_verified': result.get('return_to_base_verified') is True}


def _aggregate(games):
    result = {}
    for version in VERSIONS:
        result[version] = {
            'statuses': {status: sum(game[version]['status'] == status for game in games) for status in STATUSES},
            'metrics': {key: sum(game[version]['metrics'][key] for game in games) for key in METRICS},
        }
    result['delta'] = {key: result['candidate']['metrics'][key] - result['baseline']['metrics'][key] for key in METRICS}
    result['transitions'] = dict(sorted(Counter(game['transition'] for game in games).items()))
    result['attributable_transitions'] = dict(sorted(Counter(game['transition'] for game in games
        if game['comparison']['attribution_eligible']).items()))
    result['regressions'] = sum(game['regression'] for game in games)
    result['attribution_eligible_pairs'] = sum(game['comparison']['attribution_eligible'] for game in games)
    for field in ('source', 'configuration', 'manifest', 'environment'):
        result[field + '_mismatches'] = sum(game['comparison'][field + '_match'] == 'MISMATCH' for game in games)
    return result


def compare_cells(manifest, input_dir, *, exclude=()):
    _validate_manifest(manifest)
    indexed, issues = {}, []
    received, unreadable, unexpected = 0, 0, 0
    excluded = {path.resolve() for path in exclude}
    expected = {(case['code'], version) for case in manifest['cases'] for version in VERSIONS}
    for path in sorted(input_dir.rglob('*.json')) if input_dir.is_dir() else []:
        if path.resolve() in excluded:
            continue
        received += 1
        try:
            cell = _load(path)
            key = (cell.get('case', {}).get('code'), cell.get('version'))
            if not all(isinstance(value, str) for value in key):
                raise ValueError('CELL_IDENTITY_INVALID')
        except (OSError, ValueError, TypeError, AttributeError):
            unreadable += 1
            issues.append('UNREADABLE_CELL')
            continue
        if key not in expected:
            unexpected += 1
            issues.append('UNEXPECTED_CELL')
            continue
        indexed.setdefault(key, []).append(cell)
    games, missing_count, duplicate_count, invalid_count = [], 0, 0, unreadable + unexpected
    for case in manifest['cases']:
        game, pair, valid = dict(case), {}, True
        for version in VERSIONS:
            cells = indexed.get((case['code'], version), [])
            if not cells:
                missing_count += 1
                pair[version] = {}
                game[version] = _brief({}, ['CELL_MISSING'], missing=True)
                valid = False
            elif len(cells) > 1:
                duplicate_count += 1
                pair[version] = {}
                game[version] = _brief({'result': _empty_result('ERROR')}, ['CELL_DUPLICATE'])
                valid = False
            else:
                pair[version] = cells[0]
                cell_issues = _cell_issues(cells[0], manifest, case, version)
                invalid_count += bool(cell_issues)
                game[version] = _brief(cells[0], cell_issues)
                valid = valid and not cell_issues
        game['transition'] = game['baseline']['status'] + '->' + game['candidate']['status']
        game['regression'] = game['baseline']['status'] == 'OK' and game['candidate']['status'] != 'OK'
        game['comparison'] = _comparison(pair['baseline'], pair['candidate'], valid)
        games.append(game)
    summary = dict(_aggregate(games), expected_cells=len(expected), received_cells=received,
        missing_cells=missing_count, duplicate_cells=duplicate_count, invalid_cells=invalid_count)
    families = [dict(family=family, cohort='historical_capture', games=len(group), **_aggregate(group))
                for family in sorted({case['family'] for case in manifest['cases']})
                for group in [[game for game in games if game['family'] == family]]]
    passed = (not (missing_count or duplicate_count or invalid_count or summary['regressions'])
              and summary['candidate']['statuses']['OK'] == len(games)
              and summary['attribution_eligible_pairs'] == len(games))
    return {'schema': REPORT_SCHEMA, 'passed': passed, 'manifest_sha256': _manifest_hash(manifest),
        'baseline_sha': manifest['baseline_sha'], 'candidate_sha': manifest['candidate_sha'],
        'budget': manifest['budget'], 'scope': 'fresh_live_sample',
        'interpretation': 'Historical family cohorts; observed transitions are attributed only to comparable pairs. One bounded sample does not prove causality or exhaustive coverage.',
        'summary': summary, 'families': families, 'games': games, 'issues': sorted(set(issues))}


def _markdown(report):
    def escape(value):
        return _text(str(value)).replace('|', '\\|').replace('`', "'").replace('<', '&lt;').replace('>', '&gt;')

    lines = ['# Playtech: comparación live por familia', '',
        'Resultado: **' + ('PASS' if report.get('passed') else 'NO PASS') + '**.', '',
        'Las familias son cohortes del HAR histórico. El contrato live se informa sólo cuando la ejecución lo declara. '
        'Una muestra acotada no demuestra causalidad ni cobertura exhaustiva.', '']
    if 'summary' not in report:
        return '\n'.join(lines + ['Problemas: ' + ', '.join(report.get('issues', [])), ''])
    summary = report['summary']
    lines += [f"Baseline `{report['baseline_sha']}` · candidato `{report['candidate_sha']}`.", '',
        f"Celdas: {summary['received_cells']}/{summary['expected_cells']}; faltantes: {summary['missing_cells']}; "
        f"duplicadas: {summary['duplicate_cells']}; inválidas: {summary['invalid_cells']}. "
        f"Pares comparables: {summary['attribution_eligible_pairs']}/{len(report['games'])}.", '',
        '| Familia histórica | Juegos | Baseline OK / PARCIAL / ERROR / MISSING | Candidato OK / PARCIAL / ERROR / MISSING | PARCIAL→OK observado / atribuible | Regresiones |',
        '|---|---:|---|---|---:|---:|']
    for family in report['families']:
        counts = [' / '.join(str(family[v]['statuses'][status]) for status in STATUSES) for v in VERSIONS]
        lines.append(f"| {family['family']} | {family['games']} | {counts[0]} | {counts[1]} | "
                     f"{family['transitions'].get('PARCIAL->OK', 0)} / {family['attributable_transitions'].get('PARCIAL->OK', 0)} | {family['regressions']} |")
    lines += ['', '## Capacidades y rondas', '',
        '| Familia | Modos reconocidos B→C | Verificados B→C | UNKNOWN B→C | Modos pendientes B→C | Elecciones pendientes B→C | Rondas cerradas verificadas B→C |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for family in report['families']:
        values = [f"{family['baseline']['metrics'][key]}→{family['candidate']['metrics'][key]}"
                  for key in ('modes_recognized', 'modes_verified', 'modes_unknown', 'modes_pending', 'pending_choice_branches', 'rounds_verified')]
        lines.append('| ' + family['family'] + ' | ' + ' | '.join(values) + ' |')
    lines += ['', '## Juegos y evidencia', '',
        '| Juego | Estado B→C | Rondas B→C | Fuentes / configuración / manifest / entorno | Atribuible |',
        '|---|---|---:|---|---|']
    for game in report['games']:
        checks = ' / '.join(game['comparison'][key] for key in ('source_match', 'configuration_match', 'manifest_match', 'environment_match'))
        lines.append(f"| {escape(game['name'])} ({game['code']}) | {game['transition'].replace('->', '→')} | "
            f"{game['baseline']['metrics']['rounds_verified']}→{game['candidate']['metrics']['rounds_verified']} | {checks} | "
            f"{'sí' if game['comparison']['attribution_eligible'] else 'no'} |")
    for game in report['games']:
        lines += ['', '### ' + escape(game['name']), '']
        for version in VERSIONS:
            arm = game[version]
            reasons = arm['validation_issues'] + arm['execution_issues']
            if arm['error'] and arm['error'] not in reasons:
                reasons.append(arm['error'])
            pending = ', '.join(escape(row['name']) + ' (' + escape(row['kind']) + ')' for row in arm['pending_modes']) or 'ninguno'
            lines += [f"- **{version} {arm['status']}**: contrato live {escape(arm['live_contract_family'] or 'no declarado')}; "
                      f"rondas {arm['metrics']['rounds_verified']}/{arm['metrics']['rounds_attempted']}; "
                      f"modos pendientes: {pending}; elecciones pendientes: {arm['metrics']['pending_choice_branches']}. "
                      'Motivos: ' + ('; '.join(escape(reason) for reason in dict.fromkeys(reasons)) or 'sin incidencias declaradas') + '.']
    return '\n'.join(lines) + '\n'


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    collect = commands.add_parser('collect')
    compare = commands.add_parser('compare')
    for command in (collect, compare):
        command.add_argument('--manifest', type=Path, required=True)
        command.add_argument('--input-dir', type=Path, required=True)
        command.add_argument('--output', type=Path, required=True)
    collect.add_argument('--version', choices=VERSIONS, required=True)
    collect.add_argument('--code', required=True)
    collect.add_argument('--checkout', type=Path, required=True)
    collect.add_argument('--data-root', type=Path, required=True)
    collect.add_argument('--exit-code', type=int, required=True)
    compare.add_argument('--markdown', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = _validate_manifest(_load(args.manifest))
        if args.command == 'collect':
            report = collect_cell(manifest, args.version, args.code, args.checkout, args.data_root,
                                  args.input_dir, args.exit_code)
            exit_code = 0 if report['validation']['valid'] else 1
        else:
            report = compare_cells(manifest, args.input_dir, exclude=(args.output, args.manifest))
            exit_code = 0 if report['passed'] else 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        # Private exception messages and paths are never publication evidence.
        reason = str(exc) if re.fullmatch(r'[A-Z][A-Z0-9_]+', str(exc)) else 'INPUT_INVALID'
        report = {'schema': CELL_SCHEMA if args.command == 'collect' else REPORT_SCHEMA,
                  'passed': False, 'issues': [reason]}
        exit_code = 2
    _write(args.output, report)
    if args.command == 'compare':
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(_markdown(report), encoding='utf-8')
    print(json.dumps({'schema': report['schema'], 'exit_code': exit_code,
                      'passed': report.get('passed', report.get('validation', {}).get('valid', False))}))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
