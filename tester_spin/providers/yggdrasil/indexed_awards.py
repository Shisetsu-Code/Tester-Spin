"""Validate a current safe award choice and its finite nested frame queues.

The server's frame list is evidence, not terminality by itself: free-spin
counters, persistent treasures, respin lives, paths and cash must all agree.
Unproved feature combinations remain unsupported.
"""
from decimal import Decimal

from .cash_collect import close
from .indexed_output import board_paths, collector_cash, double_multiplier, family
from .protocol import command_values
from .supermeter import num


def require(value, message):
    if not value:
        raise ValueError('Indexed award: ' + message)


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def _output(bet, *, pending):
    event = bet['eventdata']
    require(set(event) == {'accC', 'accWa', 'boostData', 'initialPlayerState', 'playerState', 'response', 'nextCmds'}, 'unlearned event fields')
    response = event['response']
    require(set(response) == {'coinWin', 'cashWin', 'clientData'} and num(response['coinWin']) == 0, 'unlearned coin win')
    require(set(response['clientData']) == {'output'}, 'unlearned client data')
    frames = response['clientData']['output']
    require(isinstance(frames, list) and len(frames) == 1 and isinstance(frames[0], dict), 'ambiguous root frame')
    frame = frames[0]
    require(set(frame) - {'debug'} == {'reelLayout', 'fishValues', 'treasureValues', 'winningLines', 'bonusInfo', 'creditsWon', 'bonusGame', 'reelKey', 'inGamble', 'type'}, 'unlearned award frame fields')
    require(frame['inGamble'] is pending and frame['type'] == 'bonus' and isinstance(frame['reelKey'], str) and 1 <= len(frame['reelKey']) <= 128, 'not a current award frame')
    return event, frame


def _totals(bet, cash, commands):
    event, bd = bet['eventdata'], bet['betdata']
    require(set(bd) - {'initialBalance'} == {'coin', 'cashBet', 'cmd', 'accWa', 'accC', 'cmds'}, 'unlearned bet data')
    require(all(close(value, cash) for value in (bd['accWa'], event['accWa'], event['response']['cashWin'])), 'award totals disagree')
    require(all(type(value) is int and value == 0 for value in (bd['accC'], event['accC'])), 'unlearned coin accumulator')
    boost = event['boostData']
    require(isinstance(boost, dict) and set(boost) == {'wins', 'superwin', 'fisherman'} and all(type(value) is int and value == 0 for value in boost.values()), 'unlearned boost counters')
    require(command_values(bd['cmds']) == commands and command_values(event['nextCmds']) == commands, 'current command domains disagree')
    require(bet['status'] == 'RESULTED' and num(bet['wonamount']) == 0, 'award was credited before settlement')


def _offer(state, constraints):
    definition, rules = constraints['indexed_output_definition'], constraints['indexed_award_definition']
    require(state['status'] == 'Pending' and not state['terminal'] and state['max_step'] == 1 and len(state['bets']) == 1, 'not an initial current offer')
    bet = state['bets'][0]
    bd = bet['betdata']
    quote = constraints['purchase_quotes'][bd['cmd']]
    require(bet['step'] == 1 and bet['betcurrency'] == constraints['currency'], 'offer identity or currency changed')
    require(num(bet['betamount']) == num(quote['amount']) == num(bd['cashBet']) and num(bd['coin']) == num(quote['coin']), 'offer price disagrees with current quote')
    event, frame = _output(bet, pending=True)
    require(event['initialPlayerState'] in ({}, constraints.get('settled_indexed_award_state', {})), 'unproved prior player state')
    player = event['playerState']
    commands = [rules['accept'], rules['risk']]
    require(isinstance(player, dict) and set(player) == {'inGamble', 'scatters', 'possibleGambles', 'commands'}, 'unlearned current menu state')
    require(player['inGamble'] is True and integer(player['scatters'], 1, definition['width'] * definition['height']) and integer(player['possibleGambles'], 0, 128) and player['commands'] == commands and state['commands'] == commands, 'offer and current menu disagree')
    require(frame['bonusGame'] == rules['purchase_games'][bd['cmd']], 'offer differs from configured purchase')
    paths = board_paths(frame, definition, constraints['basic_amount'])
    require(paths is not None and paths[0] == 0 and num(frame['creditsWon']) == 0, 'unlearned paid trigger prize')
    require(frame['reelLayout'].count(definition['symbols']['scatter']) == player['scatters'], 'scatter count disagrees with board')
    features = frame['bonusInfo']
    require(isinstance(features, list) and len(features) == 1 and isinstance(features[0], dict), 'unlearned offered features')
    offer = features[0]
    require(set(offer) == {'bonusName', 'currentFreeSpins', 'currentScatters', 'result', 'status'} and offer['bonusName'] == rules['features']['gamble'] and offer['status'] == 'pending' and offer['result'] is None, 'unlearned offer status')
    require(integer(offer['currentFreeSpins'], 1, 256) and offer['currentScatters'] == player['scatters'] and type(offer['currentScatters']) is int, 'invalid announced award')
    _totals(bet, Decimal(0), commands)
    return bet, frame, offer


def request(state, constraints):
    if not family(state) or not isinstance(constraints, dict) or not constraints.get('indexed_award_definition'):
        return None
    if state['commands'] == ['C']:
        return None
    try:
        _offer(state, constraints)
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return None
    rules = constraints['indexed_award_definition']
    return {'cmd': rules['accept'], 'type': 'bonus', 'amount': constraints['basic_amount'], 'coin': constraints['basic_amount'], 'step': str(state['max_step'] + 1), 'wagerid': state['wagerid']}


def _held(feature, frame, definition, rules, stake, multipliers):
    require(set(feature) == {'bonusName', 'totalDiverwoman', 'initialTreasures', 'finalTreasures', 'respinList', 'resultingReels', 'creditsWon'}, 'unlearned hold fields')
    width, height = definition['width'], definition['height']
    symbol = definition['symbols']['treasure']
    require(frame['reelLayout'].count(definition['symbols']['diver']) == 1, 'unproved multiple-diver branch')
    # The client copies this opaque counter but does not consume it. It never
    # authorizes extra spins, a multiplier, or a cash amount.
    require(integer(feature['totalDiverwoman'], 0, 4096), 'malformed diver metadata')
    previous = dict(frame['treasureValues'])
    require(integer(feature['initialTreasures'], 1, width * height - 1) and feature['initialTreasures'] == len(previous), 'initial treasures disagree')
    queue = feature['respinList']
    require(isinstance(queue, list) and 1 <= len(queue) <= 4096, 'invalid respin queue')
    lives = rules['respin_lives']
    for entry in queue:
        require(lives > 0 and isinstance(entry, list) and len(entry) == 1 and isinstance(entry[0], dict), 'respin after exhaustion or ambiguous frame')
        current = entry[0]
        require(set(current) - {'debug'} == {'reelLayout', 'fishValues', 'treasureValues', 'winningLines', 'bonusInfo', 'creditsWon', 'reelKey', 'type'}, 'unlearned respin fields')
        board = current['reelLayout']
        require(isinstance(board, list) and len(board) == width * height and all(value is None or type(value) is int and value == symbol for value in board), 'unlearned respin symbols')
        values = current['treasureValues']
        require(isinstance(values, dict) and set(values) == {str(i + 1) for i, value in enumerate(board) if value == symbol} and all(num(value) > 0 for value in values.values()), 'respin treasure values disagree')
        require(set(previous) <= set(values) and all(num(previous[key]) == num(values[key]) for key in previous), 'previous treasure changed or disappeared')
        require(len(values) < width * height, 'unproved full-board termination branch')
        new = len(values) - len(previous)
        expected = [{'bonusName': rules['features']['reset']}] if new else []
        require(current['bonusInfo'] == expected, 'respin life reset disagrees with new treasures')
        require(current['fishValues'] == {} and current['winningLines'] == {'lines': [], 'creditsWon': 0} and num(current['creditsWon']) == 0 and current['reelKey'] is None and current['type'] == 'spin', 'unlearned respin award')
        lives = rules['respin_lives'] if new else lives - 1
        previous = values
    require(lives == 0, 'respin lives remain')
    columns = [[board[row * width + column] for row in range(height)] for column in range(width)]
    require(feature['resultingReels'] == columns and integer(feature['finalTreasures'], 1, width * height - 1) and feature['finalTreasures'] == len(previous), 'final treasure board or count disagrees')
    cash = num(stake) * sum((num(value) * (multipliers[(int(position) - 1) % width] if None not in columns[(int(position) - 1) % width] else 1) for position, value in previous.items()), Decimal(0))
    require(close(feature['creditsWon'], cash), 'held treasure credit disagrees with column multipliers')
    return cash, len(queue)


def _free(award, offer, definition, rules, stake):
    require(set(award) == {'bonusName', 'freeSpinList', 'count', 'multiplier', 'creditsWon', 'scatters'} and award['bonusName'] == rules['features']['free'], 'unlearned free award')
    require(type(award['count']) is int and award['count'] == offer['currentFreeSpins'] and type(award['scatters']) is int and award['scatters'] == offer['currentScatters'] and type(award['multiplier']) is int and award['multiplier'] == 1, 'announced free award changed')
    queue = award['freeSpinList']
    require(isinstance(queue, list) and 1 <= len(queue) <= 4096, 'invalid free-spin queue')
    left, extras, respins, total = award['count'], 0, 0, Decimal(0)
    multipliers = list(definition['multipliers'])
    names = rules['features']
    for entry in queue:
        require(left > 0 and isinstance(entry, list) and len(entry) == 1 and isinstance(entry[0], dict), 'free spin after exhaustion or ambiguous frame')
        left -= 1
        frame = entry[0]
        require(set(frame) - {'debug'} == {'reelLayout', 'fishValues', 'treasureValues', 'winningLines', 'bonusInfo', 'creditsWon', 'reelKey', 'type', 'creditsWonAccumulated'}, 'unlearned free-spin fields')
        require(frame['type'] == 'spin' and isinstance(frame['reelKey'], str) and 1 <= len(frame['reelKey']) <= 128 and close(frame['creditsWonAccumulated'], total), 'free-spin state or prior credit changed')
        paths = board_paths(frame, definition, stake)
        require(paths is not None, 'invalid free-spin paths')
        line_cash, leading = paths
        features = frame['bonusInfo']
        require(isinstance(features, list) and all(isinstance(value, dict) for value in features), 'malformed free features')
        labels = [value.get('bonusName') for value in features]
        double = [definition['multiplier_feature']] if leading else []
        collect_order = [names['collector'], names['duplicate'], names['extra']] + double
        hold_order = [names['duplicate'], names['hold'], names['extra']]
        require(labels in (double, collect_order, hold_order), 'unproved feature combination or order')
        fish_cash, held_cash, multiplier = Decimal(0), Decimal(0), 1
        if labels == hold_order:
            require(not leading and line_cash == 0, 'unproved simultaneous hold and line/multiplier award')
        for feature in features:
            label = feature['bonusName']
            if label == names['collector']:
                fish_cash = collector_cash(feature, frame, definition, stake, names['collector'])
                require(fish_cash is not None, 'collector positions or credit disagree with current fish values')
            elif label == names['duplicate']:
                require(set(feature) == {'bonusName', 'multipliers'} and isinstance(feature['multipliers'], list) and all(type(value) is int for value in feature['multipliers']), 'malformed multiplier array')
                expected = [value * rules['duplicate_factor'] for value in multipliers]
                require(feature['multipliers'] == expected, 'multiplier array did not follow the current duplication rule')
                multipliers = expected
            elif label == names['extra']:
                require(set(feature) == {'bonusName'}, 'unlearned extra-spin amount')
                left += rules['extra_spins']; extras += rules['extra_spins']
            elif label == names['hold']:
                held_cash, count = _held(feature, frame, definition, rules, stake, multipliers)
                respins += count
            else:
                multiplier = double_multiplier(feature, definition, multipliers, leading)
                require(multiplier is not None, 'current DoubleMax disagrees with fish columns')
        cash = (line_cash + fish_cash) * multiplier + held_cash
        require(close(frame['creditsWon'], cash), 'free-spin credit disagrees with reconstructed awards')
        total += cash
    require(left == 0 and close(award['creditsWon'], total), 'free spins remain or award total disagrees')
    return {'schema': 'indexed-output/exhausted-award-queues/v1', 'initial_free_spins': award['count'], 'extra_spins': extras, 'played_free_spins': len(queue), 'nested_respins': respins, 'free_spins_remaining': left, 'respin_lives_remaining': 0, 'exact_win': format(total.normalize(), 'f')}


def validate_transition(before, after, sent, constraints):
    if not family(before) or not isinstance(constraints, dict) or not constraints.get('indexed_award_definition'):
        return False
    if sent['cmd'] == 'C':
        return False
    expected = request(before, constraints)
    require(expected is not None and sent == expected, 'request differs from current safe client acceptance')
    prior, initial, offer = _offer(before, constraints)
    require(before['wagerid'] == after['wagerid'] and after['status'] == 'Pending' and not after['terminal'] and after['commands'] == ['C'], 'award did not advance to current settlement')
    require(len(after['bets']) == 1 and after['max_step'] == before['max_step'] + 1, 'ambiguous award step')
    current = after['bets'][0]
    require(current['betcurrency'] == prior['betcurrency'] and num(current['betamount']) == 0, 'acceptance charged or changed currency')
    event, frame = _output(current, pending=False)
    require(event['initialPlayerState'] == prior['eventdata']['playerState'] == event['playerState'], 'player state changed during acceptance')
    require({key: value for key, value in frame.items() if key not in {'debug', 'creditsWon', 'bonusInfo', 'inGamble'}} == {key: value for key, value in initial.items() if key not in {'debug', 'creditsWon', 'bonusInfo', 'inGamble'}}, 'trigger board changed during acceptance')
    features = frame['bonusInfo']
    require(isinstance(features, list) and len(features) == 2 and features[0] == {**offer, 'status': 'finished', 'result': 'fs'}, 'offered award was not accepted')
    proof = _free(features[1], offer, constraints['indexed_output_definition'], constraints['indexed_award_definition'], constraints['basic_amount'])
    proof['paid_command'] = prior['betdata']['cmd']
    cash = num(proof['exact_win'])
    require(close(frame['creditsWon'], cash), 'root award total disagrees')
    _totals(current, cash, ['C'])
    after['indexed_award_proof'] = proof
    after['indexed_award_player_state'] = dict(event['playerState'])
    return True


def direct(state, constraints):
    """A configured purchase may deliver the complete free queue immediately."""
    if not family(state) or not isinstance(constraints, dict) or not constraints.get('indexed_award_definition'):
        return None
    try:
        require(state['status'] == 'Pending' and not state['terminal'] and state['commands'] == ['C'] and state['max_step'] == 1 and len(state['bets']) == 1, 'not a direct purchased award')
        bet = state['bets'][0]
        bd = bet['betdata']
        quote = constraints['purchase_quotes'][bd['cmd']]
        require(bet['step'] == 1 and bet['betcurrency'] == constraints['currency'] and num(bet['betamount']) == num(quote['amount']) == num(bd['cashBet']) and num(bd['coin']) == num(quote['coin']), 'direct purchase disagrees with current quote')
        event, frame = _output(bet, pending=False)
        require(event['initialPlayerState'] == event['playerState'] and event['playerState'] in ({}, constraints.get('settled_indexed_award_state', {})), 'unproved retained state in direct purchase')
        definition, rules = constraints['indexed_output_definition'], constraints['indexed_award_definition']
        require(frame['bonusGame'] == rules['purchase_games'][bd['cmd']], 'direct award differs from configured purchase')
        paths = board_paths(frame, definition, constraints['basic_amount'])
        require(paths is not None and paths[0] == 0, 'unlearned direct trigger prize')
        features = frame['bonusInfo']
        require(isinstance(features, list) and len(features) == 1 and isinstance(features[0], dict), 'unlearned direct award features')
        award = features[0]
        require(integer(award['count'], 1, 256) and integer(award['scatters'], 1, definition['width'] * definition['height']) and frame['reelLayout'].count(definition['symbols']['scatter']) == award['scatters'], 'direct scatter count disagrees with board')
        announced = {'currentFreeSpins': award['count'], 'currentScatters': award['scatters']}
        proof = _free(award, announced, definition, rules, constraints['basic_amount'])
        proof['paid_command'] = bd['cmd']
        cash = num(proof['exact_win'])
        require(close(frame['creditsWon'], cash), 'direct award total disagrees')
        _totals(bet, cash, ['C'])
        state['indexed_award_proof'] = proof
        state['indexed_award_player_state'] = dict(event['playerState'])
        return proof
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return None


def safe_output(state):
    def clean(value):
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items() if key != 'debug'}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value
    return [clean(bet['eventdata']['response']['clientData']['output']) for bet in state['bets'] if 'response' in bet['eventdata']]
