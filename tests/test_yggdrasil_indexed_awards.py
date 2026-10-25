from copy import deepcopy
import json
from pathlib import Path

import pytest

from tester_spin.providers.yggdrasil.runtime import DemoRuntime, Unsupported, configuration, continuation_request, ordinary_round, validate_transition, wager_state

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCE = ''.join((FIXTURES / name).read_text() for name in ['yggdrasil_indexed_purchase_roles.js', 'yggdrasil_indexed_output_source.js', 'yggdrasil_indexed_awards_source.js'])
GAME = json.loads((FIXTURES / 'yggdrasil_indexed_purchase_roles.json').read_text())
DATA = json.loads((FIXTURES / 'yggdrasil_indexed_awards.json').read_text())
MULTIPLE_PATHS = json.loads((FIXTURES / 'yggdrasil_indexed_awards_multiple_paths.json').read_text())
INLINE = json.loads((FIXTURES / 'yggdrasil_indexed_inline_collector.json').read_text())
DIRECT = json.loads((FIXTURES / 'yggdrasil_indexed_direct_award.json').read_text())


def config():
    return configuration(GAME, '20003', 'EUR', sdk_source=SOURCE)


def test_current_safe_menu_preserves_client_bonus_request_without_creating_a_new_purchase():
    state = wager_state(DATA['round'][0])
    request = continuation_request(state, config()['ordinary_constraints'])
    assert request == {'cmd': 'COLLECT', 'type': 'bonus', 'amount': '0.1', 'coin': '0.1', 'step': '2', 'wagerid': state['wagerid']}
    assert request['cmd'] != 'GAMBLE'
    assert not ordinary_round(state, config()['ordinary_constraints'])


def test_actual_awarded_sequence_exhausts_free_spins_and_nested_respin_lives():
    before, after = map(wager_state, DATA['round'][:2])
    constraints = config()['ordinary_constraints']
    request = continuation_request(before, constraints)
    validate_transition(before, after, request, constraints)
    proof = after['indexed_award_proof']
    assert proof['initial_free_spins'] == 8
    assert proof['extra_spins'] == 2
    assert proof['played_free_spins'] == 10
    assert proof['nested_respins'] == 13
    assert proof['free_spins_remaining'] == 0 and proof['respin_lives_remaining'] == 0
    assert proof['exact_win'] == '1.84'
    assert after['cash_accounting_proof']['debit'] == '0'


def test_current_client_preserves_distinct_winning_paths_with_the_same_display_id():
    before, after = map(wager_state, MULTIPLE_PATHS['round'])
    constraints = config()['ordinary_constraints']
    validate_transition(before, after, continuation_request(before, constraints), constraints)
    proof = after['indexed_award_proof']
    assert proof['exact_win'] == '6.56'
    assert proof['played_free_spins'] == 10 and proof['extra_spins'] == 2
    assert proof['nested_respins'] == 0 and proof['free_spins_remaining'] == 0


def test_repeated_display_id_does_not_allow_a_repeated_semantic_path():
    before, after = map(wager_state, deepcopy(MULTIPLE_PATHS['round']))
    frame = after['bets'][0]['eventdata']['response']['clientData']['output'][0]['bonusInfo'][1]['freeSpinList'][0][0]
    frame['winningLines']['lines'][1] = deepcopy(frame['winningLines']['lines'][0])
    constraints = config()['ordinary_constraints']
    with pytest.raises(Unsupported):
        validate_transition(before, after, continuation_request(before, constraints), constraints)


@pytest.mark.parametrize('change', ['truncate_free', 'extra_free', 'free_credit', 'prior_credit', 'missing_retrigger', 'wrong_double', 'wrong_collect', 'wrong_positions', 'truncate_respin', 'extra_respin', 'wrong_reset', 'missing_treasure', 'changed_old_treasure', 'wrong_final_board', 'wrong_treasure_credit', 'unknown_feature', 'foreign_parent_state'])
def test_incomplete_or_unbalanced_award_is_never_accepted_as_completed(change):
    before, after = map(wager_state, deepcopy(DATA['round'][:2]))
    frame = after['bets'][0]['eventdata']['response']['clientData']['output'][0]
    award = frame['bonusInfo'][1]
    free = award['freeSpinList']
    held = next(feature for feature in free[2][0]['bonusInfo'] if feature['bonusName'] == 'HoldAndWinFeature')
    if change == 'truncate_free': free.pop()
    elif change == 'extra_free': free.append(deepcopy(free[-1]))
    elif change == 'free_credit': free[-1][0]['creditsWon'] = .04
    elif change == 'prior_credit': free[-1][0]['creditsWonAccumulated'] = 1.3
    elif change == 'missing_retrigger': free[0][0]['bonusInfo'] = [f for f in free[0][0]['bonusInfo'] if f['bonusName'] != 'AwardExtraSpin']
    elif change == 'wrong_double': free[0][0]['bonusInfo'][1]['multipliers'][0] = 4
    elif change == 'wrong_collect': free[0][0]['bonusInfo'][0]['creditsWon'] = .2
    elif change == 'wrong_positions': free[0][0]['bonusInfo'][0]['fishermanPosition'] = [6]
    elif change == 'truncate_respin': held['respinList'].pop()
    elif change == 'extra_respin': held['respinList'].append(deepcopy(held['respinList'][-1]))
    elif change == 'wrong_reset': held['respinList'][0][0]['bonusInfo'] = [{'bonusName': 'ResetLives'}]
    elif change == 'missing_treasure': held['respinList'][3][0]['treasureValues'].pop('5')
    elif change == 'changed_old_treasure': held['respinList'][3][0]['treasureValues']['5'] = 5
    elif change == 'wrong_final_board': held['resultingReels'][0][0] = 10
    elif change == 'wrong_treasure_credit': held['creditsWon'] = 1.0
    elif change == 'unknown_feature': free[1][0]['bonusInfo'].append({'bonusName': 'UnlearnedFeature'})
    else: after['bets'][0]['eventdata']['initialPlayerState']['scatters'] = 4
    constraints = config()['ordinary_constraints']
    request = continuation_request(before, constraints)
    with pytest.raises(Unsupported):
        validate_transition(before, after, request, constraints)


def test_runtime_records_full_award_proof_before_accepting_retained_metadata_as_history(tmp_path):
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = config()
    payloads = iter(deepcopy(DATA['round'] + DATA['post_award']))
    runtime.call = lambda fn, body: next(payloads)
    paid = runtime.round(runtime.config['templates']['BUYIN1'], tmp_path / 'award')
    assert paid['known'] and paid['terminal'] and not paid['base']
    assert paid['continuation_commands'] == ['COLLECT', 'C']
    normal = runtime.round(runtime.config['templates']['BASIC'], tmp_path / 'normal')
    assert normal['known'] and normal['base'] and normal['terminal']
    saved = json.loads((tmp_path / 'award/step-002-response.json').read_text())
    assert saved['indexed_award_proof']['free_spins_remaining'] == 0
    assert 'debug' not in json.dumps(saved)


def test_retained_menu_cannot_be_ignored_without_a_previous_validated_and_collected_award():
    assert not ordinary_round(wager_state(DATA['post_award'][0]), config()['ordinary_constraints'])


def test_pending_offer_requires_current_source_and_matching_scatter_positions():
    before = wager_state(deepcopy(DATA['round'][0]))
    before['bets'][0]['eventdata']['response']['clientData']['output'][0]['reelLayout'][1] = 8
    with pytest.raises(Unsupported):
        continuation_request(before, config()['ordinary_constraints'])
    source = SOURCE.replace('t.cmd="COLLECT",t.type="bonus"', 't.cmd="UNKNOWN",t.type="bonus"')
    with pytest.raises(Unsupported):
        continuation_request(wager_state(DATA['round'][0]), configuration(GAME, '20003', 'EUR', sdk_source=source)['ordinary_constraints'])


@pytest.mark.parametrize('change', ['different_session', 'changed_state', 'old_wager', 'current_feature', 'current_menu'])
def test_settled_history_is_scoped_to_session_new_wager_and_current_ordinary_state(change, tmp_path):
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = config()
    payloads = iter(deepcopy(DATA['round']))
    runtime.call = lambda fn, body: next(payloads)
    assert runtime.round(runtime.config['templates']['BUYIN1'], tmp_path / 'award')['known']
    later = deepcopy(DATA['post_award'])
    event = later[0]['data']['wager']['bets'][0]['eventdata']
    if change == 'different_session': runtime.token = 'another-test-session'
    elif change == 'changed_state': event['playerState']['scatters'] += 1
    elif change == 'old_wager': later[0]['data']['wager']['wagerid'] = DATA['round'][0]['data']['wager']['wagerid']
    elif change == 'current_feature': event['response']['clientData']['output'][0]['inGamble'] = True
    else: event['nextCmds'] = 'COLLECT,GAMBLE'
    payloads = iter(later)
    with pytest.raises(Unsupported):
        runtime.round(runtime.config['templates']['BASIC'], tmp_path / 'normal')


@pytest.mark.parametrize('change', ['reordered_features', 'duplicate_path', 'foreign_wager', 'new_debit', 'wrong_credit', 'wrong_currency', 'still_gambling'])
def test_award_order_paths_and_financial_settlement_are_separate_obligations(change, tmp_path):
    values = deepcopy(DATA['round'])
    output = values[1]['data']['wager']['bets'][0]['eventdata']['response']['clientData']['output'][0]
    free = output['bonusInfo'][1]['freeSpinList']
    if change == 'reordered_features': free[0][0]['bonusInfo'].insert(0, free[0][0]['bonusInfo'].pop())
    elif change == 'duplicate_path': free[-1][0]['winningLines']['lines'].append(deepcopy(free[-1][0]['winningLines']['lines'][0]))
    elif change == 'foreign_wager': values[-1]['data']['wager']['wagerid'] = 'fixture-foreign'
    elif change == 'new_debit': values[1]['data']['wager']['bets'][0]['betamount'] = '.1'
    elif change == 'wrong_credit': values[-1]['data']['resultBal']['cash'] = '999.99'
    elif change == 'wrong_currency': values[-1]['data']['wager']['bets'][0]['betcurrency'] = 'USD'
    else: output['inGamble'] = True
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = config()
    payloads = iter(values)
    runtime.call = lambda fn, body: next(payloads)
    with pytest.raises(Unsupported):
        runtime.round(runtime.config['templates']['BUYIN1'], tmp_path)
    assert runtime.indexed_award_history is None


@pytest.mark.parametrize('before,after', [
    ('this.freeSpins.leftUpdate--', 'this.freeSpins.leftUpdate'),
    ('this.freeSpins.leftUpdate+=1', 'this.freeSpins.leftUpdate+=2'),
    ('e.scope.model.prize*+this.slot.bet*this.arr[e.scope.model.reelIndex]', 'e.scope.model.prize*+this.slot.bet'),
    ('e.scope.model.prize*+this.slot.bet*this.arr[e.scope.model.reelIndex]', 'e.scope.model.prize*+this.slot.bet*this.arr[e.scope.model.reelIndex]*2'),
    ('t.cmd="COLLECT",t.type="bonus",t.step=this.game.getStep()+1,', 't.cmd="COLLECT",t.type="bonus",t.step=this.game.getStep()+1,t.amount=100,'),
    ('e.outcome.activeMultiplier=t.multiplier,e.outcome.featureData={isFishCollected:!0,collectedPrice:t.creditsWon}', 'e.outcome.activeMultiplier=2,e.outcome.featureData={isFishCollected:!0,collectedPrice:t.creditsWon}'),
    ('case this.TYPES.FREESPINS_NAME:this.mapFreeSpins(e,t);break;', 'case this.TYPES.FREESPINS_NAME:this.mapUnknown(e,t);break;'),
])
def test_advance_requires_current_counter_payment_and_dispatch_bindings(before, after):
    assert before in SOURCE
    current = configuration(GAME, '20003', 'EUR', sdk_source=SOURCE.replace(before, after))['ordinary_constraints']
    assert 'indexed_award_definition' not in current


@pytest.mark.parametrize('before,after', [
    ('this.totalFreeSpins=t.count,', 'this.totalFreeSpins=t.count+1,'),
    ('this.freeSpins.leftUpdate=this.freeSpins.left,', 'this.freeSpins.leftUpdate=this.freeSpins.left+1,'),
    ('e.outcome.respinLeft=3,t.respinList', 'e.outcome.respinLeft=30,t.respinList'),
    ('this.freeSpins.totalWin=(e.creditsWon||0)+e.creditsWonAccumulated+this.initialSpinWin,',
     'this.freeSpins.totalWin=(e.creditsWon||0)+e.creditsWonAccumulated+this.initialSpinWin+1,'),
])
def test_changed_queue_counters_or_total_cannot_certify_the_old_award(before, after, tmp_path):
    assert SOURCE.count(before) == 1
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = configuration(GAME, '20003', 'EUR', sdk_source=SOURCE.replace(before, after))
    payloads = iter(deepcopy(DATA['round']))
    runtime.call = lambda fn, body: next(payloads)
    with pytest.raises(Unsupported, match='indexed award continuation'):
        runtime.round(runtime.config['templates']['BUYIN1'], tmp_path)
    assert runtime.indexed_award_history is None


@pytest.mark.parametrize('before,after,field,expected', [('e.outcome.respinLeft=3', 'e.outcome.respinLeft=4', 'respin_lives', 4), ('return e/2', 'return e/3', 'duplicate_factor', 3)])
def test_counters_come_from_current_source_and_changed_rules_reject_the_old_capture(before, after, field, expected):
    current = configuration(GAME, '20003', 'EUR', sdk_source=SOURCE.replace(before, after))['ordinary_constraints']
    assert current['indexed_award_definition'][field] == expected
    initial, accepted = map(wager_state, deepcopy(DATA['round'][:2]))
    with pytest.raises(Unsupported):
        validate_transition(initial, accepted, continuation_request(initial, current), current)


def test_current_purchase_bonus_name_must_match_server_configuration():
    current = deepcopy(GAME)
    props = current['cfg']['props']
    config_prop = next(item for item in props if item['prop'] == 'Config')
    value = json.loads(config_prop['value']) if isinstance(config_prop['value'], str) else config_prop['value']
    value['buyInConfig']['bonusGames'] = ['changed-current-award', 'bonus2']
    config_prop['value'] = json.dumps(value)
    with pytest.raises(Unsupported):
        continuation_request(wager_state(DATA['round'][0]), configuration(current, '20003', 'EUR', sdk_source=SOURCE)['ordinary_constraints'])


def test_a_closed_purchase_with_unknown_indexed_source_is_never_promoted(tmp_path):
    values = deepcopy([DATA['round'][0], DATA['round'][2]])
    root = values[0]['data']['wager']['bets'][0]
    accepted = DATA['round'][1]['data']['wager']['bets'][0]
    root['eventdata'] = deepcopy(accepted['eventdata'])
    root['betdata']['accWa'] = accepted['betdata']['accWa']
    root['betdata']['cmds'] = ['C']
    values[-1]['data']['wager']['bets'][0]['step'] = 2
    changed = SOURCE.replace('e.outcome.reelLengthByIndex=[3,3,3,3,3,3]', 'e.outcome.reelLengthByIndex=[3,3,3,3,3,4]')
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = configuration(GAME, '20003', 'EUR', sdk_source=changed)
    assert 'indexed_output_definition' not in runtime.config['ordinary_constraints']
    payloads = iter(values)
    runtime.call = lambda fn, body: next(payloads)
    with pytest.raises(Unsupported, match='Unlearned indexed output'):
        runtime.round(runtime.config['templates']['BUYIN1'], tmp_path)


def test_current_indexed_declaration_cannot_be_bypassed_by_missing_output(tmp_path):
    payload = deepcopy(DATA['round'][0])
    wager = payload['data']['wager']
    wager['status'] = 'Finished'
    root = wager['bets'][0]
    root['betdata'].pop('cmds', None)
    root['eventdata'].pop('nextCmds', None)
    root['eventdata']['response']['clientData'].pop('output')
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = config()
    runtime.call = lambda fn, body: payload
    with pytest.raises(Unsupported, match='Unlearned indexed output'):
        runtime.round(runtime.config['templates']['BUYIN1'], tmp_path)


def test_zero_cost_step_format_cannot_reduce_current_currency_precision(tmp_path):
    from decimal import Decimal
    values = deepcopy(DATA['round'])
    values[1]['data']['wager']['bets'][0]['betamount'] = '0.0'
    final = values[-1]['data']
    final['resultBal']['cash'] = str(Decimal(final['resultBal']['cash']) - Decimal('.04'))
    collected = final['wager']['bets'][0]
    collected['wonamount'] = '1.80'
    collected['prizes'][0]['wonamount'] = '1.80'
    collected['prizes'][0]['netamount'] = '1.80'
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = config()
    payloads = iter(values)
    runtime.call = lambda fn, body: next(payloads)
    with pytest.raises(Unsupported, match='Cash ledger'):
        runtime.round(runtime.config['templates']['BUYIN1'], tmp_path)
    assert runtime.indexed_award_history is None


def test_actual_inline_collector_is_known_and_settled_but_cannot_count_as_ordinary(tmp_path):
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = config()
    payloads = iter(deepcopy(INLINE['round']))
    runtime.call = lambda fn, body: next(payloads)
    assert not ordinary_round(wager_state(INLINE['round'][0]), config()['ordinary_constraints'])
    result = runtime.round(runtime.config['templates']['BASIC'], tmp_path)
    assert result['known'] and result['terminal'] and not result['base']
    assert result['continuation_commands'] == ['C']
    saved = json.loads((tmp_path / 'step-001-response.json').read_text())
    assert saved['indexed_output_outcomes'][0]['schema'] == 'indexed-cash-path-inline-feature/v1'


@pytest.mark.parametrize('change', ['collector_position', 'collector_credit', 'feature_order', 'unknown_source'])
def test_inline_collection_requires_positions_awards_order_and_current_source(change, tmp_path):
    values = deepcopy(INLINE['round'])
    frame = values[0]['data']['wager']['bets'][0]['eventdata']['response']['clientData']['output'][0]
    if change == 'collector_position': frame['bonusInfo'][0]['fishermanPosition'] = [1]
    elif change == 'collector_credit': frame['bonusInfo'][0]['creditsWon'] = .2
    elif change == 'feature_order': frame['bonusInfo'].reverse()
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = config() if change != 'unknown_source' else configuration(GAME, '20003', 'EUR', sdk_source=SOURCE.replace('collectedPrice:t.creditsWon', 'collectedPrice:100*t.creditsWon'))
    payloads = iter(values)
    runtime.call = lambda fn, body: next(payloads)
    with pytest.raises(Unsupported):
        runtime.round(runtime.config['templates']['BASIC'], tmp_path)


def test_actual_direct_purchase_exhausts_its_announced_queue_and_settles_current_price(tmp_path):
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = config()
    payloads = iter(deepcopy(DIRECT['prior_round'] + DIRECT['round']))
    runtime.call = lambda fn, body: next(payloads)
    assert runtime.round(runtime.config['templates']['BUYIN1'], tmp_path / 'prior')['known']
    result = runtime.round(runtime.config['templates']['BUYIN2'], tmp_path / 'direct')
    assert result['known'] and result['terminal'] and not result['base']
    assert result['continuation_commands'] == ['C']
    saved = json.loads((tmp_path / 'direct/step-001-response.json').read_text())
    proof = saved['indexed_award_proof']
    assert proof['initial_free_spins'] == 20 and proof['extra_spins'] == 3
    assert proof['played_free_spins'] == 23 and proof['free_spins_remaining'] == 0
    assert proof['exact_win'] == '58'


@pytest.mark.parametrize('change', ['missing_history', 'foreign_bonus', 'scatter_count', 'truncated_queue', 'unknown_feature'])
def test_direct_purchase_cannot_bypass_history_source_or_queue_obligations(change, tmp_path):
    values = deepcopy(DIRECT['round'])
    frame = values[0]['data']['wager']['bets'][0]['eventdata']['response']['clientData']['output'][0]
    if change == 'foreign_bonus': frame['bonusGame'] = 'unlearned-bonus'
    elif change == 'scatter_count': frame['bonusInfo'][0]['scatters'] = 5
    elif change == 'truncated_queue': frame['bonusInfo'][0]['freeSpinList'].pop()
    elif change == 'unknown_feature': frame['bonusInfo'][0]['freeSpinList'][0][0]['bonusInfo'].append({'bonusName': 'UnknownFeature'})
    runtime = DemoRuntime(None, '20003', 1, None)
    runtime.config = config()
    payloads = iter(deepcopy(DIRECT['prior_round']) + values)
    runtime.call = lambda fn, body: next(payloads)
    runtime.round(runtime.config['templates']['BUYIN1'], tmp_path / 'prior')
    if change == 'missing_history': runtime.indexed_award_history = None
    with pytest.raises(Unsupported):
        runtime.round(runtime.config['templates']['BUYIN2'], tmp_path / 'direct')
