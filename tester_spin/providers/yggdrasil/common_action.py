"""Validate complete CommonAPI queues with state saved separately per stake.

The terminal marker does not erase counters, previous panels or walking awards.
A new paid round must start from the previous settled snapshot in this session;
only a fully checked MAIN result can count towards a return to ordinary play.
"""
from copy import deepcopy
from decimal import Decimal
from math import prod
import json
import re

from .protocol import command_values
from .supermeter import num

_COUNTERS = {
    'MULTIPLIER': (1, [1]),
    'COLLECTED_SCATTERS': (0, [0, 5]),
    'HIGH_MULTIPLIER': (False, [False, True]),
    'FREE_SPINS': (0, [0]),
    'MULTIPLIERS_BOOSTERS': (['BLANK', 'BLANK'], [
        ['BLANK', 'BLANK'], ['+', 'BLANK'], ['BLANK', '+'], ['+', '+'],
        ['*', 'BLANK'], ['BLANK', '*'], ['*', '*'], ['+', '*'], ['*', '+']]),
    'FREE_SPINS_PURCHASE': (False, [False, True]),
}
_CHANNELS = {'THREE_WILDS', 'SPECIAL_REEL_OPS_IN_RESPIN', 'COLLECTED_SCATTERS',
             'RESPIN_BOOST', 'WINNING_WAYS', 'SPECIAL_REEL_OPS', 'FREE_SPINS_SINGLE_PANEL',
             'FREE_SPINS', 'WILD', 'WILD_WINNINGS'}
_DATA = {'original_state', 'state', 'bet_amount', 'fixed_bet', 'action_winnings', 'round_winnings',
         'winnings', 'counters', 'opens_game_round', 'closes_game_round', 'available_actions',
         'redeemables', 'max_win_reached', 'action_type', 'original_panel', 'panel',
         'special_reels', 'taxonomy', 'transforms', 'taxonomy_transforms'}
_SNAPSHOT = {'previous_panel', 'counters', 'previous_panel_per_bet', 'transform_sources_per_bet',
             'base_state', 'base_state_per_bet'}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, minimum=0, maximum=10000000):
    return type(value) is int and minimum <= value <= maximum


def _same(left, right):
    """JSON equality without Python's bool/int/float equivalences."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(_same(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def family(state):
    for bet in state.get('bets', []):
        event = bet.get('eventdata') or {}
        response = event.get('response') or {}
        data = response.get('clientData')
        if isinstance(data, dict) and (data.get('type') == 'GameActionResponse' or
                                      isinstance(data.get('data'), dict) and 'previous_panel_per_bet' in data['data']):
            return True
    return False


def prepare_request(template, constraints, message_id):
    rules = constraints['common_action_definition']
    _need(constraints.get('currency') == rules['currency'] == 'EUR', 'Undeclared action currency')
    basic_coin = num(constraints['basic_coin'])
    base = num(constraints['basic_amount'])
    _need(basic_coin * rules['coins_per_bet'] == base, 'Base price disagrees with current coin quantity')
    stake = base * 100
    _need(stake == stake.to_integral_value() and stake > 0, 'Nonintegral internal stake')
    command = template.get('cmd')
    _need(command in (None, '', 'BUY'), 'Unlearned typed paid action')
    quote = constraints['purchase_quotes']['BUY'] if command else {'coin': constraints['basic_coin'], 'amount': constraints['basic_amount']}
    _need(num(template['coin']) == basic_coin == num(quote['coin']) and num(template['amount']) == num(quote['amount']), 'Action request changed its declared quote')
    _need(num(template['amount']) == base * (rules['purchase_multiplier'] if command else 1), 'Purchase price disagrees with current multiplier')
    params = {'action_type': 'BuyGameAction', 'id': rules['purchase_id'], 'bet_amount': int(stake)} if command else {'action_type': 'SpinGameAction', 'bet_amount': int(stake)}
    body = {'type': 'GameActionRequest', 'message_id': str(message_id), 'params': params}
    if 'clientParams' in template:
        supplied = template['clientParams']
        supplied = json.loads(supplied) if isinstance(supplied, str) else supplied
        _need(_same(supplied, body), 'Conflicting explicit typed action request')
    return {**template, 'clientParams': json.dumps(body, separators=(',', ':'))}


def _panel(value, rules):
    _need(isinstance(value, dict) and set(value) == {'reels'}, 'Unknown panel envelope')
    board = value['reels'];symbols = {*rules['awards'], rules['wild'], rules['scatter']}
    _need(isinstance(board, list) and len(board) == rules['width'] and all(
        isinstance(column, list) and len(column) == rules['height'] and all(isinstance(symbol, str) and symbol in symbols for symbol in column)
        for column in board), 'Malformed or unknown panel symbol')
    _need(all(symbol != rules['wild'] or col in rules['wild_columns']
              for col, column in enumerate(board) for symbol in column), 'Wild outside declared middle reels')
    return board


def _position(value, rules):
    _need(isinstance(value, dict) and set(value) == {'reel', 'row'} and
          _integer(value['reel'], 0, rules['width'] - 1) and _integer(value['row'], 0, rules['height'] - 1), 'Invalid symbol position')
    return value['reel'], value['row']


def _symbols(items, board, rules):
    _need(isinstance(items, list) and len(items) <= rules['width'] * rules['height'], 'Invalid symbol list')
    found = {}
    for item in items:
        _need(isinstance(item, dict) and set(item) == {'symbol', 'coordinates'}, 'Unknown symbol record')
        point = _position(item['coordinates'], rules)
        _need(point not in found and item['symbol'] == board[point[0]][point[1]], 'Duplicate position or symbol mismatch')
        found[point] = item['symbol']
    return found


def _counters(value, stake, previous=None):
    _need(isinstance(value, dict) and set(value) == set(_COUNTERS), 'Unknown persistent counter')
    selected = {}
    for name, (default, limits) in _COUNTERS.items():
        item = value[name]
        _need(isinstance(item, dict) and set(item) == {'value_per_bet', 'default_value', 'limits'} and
              _same(item['default_value'], default) and _same(item['limits'], limits),
              'Counter declaration changed')
        mapping = item['value_per_bet']
        _need(isinstance(mapping, dict) and len(mapping) <= 64 and all(isinstance(key, str) and re.fullmatch(r'[1-9][0-9]{0,8}', key) for key in mapping), 'Invalid counter stake domain')
        for v in mapping.values():
            if name in ('HIGH_MULTIPLIER', 'FREE_SPINS_PURCHASE'):
                _need(type(v) is bool, 'Counter is not boolean')
            elif name == 'MULTIPLIERS_BOOSTERS':
                _need(isinstance(v, list) and v in limits, 'Unlearned multiplier booster')
            elif name == 'MULTIPLIER':
                _need(type(v) is int and v == 1, 'Unlearned cash multiplier')
            else:
                _need(_integer(v, 0, 1000), 'Invalid remaining counter')
        if previous is not None:
            old = previous[name]['value_per_bet']
            _need(_same({k: v for k, v in mapping.items() if k != stake}, {k: v for k, v in old.items() if k != stake}), 'Another stake counter changed')
        selected[name] = mapping.get(stake, default)
    return selected


def _snapshot(value, stake, rules):
    _need(isinstance(value, dict) and set(value) == _SNAPSHOT and value['base_state'] == 'MAIN' and value['base_state_per_bet'] is None, 'Unlearned saved state envelope')
    selected = _counters(value['counters'], stake)
    _need(selected['FREE_SPINS'] == 0, 'Saved state still has awarded spins')
    panels = value['previous_panel_per_bet']
    transforms = value['transform_sources_per_bet']
    if panels is None:
        _need(value['previous_panel'] is None and transforms is None and all(not v['value_per_bet'] for v in value['counters'].values()), 'Nonpristine initial snapshot')
        return {}
    _need(isinstance(panels, dict) and 1 <= len(panels) <= 64 and stake in panels, 'Saved panel is not bound to this stake')
    for panel in panels.values():
        _panel(panel, rules)
    _need(value['previous_panel'] == panels[stake], 'Global and stake panels disagree')
    _need(isinstance(transforms, dict) and set(transforms) == {'WALKING_WILDS'} and isinstance(transforms['WALKING_WILDS'], dict) and
          set(transforms['WALKING_WILDS']) == set(panels) and all(v == [] for v in transforms['WALKING_WILDS'].values()), 'Unsettled saved walking-symbol state')
    return panels


def _win_record(item, kind, prize):
    _need(isinstance(item, dict) and set(item) == {'id', 'winnings', 'winning_type', 'prize_type', 'source'} and
          item['winning_type'] == kind and item['prize_type'] == prize and _integer(item['winnings'], 1), 'Unknown or malformed award record')


def _scatter(items, symbol, board, rules, *, prize='FeatureStart', required=True):
    expected = {(col, row): value for col, column in enumerate(board) for row, value in enumerate(column) if value == symbol}
    _need(isinstance(items, list), 'Malformed scatter award')
    if not items:
        _need(not required or not expected, 'Missing displayed scatter award')
        return 0
    _need(len(items) == 1, 'Duplicate scatter award')
    item = items[0];_win_record(item, 'Scatter', prize)
    source = item['source']
    _need(isinstance(source, dict) and set(source) == {'type', 'main_symbol', 'occurrences', 'winning_symbols', 'aggregations'} and
          source['type'] == 'Symbols' and source['main_symbol'] == item['id'] == symbol and _integer(source['aggregations'], 1, 1) and _integer(source['occurrences'], 1) and
          source['occurrences'] == item['winnings'] == len(expected) and _symbols(source['winning_symbols'], board, rules) == expected,
          'Scatter count or source changed')
    return len(expected)


def _ways(items, board, bet_amount, rules):
    _need(isinstance(items, list) and len(items) <= len(rules['awards']), 'Invalid ways awards')
    expected = {}
    for symbol, prizes in rules['awards'].items():
        points = {};counts = []
        for col, column in enumerate(board):
            rows = [row for row, value in enumerate(column) if value in (symbol, rules['wild'])]
            if not rows:
                break
            counts.append(len(rows))
            points.update({(col, row): board[col][row] for row in rows})
        if str(len(counts)) in prizes:
            amount = num(prizes[str(len(counts))]) * num(bet_amount) / rules['bet_scaler'] * prod(counts)
            expected[symbol] = (points, len(counts), prod(counts), amount)
    _need(len(items) == len(expected), 'Omitted or additional winning way')
    total = Decimal(0);wild_credits = {};seen = set()
    for item in items:
        _win_record(item, 'Way', 'Money');symbol = item['id']
        _need(symbol in expected and symbol not in seen, 'Foreign or duplicate winning way')
        seen.add(symbol);points, count, aggregates, amount = expected[symbol];source = item['source']
        _need(isinstance(source, dict) and set(source) == {'type', 'main_symbol', 'occurrences', 'winning_symbols', 'aggregations'} and
              source['type'] == 'Symbols' and source['main_symbol'] == symbol and _integer(source['occurrences'], count, count) and
              _integer(source['aggregations'], aggregates, aggregates) and _symbols(source['winning_symbols'], board, rules) == points and num(item['winnings']) == amount,
              'Winning way does not match panel and current paytable')
        total += amount
        for point, value in points.items():
            if value == rules['wild']:
                # The aggregate includes every matching row on this reel;
                # this wild collects only paths selecting its own row.
                column_matches = sum(position[0] == point[0] for position in points)
                wild_credits[point] = wild_credits.get(point, Decimal(0)) + amount / column_matches
    return total, wild_credits


def _walking(data, board, original, previous_board, active, credits, rules):
    transforms = data['transforms'];wins = data['winnings']
    _need(isinstance(transforms, dict) and set(transforms) == {'WALKING_WILDS'} and isinstance(transforms['WALKING_WILDS'], list) and len(transforms['WALKING_WILDS']) <= 15,
          'Unknown walking transform')
    final = deepcopy(original);seen_from = set();seen_to = set();following = {};departed = {}
    for item in transforms['WALKING_WILDS']:
        _need(isinstance(item, dict) and set(item) == {'type', 'winnings', 'transform'} and item['type'] == 'WinningsTransform' and _integer(item['winnings']), 'Malformed walking winnings')
        trans = item['transform']
        _need(isinstance(trans, dict) and set(trans) == {'type', 'source', 'movements'} and trans['type'] == 'MovementsTransform' and
              isinstance(trans['movements'], list) and len(trans['movements']) == 1, 'Unknown walking movement')
        move = trans['movements'][0]
        _need(isinstance(move, dict) and set(move) == {'from', 'to', 'symbol'} and move['symbol'] == rules['wild'], 'Unknown moving symbol')
        origin = None if move['from'] is None else _position(move['from'], rules)
        target = None if move['to'] is None else _position(move['to'], rules)
        _need(origin is not None or target is not None, 'Empty movement')
        _need(trans['source'] == [{'symbol': rules['wild'], 'coordinates': move['from'] if origin is not None else move['to']}], 'Movement source mismatch')
        if origin is None:
            _need(target not in active and original[target[0]][target[1]] == rules['wild'] and item['winnings'] == 0, 'Unbacked new walking wild')
        else:
            _need(origin not in seen_from and origin in active and previous_board is not None and previous_board[origin[0]][origin[1]] == rules['wild'] and
                  num(item['winnings']) == active[origin], 'Walking credit or prior position changed')
            seen_from.add(origin)
            expected = (origin[0], origin[1] - 1) if 'RESPIN' in data['original_state'] and origin[1] else None if 'RESPIN' in data['original_state'] else origin
            _need(target == expected, 'Unlearned walking direction')
        if target is None:
            departed[origin] = num(item['winnings'])
        else:
            _need(target not in seen_to, 'Duplicate walking destination');seen_to.add(target)
            final[target[0]][target[1]] = rules['wild']
            amount = num(item['winnings']) + credits.get(target, Decimal(0))
            if amount > 0:
                following[target] = amount
    _need(seen_from == set(active), 'Missing active walking symbol')
    _need(final == board, 'Panel does not match all walking transforms')
    _need(seen_to == {(col, row) for col, column in enumerate(board) for row, symbol in enumerate(column) if symbol == rules['wild']}, 'Unrepresented wild on final panel')
    wild_wins = wins['WILD_WINNINGS']
    _need(isinstance(wild_wins, list) and len(wild_wins) == len(credits), 'Missing walking collection')
    observed = {}
    for item in wild_wins:
        _win_record(item, 'SymbolWinnings', 'FeatureStart');source = item['source']
        _need(isinstance(source, dict) and set(source) == {'type', 'symbol'} and source['type'] == 'Symbol' and item['id'] == rules['wild'], 'Unknown walking collection source')
        positions = _symbols([source['symbol']], board, rules);point = next(iter(positions))
        _need(point not in observed and positions[point] == rules['wild'], 'Duplicate wild collection')
        observed[point] = num(item['winnings'])
    _need(observed == credits, 'Wild collection differs from its winning ways')
    paid = wins.get('WALKING_SYMBOLS_MULTIPLIER', [])
    _need(isinstance(paid, list) and len(paid) == len(departed), 'Missing walking exit prize')
    observed = set();total = Decimal(0)
    for item in paid:
        _win_record(item, 'PostProduced', 'Money');source = item['source']
        _need(isinstance(source, dict) and set(source) == {'type', 'main_symbol', 'occurrences', 'winning_symbols', 'aggregations'} and
              source['type'] == 'Symbols' and source['main_symbol'] == rules['wild'] and _integer(source['occurrences'], 1, 1) and _integer(source['aggregations'], 0, 0) and
              isinstance(source['winning_symbols'], list) and len(source['winning_symbols']) == 1, 'Unknown walking exit source')
        positions = _symbols(source['winning_symbols'], previous_board, rules);point = next(iter(positions))
        _need(point in departed and point not in observed and point[1] == 0, 'Unbacked walking exit')
        factor = int(data['special_reels']['SPECIAL_REEL'][point[0] - 1])
        _need(item['id'] == f'{rules["wild"]}_{point[0]}_{factor}x' and num(item['winnings']) == departed[point] * factor, 'Walking multiplier prize changed')
        observed.add(point);total += num(item['winnings'])
    return total, following


def validate(state, constraints, request=None):
    rules = constraints.get('common_action_definition')
    _need(isinstance(rules, dict), 'Missing current CommonAPI source declaration')
    bets = state['bets'];_need(1 <= len(bets) <= 512 and [b['step'] for b in bets] == list(range(1, len(bets) + 1)), 'Missing, duplicate or skipped queued frame')
    root = bets[0];last = bets[-1];bd = root['betdata'];coin = num(constraints['basic_coin']);base = num(constraints['basic_amount']);stake = str(int(base * 100))
    _need(constraints['currency'] == rules['currency'] == 'EUR' and base * 100 == int(stake), 'Unbound currency or stake')
    command = bd['cmd'];purchase = command == 'BUY'
    _need(command in ('BUY', 'BASE_SPIN') and num(bd['coin']) == coin and num(root['betamount']) == num(bd['cashBet']) == base * (rules['purchase_multiplier'] if purchase else 1), 'Wrong paid price or command')
    typed = bd.get('clientParams')
    if request is not None:
        expected = json.loads(request['clientParams'])
        _need(_same(typed, expected), 'Typed request was not echoed by the paid result')
    else:
        expected = typed
    _need(isinstance(expected, dict) and set(expected) == {'type', 'message_id', 'params'} and expected['type'] == 'GameActionRequest' and
          isinstance(expected['message_id'], str) and re.fullmatch(r'[1-9][0-9]{0,8}', expected['message_id']), 'Missing typed action identity')
    expected_params = {'action_type': 'BuyGameAction', 'id': rules['purchase_id'], 'bet_amount': int(stake)} if purchase else {'action_type': 'SpinGameAction', 'bet_amount': int(stake)}
    _need(_same(expected['params'], expected_params), 'Wrong internal stake or purchase identity')
    before = root['eventdata']['initialPlayerState'];before_panels = _snapshot(before, stake, rules)
    history = constraints.get('settled_common_action_state')
    if history is None:
        _need(before['previous_panel'] is None, 'Persistent history is not bound to this session')
    else:
        _need(_same(before, history['player_state']) and num(bd['initialBalance']) == num(history['balance']) and int(expected['message_id']) == history['message_id'] + 1,
              'Persistent snapshot, balance or message changed between paid rounds')
    buy = num(state['cash_balances']['buy']);result = num(state['cash_balances']['result'])
    _need(num(bd['initialBalance']) - buy == num(root['betamount']) and result == buy and buy >= 0, 'Paid debit or premature credit disagrees with cash ledger')
    panels = deepcopy(before_panels);previous_board = panels.get(stake, {}).get('reels');previous_counters = before['counters']
    previous_values = _counters(previous_counters, stake);previous_state = 'MAIN';total = Decimal(0);active = {};free_played = 0;awarded = 0
    for index, bet in enumerate(bets):
        first = index == 0;final = index == len(bets) - 1;event = bet['eventdata']
        _need(bet['status'] == 'RESULTED' and bet['betcurrency'] == constraints['currency'] and num(bet['betamount']) == (num(root['betamount']) if first else 0) and
              num(bet['wonamount']) == 0 and bet.get('prizes') is None, 'Queued result changed debit, credit or currency')
        required_event = {'accC', 'accWa', 'response'} | ({'initialPlayerState'} if first else set()) | ({'playerState', 'boostData'} if final else set())
        _need(isinstance(event, dict) and set(event) - {'nextCmds'} == required_event and (final or 'nextCmds' not in event), 'Unknown or misplaced queued event data')
        response = event['response'];_need(isinstance(response, dict) and set(response) == {'coinWin', 'cashWin', 'clientData'}, 'Unknown action response')
        cd = response['clientData'];_need(isinstance(cd, dict) and set(cd) == {'type', 'message_id', 'data'} and cd['type'] == 'GameActionResponse' and cd['message_id'] == expected['message_id'], 'Response identity or message changed')
        data = cd['data'];_need(isinstance(data, dict) and set(data) - {'previous_panel_per_bet'} == _DATA, 'Unknown action fields')
        _need(data['original_state'] == previous_state and data['state'] in rules['states'] and data['bet_amount'] == int(stake) and type(data['bet_amount']) is int and
              data['opens_game_round'] is first and data['closes_game_round'] is final and data['fixed_bet'] is (not final) and
              data['available_actions'] == (['Buy', 'Spin'] if final else ['Spin']) and data['action_type'] == 'Spin' and data['redeemables'] == [] and data['max_win_reached'] is False and data['taxonomy_transforms'] == [], 'State chain or terminal obligations changed')
        _need(_same(data['taxonomy'], {'type': 'SimpleTaxonomy', 'dimensions': [rules['height']] * rules['width']}), 'Changed panel taxonomy')
        _need(data.get('previous_panel_per_bet') == (panels or None), 'Queued prior panel is incomplete or changed')
        original = _panel(data['original_panel'], rules);board = _panel(data['panel'], rules)
        special = data['special_reels'];_need(isinstance(special, dict) and 'SPECIAL_REEL' in special and len(special) <= 5 and all(
            re.fullmatch(r'SPECIAL_REEL(?:_[0-3])?', key) and isinstance(values, list) and len(values) == 3 and all(isinstance(value, str) and re.fullmatch(r'[1-9][0-9]{0,3}', value) for value in values)
            for key, values in special.items()), 'Unknown special multiplier reels')
        counters = _counters(data['counters'], stake, previous_counters)
        wins = data['winnings'];_need(isinstance(wins, dict) and {'WINNING_WAYS', 'WILD_WINNINGS'} <= set(wins) <= _CHANNELS | {'FREE_SPINS_BUY', 'WALKING_SYMBOLS_MULTIPLIER', 'SPECIAL_REEL_OPS_IN_WINNING'} and
                                   all(isinstance(items, list) for items in wins.values()), 'Unknown award channel')
        _need(all(wins.get(key, []) == [] for key in ('THREE_WILDS', 'SPECIAL_REEL_OPS_IN_RESPIN', 'RESPIN_BOOST', 'SPECIAL_REEL_OPS_IN_WINNING')), 'Unlearned active booster')
        scattering = _scatter(wins.get('COLLECTED_SCATTERS', []), rules['scatter'], board, rules, prize='CollectedItem', required='FREE_SPINS' not in previous_state)
        if 'FREE_SPINS' in previous_state:
            _need(scattering == 0 and all(rules['scatter'] not in column for column in board), 'Scatter in unlearned free-spin state')
        _scatter(wins.get('WILD', []), rules['wild'], board, rules, required='RESPIN' not in previous_state)
        ways, credits = _ways(wins['WINNING_WAYS'], board, int(stake), rules)
        walking, next_active = _walking(data, board, original, previous_board, active, credits, rules)
        _need(_integer(data['action_winnings']) and num(data['action_winnings']) == ways + walking, 'Action win does not match all monetary awards')
        total += ways + walking
        _need(_integer(data['round_winnings']) and num(data['round_winnings']) == total and num(event['accWa']) * 100 == total and num(event['accC']) * coin * 100 == total and
              num(response['cashWin']) * 100 == ways + walking and num(response['coinWin']) * coin * 100 == ways + walking, 'Action, round or wrapper accumulator mismatch')
        collected = scattering if previous_state == 'MAIN' else previous_values['COLLECTED_SCATTERS'] + scattering
        _need(counters['COLLECTED_SCATTERS'] == collected, 'Collected scatters lost or duplicated')
        boosters = wins.get('SPECIAL_REEL_OPS', [])
        _need(len(boosters) <= 1, 'Duplicate booster action')
        if boosters:
            item = boosters[0];_win_record(item, 'Counter', 'FeatureStart')
            _need(item['id'] == 'SPECIAL_REEL_OPS' and item['winnings'] == 1 and _same(item['source'], {'type': 'Counters', 'counters': [{'counter_name': 'MULTIPLIERS_BOOSTERS', 'bet': int(stake), 'value': counters['MULTIPLIERS_BOOSTERS']}]}) and counters['MULTIPLIERS_BOOSTERS'] != ['BLANK', 'BLANK'], 'Booster declaration or counter differs')
        elif 'RESPIN' not in previous_state:
            _need(counters['MULTIPLIERS_BOOSTERS'] == ['BLANK', 'BLANK'], 'Unannounced multiplier booster')
        free = wins.get('FREE_SPINS', []);single = wins.get('FREE_SPINS_SINGLE_PANEL', []);bought = wins.get('FREE_SPINS_BUY', [])
        if free:
            _need(first and previous_state == 'MAIN' and len(free) == 1 and collected >= 5 and data['state'] == 'FREE_SPINS', 'Unlearned free-spin trigger')
            item = free[0];_win_record(item, 'Counter', 'FeatureStart')
            _need(item['id'] == 'FREE_SPINS' and _same(item['source'], {'type': 'Counters', 'counters': [{'counter_name': 'COLLECTED_SCATTERS', 'bet': int(stake), 'value': collected}]}), 'Free-spin trigger counter changed')
            awarded = item['winnings'];_need(counters['FREE_SPINS'] == awarded, 'Initial awarded count differs')
            _scatter(single, rules['scatter'], board, rules)
            if purchase:
                _need(_same(bought, [{'id': 'FREE_SPINS_BUY', 'winnings': 1, 'winning_type': 'Purchase', 'prize_type': 'FeatureStart', 'source': {'type': 'Purchase', 'id': rules['purchase_id']}}]), 'Missing typed purchase award')
            else:
                _need(not bought, 'Unrequested purchase award')
        else:
            _need(not single and not bought and not (first and purchase), 'Unbacked feature or missing purchase trigger')
            decrement = 1 if previous_state == 'FREE_SPINS' else 0
            _need(previous_values['FREE_SPINS'] >= decrement and counters['FREE_SPINS'] == previous_values['FREE_SPINS'] - decrement, 'Skipped or duplicated awarded spin')
            free_played += decrement
        _need(counters['FREE_SPINS_PURCHASE'] is purchase, 'Purchased feature flag changed')
        if final:
            _need(data['state'] == 'MAIN' and counters['FREE_SPINS'] == 0 and not next_active and free_played == awarded, 'Closed result retains unconsumed feature state')
        elif counters['FREE_SPINS'] > 0 or previous_state.startswith('FREE_SPINS'):
            _need(data['state'] == ('FREE_SPINS_RESPIN' if credits else 'FREE_SPINS'), 'Free-spin respin transition differs from wild award')
        else:
            _need(data['state'] == 'MAIN_RESPIN' and bool(credits), 'Unbacked main respin')
        if first or final:
            echoed = bet['betdata'];_need(isinstance(echoed, dict) and set(echoed) - {'cmds'} == {'coin', 'cashBet', 'clientParams', 'initialBalance', 'cmd', 'accWa', 'accC'} and
                _same(echoed['clientParams'], expected) and echoed['cmd'] == command and num(echoed['coin']) == coin and num(echoed['cashBet']) == num(root['betamount']) and num(echoed['initialBalance']) == num(bd['initialBalance']) and
                num(echoed['accWa']) * 100 == total and num(echoed['accC']) * coin * 100 == total, 'Paid wrapper echo changed across queue')
        else:
            _need(bet['betdata'] is None, 'Unknown intermediate paid command')
        _need(command_values(event.get('nextCmds')) in ([], ['C']) and (not command_values(event.get('nextCmds')) or final and total > 0), 'Unlearned queued continuation')
        panels[stake] = deepcopy(data['panel']);previous_board = board;previous_counters = data['counters'];previous_values = counters;previous_state = data['state'];active = next_active
    after = last['eventdata']['playerState'];_snapshot(after, stake, rules)
    _need(after['previous_panel_per_bet'] == panels and after['previous_panel'] == last['eventdata']['response']['clientData']['data']['panel'] and _same(after['counters'], previous_counters), 'Final persisted snapshot differs from all queued actions')
    old_transforms = before['transform_sources_per_bet'] or {'WALKING_WILDS': {}}
    _need(after['transform_sources_per_bet'] == {'WALKING_WILDS': {**old_transforms['WALKING_WILDS'], stake: []}}, 'Foreign stake transforms changed')
    boost = last['eventdata']['boostData']
    reduced = {key: [{'id': item['id'], 'winnings': item['winnings']} for item in items] for key, items in last['eventdata']['response']['clientData']['data']['winnings'].items()}
    _need(_same(boost, {'winnings': [reduced] if len(bets) == 1 else []}), 'Boost display does not agree with action queue')
    _need(state['commands'] == (['C'] if total else []) and state['terminal'] is (total == 0) and state['status'] == ('Pending' if total else 'Finished'), 'Wire collection state disagrees with accrued prize')
    proof = {'schema': rules['schema'], 'source_sha256': rules['source_sha256'], 'frames': len(bets),
             'free_spins_awarded': awarded, 'free_spins_played': free_played, 'stake': stake,
             'exact_win': format(total / 100, '.2f'), 'paid_command': command,
             'ordinary': len(bets) == 1 and not purchase and awarded == 0,
             'all_frames_checked': True, 'per_stake_continuity_verified': True}
    state['common_action_proof'] = proof
    state['common_action_player_state'] = deepcopy(after)
    state['common_action_message_id'] = int(expected['message_id'])
    state['cash_accounting_proof'] = {'schema': 'current-cash-ledger/v1', 'debit': str(num(root['betamount'])), 'credit': '0', 'balance_delta_verified': True, 'settlement_precision': '0.01'}
    return proof


def ordinary(state, constraints):
    try:
        return validate(state, constraints)['ordinary']
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        return False


def collect(before, after, request, constraints):
    proof = before.get('common_action_proof')
    if proof is None:
        return False
    _need(request == {'cmd': 'C', 'amount': '0', 'wagerid': before['wagerid'], 'step': str(before['max_step'] + 1), 'betid': str(before['root_step'])}, 'Unlearned settlement request')
    _need(after['wagerid'] == before['wagerid'] and after['terminal'] and after['status'] == 'Finished' and not after['commands'] and len(after['bets']) == 1, 'Settlement did not close the current wager')
    bet = after['bets'][0];prior = before['bets'][-1];amount = num(proof['exact_win']);bd = bet['betdata']
    _need(bet['step'] == before['max_step'] + 1 and bet['status'] == 'RESULTED' and num(bet['betamount']) == 0 and bet['betcurrency'] == constraints['currency'], 'Settlement changed step, stake or currency')
    _need(num(after['cash_balances']['buy']) == num(before['cash_balances']['result']) and num(after['cash_balances']['result']) - num(after['cash_balances']['buy']) == amount == num(bet['wonamount']), 'Settlement cash delta differs from accrued prize')
    _need(isinstance(bet['eventdata'], dict) and set(bet['eventdata']) == {'exactWon'} and num(bet['eventdata']['exactWon']) == amount, 'Settlement exact prize changed')
    _need(isinstance(bd, dict) and set(bd) == {'coin', 'cashBet', 'cmd', 'accWa', 'accC'} and bd['cmd'] == 'C' and
          num(bd['coin']) == num(prior['betdata']['coin']) and num(bd['cashBet']) == num(prior['betdata']['cashBet']) and num(bd['accWa']) == amount and num(bd['accC']) == num(prior['betdata']['accC']), 'Settlement echo changed')
    prizes = bet['prizes'];_need(isinstance(prizes, list) and len(prizes) == 1, 'Unlearned cash settlement prizes')
    prize = prizes[0]
    _need(prize.get('type') == 'FIXED' and prize.get('wonAspect') == 'CASH' and prize.get('woncurrency') == constraints['currency'] and num(prize['wonamount']) == num(prize['netamount']) == amount, 'Settlement prize or net value differs')
    after['cash_accounting_proof'] = {'schema': 'current-cash-ledger/v1', 'debit': '0', 'credit': str(amount), 'exact_win': str(amount), 'settled_win': str(amount), 'settlement_precision': '0.01', 'balance_delta_verified': True}
    return True


def safe_output(state):
    return [{'step': bet['step'], 'data': deepcopy(bet['eventdata'])} for bet in state['bets'] if isinstance((bet.get('eventdata') or {}).get('response'), dict)]
