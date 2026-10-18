"""Synthetic regressions for updater, exported evidence and shared history."""
from __future__ import annotations

import hashlib
import io
import json
import multiprocessing
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from tester_spin.models import GameTestResult, SpinAttempt
from tester_spin.updater import MANIFEST_SCHEMA, Updater


def _result(root, **kwargs):
    values = dict(provider='synthetic', slug='game', game_name='Game',
                  game_url='https://example.invalid', requested_spins=1,
                  successful_spins=1, failed_spins=0, status='OK', run_dir=str(root))
    values.update(kwargs)
    return GameTestResult(**values)


def _package():
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as archive:
        archive.writestr('run.py', 'print("safe fixture")\n')
    return raw.getvalue()


@pytest.mark.parametrize('version', ['.', '..'])
def test_invalid_manifest_version_preserves_data_and_config(tmp_path, version):
    updater = Updater(home=tmp_path/'home')
    marker = updater.home/'data'/'tester-spin.sqlite3'
    marker.parent.mkdir()
    marker.write_text('existing user data')
    config = updater.config_path.read_bytes()
    package = _package()
    manifest = dict(schema=MANIFEST_SCHEMA, version=version,
                    url='https://updates.invalid/app.zip', sha256=hashlib.sha256(package).hexdigest())
    with patch.object(updater, '_fetch_json', return_value=manifest), patch(
            'tester_spin.updater.urllib.request.urlopen', side_effect=lambda *a, **k: io.BytesIO(package)):
        with pytest.raises(ValueError, match='version'):
            updater._prepare_manifest_runtime(lambda _: None)
    assert marker.read_text() == 'existing user data'
    assert updater.config_path.read_bytes() == config


@pytest.mark.parametrize('location', ['install', 'staging'])
def test_manifest_rejects_resolved_escape_paths(tmp_path, location):
    updater = Updater(home=tmp_path/'home')
    updater.versions_root.mkdir()
    outside = tmp_path/'outside'
    outside.mkdir()
    marker = outside/'keep.txt'
    marker.write_text('untouched')
    config = updater.config_path.read_bytes()
    link = updater.versions_root/('1.0' if location == 'install' else '.1.0.staging')
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f'directory symlinks unavailable: {exc}')
    package = _package()
    manifest = dict(schema=MANIFEST_SCHEMA, version='1.0',
                    url='https://updates.invalid/app.zip', sha256=hashlib.sha256(package).hexdigest())
    with patch.object(updater, '_fetch_json', return_value=manifest), patch(
            'tester_spin.updater.urllib.request.urlopen', side_effect=lambda *a, **k: io.BytesIO(package)):
        with pytest.raises(ValueError, match='versions'):
            updater._prepare_manifest_runtime(lambda _: None)
    assert marker.read_text() == 'untouched'
    assert list(outside.iterdir()) == [marker]
    assert updater.config_path.read_bytes() == config


def test_current_manifest_does_not_accept_runtime_outside_versions(tmp_path):
    updater = Updater(home=tmp_path/'home')
    updater.versions_root.mkdir()
    (updater.home/'run.py').write_text('outside runtime')
    updater.current_path.write_text(json.dumps({'version': '..', 'entrypoint': 'run.py'}))
    assert updater._read_current_manifest_runtime() is None


def test_publication_sanitizes_metadata_and_protocol_without_private_files(tmp_path):
    from tester_spin.run_result_publisher import build_result_document
    (tmp_path/'request.json').write_text(json.dumps({
        'command': 'spin', 'options': {'token': 'PRIVATE_TOKEN', 'state_lock': 'PRIVATE_LOCK'},
        'headers': [{'name': 'Authorization', 'value': 'Bearer PRIVATE_AUTH'},
                    {'name': 'Cookie', 'value': 'sid=PRIVATE_COOKIE; other=PRIVATE_OTHER'}],
        'url': 'https://example.invalid/api/demo/game/PRIVATE_PATH?sid=PRIVATE_SID&bet=2',
    }))
    (tmp_path/'response.raw').write_text('Cookie: sid=PRIVATE_RAW_COOKIE; other=PRIVATE_RAW_OTHER\n'
        'Authorization: Bearer PRIVATE_RAW_AUTH\nstate_lock=PRIVATE_RAW_LOCK&state=base&win=12\n'
        'url=https://example.invalid/?api_key=PRIVATE_QUERY&bet=2')
    for relative in ['session.private.json', '.private/request.json', 'private/token.txt']:
        private = tmp_path/relative
        private.parent.mkdir(exist_ok=True)
        private.write_text('PRIVATE_FILE')
    result = _result(tmp_path, game_url='https://example.invalid/?token=PRIVATE_GAME&game=demo',
                     error='session=PRIVATE_ERROR', discovered_modes=[{'id': 'SPIN', 'session': 'PRIVATE_MODE'}],
                     attempts=[SpinAttempt(1, True, error='Authorization: Bearer PRIVATE_ATTEMPT')])
    document = build_result_document(result)
    assert 'PRIVATE_' not in json.dumps(document)
    assert set(document['artifacts']) == {'request.json', 'response.raw'}
    request = document['artifacts']['request.json']['value']
    assert request['command'] == 'spin'
    assert 'state=base&win=12' in document['artifacts']['response.raw']['value']
    assert 'bet=2' in document['artifacts']['response.raw']['value']


def test_publication_redacts_encoded_url_credentials(tmp_path):
    from tester_spin.run_result_publisher import build_result_document
    (tmp_path/'request.json').write_text(json.dumps({
        'headers': [{'name': 'X-Api-Key', 'value': 'PRIVATE_HEADER'}],
        'url': 'https://PRIVATE_USER:PRIVATE_PASS@example.invalid/?%74oken=PRIVATE_ENCODED&bet=2',
    }))
    document = build_result_document(_result(tmp_path))
    assert set(document['artifacts']) == {'request.json'}
    assert 'PRIVATE_' not in json.dumps(document)
    assert 'bet=2' in document['artifacts']['request.json']['value']['url']


def test_publication_excludes_private_file_aliases(tmp_path):
    from tester_spin.run_result_publisher import build_result_document
    private = tmp_path/'session.private.json'
    private.write_text(json.dumps({'value': 'PRIVATE_FILE'}))
    try:
        (tmp_path/'response.json').symlink_to(private)
    except OSError as exc:
        pytest.skip(f'file symlinks unavailable: {exc}')
    document = build_result_document(_result(tmp_path))
    assert document['artifacts'] == {}
    assert 'PRIVATE_' not in json.dumps(document)


def test_git_runtime_rejects_cached_install_outside_versions(tmp_path):
    updater = Updater(home=tmp_path/'home')
    updater.versions_root.mkdir()
    outside = tmp_path/'outside'
    outside.mkdir()
    (outside/'run.py').write_text('outside runtime')
    try:
        (updater.versions_root/('git-' + 'a'*40)).symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f'directory symlinks unavailable: {exc}')
    with patch.object(updater, '_find_executable', return_value='git'), patch.object(updater, '_run', return_value='a'*40):
        with pytest.raises(ValueError, match='versions'):
            updater.pin_git_runtime(tmp_path/'repo', lambda _: None)


def test_publication_sanitizes_json_messages_embedded_in_text_artifacts(tmp_path):
    from tester_spin.run_result_publisher import build_result_document
    capture = {'command': 'spin', 'headers': [{'name': 'Authorization', 'value': 'PRIVATE_JSONL'}]}
    (tmp_path/'events.jsonl').write_text(json.dumps(capture) + '\n' + json.dumps({'state': 'base'}))
    (tmp_path/'response.raw').write_text(json.dumps(capture))
    document = build_result_document(_result(tmp_path))
    assert 'PRIVATE_' not in json.dumps(document)
    assert json.loads(document['artifacts']['events.jsonl']['value'].splitlines()[1]) == {'state': 'base'}
    assert json.loads(document['artifacts']['response.raw']['value'])['command'] == 'spin'


def test_publication_redacts_encoded_relative_target_and_form_fields(tmp_path):
    from tester_spin.run_result_publisher import build_result_document
    (tmp_path/'request.raw').write_text(
        'POST /spin?%74oken=PRIVATE_RELATIVE&bet=2 HTTP/1.1\r\n'
        'Content-Type: application/x-www-form-urlencoded\r\n\r\n'
        '%73ession=PRIVATE_FORM&command=spin&stake=0.25')
    document = build_result_document(_result(tmp_path))
    request = document['artifacts']['request.raw']['value']
    assert 'PRIVATE_' not in json.dumps(document)
    assert request.startswith('POST /spin?%74oken=')
    assert '&bet=2 HTTP/1.1\n' in request
    assert 'Content-Type: application/x-www-form-urlencoded\n\n' in request
    assert request.endswith('&command=spin&stake=0.25')


@pytest.mark.parametrize('secret', [
    'PRIVATE_FIRST,PRIVATE_COMMA;PRIVATE_SEMICOLON',
    'PRIVATE_FIRST%2CPRIVATE_COMMA%3BPRIVATE_SEMICOLON%27PRIVATE_QUOTE',
])
@pytest.mark.parametrize('representation', ['absolute', 'relative', 'form'])
def test_publication_redacts_complete_query_and_form_values(tmp_path, secret, representation):
    from tester_spin.run_result_publisher import build_result_document
    if representation == 'absolute':
        (tmp_path/'request.json').write_text(json.dumps({
            'url': f'https://example.invalid/?%70assword={secret}&bet=2&command=spin',
            'state': 'base',
        }))
    else:
        fields = f'%73ession={secret}&bet=2&command=spin'
        text = f'POST /spin?{fields} HTTP/1.1' if representation == 'relative' else fields
        (tmp_path/'request.raw').write_text(text)
    document = build_result_document(_result(tmp_path))
    assert 'PRIVATE_' not in json.dumps(document)
    if representation == 'absolute':
        observed = document['artifacts']['request.json']['value']
        assert observed['state'] == 'base'
        assert observed['url'].startswith('https://example.invalid/?%70assword=')
        assert observed['url'].endswith('&bet=2&command=spin')
    else:
        observed = document['artifacts']['request.raw']['value']
        if representation == 'relative':
            assert observed.startswith('POST /spin?%73ession=')
            assert observed.endswith('&bet=2&command=spin HTTP/1.1')
        else:
            assert observed.startswith('%73ession=')
            assert observed.endswith('&bet=2&command=spin')


def test_publication_sanitizes_json_records_after_plain_log_preamble(tmp_path):
    from tester_spin.run_result_publisher import build_result_document
    message = {'headers': [{'name': 'Authorization', 'value': 'Bearer PRIVATE_LOG'}],
               'command': 'spin', 'bet': 2}
    (tmp_path/'events.log').write_text('capture started\n' + json.dumps(message) + '\ncapture finished\n')
    document = build_result_document(_result(tmp_path))
    assert 'PRIVATE_' not in json.dumps(document)
    lines = document['artifacts']['events.log']['value'].splitlines()
    assert lines[0] == 'capture started'
    assert lines[-1] == 'capture finished'
    observed = json.loads(lines[1])
    assert observed['command'] == 'spin' and observed['bet'] == 2
    assert observed['headers'][0]['name'] == 'Authorization'


@pytest.mark.parametrize('separators', [None, (',', ':')])
@pytest.mark.parametrize('suffix', ['raw', 'jsonl'])
def test_publication_keeps_structured_session_messages_parseable(tmp_path, separators, suffix):
    from tester_spin.run_result_publisher import build_result_document
    message = {'url': 'https://example.invalid/api/demo/game/PRIVATE_SESSION',
               'command': 'spin', 'bet': 2}
    text = json.dumps(message, separators=separators)
    if suffix == 'jsonl':
        text += '\n' + json.dumps({'state': 'base', 'win': 12}) + '\n'
    (tmp_path/f'response.{suffix}').write_text(text)
    document = build_result_document(_result(tmp_path))
    assert 'PRIVATE_' not in json.dumps(document)
    lines = document['artifacts'][f'response.{suffix}']['value'].splitlines()
    observed = json.loads(lines[0])
    assert observed['command'] == 'spin' and observed['bet'] == 2
    assert observed['url'].startswith('https://example.invalid/api/demo/game/')
    if suffix == 'jsonl':
        assert json.loads(lines[1]) == {'state': 'base', 'win': 12}


@pytest.mark.parametrize('header', ['Authorization', 'aUtHoRiZaTiOn', 'Proxy-Authorization'])
@pytest.mark.parametrize('layout', ['plain', 'indented', 'logged', 'folded', 'logged_folded'])
def test_publication_redacts_complete_raw_authorization_headers(tmp_path, header, layout):
    from tester_spin.run_result_publisher import build_result_document
    prefix = '[capture DEBUG] > ' if layout.startswith('logged') else '  ' if layout == 'indented' else ''
    separator = '\r\n' + prefix + '\t' if 'folded' in layout else ' '
    credentials = separator.join([
        'Digest username="PRIVATE_USER",', 'realm="example", nonce="PRIVATE_NONCE",',
        'uri="/spin", response="PRIVATE_AUTH_RESPONSE"',
    ])
    capture = ('POST /spin HTTP/1.1\r\n' + prefix + header + ': ' + credentials + '\r\n'
               + prefix + 'Content-Type: application/json\r\n'
               + prefix + 'X-Public: retained\r\n\r\n'
               + '  {"command":"spin","bet":2,"state":"base"}\r\n')
    (tmp_path/'request.log').write_text(capture)
    document = build_result_document(_result(tmp_path))
    published = json.dumps(document)
    for secret in ['PRIVATE_USER', 'PRIVATE_NONCE', 'PRIVATE_AUTH_RESPONSE']:
        assert secret not in published
    observed = document['artifacts']['request.log']['value']
    assert observed.startswith('POST /spin HTTP/1.1\n' + prefix + header + ': [REDACTED]\n')
    assert prefix + 'Content-Type: application/json\n' in observed
    assert prefix + 'X-Public: retained\n\n' in observed
    assert json.loads(observed.split('\n\n')[1]) == {'command': 'spin', 'bet': 2, 'state': 'base'}


@pytest.mark.parametrize('suffix', ['json', 'raw', 'jsonl'])
def test_publication_redacts_unknown_authorization_scheme_inside_json(tmp_path, suffix):
    from tester_spin.run_result_publisher import build_result_document
    message = {
        'command': 'spin', 'bet': 2,
        'request': ('  pRoXy-AuThOrIzAtIoN: CustomAuth PRIVATE_FIRST PRIVATE_SECOND\n'
                    '\tPRIVATE_CONTINUATION\n'
                    '  Content-Type: application/json\n\n'
                    '{"state":"base","win":12}'),
    }
    text = json.dumps(message)
    if suffix == 'jsonl':
        text = 'capture started\n' + text + '\n' + json.dumps({'complete': True}) + '\n'
    (tmp_path/f'capture.{suffix}').write_text(text)
    document = build_result_document(_result(tmp_path))
    for secret in ['PRIVATE_FIRST', 'PRIVATE_SECOND', 'PRIVATE_CONTINUATION']:
        assert secret not in json.dumps(document)
    value = document['artifacts'][f'capture.{suffix}']['value']
    if suffix == 'jsonl':
        lines = value.splitlines()
        assert lines[0] == 'capture started'
        assert json.loads(lines[2]) == {'complete': True}
        observed = json.loads(lines[1])
    else:
        observed = value if suffix == 'json' else json.loads(value)
    assert observed['command'] == 'spin' and observed['bet'] == 2
    assert observed['request'].startswith('  pRoXy-AuThOrIzAtIoN: [REDACTED]\n')
    assert '  Content-Type: application/json\n\n' in observed['request']
    assert json.loads(observed['request'].split('\n\n')[1]) == {'state': 'base', 'win': 12}


def _history_writer(directory, label, entered, release, completed):
    from tester_spin import coverage_history
    original = coverage_history._archive_classified_selector_replacements

    def after_read(*args):
        if label == 'A':
            entered.set()
            if not release.wait(10):
                raise RuntimeError('test did not release history writer')
        return original(*args)

    coverage_history._archive_classified_selector_replacements = after_read
    if label == 'B':
        entered.set()
    result = _result(directory, discovered_modes=[{
        'id': label, 'kind': 'CHOICE_BRANCH', 'coverage_required': True,
        'required_options': ['pending'], 'covered_options': [],
    }])
    coverage_history.retain_pending_branches(directory, result)
    completed.set()


def test_history_transaction_retains_updates_from_independent_processes(tmp_path):
    path = tmp_path/'coverage-history.json'
    path.write_text(json.dumps({'provider': 'synthetic', 'slug': 'game', 'pending': {}}))
    context = multiprocessing.get_context('spawn')
    a_entered, b_entered, release = context.Event(), context.Event(), context.Event()
    a_done, b_done = context.Event(), context.Event()
    first = context.Process(target=_history_writer, args=(str(tmp_path), 'A', a_entered, release, a_done))
    second = context.Process(target=_history_writer, args=(str(tmp_path), 'B', b_entered, release, b_done))
    processes = [first, second]
    try:
        first.start()
        assert a_entered.wait(10), 'writer A did not reach its read/merge transaction'
        second.start()
        assert b_entered.wait(10), 'independent writer B did not start'
        # Before the fix B writes while A holds a stale snapshot. A proper lock
        # keeps B waiting until A commits; the short wait bounds that contention.
        b_done.wait(0.5)
        release.set()
        for process in processes:
            process.join(10)
            assert process.exitcode == 0
        assert a_done.is_set() and b_done.is_set()
        assert set(json.loads(path.read_text())['pending']) == {'A', 'B'}
        assert not list(tmp_path.glob('*.tmp'))
    finally:
        release.set()
        for process in processes:
            if process.pid and process.is_alive():
                process.terminate()
                process.join(5)


@pytest.mark.parametrize('indices,wire_steps,validated', [([0, 2], 3, False), ([0, 1], 3, False), ([0, 1, 2], 3, True)])
def test_diagnostics_require_complete_wire_sequence(tmp_path, indices, wire_steps, validated):
    from tester_spin.run_diagnostics import write_run_diagnostics
    directory = tmp_path/'attempt'
    directory.mkdir()
    for index in indices:
        for direction in ['request', 'response']:
            (directory/f'step-{index:03}.{direction}.json').write_text(json.dumps({'step': index}))
    (tmp_path/'path-coverage.json').write_text(json.dumps({'complete': True, 'branch_points': []}))
    (tmp_path/'sample-catalog.json').write_text(json.dumps({'observed_paths_sampled': True}))
    report = write_run_diagnostics(_result(tmp_path, attempts=[SpinAttempt(
        1, True, terminal=True, wire_steps=wire_steps, artifact_dir=str(directory))]))
    assert report['modes'][0]['validated'] is validated
    tree = json.loads((tmp_path/'run-tree.json').read_text())
    if not validated:
        details = [gap['detail'] for gap in report['evidence_gaps'] if gap['code'] == 'TRAJECTORY_SEQUENCE_GAP']
        assert details == tree['trajectories'][0]['gaps']
        assert report['attempts'][0]['sequence_complete'] is False
