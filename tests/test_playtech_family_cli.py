"""The family audit must be available without opening a provider or database."""
import json

import pytest

from tester_spin.cli import main


def capture(tmp_path):
    path = tmp_path / 'sample.har'
    path.write_text(json.dumps({'log': {'entries': [
        {'request': {'url': 'https://example.invalid/static'},
         'response': {'status': 200, 'content': {'text': '{}'}}},
    ]}}), encoding='utf-8')
    return path


def test_family_command_writes_report_without_creating_game_database(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = capture(tmp_path)
    original = source.read_bytes()
    output = tmp_path / 'reports' / 'families.json'
    assert main(['families', 'playtech', str(source), '--output', str(output)]) == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads(output.read_text(encoding='utf-8'))
    assert printed == saved
    assert saved['schema'] == 'tester-spin/playtech-family-audit/v1'
    assert saved['certifies_live_ok'] is False
    assert saved['summary']['files'] == 1
    assert saved['families'] == []
    assert source.read_bytes() == original
    assert not list(tmp_path.rglob('*.sqlite3'))


@pytest.mark.parametrize('suffix', ['har', 'zip'])
def test_family_command_refuses_to_overwrite_an_input(tmp_path, capsys, suffix):
    source = tmp_path / ('capture.' + suffix)
    original = b'original capture bytes'
    source.write_bytes(original)
    assert main(['families', 'playtech', str(source), '--output', str(source)]) == 2
    assert source.read_bytes() == original
    assert 'sobrescribir' in capsys.readouterr().err


def test_family_command_does_not_echo_malformed_capture_contents(tmp_path, capsys):
    source = tmp_path / 'broken.har'
    source.write_text('private-session-token invalid JSON', encoding='utf-8')
    assert main(['families', 'playtech', str(source)]) == 2
    streams = capsys.readouterr()
    assert 'private-session-token' not in streams.out + streams.err
    assert streams.err


@pytest.mark.parametrize('native', [False, True])
def test_manual_gpas_diagnostics_exposes_family_and_missing_receipt(tmp_path, native):
    from tester_spin.har_learning import inspect_capture
    messages = [
        {'data': {'_type': 'InitGameSession', 'gameCode': 'gpas_fixture'}},
        {'correlationId': 'fixture-correlation', 'data': {
            '_type': 'com.pt.casino.platform.game.GameCommand',
            'gameData': {'_type': 'com.pt.gpas.platform.game.OgwCorosinGameCommand',
                         'ID': 40021, 'parameters': []},
            'betType': 'default', 'featureType': 'default', 'betCost': 10,
        }},
    ]
    document = {'log': {'entries': [{
        'request': {'url': 'wss://example.invalid/socket?token=never-report'},
        '_webSocketFrames': [
            {'direction': 'sent', 'timestamp': index + 1,
             'payloadData': '3:::' + json.dumps(message)}
            for index, message in enumerate(messages)
        ],
    }]}}
    if native:
        entry = document['log']['entries'][0]
        document['log']['_warpWebSockets'] = [
            {'url': entry['request']['url'], 'connectionId': 'native-fixture',
             'direction': frame['direction'], 'timestamp': frame['timestamp'],
             'payload': frame['payloadData'], 'opcode': 1}
            for frame in entry['_webSocketFrames']
        ]
        document['log']['entries'] = []
    source = tmp_path / 'gpas.har'
    original = json.dumps(document)
    source.write_text(original, encoding='utf-8')
    report = inspect_capture(source)
    assert report['protocol'] == 'GPAS'
    assert report['family_audit']['summary']['gameplay_requests'] == 1
    assert report['issues']
    assert report['next_steps']
    assert 'never-report' not in json.dumps(report)
    assert source.read_text(encoding='utf-8') == original
