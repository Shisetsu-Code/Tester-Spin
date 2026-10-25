from copy import deepcopy
import json
from pathlib import Path

import pytest

from tester_spin.providers.yggdrasil.runtime import Unsupported, configuration, props_of
from tester_spin.providers.yggdrasil.sdk_mode_roles import source_roles

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCE = (FIXTURES / 'yggdrasil_indexed_purchase_roles.js').read_text()
GAME = json.loads((FIXTURES / 'yggdrasil_indexed_purchase_roles.json').read_text())


def test_current_sdk_menu_and_current_server_factors_authorize_both_purchase_quotes():
    config = configuration(GAME, '20003', 'EUR', sdk_source=SOURCE)
    assert config['mode_kinds'] == {'BUYIN2': 'PURCHASE', 'BUYIN1': 'PURCHASE', 'BASIC': 'SPIN'}
    assert config['templates']['BUYIN1']['amount'] == '10'
    assert config['templates']['BUYIN2']['amount'] == '50'
    assert config['unresolved'] == {}


def test_command_roles_follow_current_menu_membership_instead_of_aliases():
    source = SOURCE.replace('BUYIN1', 'PURCHASE_ALPHA').replace('BUYIN2', 'PURCHASE_BETA')
    game = json.loads(json.dumps(GAME).replace('BUYIN1', 'PURCHASE_ALPHA').replace('BUYIN2', 'PURCHASE_BETA'))
    proof = source_roles(source, props_of(game)['Modes'])
    assert proof is not None
    assert proof['purchase_price_factor_indices'] == {'PURCHASE_BETA': 1, 'PURCHASE_ALPHA': 0}
    config = configuration(game, '20003', 'EUR', sdk_source=source)
    assert config['mode_kinds']['PURCHASE_ALPHA'] == 'PURCHASE'
    assert config['templates']['PURCHASE_BETA']['amount'] == '50'


@pytest.mark.parametrize('before,after', [
    ('BUY_BONUS_MODES.includes(e)', 'UNKNOWN_MODES.includes(e)'),
    ('cmd:e', 'cmd:"UNRELATED"'),
    ('this.game.getBuyBonusCmd()', '"UNRELATED"'),
    ('e.multipliers[this.BUY_BONUS_MODES_BASIC.includes(t)?0:1]', 'e.multipliers[0]'),
    ('return e.active', 'return true'),
    ('return this.getBuyBonusBet()*e', 'return this.getBuyBonusBet()'),
])
def test_missing_menu_or_payment_binding_never_declares_a_purchase(before, after):
    assert before in SOURCE
    assert source_roles(SOURCE.replace(before, after), props_of(GAME)['Modes']) is None


def test_duplicate_conflicting_menu_is_not_a_source_proof():
    assert source_roles(SOURCE + SOURCE, props_of(GAME)['Modes']) is None


def test_malformed_current_source_membership_is_rejected_without_crashing():
    source = SOURCE.replace('["BUYIN","BUY_BONUS","SUPER_BUY_BONUS","BUYIN1","BUYIN2"]', '[{}]')
    assert source_roles(source, props_of(GAME)['Modes']) is None


def test_source_amount_and_coin_binding_cannot_authorize_a_quantity_multiplier():
    modes = deepcopy(props_of(GAME)['Modes'])
    for record in modes.values():
        record['coinsPerBet'] = 2
    assert source_roles(SOURCE, modes) is None


@pytest.mark.parametrize('change', ['factor', 'missing_factor', 'buy_in_cost', 'currency_domain', 'default_domain'])
def test_current_source_price_must_agree_with_every_current_server_denomination(change):
    game = deepcopy(GAME)
    record = next(item for item in game['cfg']['props'] if item['prop'] == 'Config')
    settings = record['value']
    if change == 'factor':
        settings['buyInConfig']['multipliers'][0] = 99
    elif change == 'missing_factor':
        settings['buyInConfig']['multipliers'].pop()
    elif change == 'buy_in_cost':
        settings['buyInCost'] = 200
    elif change == 'currency_domain':
        game['extraOrgSettings'][1]['Denoms'] = game['extraOrgSettings'][1]['Denoms'].replace('10000.0', '10000.1')
    else:
        game['extraOrgSettings'][1]['DefaultDenom'] = 'EUR:100.0'
    with pytest.raises(Unsupported):
        configuration(game, '20003', 'EUR', sdk_source=SOURCE)


def test_without_current_source_the_purchase_obligations_remain_unresolved():
    assert set(configuration(GAME, '20003', 'EUR')['unresolved']) == {'BUYIN1', 'BUYIN2'}
