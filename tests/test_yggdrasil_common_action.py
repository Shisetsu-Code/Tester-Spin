from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from tester_spin.providers.yggdrasil.runtime import DemoRuntime, Unsupported, configuration
from tester_spin.return_to_base import verify_return_to_base

FIXTURES = Path(__file__).parent / 'fixtures'
DATA = json.loads((FIXTURES / 'yggdrasil_common_action.json').read_text())
SOURCE = (FIXTURES / 'yggdrasil_common_action_source.js').read_text()


def config(source=SOURCE):
    return configuration(deepcopy(DATA['game']), '10447', 'EUR', sdk_source=source)


def runtime(rounds=None):
    instance = DemoRuntime(None, '10447', 1, threading.Event(), gate=None)
    instance.config = config()
    values = iter(deepcopy(rounds if rounds is not None else [item for round_ in DATA['rounds'] for item in round_]))
    instance.sent = []
    def call(fn, body):
        instance.sent.append(deepcopy(body))
        return next(values)
    instance.call = call
    return instance


def test_current_source_and_config_bind_purchase_price_stake_and_typed_request(tmp_path):
    instance = runtime(DATA['rounds'][0])
    result = instance.round(instance.config['templates']['BUY'], tmp_path)
    request = instance.sent[0]
    assert request['amount'] == '19' and request['coin'] == '0.02'
    assert json.loads(request['clientParams']) == {
        'type': 'GameActionRequest', 'message_id': '1',
        'params': {'action_type': 'BuyGameAction', 'id': 'BUY', 'bet_amount': 20},
    }
    assert result['known'] and result['terminal'] and not result['base']
    assert result['continuation_commands'] == ['C']
    saved = json.loads((tmp_path / 'step-001-response.json').read_text())
    assert saved['common_action_proof']['frames'] == 11
    assert saved['common_action_proof']['free_spins_played'] == 7
    assert saved['common_action_proof']['exact_win'] == '5.06'
    collected = json.loads((tmp_path / 'step-002-response.json').read_text())
    assert collected['cash_accounting']['balance_delta_verified']
    assert collected['cash_accounting']['settled_win'] == '5.06'


def test_full_buy_queue_and_same_session_saved_per_stake_state_return_to_base(tmp_path):
    instance = runtime()
    instance.round(instance.config['templates']['BUY'], tmp_path / 'purchase')
    proof = verify_return_to_base(tmp_path / 'purchase', lambda path: instance.round(instance.config['templates']['BASIC'], path), max_probes=2)
    assert proof['status'] == 'CONFIRMED' and proof['consecutive_base'] == 2
    assert [json.loads(body['clientParams'])['message_id'] for body in instance.sent if 'clientParams' in body] == ['1', '2', '3']
    assert instance.common_action_history['player_state']['counters']['FREE_SPINS_PURCHASE']['value_per_bet'] == {'20': False}


@pytest.mark.parametrize('change', [
    'missing_frame', 'duplicate_frame', 'free_count', 'wrong_previous_panel',
    'wrong_accumulator', 'wrong_way', 'omitted_way', 'walking_credit', 'walking_payout',
    'final_pending_counter', 'foreign_stake', 'paid_debit', 'collect_credit',
    'collect_exact', 'last_state', 'unknown_win', 'extra_action', 'wrong_stake',
])
def test_complete_wire_queue_cannot_certify_changed_obligations_or_ledger(tmp_path, change):
    replies = deepcopy(DATA['rounds'][0]);bets = replies[0]['data']['wager']['bets']
    data = lambda index: bets[index]['eventdata']['response']['clientData']['data']
    if change == 'missing_frame': bets.pop(3)
    elif change == 'duplicate_frame': bets.insert(4, deepcopy(bets[3]))
    elif change == 'free_count': data(3)['counters']['FREE_SPINS']['value_per_bet']['20'] += 1
    elif change == 'wrong_previous_panel': data(4)['previous_panel_per_bet']['20']['reels'][0][0] = 'L6'
    elif change == 'wrong_accumulator': data(5)['round_winnings'] += 1
    elif change == 'wrong_way': data(3)['winnings']['WINNING_WAYS'][0]['winnings'] += 1
    elif change == 'omitted_way': data(5)['winnings']['WINNING_WAYS'].pop()
    elif change == 'walking_credit': data(6)['transforms']['WALKING_WILDS'][0]['winnings'] += 1
    elif change == 'walking_payout': data(9)['winnings']['WALKING_SYMBOLS_MULTIPLIER'][0]['winnings'] += 1
    elif change == 'final_pending_counter':
        data(10)['counters']['FREE_SPINS']['value_per_bet']['20'] = 1
        bets[-1]['eventdata']['playerState']['counters']['FREE_SPINS']['value_per_bet']['20'] = 1
    elif change == 'foreign_stake': bets[-1]['eventdata']['playerState']['counters']['FREE_SPINS']['value_per_bet']['40'] = 5
    elif change == 'paid_debit': replies[0]['data']['buyBal']['cash'] = '10982.00'
    elif change == 'collect_credit': replies[1]['data']['resultBal']['cash'] = '10987.06'
    elif change == 'collect_exact': replies[1]['data']['wager']['bets'][0]['eventdata']['exactWon'] = '5.07'
    elif change == 'last_state': data(10)['state'] = 'FREE_SPINS'
    elif change == 'unknown_win': data(4)['winnings']['UNLEARNED_AWARD'] = []
    elif change == 'extra_action': data(10)['available_actions'].append('Gamble')
    elif change == 'wrong_stake': data(5)['bet_amount'] = 1900
    instance = runtime(replies)
    with pytest.raises(Unsupported, match='Pasos repetidos' if change == 'duplicate_frame' else 'Common action'):
        instance.round(instance.config['templates']['BUY'], tmp_path)
    assert instance.common_action_history is None


@pytest.mark.parametrize('change', ['previous_state', 'balance', 'session'])
def test_settled_result_does_not_authorize_unbound_persistent_history(tmp_path, change):
    replies = deepcopy(DATA['rounds'][0] + DATA['rounds'][1])
    if change == 'previous_state': replies[-1]['data']['wager']['bets'][0]['eventdata']['initialPlayerState']['counters']['COLLECTED_SCATTERS']['value_per_bet']['20'] = 0
    elif change == 'balance': replies[-1]['data']['wager']['bets'][0]['betdata']['initialBalance'] = '10987.06'
    instance = runtime(replies)
    instance.round(instance.config['templates']['BUY'], tmp_path / 'purchase')
    if change == 'session': instance.token = 'different-demo-session'
    with pytest.raises(Unsupported, match='Common action'):
        instance.round(instance.config['templates']['BASIC'], tmp_path / 'return')


@pytest.mark.parametrize('old,new', [
    ('bet_amount:r}},s=JSON.stringify(i)', 'bet_amount:r+1}},s=JSON.stringify(i)'),
    ('freeSpinRemaining:ge.includes(a.gameState)?r.counters.FREE_SPINS.value_per_bet[r.bet_amount]:0', 'freeSpinRemaining:ge.includes(a.gameState)?r.counters.FREE_SPINS.value_per_bet[r.bet_amount]+1:0'),
    ('n.winnings+=L.winnings,n.winIncluded=!0', 'n.winnings+=L.winnings+1,n.winIncluded=!0'),
    ('t.closesGameRound=r.data.closes_game_round,t.wager=n', 't.closesGameRound=!0,t.wager=n'),
])
def test_changed_complete_client_expressions_cannot_declare_old_contract(old, new):
    assert old in SOURCE
    assert 'common_action_definition' not in config(SOURCE.replace(old, new))['ordinary_constraints']


def test_current_config_without_bound_source_keeps_purchase_unexecutable():
    value = config(None)
    assert 'BUY' in value['unresolved'] and 'BUY' not in value['templates']


def test_official_loader_accepts_current_action_contract_without_invented_mode_roles(tmp_path):
    from tester_spin.providers.yggdrasil.runtime import props_of
    from tester_spin.providers.yggdrasil.sdk_mode_roles import load_source
    class Response:
        status_code = 200
        def __init__(self, text, url): self.text, self.url = text, url
    class HTTP:
        def get(self, url, timeout):
            if '/init/' in url:
                return Response('<script src="engine.js"></script>', 'https://staticdemo.yggdrasilgaming.com/10447/index.html')
            return Response(SOURCE, url)
    page = '<div data-iframe-src="https://staticdemo.yggdrasilgaming.com/init/launchClient.html?org=Demo&amp;gameid=10447"></div>'
    source = load_source(HTTP(), page, '10447', config()['wire_modes'], tmp_path, 1, props=props_of(DATA['game']))
    assert source == SOURCE
    assert (tmp_path / 'sdk-common-action-proof.json').exists()


def test_closed_purchase_cannot_use_its_command_as_proof_without_action_source(tmp_path):
    instance = runtime(DATA['rounds'][0])
    instance.config['ordinary_constraints'].pop('common_action_definition')
    with pytest.raises(Unsupported, match='Common action: Missing current'):
        instance.round(instance.config['templates']['BUY'], tmp_path)
    assert instance.common_action_history is None


def test_changed_typed_internal_stake_is_rejected_before_any_paid_request(tmp_path):
    instance = runtime(DATA['rounds'][0])
    template = deepcopy(instance.config['templates']['BUY'])
    template['clientParams'] = json.dumps({'type': 'GameActionRequest', 'message_id': '1', 'params': {'action_type': 'BuyGameAction', 'id': 'BUY', 'bet_amount': 1900}})
    with pytest.raises(Unsupported, match='Conflicting explicit typed'):
        instance.round(template, tmp_path)
    assert instance.sent == []


@pytest.mark.parametrize('override', [
    'Ye.trigger=function(e){return w().spin({amount:999,coin:0.02})},',
    'Ye["trigger"]=function(e){return w().spin({amount:999,coin:0.02})},',
    'Object.assign(Ye,{trigger:function(e){return w().spin({amount:999,coin:0.02})}}),',
    'Object.defineProperty(Ye,"trigger",{value:function(e){return w().spin({amount:999,coin:0.02})}}),',
    'Alias=Ye,Alias.trigger=function(e){return w().spin({amount:999,coin:0.02})},',
    'Ze={trigger:function(e){return w().spin({amount:999,coin:0.02})}},',
])
def test_rebound_renderer_objects_and_aliases_cannot_authorize_prior_request(override):
    anchor = 'On[o.GameActionTypes.SPIN]=Ye,On[o.GameActionTypes.BUY]=Ze,'
    assert 'common_action_definition' not in config(SOURCE.replace(anchor, anchor + override))['ordinary_constraints']


@pytest.mark.parametrize('value', [False, 0.0])
def test_counter_metadata_uses_exact_json_types_across_persistent_history(tmp_path, value):
    replies = deepcopy(DATA['rounds'][0] + DATA['rounds'][1])
    replies[-1]['data']['wager']['bets'][0]['eventdata']['initialPlayerState']['counters']['COLLECTED_SCATTERS']['limits'][0] = value
    instance = runtime(replies)
    instance.round(instance.config['templates']['BUY'], tmp_path / 'purchase')
    with pytest.raises(Unsupported, match='Common action'):
        instance.round(instance.config['templates']['BASIC'], tmp_path / 'return')


def test_current_loader_reads_declared_engine_assets_without_parsing_ui_bundles(tmp_path, monkeypatch):
    from tester_spin.providers.yggdrasil.runtime import props_of
    from tester_spin.providers.yggdrasil import sdk_mode_roles
    def unrelated(*args, **kwargs):
        raise AssertionError('Unrelated mode grammar must not parse a declared CommonAPI game')
    monkeypatch.setattr(sdk_mode_roles, 'source_roles', unrelated)
    loader = (FIXTURES / 'yggdrasil_common_action_loader.js').read_text()
    engine, extension = SOURCE.split('\n!function(L)', 1)
    extension = '!function(L)' + extension
    class Response:
        status_code = 200
        def __init__(self, text, url): self.text, self.url = text, url
    class HTTP:
        def get(self, url, timeout):
            if '/init/' in url:
                return Response('<script src="game-menu/index.js"></script><script src="debug-loader.js"></script>', 'https://staticdemo.yggdrasilgaming.com/10447/index.html')
            if url.endswith('/debug-loader.js'): return Response(loader, url)
            if '/engine-extensions.' in url: return Response(extension, url)
            if '/engine.' in url: return Response(engine, url)
            raise AssertionError('Undeclared/unrelated asset requested: ' + url)
    page = '<div data-iframe-src="https://staticdemo.yggdrasilgaming.com/init/launchClient.html?org=Demo&amp;gameid=10447"></div>'
    source = sdk_mode_roles.load_source(HTTP(), page, '10447', {'BASIC': {'coinsPerBet': 10}, 'BUY': {'coinsPerBet': 950}}, tmp_path, 1, props=props_of(DATA['game']))
    assert source == SOURCE
    assert (tmp_path / 'sdk-common-action-loader.js').read_text() == loader
    assert config(source)['ordinary_constraints']['common_action_definition']


def test_complete_current_queue_credits_only_ways_containing_each_wild(tmp_path):
    from tester_spin.providers.yggdrasil.common_action import prepare_request, validate
    from tester_spin.providers.yggdrasil.runtime import wager_state
    captured = json.loads((FIXTURES / 'yggdrasil_common_action_multiple_ways.json').read_text())
    instance = runtime([response for round_ in captured['rounds'][:3] for response in round_])
    instance.config = configuration(captured['game'], '10447', 'EUR', sdk_source=SOURCE)
    for index in range(3):
        instance.round(instance.config['templates']['BASIC'], tmp_path / str(index))
    request = prepare_request(instance.config['templates']['BUY'], instance.current_constraints(), 4)
    state = wager_state(captured['rounds'][3][0])
    proof = validate(state, instance.current_constraints(), request)
    assert proof['frames'] == 12 and proof['free_spins_played'] == 7
    assert proof['exact_win'] == '3.10'
    assert state['commands'] == ['C'] and not state['terminal']
    wrong_column = deepcopy(state)
    exit_award = wrong_column['bets'][10]['eventdata']['response']['clientData']['data']['winnings']['WALKING_SYMBOLS_MULTIPLIER'][0]
    exit_award.update(id='WI_2_10x', winnings=160)
    with pytest.raises(ValueError, match='Walking multiplier prize changed'):
        validate(wrong_column, instance.current_constraints(), request)
    outer_reel = deepcopy(state)
    outer_reel['bets'][6]['eventdata']['response']['clientData']['data']['original_panel']['reels'][0][0] = 'WI'
    with pytest.raises(ValueError, match='Wild outside declared middle reels'):
        validate(outer_reel, instance.current_constraints(), request)
    # The first of two equal L3 ways contains a regular symbol at this reel;
    # only the other way contributes six cents to the wild's later multiplier.
    state['bets'][6]['eventdata']['response']['clientData']['data']['winnings']['WILD_WINNINGS'][0]['winnings'] = 12
    with pytest.raises(ValueError, match='Wild collection differs'):
        validate(state, instance.current_constraints(), request)


@pytest.mark.parametrize('regular_in_wild_column,aggregations,total', [(False, 8, 48), (True, 12, 72)])
def test_two_wilds_collect_their_own_paths_with_multiple_matches_on_other_reels(regular_in_wild_column, aggregations, total):
    from decimal import Decimal
    from tester_spin.providers.yggdrasil.common_action import _ways
    rules = config()['ordinary_constraints']['common_action_definition']
    board = [['L3', 'L3', 'H1'], ['WI', 'WI', 'L3' if regular_in_wild_column else 'H2'],
             ['L3', 'L3', 'H3'], ['H4', 'H4', 'H4'], ['H5', 'H5', 'H5']]
    symbols = [{'symbol': value, 'coordinates': {'reel': col, 'row': row}}
               for col, column in enumerate(board[:3]) for row, value in enumerate(column) if value in ('L3', 'WI')]
    award = {'id': 'L3', 'winnings': total, 'winning_type': 'Way', 'prize_type': 'Money',
             'source': {'type': 'Symbols', 'main_symbol': 'L3', 'occurrences': 3,
                        'winning_symbols': symbols, 'aggregations': aggregations}}
    cash, credits = _ways([award], board, 20, rules)
    assert cash == total
    # Each wild participates in four six-cent paths (two choices on each
    # neighbouring reel), regardless of a third regular match beside it.
    assert credits == {(1, 0): Decimal(24), (1, 1): Decimal(24)}
