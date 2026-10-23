from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from tester_spin.providers.yggdrasil.runtime import DemoRuntime, Unsupported, configuration, ordinary_round

ROOT = Path(__file__).parent / 'fixtures'
DATA = json.loads((ROOT / 'yggdrasil_cluster_cascades.json').read_text())
SOURCE = (ROOT / 'yggdrasil_cluster_cascades_source.js').read_text()
GAME = {'gameid': '20004', 'cfg': {'props': [{'prop': name, 'value': value} for name, value in DATA['props'].items()]},
        'orgSettings': {'type': 'BASIC', 'Denoms': 'EUR:0.01,0.02', 'DefaultDenom': 'EUR:0.01'}, 'extraOrgSettings': []}


def config():
    return configuration(GAME, '20004', 'EUR', sdk_source=SOURCE)


def payload(name, reference='fixture-runtime-round'):
    value = deepcopy(DATA[name])
    return {'code': 0, 'fn': 'play', 'data': {'wager': {'wagerid': reference, 'status': value['wager_status'], 'bets': [value['bet']]},
                                           'buyBal': value['buyBal'], 'resultBal': value['resultBal']}}


def runtime(values):
    instance = DemoRuntime(None, '20004', 1, threading.Event(), gate=None)
    instance.config = config()
    replies = iter(values)
    instance.call = lambda *args, **kwargs: next(replies)
    return instance


def test_current_config_installs_strict_cluster_contract():
    current = config()
    assert current['ordinary_constraints']['cluster_cascade_definition']['prices'] == DATA['props']['PrizesPerIcon']
    assert not current['unresolved']


def test_current_sdk_loader_accepts_cluster_contract_without_inventing_mode_roles(tmp_path):
    from tester_spin.providers.yggdrasil.sdk_mode_roles import load_source
    class Response:
        status_code = 200
        def __init__(self, text, url): self.text, self.url = text, url
    class HTTP:
        def get(self, url, timeout):
            if '/init/' in url:
                return Response('<script src="game.js"></script>', 'https://staticdemo.yggdrasilgaming.com/20004/index.html')
            return Response(SOURCE, url)
    page = '<div data-iframe-src="https://staticdemo.yggdrasilgaming.com/init/launchClient.html?org=Demo&amp;gameid=20004"></div>'
    source = load_source(HTTP(), page, '20004', DATA['props']['Modes'], tmp_path, 1, props=DATA['props'])
    assert source == SOURCE
    assert (tmp_path / 'sdk-cluster-cascade-proof.json').exists()


def test_actual_feature_has_exact_cash_settlement_and_stays_nonordinary(tmp_path):
    instance = runtime([payload('mutiny_cascade'), payload('collect')])
    result = instance.round(instance.config['templates']['BASIC'], tmp_path)
    assert result['known'] and result['terminal'] and not result['base']
    saved = json.loads((tmp_path / 'step-001-response.json').read_text())
    assert saved['cluster_cascade_outcomes'][0]['schema'] == 'legacy-cluster-cascade/feature/v1'
    final = json.loads((tmp_path / 'step-002-response.json').read_text())
    assert final['cash_accounting']['balance_delta_verified']
    assert final['cash_accounting']['debit'] == '0'
    assert final['cash_accounting']['credit'] == '1.20'
    assert final['cash_accounting']['exact_win'] == '1.20'


def test_actual_neutral_cluster_board_is_an_ordinary_paid_result(tmp_path):
    instance = runtime([payload('ordinary_zero')])
    assert ordinary_round({'bets': [DATA['ordinary_zero']['bet']]}, instance.current_constraints())
    result = instance.round(instance.config['templates']['BASIC'], tmp_path)
    assert result['known'] and result['terminal'] and result['base']
    saved = json.loads((tmp_path / 'step-001-response.json').read_text())
    assert saved['cluster_cascade_outcomes'][0]['schema'] == 'legacy-cluster-cascade/ordinary/v1'
    assert saved['cash_accounting']['balance_delta_verified']


@pytest.mark.parametrize('mutation', ['paid_debit', 'settled_credit', 'settled_exact', 'terminal'])
def test_known_clusters_never_override_actual_balance_or_final_settlement(tmp_path, mutation):
    values = [payload('mutiny_cascade'), payload('collect')]
    if mutation == 'paid_debit': values[0]['data']['buyBal']['cash'] = '1.00'
    if mutation == 'settled_credit': values[1]['data']['resultBal']['cash'] = '999.00'
    if mutation == 'settled_exact': values[1]['data']['wager']['bets'][0]['eventdata']['exactWon'] = '1.21'
    if mutation == 'terminal': values[1]['data']['wager']['status'] = 'Pending'
    instance = runtime(values)
    with pytest.raises(Unsupported):
        instance.round(instance.config['templates']['BASIC'], tmp_path)


@pytest.mark.parametrize('mutation', ['unknown_feature', 'missing_frame', 'missing_definition'])
def test_closed_cluster_wagers_cannot_bypass_current_contract(tmp_path, mutation):
    values = [payload('mutiny_cascade'), payload('collect')]
    if mutation == 'unknown_feature': values[0]['data']['wager']['bets'][0]['eventdata']['listAvalanche'][0]['type'] = 'UNKNOWN'
    if mutation == 'missing_frame': values[0]['data']['wager']['bets'][0]['eventdata'] = {'accWa': '1.20', 'nextCmds': 'C'}
    instance = runtime(values)
    if mutation == 'missing_definition': instance.config['ordinary_constraints'].pop('cluster_cascade_definition', None)
    with pytest.raises(Unsupported, match='cluster'):
        instance.round(instance.config['templates']['BASIC'], tmp_path)
