from copy import deepcopy
import json
from pathlib import Path

import pytest

from tester_spin.providers.yggdrasil.runtime import DemoRuntime, Unsupported, configuration, ordinary_round, wager_state

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCE = (FIXTURES / 'yggdrasil_indexed_purchase_roles.js').read_text() + (FIXTURES / 'yggdrasil_indexed_output_source.js').read_text()
GAME = json.loads((FIXTURES / 'yggdrasil_indexed_purchase_roles.json').read_text())
ROUNDS = json.loads((FIXTURES / 'yggdrasil_indexed_output.json').read_text())['rounds']


def constraints():
    return configuration(GAME, '20003', 'EUR', sdk_source=SOURCE)['ordinary_constraints']


@pytest.mark.parametrize('index', range(4))
def test_actual_closed_base_paths_and_board_derived_double_multiplier_are_ordinary(index):
    assert ordinary_round(wager_state(ROUNDS[index][0]), constraints())


def test_source_geometry_symbol_roles_and_multiplier_domain_are_current_declarations():
    value = constraints()['indexed_output_definition']
    assert value['height'] == 3 and value['width'] == 6
    assert value['symbols'] == {'fish': 5, 'treasure': 10, 'collector': 11, 'diver': 12, 'scatter': 13}
    assert value['multipliers'] == [1, 2, 4, 8, 16, 32]
    assert value['bet_divisor'] == 10
    assert value['awards']['8']['3'] == '1'


@pytest.mark.parametrize('before,after', [
    ('e.outcome.reelLengthByIndex=[3,3,3,3,3,3]', 'e.outcome.reelLengthByIndex=[3,3,3,3,3]'),
    ('r.multipliedAmount=e.creditsWon*(e.multiplier||1)', 'r.multipliedAmount=e.creditsWon*2'),
    ('r.multipliedAmount=e.creditsWon*(e.multiplier||1)', 'r.multipliedAmount=e.creditsWon*(e.multiplier||1)*2'),
    ('var e=e-1,t=e%i.numberOfReels', 'var e=e,t=e%i.numberOfReels'),
    ('this.scope.game.doubleMax=null,this.scope.game.activeMultiplier=null', 'this.scope.game.doubleMax=null'),
    ('e.outcome.fishermanSymbol.push', 'e.outcome.unknownCollector.push'),
])
def test_source_without_proven_geometry_payment_index_or_reset_does_not_declare_family(before, after):
    assert before in SOURCE
    assert 'indexed_output_definition' not in configuration(GAME, '20003', 'EUR', sdk_source=SOURCE.replace(before, after))['ordinary_constraints']


def test_symbol_role_extraction_follows_renderer_without_title_or_numeric_aliases():
    changed = SOURCE.replace('LeanderNiceCatchTooWildLegaCommunicationService', 'AnotherCurrentRenderer').replace('"sym05"==t', '"sym07"==t')
    value = configuration(GAME, '20003', 'EUR', sdk_source=changed)['ordinary_constraints']['indexed_output_definition']
    assert value['symbols']['fish'] == 7


def test_duplicate_child_symbol_overrides_do_not_look_like_absent_overrides():
    override = 'sna.service.leanderProvider.LeanderNiceCatchTooWildLegaCommunicationService.prototype.mapSymbol=function(e){return "unknown"};'
    assert 'indexed_output_definition' not in configuration(GAME, '20003', 'EUR', sdk_source=SOURCE + override + override)['ordinary_constraints']


def test_child_win_override_cannot_be_authorized_by_a_shadowed_parent_method():
    override = 'sna.service.leanderProvider.LeanderNiceCatchTooWildLegaCommunicationService.prototype.mapWins=function(n,e){n.outcome.wins=[]};'
    assert 'indexed_output_definition' not in configuration(GAME, '20003', 'EUR', sdk_source=SOURCE + override)['ordinary_constraints']


@pytest.mark.parametrize('change', ['position', 'symbol', 'amount', 'omitted_win', 'duplicate_win', 'fish_missing', 'fish_foreign', 'false_multiplier', 'false_count', 'feature', 'extra_output', 'player_state', 'response_cash', 'stake'])
def test_malformed_paths_or_unlearned_features_cannot_count_as_ordinary(change):
    state = wager_state(deepcopy(ROUNDS[0 if change in {'position', 'symbol', 'amount', 'omitted_win', 'duplicate_win', 'response_cash', 'stake'} else 2][0]))
    bet = state['bets'][0]
    event = bet['eventdata']
    output = event['response']['clientData']['output']
    frame = output[0]
    if change == 'position': frame['winningLines']['lines'][0]['matchPositions'][1] = 4
    elif change == 'symbol': frame['winningLines']['lines'][0]['symbol'] = 3
    elif change == 'amount': frame['winningLines']['lines'][0]['creditsWon'] = .02
    elif change == 'omitted_win': frame['winningLines'] = {'lines': [], 'creditsWon': .01}
    elif change == 'duplicate_win': frame['winningLines']['lines'].append(deepcopy(frame['winningLines']['lines'][0]))
    elif change == 'fish_missing': frame['fishValues'].pop('8')
    elif change == 'fish_foreign': frame['fishValues']['1'] = 2
    elif change == 'false_multiplier': frame['bonusInfo'][0]['multiplier'] = 4
    elif change == 'false_count': frame['bonusInfo'][0]['consecutive'] = 3
    elif change == 'feature': frame['bonusInfo'].append({'bonusName': 'UnlearnedFeature'})
    elif change == 'extra_output': output.append(deepcopy(frame))
    elif change == 'player_state': event['playerState']['featureActive'] = True
    elif change == 'response_cash': event['response']['cashWin'] = '.02'
    elif change == 'stake': bet['betamount'] = '.20'
    assert not ordinary_round(state, constraints())


def test_absent_renderer_or_conflicting_current_paytable_does_not_recognize_shape_only():
    assert not ordinary_round(wager_state(ROUNDS[0][0]), configuration(GAME, '20003', 'EUR')['ordinary_constraints'])
    c = constraints()
    c['indexed_output_definition']['awards']['8']['3'] = '2'
    assert not ordinary_round(wager_state(ROUNDS[0][0]), c)


def test_same_real_round_reconciles_debit_prize_collect_and_safe_evidence(tmp_path):
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = configuration(GAME, '20003', 'EUR', sdk_source=SOURCE)
    payloads = iter(deepcopy(ROUNDS[0]))
    runtime.call = lambda fn, body: next(payloads)
    result = runtime.round(runtime.config['templates']['BASIC'], tmp_path)
    assert result['base'] and result['known'] and result['terminal']
    assert result['continuation_commands'] == ['C']
    evidence = json.loads((tmp_path / 'step-002-response.json').read_text())
    assert evidence['cash_accounting']['exact_win'] == '0.01'
    original = json.loads((tmp_path / 'step-001-response.json').read_text())
    assert original['indexed_output_outcomes'][0]['data']['response']['clientData']['output'][0]['winningLines']['lines']
    assert 'initialBalance' not in json.dumps(original)


def test_unknown_root_cannot_be_covered_by_collect_and_later_ordinary_rounds(tmp_path):
    payload = deepcopy(ROUNDS[2][0])
    payload['data']['wager']['bets'][0]['eventdata']['response']['clientData']['output'][0]['bonusInfo'].append({'bonusName': 'UnlearnedFeature'})
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = configuration(GAME, '20003', 'EUR', sdk_source=SOURCE)
    runtime.call = lambda fn, body: payload
    with pytest.raises(Unsupported, match='Unlearned indexed output'):
        runtime.round(runtime.config['templates']['BASIC'], tmp_path)


@pytest.mark.parametrize('part', ['debit', 'collect'])
def test_indexed_output_requires_real_debit_and_credit_to_match_award(part, tmp_path):
    rounds = deepcopy(ROUNDS[0])
    rounds[0 if part == 'debit' else 1]['data']['resultBal']['cash'] = '999.01'
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = configuration(GAME, '20003', 'EUR', sdk_source=SOURCE)
    payloads = iter(rounds)
    runtime.call = lambda fn, body: next(payloads)
    with pytest.raises(Unsupported, match='Cash ledger'):
        runtime.round(runtime.config['templates']['BASIC'], tmp_path)
