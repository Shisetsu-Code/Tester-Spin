"""Validate indexed cash paths and board-derived multipliers in ordinary play."""
from decimal import Decimal
from itertools import product

from .cash_collect import close
from .protocol import command_values
from .supermeter import num


def family(state):
    try:
        data = state['bets'][0]['eventdata']['response']['clientData']
        return isinstance(data, dict) and 'output' in data
    except (TypeError, KeyError, IndexError):
        return False


def _values(values, board, symbol):
    if not isinstance(values, dict) or set(values) != {str(index + 1) for index, value in enumerate(board) if value == symbol}:
        return False
    return all(num(value) > 0 for value in values.values())


def board_paths(frame, definition, stake):
    """Validate every cash path; feature totals are checked by their caller."""
    board = frame['reelLayout']
    width, height = definition['width'], definition['height']
    awards, symbols = definition['awards'], definition['symbols']
    if not isinstance(board, list) or len(board) != width * height or any(type(value) is not int or str(value) not in awards for value in board):
        return None
    if not _values(frame['fishValues'], board, symbols['fish']) or not _values(frame['treasureValues'], board, symbols['treasure']):
        return None
    leading = 0
    for column in range(width):
        if symbols['fish'] not in board[column::width]:
            break
        leading += 1
    # Current SDK has no wild substitution in this renderer. Enumerate all
    # left-contiguous ways using current server award tables, not just the
    # advertised matching positions, to reject missing or duplicated paths.
    expected = {}
    unit = num(stake) / num(definition['bet_divisor'])
    for symbol, table in awards.items():
        columns = []
        for column in range(width):
            positions = [row * width + column + 1 for row in range(height) if board[row * width + column] == int(symbol)]
            if not positions:
                break
            columns.append(positions)
        count = len(columns)
        prize = num(table[str(count)]) if count else Decimal(0)
        if prize <= 0:
            continue
        path_count = 1
        for positions in columns:
            path_count *= len(positions)
        if len(expected) + path_count > 4096:
            return None
        for positions in product(*columns):
            expected[(int(symbol), positions)] = unit * prize
    wins = frame['winningLines']
    if not isinstance(wins, dict) or set(wins) != {'lines', 'creditsWon'} or not isinstance(wins['lines'], list) or len(wins['lines']) != len(expected):
        return None
    found, total = set(), Decimal(0)
    for win in wins['lines']:
        if not isinstance(win, dict) or set(win) != {'line', 'creditsWon', 'symbol', 'count', 'matchPositions'}:
            return None
        if type(win['line']) is not int or not 0 <= win['line'] <= 4096 or type(win['symbol']) is not int or type(win['count']) is not int:
            return None
        positions = win['matchPositions']
        if not isinstance(positions, list) or len(positions) != win['count'] or any(type(value) is not int for value in positions):
            return None
        key = (win['symbol'], tuple(positions))
        if key not in expected or key in found or not close(win['creditsWon'], expected[key]):
            return None
        # The current SDK appends every path and preserves a display id that
        # can repeat. The path's symbol and positions are the unique identity.
        found.add(key); total += expected[key]
    if found != set(expected) or not close(wins['creditsWon'], total):
        return None
    return total, leading


def double_multiplier(feature, definition, multipliers, leading):
    if not isinstance(feature, dict) or set(feature) != {'bonusName', 'multiplier', 'consecutive'} or feature['bonusName'] != definition['multiplier_feature']:
        return None
    if not leading or type(feature['consecutive']) is not int or feature['consecutive'] != leading or type(feature['multiplier']) is not int or feature['multiplier'] != multipliers[leading - 1]:
        return None
    return feature['multiplier']


def collector_cash(feature, frame, definition, stake, label):
    if set(feature) != {'bonusName', 'fishermanPosition', 'fishermanCollector', 'creditsWon'} or feature['bonusName'] != label:
        return None
    positions = [i + 1 for i, value in enumerate(frame['reelLayout']) if value == definition['symbols']['collector']]
    if len(positions) != 1 or feature['fishermanPosition'] != positions or type(feature['fishermanCollector']) is not int or not 1 <= feature['fishermanCollector'] <= 4096:
        return None
    cash = num(stake) * sum((num(value) for value in frame['fishValues'].values()), Decimal(0))
    return cash if cash > 0 and close(feature['creditsWon'], cash) else None


def _frame(frame, definition, stake, rules):
    if not isinstance(frame, dict) or set(frame) - {'debug'} != {'reelLayout', 'fishValues', 'treasureValues', 'winningLines', 'bonusInfo', 'jackpotsInfo', 'creditsWon', 'reelKey', 'inGamble', 'type'}:
        return None
    if frame['inGamble'] is not False or frame['type'] != 'spin' or frame['jackpotsInfo'] != [] or not isinstance(frame['reelKey'], str) or not 1 <= len(frame['reelKey']) <= 128:
        return None
    paths = board_paths(frame, definition, stake)
    if paths is None or not isinstance(frame['bonusInfo'], list):
        return None
    total, leading = paths
    features = frame['bonusInfo']
    if not all(isinstance(feature, dict) for feature in features):
        return None
    labels = [feature.get('bonusName') for feature in features]
    expected = [definition['multiplier_feature']] if leading else []
    collected, fish_cash = False, Decimal(0)
    if labels != expected:
        if rules is None or labels != [rules['features']['collector']] + expected:
            return None
        fish_cash = collector_cash(features[0], frame, definition, stake, rules['features']['collector'])
        if fish_cash is None:
            return None
        collected, features = True, features[1:]
    multiplier = 1
    if leading:
        if len(features) != 1:
            return None
        multiplier = double_multiplier(features[0], definition, definition['multipliers'], leading)
        if multiplier is None:
            return None
    elif features:
        return None
    cash = (total + fish_cash) * multiplier
    return {'cash': cash, 'collected': collected} if close(frame['creditsWon'], cash) else None


def _paid(bet, constraints, *, allow_collector):
    try:
        definition = constraints['indexed_output_definition']
        if bet['step'] != 1 or bet['status'] != 'RESULTED' or bet['betcurrency'] != constraints['currency'] or num(bet['betamount']) != num(constraints['basic_amount']) or num(bet['wonamount']) != 0:
            return False
        bd, event = bet['betdata'], bet['eventdata']
        if set(bd) - {'cmds', 'initialBalance'} != {'coin', 'cashBet', 'cmd', 'accWa', 'accC'} or bd['cmd'] != 'BASE_SPIN' or num(bd['cashBet']) != num(constraints['basic_amount']) or num(bd['coin']) != num(constraints['basic_coin']):
            return False
        history = constraints.get('settled_indexed_award_state', {})
        if set(event) - {'nextCmds'} != {'accC', 'accWa', 'boostData', 'initialPlayerState', 'playerState', 'response'} or event['initialPlayerState'] != event['playerState'] or event['playerState'] not in ({}, history):
            return False
        response = event['response']
        if set(response) != {'coinWin', 'cashWin', 'clientData'} or num(response['coinWin']) != 0 or set(response['clientData']) != {'output'}:
            return False
        output = response['clientData']['output']
        if not isinstance(output, list) or len(output) != 1:
            return False
        result = _frame(output[0], definition, constraints['basic_amount'], constraints.get('indexed_award_definition'))
        if result is None or result['collected'] and not allow_collector:
            return False
        cash = result['cash']
        if any(not close(value, cash) for value in (response['cashWin'], event['accWa'], bd['accWa'])) or any(type(value) is not int or value != 0 for value in (event['accC'], bd['accC'])):
            return False
        boost = event['boostData']
        if not isinstance(boost, dict) or set(boost) != {'wins', 'superwin', 'fisherman'} or any(type(value) is not int for value in boost.values()) or boost != {'wins': int(cash > 0), 'superwin': 0, 'fisherman': int(result['collected'])}:
            return False
        commands = ['C'] if cash > 0 else []
        return command_values(event.get('nextCmds')) == commands and command_values(bd.get('cmds')) == commands
    except (KeyError, TypeError, ValueError, AttributeError, ArithmeticError):
        return False


def ordinary(bet, constraints):
    return _paid(bet, constraints, allow_collector=False)


def known(bet, constraints):
    return _paid(bet, constraints, allow_collector=True)
