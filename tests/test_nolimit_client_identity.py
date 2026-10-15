import json
from pathlib import Path

import pytest

from tester_spin.providers.nolimit_city.client_identity import validate_client_info
from tester_spin.providers.nolimit_city.errors import Unlearned


@pytest.mark.parametrize('row', json.loads(Path('tests/fixtures/nolimit_public_client_identity.json').read_text(encoding='utf-8'))['clients'])
def test_public_demo_client_versions_preserve_published_identity(row):
    info = row['info']
    assert validate_client_info(info, info['name']) == info


def test_stable_client_preserves_metadata():
    info = {'name': 'Example', 'version': '1.2.3', 'size': {'width': 1280}}
    assert validate_client_info(info, 'Example') == info


@pytest.mark.parametrize('info', [None, [], {}, {'name': 'Example'}, {'name': 'Other', 'version': '1.2.3'}, {'name': 'example', 'version': '1.2.3'}])
def test_missing_or_mismatched_identity_is_rejected(info):
    with pytest.raises(Unlearned):
        validate_client_info(info, 'Example')


@pytest.mark.parametrize('version', [None, 123, '', '1.2', '1.2.3/escape', '../1.2.3', '1.2.3?x', '1.2.3#x', '1.2.3%2f', '1.2.3\\x', '1.2.3\n', '1.2.3..battle', '1.2.3-battle..8', '1.2.3-','1.2.3.4', '1.2.3-' + 'a' * 128])
def test_unsafe_or_unobserved_version_structure_is_rejected(version):
    with pytest.raises(Unlearned):
        validate_client_info({'name': 'Example', 'version': version}, 'Example')


@pytest.mark.parametrize('symbol', ['', '../Example', 'Example/Other', 'Example?x', 'Example\n'])
def test_requested_symbol_must_be_a_single_safe_identifier(symbol):
    with pytest.raises(Unlearned):
        validate_client_info({'name': symbol, 'version': '1.2.3'}, symbol)


@pytest.mark.parametrize('version', ['1.2.3', '1.2.3-battlenopixi.8', '1.2.3.battle.6'])
def test_session_uses_published_version_before_opening_demo(tmp_path, version):
    import threading
    from types import SimpleNamespace
    from tester_spin.providers.nolimit_city.runtime import NolimitSession
    class BootstrapReached(Exception):
        pass
    class Http:
        def get(self, url, **kwargs):
            assert url.endswith('/Example/info.json')
            return SimpleNamespace(json=lambda: {'name': 'Example', 'version': version}, raise_for_status=lambda: None)
        def post(self, *args, **kwargs):
            raise BootstrapReached
    directory=tmp_path/'game'/'tests'/'run'/'bootstrap'
    directory.mkdir(parents=True)
    session=NolimitSession()
    with pytest.raises(BootstrapReached):
        session.open(SimpleNamespace(symbol='Example'), Http(), 1, threading.Event(), directory)
    assert session.client_cache.name == version+'.js'
    assert json.loads((directory/'client-info.json').read_text(encoding='utf-8'))['version'] == version


@pytest.mark.parametrize('info', [{'name':'Example','version':'1.2.3.battle.6'}, None, {'name':'../escape','version':'1.2.3'}])
def test_corpus_loads_only_validated_public_client_paths(tmp_path, monkeypatch, info):
    from tester_spin.providers.nolimit_city import corpus
    capture=tmp_path/'run'/'capture.har'
    bootstrap=capture.parent/'bootstrap'
    bootstrap.mkdir(parents=True)
    (bootstrap/'client-info.json').write_text(json.dumps(info),encoding='utf-8')
    clients=tmp_path/'clients'
    (clients/'Example').mkdir(parents=True)
    (clients/'Example/1.2.3.battle.6.js').write_text('EXACT_CLIENT',encoding='utf-8')
    monkeypatch.setattr(corpus,'capture_rows',lambda *args: iter([{'path':str(capture),'sha256':'fixture','exchanges':[]}]))
    sources=[]
    def audit(exchanges, *, client_source):
        sources.append(client_source)
        return {'steps_checked':0,'money_accepted_steps':0,'closed_rounds':0,'contract_actions':0,'unresolved_actions':[]}
    monkeypatch.setattr(corpus,'audit_exchanges',audit)
    corpus.main([str(tmp_path/'input'),'--client-dir',str(clients),'--output',str(tmp_path/'output.json')])
    assert sources == ['EXACT_CLIENT' if isinstance(info,dict) and info.get('name')=='Example' else None]
