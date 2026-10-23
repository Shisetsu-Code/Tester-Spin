"""Current official Config and sanitized DEMO regression, not invented payouts."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import re

import pytest


FIXTURE = json.loads((Path(__file__).parent / 'fixtures/yggdrasil_cluster_cascades.json').read_text())
SOURCE = (Path(__file__).parent / 'fixtures/yggdrasil_cluster_cascades_source.js').read_text()
REPEATED = json.loads((Path(__file__).parent / 'fixtures/yggdrasil_cluster_cascades_repeated.json').read_text())


def test_actual_mutiny_cascade_is_known_but_preserves_its_feature_status():
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration, known, ordinary

    constraints = copy.deepcopy(FIXTURE['constraints'])
    constraints['cluster_cascade_definition'] = declaration(FIXTURE['props'], SOURCE)
    bet = FIXTURE['mutiny_cascade']['bet']
    assert constraints['cluster_cascade_definition'] is not None
    # Ten preserved HIGH3 symbols, twelve current coins each, coin EUR 0.01.
    assert bet['eventdata']['wonCoins'] == 120
    assert bet['eventdata']['wonMoney'] == '1.20'
    assert known(bet, constraints)
    assert not ordinary(bet, constraints)


def test_actual_zero_after_collection_is_an_ordinary_paid_round():
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration, known, ordinary

    constraints = copy.deepcopy(FIXTURE['constraints'])
    constraints['cluster_cascade_definition'] = declaration(FIXTURE['props'], SOURCE)
    bet = FIXTURE['ordinary_zero']['bet']
    assert known(bet, constraints)
    assert ordinary(bet, constraints)


@pytest.fixture(scope='module')
def definition():
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    result = declaration(FIXTURE['props'], SOURCE)
    assert result is not None
    return result


def _sample(definition, name='mutiny_cascade'):
    constraints = copy.deepcopy(FIXTURE['constraints'])
    constraints['cluster_cascade_definition'] = copy.deepcopy(definition)
    return copy.deepcopy(FIXTURE[name]['bet']), constraints


def _pure_sample(definition):
    _, constraints = _sample(definition)
    return copy.deepcopy(REPEATED['pure_cascades']['bet']), constraints


def test_real_pure_cascades_are_ordinary_basic_with_one_final_award(definition):
    from tester_spin.providers.yggdrasil.cluster_cascades import known, ordinary
    bet, constraints = _pure_sample(definition)
    assert len(bet['eventdata']['listAvalanche'][0]['shifts']) == 6
    assert len(bet['eventdata']['listAvalanche'][1]['shifts']) == 3
    assert bet['eventdata']['wonCoins'] == 18
    assert bet['eventdata']['wonMoney'] == '0.18'
    assert known(bet, constraints)
    assert ordinary(bet, constraints)
    # ordinary() classifies the paid result. The external ledger still must
    # require C: it is the next captured response that settles this wager.
    assert REPEATED['pure_cascades']['wager_status'] == 'Pending'
    assert REPEATED['collect']['wager_status'] == 'Finished'
    assert REPEATED['collect']['bet']['eventdata']['exactWon'] == '0.1800'


def _replace_pure_award(bet, coins, *, mask=None):
    event, data = bet['eventdata'], bet['betdata']
    cash = format(Decimal(data['coin']) * coins, '.2f')
    event['wonCoins'] = event['accC'] = data['accC'] = coins
    event['wonMoney'] = event['accWa'] = data['accWa'] = cash
    event['wtw'][0][1] = event['wtw'][0][4] = coins
    event['wtw'][0][3] = event['wtw'][0][5] = cash
    if mask is not None:
        event['wtw'][0][2] = mask


def test_pure_sequence_cannot_stop_with_unconsumed_refill_winners(definition):
    from tester_spin.providers.yggdrasil.cluster_cascades import known, ordinary
    bet, constraints = _pure_sample(definition)
    event = bet['eventdata']
    event['listAvalanche'].pop()
    event['finalBoard'] = copy.deepcopy(event['listAvalanche'][0]['finalIntermediateBoard'])
    # The three new LOW1 already appear in this board, so even a matching
    # nine-symbol award and mask cannot make the unfinished refill terminal.
    mask = ''.join('1' if value == 'LOW1' else '0' for column in event['finalBoard'] for value in column)
    _replace_pure_award(bet, 18, mask=mask)
    assert not known(bet, constraints)
    assert not ordinary(bet, constraints)


@pytest.mark.parametrize('coins', [30, 6])
def test_pure_award_cannot_sum_intermediate_boards_or_pay_only_the_last_delta(definition, coins):
    from tester_spin.providers.yggdrasil.cluster_cascades import known
    bet, constraints = _pure_sample(definition)
    # Six first-stage winners plus nine final winners would double count;
    # paying just the three new winners would omit the six retained symbols.
    _replace_pure_award(bet, coins)
    assert not known(bet, constraints)


def test_pure_mask_must_include_old_sticky_and_new_winners(definition):
    from tester_spin.providers.yggdrasil.cluster_cascades import known
    bet, constraints = _pure_sample(definition)
    fresh = {(shift['target']['column'], shift['target']['row'])
             for shift in bet['eventdata']['listAvalanche'][1]['shifts']}
    bet['eventdata']['wtw'][0][2] = ''.join('1' if (column, row) in fresh else '0'
                                          for column in range(5) for row in range(5))
    assert not known(bet, constraints)


@pytest.mark.parametrize('fault', ['repeat_sticky', 'omit_identity', 'duplicate_refill', 'omit_refill', 'redundant_group'])
def test_pure_groups_preserve_exactly_the_previous_winners_and_consume_new_ones(definition, fault):
    from tester_spin.providers.yggdrasil.cluster_cascades import known, ordinary
    bet, constraints = _pure_sample(definition)
    frames = bet['eventdata']['listAvalanche']
    second = frames[1]
    if fault == 'repeat_sticky':
        for shift in frames[0]['shifts']:
            second['shifts'].append({'origin': copy.deepcopy(shift['target']), 'target': copy.deepcopy(shift['target'])})
    elif fault == 'omit_identity':
        second['shifts'] = [shift for shift in second['shifts'] if shift['origin'] != shift['target']]
    elif fault == 'duplicate_refill':
        second['newIcons'][-1] = copy.deepcopy(second['newIcons'][0])
    elif fault == 'omit_refill':
        second['newIcons'].pop()
    else:
        frames.append(copy.deepcopy(second))
    assert not known(bet, constraints)
    assert not ordinary(bet, constraints)


@pytest.mark.parametrize(('path', 'value'), [
    (('multiplierBefore',), 1), (('multiplierAfter',), 2),
    (('collectedScattersBefore',), 1), (('collectedScattersAfter',), 1),
    (('shifts', 0, 'target', 'row'), 2),
    (('shifts', 0, 'target', 'column'), 3),
    (('shifts', 0, 'origin', 'row'), 2),
    (('initialIntermediateBoard', 2, 2), 'EMPTY'),
    (('cascadeIntermediateBoard', 2, 2), 'EMPTY'),
    (('finalIntermediateBoard', 2, 2), 'LOW2'),
    (('initialIntermediateBoard', 0, 0), 'LOW1'),
    (('clusters',), []), (('mutinyPositions',), []),
    (('type',), 'TSUNAMI'), (('type',), 'CLUSTER_MUTATION'),
    (('type',), 'MUTINY'), (('type',), 'CANNON_BLAST'),
])
def test_pure_second_group_cannot_change_geometry_counters_or_feature_branch(definition, path, value):
    from tester_spin.providers.yggdrasil.cluster_cascades import known, ordinary
    bet, constraints = _pure_sample(definition)
    _set(bet['eventdata']['listAvalanche'][1], path, value)
    assert not known(bet, constraints)
    assert not ordinary(bet, constraints)


def test_final_pure_refill_winner_requires_another_group_even_with_compensated_award(definition):
    from tester_spin.providers.yggdrasil.cluster_cascades import known, ordinary
    bet, constraints = _pure_sample(definition)
    event = bet['eventdata']
    event['finalBoard'][0][3] = 'LOW1'
    event['listAvalanche'][1]['finalIntermediateBoard'][0][3] = 'LOW1'
    mask = list(event['wtw'][0][2]); mask[3] = '1'
    _replace_pure_award(bet, 20, mask=''.join(mask))
    assert not known(bet, constraints)
    assert not ordinary(bet, constraints)


@pytest.mark.parametrize(('old', 'new'), [
    ('t.add(this._createAvalancheFlow()))', 't.add(this._createAvalancheFlow()),t.add(this._createFlowPhase(s.WIN_PRESENTATION_PHASE)))'),
    ('var e=o.getEmptySymbols();n.machine.cascadePresentation.hideSymbols(t,e)', 'var e=[];n.machine.cascadePresentation.hideSymbols(t,e)'),
    ('WIN_PRESENTATION_PHASE:{START:"winPresentationPhase/start"', 'WIN_PRESENTATION_PHASE:{START:"cascadePhase/start"'),
])
def test_cascade_flow_source_binds_sticky_positions_and_one_final_presentation(old, new):
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    assert old in SOURCE
    assert declaration(FIXTURE['props'], SOURCE.replace(old, new)) is None


def _set(obj, path, value):
    for key in path[:-1]:
        obj = obj[key]
    obj[path[-1]] = value


def test_family_routes_incomplete_frames_to_the_strict_contract():
    from tester_spin.providers.yggdrasil.cluster_cascades import family, known
    assert family({'bets': [{'eventdata': {'listAvalanche': []}}]})
    assert family({'bets': [FIXTURE['mutiny_cascade']['bet']]})
    assert not known(FIXTURE['mutiny_cascade']['bet'], FIXTURE['constraints'])
    assert not family({'bets': []})
    assert not family(None)


@pytest.mark.parametrize(('path', 'value'), [
    (('step',), 2), (('step',), True), (('status',), 'PENDING'),
    (('prepaid',), True), (('prizes',), []), (('betamount',), '0.19'),
    (('wonamount',), '1.20'), (('betcurrency',), 'USD'),
    (('betdata', 'cmd'), 'BASE_SPIN'), (('betdata', 'coin'), '0.02'),
    (('betdata', 'ncoins'), 21), (('betdata', 'ncoins'), True),
    (('betdata', 'initialBalance'), '0.10'), (('betdata', 'accC'), 121),
    (('betdata', 'accWa'), '1.21'), (('betdata', 'cmds'), 'FS'),
    (('eventdata', 'globalMultiBefore'), 1), (('eventdata', 'globalMultiAfter'), 1),
    (('eventdata', 'minClusterSize'), 5),
    (('eventdata', 'prizesForIcon', 'HIGH3'), 13),
    (('eventdata', 'collectedInitialScatters'), 2),
    (('eventdata', 'reels', 0, 0), 'LOW1'),
    (('eventdata', 'wonCoins'), 119), (('eventdata', 'accC'), 119),
    (('eventdata', 'wonMoney'), '1.2000000001'), (('eventdata', 'accWa'), '1.21'),
    (('eventdata', 'nextCmds'), 'FS'), (('eventdata', 'winningIcon'), 'MID1'),
    (('eventdata', 'listAvalanche', 0, 'multiplierBefore'), 0),
    (('eventdata', 'listAvalanche', 0, 'multiplierAfter'), 1),
    (('eventdata', 'listAvalanche', 1, 'multiplierBefore'), 1),
    (('eventdata', 'listAvalanche', 1, 'multiplierAfter'), 2),
    (('eventdata', 'listAvalanche', 0, 'collectedScattersBefore'), 0),
    (('eventdata', 'listAvalanche', 0, 'collectedScattersAfter'), 2),
    (('eventdata', 'listAvalanche', 1, 'collectedScattersBefore'), 0),
    (('eventdata', 'listAvalanche', 1, 'collectedScattersAfter'), 1),
    (('eventdata', 'listAvalanche', 0, 'cascadeIntermediateBoard'), []),
    (('eventdata', 'listAvalanche', 0, 'clusters'), {}),
    (('eventdata', 'listAvalanche', 0, 'shifts'), []),
    (('eventdata', 'listAvalanche', 0, 'newIcons'), []),
    (('eventdata', 'listAvalanche', 1, 'clusters'), {}),
    (('eventdata', 'listAvalanche', 1, 'mutinyPositions'), []),
    (('eventdata', 'listAvalanche', 0, 'mutinyPositions', 0, 'row'), 5),
    (('eventdata', 'listAvalanche', 0, 'finalIntermediateBoard', 0, 4), 'HIGH1'),
    (('eventdata', 'listAvalanche', 1, 'initialIntermediateBoard', 0, 0), 'EMPTY'),
    (('eventdata', 'listAvalanche', 1, 'cascadeIntermediateBoard', 0, 4), 'EMPTY'),
    (('eventdata', 'listAvalanche', 1, 'finalIntermediateBoard', 0, 0), 'LOW1'),
    (('eventdata', 'wtw', 0, 0), True), (('eventdata', 'wtw', 0, 1), 121),
    (('eventdata', 'wtw', 0, 2), '1' * 25), (('eventdata', 'wtw', 0, 3), '1.21'),
    (('eventdata', 'wtw', 0, 4), 60), (('eventdata', 'wtw', 0, 5), '0.60'),
])
def test_each_paid_field_remains_bound_to_the_current_round(definition, path, value):
    from tester_spin.providers.yggdrasil.cluster_cascades import known, ordinary
    bet, constraints = _sample(definition)
    _set(bet, path, value)
    assert not known(bet, constraints)
    assert not ordinary(bet, constraints)


@pytest.mark.parametrize('label', ['TSUNAMI', 'CLUSTER_MUTATION', 'CANNON', 'FREE_SPINS'])
def test_additional_features_are_rejected_even_with_unchanged_totals(definition, label):
    from tester_spin.providers.yggdrasil.cluster_cascades import known
    bet, constraints = _sample(definition)
    addition = copy.deepcopy(bet['eventdata']['listAvalanche'][1])
    addition['type'] = label
    bet['eventdata']['listAvalanche'].append(addition)
    assert not known(bet, constraints)


def test_feature_order_duplicates_and_omissions_cannot_be_compensated(definition):
    from tester_spin.providers.yggdrasil.cluster_cascades import known
    for kind in ('reverse', 'duplicate', 'omit'):
        bet, constraints = _sample(definition)
        frames = bet['eventdata']['listAvalanche']
        if kind == 'reverse':
            frames.reverse()
        elif kind == 'duplicate':
            frames.append(copy.deepcopy(frames[-1]))
        else:
            frames.pop(0)
        assert not known(bet, constraints), kind


def test_equal_symbols_do_not_hide_permuted_gravity_destinations(definition):
    from tester_spin.providers.yggdrasil.cluster_cascades import known
    bet, constraints = _sample(definition)
    shifts = bet['eventdata']['listAvalanche'][1]['shifts']
    # Same-column HIGH3 destinations exchange; board, mask and cash still match.
    same_column = [shift for shift in shifts if shift['origin']['column'] == 1]
    same_column[0]['target'], same_column[1]['target'] = same_column[1]['target'], same_column[0]['target']
    assert not known(bet, constraints)


@pytest.mark.parametrize('field', ['mutinyPositions', 'shifts', 'newIcons'])
def test_duplicate_coordinates_are_not_silently_deduplicated(definition, field):
    from tester_spin.providers.yggdrasil.cluster_cascades import known
    bet, constraints = _sample(definition)
    frame = bet['eventdata']['listAvalanche'][field != 'mutinyPositions']
    frame[field][-1] = copy.deepcopy(frame[field][0])
    assert not known(bet, constraints)


def test_refill_winner_is_not_accepted_as_an_unreported_extra_cascade(definition):
    from tester_spin.providers.yggdrasil.cluster_cascades import known
    bet, constraints = _sample(definition)
    event = bet['eventdata']
    event['finalBoard'][0][3] = 'HIGH3'
    event['listAvalanche'][1]['finalIntermediateBoard'][0][3] = 'HIGH3'
    mask = list(event['wtw'][0][2]); mask[3] = '1'
    event['wtw'] = [[5, 132, ''.join(mask), '1.32', 132, '1.32']]
    event['wonCoins'] = event['accC'] = bet['betdata']['accC'] = 132
    event['wonMoney'] = event['accWa'] = bet['betdata']['accWa'] = '1.32'
    assert not known(bet, constraints)


def test_third_collected_scatter_requires_an_unsupported_free_spin_award(definition):
    from tester_spin.providers.yggdrasil.cluster_cascades import known
    bet, constraints = _sample(definition)
    event = bet['eventdata']
    event['finalBoard'][0][0] = 'FREE_SPINS'
    event['listAvalanche'][1]['finalIntermediateBoard'][0][0] = 'FREE_SPINS'
    event['listAvalanche'][1]['collectedScattersAfter'] = 3
    assert not known(bet, constraints)


def test_simultaneously_forged_event_paytable_and_payout_cannot_replace_config(definition):
    from tester_spin.providers.yggdrasil.cluster_cascades import known
    bet, constraints = _sample(definition)
    event = bet['eventdata']
    event['prizesForIcon']['HIGH3'] = 13
    event['wonCoins'] = event['accC'] = bet['betdata']['accC'] = 130
    event['wonMoney'] = event['accWa'] = bet['betdata']['accWa'] = '1.30'
    event['wtw'][0][1] = event['wtw'][0][4] = 130
    event['wtw'][0][3] = event['wtw'][0][5] = '1.30'
    assert not known(bet, constraints)


@pytest.mark.parametrize('field', ['freeSpins', 'freeSpinsAwarded', 'initialPlayerState', 'unprovedCounter'])
def test_new_event_state_is_not_ignored_as_metadata(definition, field):
    from tester_spin.providers.yggdrasil.cluster_cascades import known
    bet, constraints = _sample(definition)
    bet['eventdata'][field] = 0
    assert not known(bet, constraints)


@pytest.mark.parametrize('symbol', ['MUTINY', 'EMPTY', 'UNKNOWN'])
def test_ordinary_zero_cannot_hide_special_or_unrecognized_symbols(definition, symbol):
    from tester_spin.providers.yggdrasil.cluster_cascades import known, ordinary
    bet, constraints = _sample(definition, 'ordinary_zero')
    for field in ('reels', 'inputBoard', 'finalBoard'):
        bet['eventdata'][field][0][0] = symbol
    assert not known(bet, constraints)
    assert not ordinary(bet, constraints)


def test_ordinary_zero_rejects_even_diagonally_ambiguous_candidate_clusters(definition):
    from tester_spin.providers.yggdrasil.cluster_cascades import ordinary
    bet, constraints = _sample(definition, 'ordinary_zero')
    # Six HIGH1 form a diagonal candidate. The public client does not prove
    # whether diagonals count, so neither interpretation may silently pass.
    for field in ('reels', 'inputBoard', 'finalBoard'):
        for column, row in [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (3, 1)]:
            bet['eventdata'][field][column][row] = 'HIGH1'
    bet['eventdata']['collectedInitialScatters'] = 0
    assert not ordinary(bet, constraints)


@pytest.mark.parametrize(('path', 'value'), [
    (('PrizesPerIcon', 'HIGH3'), 13), (('Prizes', 2, 10), '121'),
    (('MinClusterSize',), 5), (('MinClusterSize',), True),
    (('WindowHeight',), 6), (('NumberOfReels',), 4),
    (('Icons', 4), 'HIGH1'), (('IconTypes', 5), 'W'),
    (('MultipliersPerLevel', '0'), 1), (('MultipliersPerLevel', '2'), 1),
    (('CoinsPerBet', 0), True), (('Modes', 'BASIC', 'coinsPerBet'), 21),
])
def test_contradictory_current_configuration_cannot_declare_the_family(path, value):
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    props = copy.deepcopy(FIXTURE['props'])
    _set(props, path, value)
    assert declaration(props, SOURCE) is None


@pytest.mark.parametrize(('old', 'new'), [
    ('o.formatPrize(n*r,!0)', 'o.formatPrize(n*r*2,!0)'),
    ('this.formatMoney(t*n.bet)', 'this.formatMoney(t*n.bet*2)'),
    ('prize=t.Config.PrizesPerIcon[e]', 'prize=t.Config.PrizesPerIcon[e]*2'),
    ('this.totalBet=Number(i.bet)*i.coinsPerBet', 'this.totalBet=Number(i.bet)*i.coinsPerBet*2'),
    ('coins:t[1],payline:t[0]-1', 'coins:t[4],payline:t[0]-1'),
    ('Math.floor(i/e._rows)', 'Math.floor(i/4)'),
    ('e?e[4]:0', 'e?e[1]:0'),
    ('t[4].column,row:t[4].row', 't[0].column,row:t[0].row'),
    ('n.setType(e),n.alpha=0', 'n.setType("MID1"),n.alpha=0'),
    ('getFinalMultiplier()>1?', 'getFinalMultiplier()>0?'),
    ('PLAY_COMMAND={CMD:"",COINS_PER_BET:0}', 'PLAY_COMMAND={CMD:"ALT",COINS_PER_BET:0}'),
    ('SCATTERS_COUNT_TO_TRIGGER=3', 'SCATTERS_COUNT_TO_TRIGGER=4'),
    ('ROWS:5', 'ROWS:4'),
])
def test_complete_source_semantics_reject_changed_formulas_and_controls(old, new):
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    assert old in SOURCE
    assert declaration(FIXTURE['props'], SOURCE.replace(old, new)) is None


def test_disconnected_or_duplicate_source_evidence_does_not_declare():
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    assert declaration(FIXTURE['props'], SOURCE + SOURCE) is None
    # Config's price writer must reference the symbol model used by the paytable.
    disconnected = SOURCE.replace('"%)@","@^#","@)&"', '"%)@","unrelated-symbol-model","@)&"')
    assert disconnected != SOURCE
    assert declaration(FIXTURE['props'], disconnected) is None


def test_source_high_class_must_match_the_mutiny_symbol_domain():
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    changed = SOURCE.replace('HIGH:"HIGH\\\\d"', 'HIGH:"MID\\\\d"')
    assert changed != SOURCE
    assert declaration(FIXTURE['props'], changed) is None


def test_configuration_cannot_add_a_high_symbol_absent_from_the_current_renderer():
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    props = json.loads(json.dumps(FIXTURE['props']).replace('"HIGH3"', '"HIGH5"'))
    assert declaration(props, SOURCE) is None


@pytest.mark.parametrize(('old', 'new'), [
    ('return t=t||this._step,this._avalanches[t]', 'return t=t||this._step,this._avalanches[t+1]'),
    ('return t.filter(function(t){return!e.contains(this._irrelevantFeatures,t.type)},this)',
     'return t.filter(function(t){return!e.contains(this._irrelevantFeatures,t.type)},this).slice(0,0)'),
])
def test_transitive_avalanche_helpers_cannot_change_under_identical_entry_methods(old, new):
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    assert old in SOURCE
    assert declaration(FIXTURE['props'], SOURCE.replace(old, new)) is None


def test_later_loader_override_cannot_leave_stale_source_authority():
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    assert declaration(FIXTURE['props'], SOURCE + '_d("&!!",[],function(){return{}});') is None


def test_outer_module_arguments_must_still_bind_the_inspected_body():
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    header = '_d("&!!",["!","@","((","^&*","*","%*%","%&*"],function(t,e,i,n,o,a,s)'
    assert header in SOURCE
    changed = SOURCE.replace(header, header.replace('function(t,e,i,n,o,a,s)', 'function(t,e,z,n,o,a,s)'))
    assert declaration(FIXTURE['props'], changed) is None


@pytest.mark.parametrize(('old', 'new'), [
    ('this.wonCoins=e.wonCoins||0', 'this.wonCoins=e.wonCoins*2||0'),
    ('this.parseMachine(t),this.parseSymbolPrizes(t)', 'this.parseMachine(t)'),
])
def test_inherited_prize_and_config_parsers_remain_part_of_the_source_contract(old, new):
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    assert old in SOURCE
    assert declaration(FIXTURE['props'], SOURCE.replace(old, new)) is None


def test_paid_request_parent_must_be_the_proved_basic_command_builder():
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    header = '_d("@%)",["!","#^!","(%","(*","(&",")@"]'
    assert header in SOURCE
    changed = SOURCE.replace(header, header.replace('"#^!"', '"alteredRequestBase"'))
    changed += '_d("alteredRequestBase",[],function(){function x(){}return x.prototype.getParams=function(){return{cmd:"BUY"}},x});'
    assert declaration(FIXTURE['props'], changed) is None


def test_full_winner_board_without_refill_is_outside_the_proved_cascade_branch(definition):
    from tester_spin.providers.yggdrasil.cluster_cascades import known
    bet, constraints = _sample(definition)
    event = bet['eventdata']; mutiny, cascade = event['listAvalanche']
    initial = [['MUTINY' if symbol == 'MUTINY' else 'HIGH3' for symbol in column] for column in event['inputBoard']]
    complete = [['HIGH3'] * 5 for _ in range(5)]
    event['reels'] = copy.deepcopy(initial); event['inputBoard'] = copy.deepcopy(initial)
    event['finalBoard'] = copy.deepcopy(complete)
    event['collectedInitialScatters'] = 0
    mutiny['initialIntermediateBoard'] = copy.deepcopy(initial)
    mutiny['finalIntermediateBoard'] = copy.deepcopy(complete)
    for field in ('initialIntermediateBoard', 'cascadeIntermediateBoard', 'finalIntermediateBoard'):
        cascade[field] = copy.deepcopy(complete)
    for frame in (mutiny, cascade):
        frame['collectedScattersBefore'] = frame['collectedScattersAfter'] = 0
    cascade['newIcons'] = []
    cascade['shifts'] = [{'origin': {'column': column, 'row': row}, 'target': {'column': column, 'row': row}}
                         for column in range(5) for row in range(5)]
    event['wtw'] = [[5, 300, '1' * 25, '3.00', 300, '3.00']]
    event['wonCoins'] = event['accC'] = bet['betdata']['accC'] = 300
    event['wonMoney'] = event['accWa'] = bet['betdata']['accWa'] = '3.00'
    # The capture does not establish whether this full-board case must trigger
    # TSUNAMI; equal money alone must not promote an unproved branch.
    assert not known(bet, constraints)


def test_module_identifiers_title_and_game_id_are_not_family_aliases():
    from tester_spin.providers.yggdrasil.cluster_cascades import declaration
    pattern = re.compile(r'_d\(("(?:[^"\\]|\\.)*"),(\[[^\]\n]*\]),function')
    identifiers = set()
    for match in pattern.finditer(SOURCE):
        identifiers.add(json.loads(match[1]))
        identifiers.update(json.loads(match[2]))
    mapping = {name: 'module_' + str(index) for index, name in enumerate(sorted(identifiers))}
    def rename(match):
        return '_d(' + json.dumps(mapping[json.loads(match[1])]) + ',' + json.dumps([mapping[name] for name in json.loads(match[2])], separators=(',', ':')) + ',function'
    source = pattern.sub(rename, SOURCE)
    source = source.replace('GAME_NAME:"pirates2"', 'GAME_NAME:"another"').replace('FORMATTED_GAME_NAME:"Pirates 2 Mutiny"', 'FORMATTED_GAME_NAME:"Another title"').replace('GAME_ID:8309', 'GAME_ID:999999')
    assert declaration(FIXTURE['props'], source) is not None
