"""A bounded legacy cluster/cascade contract from current Config and SDK.

Paid zero results, exhausted pure cascades and one MUTINY -> CASCADE group
with neutral multipliers are supported. MUTINY remains a feature. Connectivity below is
deliberately conservative: the public client displays backend clusters but
does not implement their adjacency algorithm.  Boards ambiguous between
four/eight neighbours, unconsumed winning refill symbols and other branches fail.

The source recognizer compares complete current function bodies and checks
their module dependencies.  A changed implementation must be reviewed; a
title, game ID, command spelling or response shape is never its authority.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re


_IDENT = r'[A-Za-z_$][\w$]*'
_MODULE = re.compile(r'_d\(("(?:[^"\\]|\\.)*"),(\[[^\]\n]*\]),function\(([^)]*)\)\{')


def _body(source, start):
    depth, quote, escaped, end = 1, None, False, start
    while depth and end < min(len(source), start + 100000):
        char = source[end]
        if quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == '`' or source[end:end + 2] in ('//', '/*'):
            return None
        else:
            depth += int(char == '{') - int(char == '}')
        end += 1
    return (source[start:end - 1], end) if depth == 0 else None


def _modules(source):
    records = []
    for match in _MODULE.finditer(source):
        found = _body(source, match.end())
        if found is None or source[found[1]:found[1] + 1] != ')':
            continue
        deps = json.loads(match[2])
        args = match[3].split(',') if match[3] else []
        if len(args) != len(deps) or len(set(args)) != len(args) or any(not re.fullmatch(_IDENT, value) for value in args):
            continue
        records.append({'name': json.loads(match[1]), 'deps': dict(zip(args, deps)), 'body': found[0], 'index': len(records)})
    return records


def _resolve(modules, module, variable, *, unwrap=True):
    name = module['deps'].get(variable)
    candidates = [item for item in modules if item['name'] == name
                  and (name != module['name'] or item['index'] < module['index'])]
    if not candidates:
        return None
    selected = candidates[-1]
    if unwrap:
        seen = set()
        while re.fullmatch(r'return new ' + _IDENT, selected['body']):
            if selected['index'] in seen:
                return None
            seen.add(selected['index'])
            selected = _resolve(modules, selected, selected['body'][11:], unwrap=False)
            if selected is None:
                return None
    return selected


def _enum(module):
    if module is None or module['deps'] or not re.fullmatch(r'return\{(?:[A-Z][A-Z_0-9]*:"(?:[^"\\]|\\.)*",?)+\}', module['body']):
        return None
    value = re.sub(r'([,{])([A-Z][A-Z_0-9]*):', r'\1"\2":', module['body'][6:])
    pairs = json.loads(value, object_pairs_hook=list)
    return dict(pairs) if len(dict(pairs)) == len(pairs) else None


def _source(source):
    if not isinstance(source, str) or not source or len(source) > 20000000:
        return None
    modules = _modules(source)
    selected = {}
    for role, body in _SOURCE_BODIES.items():
        candidates = [module for module in modules if module['body'] == body
                      and tuple(module['deps']) == _SOURCE_ARGS[role]]
        if len(candidates) != 1:
            return None
        selected[role] = candidates[0]
    if len({item['index'] for item in selected.values()}) != len(selected):
        return None
    for role, variable, target in _SOURCE_LINKS:
        if _resolve(modules, selected[role], variable) != selected[target]:
            return None
    inherited = {selected[target]['index'] for role, _, target in _SOURCE_LINKS
                 if selected[role]['name'] == selected[target]['name']}
    for module in selected.values():
        if module['index'] not in inherited and module != [item for item in modules if item['name'] == module['name']][-1]:
            return None
    features = _enum(_resolve(modules, selected['parser'], 't'))
    kinds = _enum(_resolve(modules, selected['symbols'], 'i'))
    icons = _enum(_resolve(modules, selected['mutiny'], 'i'))
    if not features or set(features) != {'TSUNAMI', 'MUTINY', 'CLUSTER_MUTATION', 'CASCADE', 'CANNON_BLAST'} or len(set(features.values())) != len(features):
        return None
    if not kinds or set(kinds) != {'LOW', 'MID', 'HIGH', 'FREE_SPIN', 'MUTINY'} or not icons:
        return None
    if kinds['MUTINY'] != icons.get('MUTINY') or kinds['FREE_SPIN'] != icons.get('FREE_SPINS'):
        return None
    classes = {kind: {value for key, value in icons.items() if re.fullmatch(kind + r'_[1-9][0-9]*', key)}
               for kind in ('LOW', 'MID', 'HIGH')}
    if any(not values or not re.fullmatch(r'[A-Z]+\\d', kinds[kind])
           or any(not re.fullmatch(kinds[kind], value) for value in values)
           for kind, values in classes.items()):
        return None
    cash_symbols = set.union(*classes.values())
    if len(cash_symbols) != sum(map(len, classes.values())):
        return None
    transformed = {value for key, value in icons.items() if re.fullmatch(r'MUTINY_HIGH_[1-9][0-9]*', key)}
    if transformed != {icons['MUTINY'] + '_' + value for value in classes['HIGH']}:
        return None
    for role, variable in [('avalanche', 'n'), ('cascade', 'e'), ('mutiny', 'e'), ('multiplier', 'i'), ('cannon', 'e')]:
        if _enum(_resolve(modules, selected[role], variable)) != features:
            return None
    # The formatter gets its mask row stride from the current settings module.
    bridges = [item for item in modules if item['body'] == 'return new t(e.serverType,e.serverLegacyType,n.ROWS)'
               and set(item['deps']) == {'t', 'e', 'n'}]
    if len(bridges) != 1 or _resolve(modules, bridges[0], 't') != selected['facade']:
        return None
    settings = _resolve(modules, bridges[0], 'n', unwrap=False)
    geometry = re.fullmatch(
        r'return e\.mixin\(t,\{GAME_NAME:"[^"\\]*",FORMATTED_GAME_NAME:"[^"\\]*",'
        r'TRANSLATION_CATEGORIES:t\.TRANSLATION_CATEGORIES\.concat\(\[[^\]]*\]\),'
        r'CURRENCIES_SUPPORTED_CASH_WIN:\[[^\]]*\],GAME_ID:[0-9]+,NEW_MOBILE_UI:!0,USE_OGG:!1,'
        r'SCATTER:"([^"\\]+)",ROWS:([1-9][0-9]*),RENDERER_OPTIONS:\{ANTIALIASING:\{DESKTOP:!0,TABLET:!0,MOBILE:!1\}\}\}\),t',
        settings['body'] if settings else '')
    if geometry is None or geometry[1] != kinds['FREE_SPIN']:
        return None
    trigger = re.findall(r'this\.SCATTERS_COUNT_TO_TRIGGER=([1-9][0-9]*)(?=,)', selected['free']['body'])
    if len(trigger) != 1:
        return None
    return {'rows': int(geometry[2]), 'scatter_trigger': int(trigger[0]),
            'empty': 'EMPTY', 'scatter': kinds['FREE_SPIN'], 'mutiny': kinds['MUTINY'],
            'high_pattern': kinds['HIGH'], 'cash_symbols': cash_symbols,
            'highs': classes['HIGH'], 'features': features,
            'source_sha256': hashlib.sha256(source.encode()).hexdigest()}


def _number(value):
    if type(value) not in (str, int, float, Decimal):
        raise ValueError('Not a monetary number')
    if isinstance(value, str) and not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', value):
        raise ValueError('Not a nonnegative decimal')
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError('Invalid monetary number')
    return result


def _int(value, minimum=0, maximum=1000000):
    return type(value) is int and minimum <= value <= maximum


def declaration(props, sdk_source):
    """Bind the current complete paytable and geometry to the current client."""
    try:
        proof = _source(sdk_source)
        if proof is None or not isinstance(props, dict):
            return None
        width, height = props['NumberOfReels'], props['WindowHeight']
        minimum, prices = props['MinClusterSize'], props['PrizesPerIcon']
        symbols, types = props['Icons'], props['IconTypes']
        if not _int(width, 1, 25) or not _int(height, 1, 25) or width * height != 25 or height != proof['rows']:
            return None
        if not _int(minimum, 2, width * height) or not isinstance(symbols, list) or not isinstance(types, list) or len(symbols) != len(types) or len(set(symbols)) != len(symbols):
            return None
        if any(not isinstance(value, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', value) for value in symbols):
            return None
        specials = {proof['empty']: 'R', proof['mutiny']: 'S', proof['scatter']: 'S'}
        if len(specials) != 3 or not isinstance(prices, dict) or not prices or set(symbols) != set(prices) | set(specials) or set(prices) & set(specials):
            return None
        if set(prices) != proof['cash_symbols']:
            return None
        if dict(zip(symbols, types)) != {**dict.fromkeys(prices, 'N'), **specials} or any(not _int(value, 1) for value in prices.values()):
            return None
        table = props['Prizes']
        if not isinstance(table, list) or len(table) != len(prices):
            return None
        seen = set()
        for row in table:
            if not isinstance(row, list) or len(row) != width * height + 1 or row[0] not in prices or row[0] in seen:
                return None
            seen.add(row[0])
            if any(_number(value) != (0 if count < minimum else prices[row[0]] * count) for count, value in enumerate(row[1:], 1)):
                return None
        coins = props['CoinsPerBet']
        if not isinstance(coins, list) or len(coins) != 1 or not _int(coins[0], 1) or props['Modes'] != {'BASIC': {'coinsPerBet': coins[0]}}:
            return None
        multipliers = props['MultipliersPerLevel']
        if not isinstance(multipliers, dict) or set(multipliers) != set('012345') or any(not _int(value) for value in multipliers.values()) or multipliers['0'] != 0 or multipliers['1'] != 1:
            return None
        if any(multipliers[str(i)] <= multipliers[str(i - 1)] for i in range(2, 6)):
            return None
        if not re.fullmatch(r'[A-Z]+\\d', proof['high_pattern']):
            return None
        highs = [symbol for symbol in prices if re.fullmatch(proof['high_pattern'], symbol)]
        if set(highs) != proof['highs'] or not 1 < proof['scatter_trigger'] <= width * height:
            return None
        return {'schema': 'legacy-cluster-cascade/current-config/v1', 'width': width, 'height': height,
                'min_cluster': minimum, 'prices': dict(prices), 'symbols': list(symbols),
                'empty': proof['empty'], 'mutiny': proof['mutiny'], 'scatter': proof['scatter'],
                'highs': highs, 'features': proof['features'], 'scatter_trigger': proof['scatter_trigger'],
                'coins_per_bet': coins[0], 'source_sha256': proof['source_sha256']}
    except (KeyError, TypeError, ValueError, InvalidOperation, re.error):
        return None


def family(state):
    """Route any apparent member here, including malformed/unsupported frames."""
    try:
        event = state['bets'][0]['eventdata']
        return isinstance(event, dict) and bool({'listAvalanche', 'minClusterSize', 'prizesForIcon'} & set(event))
    except (TypeError, KeyError, IndexError):
        return False


def _board(value, definition, *, empty=False):
    allowed = set(definition['symbols'])
    if not empty:
        allowed.remove(definition['empty'])
    return (isinstance(value, list) and len(value) == definition['width']
            and all(isinstance(column, list) and len(column) == definition['height']
                    and all(isinstance(symbol, str) and symbol in allowed for symbol in column) for column in value))


def _positions(board, symbol):
    return {(column, row) for column, values in enumerate(board) for row, value in enumerate(values) if value == symbol}


def _position(position, definition):
    if not isinstance(position, dict) or set(position) != {'column', 'row'} or not _int(position['column'], 0, definition['width'] - 1) or not _int(position['row'], 0, definition['height'] - 1):
        raise ValueError('Invalid position')
    return position['column'], position['row']


def _components(board, definition, diagonal):
    candidates = []
    neighbours = [(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x or y) and (diagonal or not x or not y)]
    for symbol in definition['prices']:
        pending = _positions(board, symbol)
        while pending:
            group = {pending.pop()}
            todo = list(group)
            while todo:
                column, row = todo.pop()
                adjacent = {(column + x, row + y) for x, y in neighbours} & pending
                group.update(adjacent); pending.difference_update(adjacent); todo.extend(adjacent)
            if len(group) >= definition['min_cluster']:
                candidates.append((symbol, group))
    return candidates


def _unique_winner(board, definition, symbol):
    all_positions = _positions(board, symbol)
    expected = [(symbol, all_positions)]
    return (_components(board, definition, False) == expected
            and _components(board, definition, True) == expected)


_EVENT_FIELDS = {'accC', 'accWa', 'collectedInitialScatters', 'finalBoard', 'globalMultiAfter',
                 'globalMultiBefore', 'inputBoard', 'listAvalanche', 'minClusterSize',
                 'prizesForIcon', 'reels', 'wonCoins', 'wonMoney', 'wtw'}
_FEATURE_FIELDS = {'initialIntermediateBoard', 'cascadeIntermediateBoard', 'finalIntermediateBoard',
                   'shifts', 'newIcons', 'clusters', 'mutinyPositions', 'multiplierBefore',
                   'multiplierAfter', 'collectedScattersBefore', 'collectedScattersAfter', 'type'}


def _retained_board(positions, definition, symbol):
    return [[symbol if (column, row) in positions else definition['empty']
             for row in range(definition['height'])] for column in range(definition['width'])]


def _mutiny_board(frame, board, definition, symbol, scatters):
    if symbol not in definition['highs'] or frame['initialIntermediateBoard'] != board:
        return None
    if any(frame[key] is not None for key in ('cascadeIntermediateBoard', 'shifts', 'newIcons', 'clusters')):
        return None
    if any(type(frame[key]) is not int or frame[key] != value for key, value in
           [('multiplierBefore', 1), ('multiplierAfter', 0),
            ('collectedScattersBefore', scatters), ('collectedScattersAfter', scatters)]):
        return None
    coordinates = frame['mutinyPositions']
    if not isinstance(coordinates, list) or len(coordinates) != 9:
        return None
    positions = [_position(position, definition) for position in coordinates]
    columns, rows = sorted({c for c, _ in positions}), sorted({r for _, r in positions})
    if len(set(positions)) != 9 or len(columns) != 3 or len(rows) != 3 or columns[-1] - columns[0] != 2 or rows[-1] - rows[0] != 2 or set(positions) != {(c, r) for c in columns for r in rows} or set(positions) != _positions(board, definition['mutiny']):
        return None
    transformed = [[symbol if (column, row) in positions else value for row, value in enumerate(values)] for column, values in enumerate(board)]
    return transformed if frame['finalIntermediateBoard'] == transformed and _unique_winner(transformed, definition, symbol) else None


def _cascade_boards(frames, board, definition, symbol, scatters, first_multiplier):
    """Keep old winners fixed; every next group consumes exactly the new ones."""
    if not frames or len(frames) > definition['width'] * definition['height']:
        return None
    locked = set()
    for index, frame in enumerate(frames):
        if frame['type'] != definition['features']['CASCADE'] or frame['clusters'] is not None or frame['mutinyPositions'] is not None:
            return None
        if any(type(frame[key]) is not int or frame[key] != value for key, value in
               [('multiplierBefore', first_multiplier if index == 0 else 0), ('multiplierAfter', 0), ('collectedScattersBefore', scatters)]):
            return None
        if _positions(board, definition['mutiny']) or not _unique_winner(board, definition, symbol):
            return None
        winners = _positions(board, symbol)
        fresh = winners - locked
        if not locked <= winners or not fresh or frame['initialIntermediateBoard'] != _retained_board(winners, definition, symbol):
            return None
        gravity = {}
        for column in range(definition['width']):
            rows = sorted(row for col, row in fresh if col == column)
            bottom = definition['height'] - sum(col == column for col, _ in locked)
            gravity.update({(column, row): (column, bottom - len(rows) + rank) for rank, row in enumerate(rows)})
        shifts = frame['shifts']
        if not isinstance(shifts, list) or len(shifts) != len(gravity) or any(not isinstance(shift, dict) or set(shift) != {'origin', 'target'} for shift in shifts):
            return None
        actual = [(_position(shift['origin'], definition), _position(shift['target'], definition)) for shift in shifts]
        if len({origin for origin, _ in actual}) != len(actual) or dict(actual) != gravity:
            return None
        destinations = locked | set(gravity.values())
        if len(destinations) != len(winners) or frame['cascadeIntermediateBoard'] != _retained_board(destinations, definition, symbol):
            return None
        final = frame['finalIntermediateBoard']
        if not _board(final, definition) or not destinations <= _positions(final, symbol) or _positions(final, definition['mutiny']) or not _unique_winner(final, definition, symbol):
            return None
        new = frame['newIcons']
        if not isinstance(new, list):
            return None
        new_positions = [_position(position, definition) for position in new]
        expected_new = {(c, r) for c in range(definition['width']) for r in range(definition['height'])} - destinations
        # A full winning board may need TSUNAMI; only actual nonempty refills
        # are proved here. Every new winner must have another complete group.
        if not expected_new or len(set(new_positions)) != len(new_positions) or set(new_positions) != expected_new:
            return None
        extra_winners = _positions(final, symbol) - destinations
        if bool(extra_winners) != (index < len(frames) - 1):
            return None
        after = scatters + len(_positions(final, definition['scatter']))
        if type(frame['collectedScattersAfter']) is not int or frame['collectedScattersAfter'] != after or after >= definition['scatter_trigger']:
            return None
        board, locked, scatters = final, destinations, after
    return board, locked


def _result(bet, constraints):
    definition = constraints['cluster_cascade_definition']
    if not isinstance(definition, dict) or definition.get('schema') != 'legacy-cluster-cascade/current-config/v1':
        return None
    if type(bet['step']) is not int or bet['step'] != 1 or bet['status'] != 'RESULTED' or bet['prepaid'] is not False or bet['prizes'] is not None:
        return None
    coin, amount = _number(constraints['basic_coin']), _number(constraints['basic_amount'])
    if not coin or coin * definition['coins_per_bet'] != amount or _number(bet['betamount']) != amount or _number(bet['wonamount']) != 0 or bet['betcurrency'] != constraints['currency']:
        return None
    bd, event = bet['betdata'], bet['eventdata']
    if not isinstance(bd, dict) or set(bd) - {'cmds'} != {'coin', 'cmd', 'initialBalance', 'ncoins', 'accWa', 'accC'} or bd['cmd'] != '' or _number(bd['coin']) != coin or type(bd['ncoins']) is not int or bd['ncoins'] != definition['coins_per_bet'] or _number(bd['initialBalance']) < amount:
        return None
    if not isinstance(event, dict) or set(event) not in (_EVENT_FIELDS, _EVENT_FIELDS | {'nextCmds', 'winningIcon'}):
        return None
    if not _int(event['minClusterSize']) or event['minClusterSize'] != definition['min_cluster'] or event['prizesForIcon'] != definition['prices'] or any(type(value) is not int for value in event['prizesForIcon'].values()):
        return None
    if any(type(event[key]) is not int or event[key] != 0 for key in ('globalMultiBefore', 'globalMultiAfter')):
        return None
    initial, final = event['inputBoard'], event['finalBoard']
    if not _board(initial, definition) or not _board(final, definition) or event['reels'] != initial:
        return None
    scatters = len(_positions(initial, definition['scatter']))
    if type(event['collectedInitialScatters']) is not int or event['collectedInitialScatters'] != scatters or scatters >= definition['scatter_trigger']:
        return None
    sequence = event['listAvalanche']
    if not isinstance(sequence, list):
        return None
    feature = False
    if not sequence:
        if set(event) != _EVENT_FIELDS or initial != final or _positions(initial, definition['mutiny']) or _components(initial, definition, True):
            return None
        if event['wtw'] != [] or 'cmds' in bd:
            return None
        won = 0
    else:
        if set(event) != _EVENT_FIELDS | {'nextCmds', 'winningIcon'} or event['nextCmds'] != 'C' or bd.get('cmds') != 'C':
            return None
        if any(not isinstance(frame, dict) or set(frame) != _FEATURE_FIELDS for frame in sequence):
            return None
        symbol = event['winningIcon']
        if not isinstance(symbol, str) or symbol not in definition['prices']:
            return None
        labels = [frame['type'] for frame in sequence]
        if labels == [definition['features']['MUTINY'], definition['features']['CASCADE']]:
            feature = True
            board = _mutiny_board(sequence[0], initial, definition, symbol, scatters)
            cascades = _cascade_boards(sequence[1:], board, definition, symbol, scatters, 0) if board is not None else None
        elif all(label == definition['features']['CASCADE'] for label in labels):
            cascades = _cascade_boards(sequence, initial, definition, symbol, scatters, 1)
        else:
            return None
        if cascades is None or cascades[0] != final:
            return None
        destinations = cascades[1]
        won = len(destinations) * definition['prices'][symbol]
        mask = ''.join('1' if (c, r) in destinations else '0' for c in range(definition['width']) for r in range(definition['height']))
        wins = event['wtw']
        if not isinstance(wins, list) or len(wins) != 1 or not isinstance(wins[0], list) or len(wins[0]) != 6:
            return None
        win = wins[0]
        # Row zero is a presentation/payline id, not a proved symbol id.
        if not _int(win[0], 1, 4096) or win[2] != mask or any(type(win[i]) is not int or win[i] != won for i in (1, 4)) or any(_number(win[i]) != won * coin for i in (3, 5)):
            return None
    if any(type(value) is not int or value != won for value in (event['wonCoins'], event['accC'], bd['accC'])):
        return None
    if any(_number(value) != won * coin for value in (event['wonMoney'], event['accWa'], bd['accWa'])):
        return None
    return {'feature': feature, 'coins': won, 'cash': won * coin}


def known(bet, constraints):
    try:
        return _result(bet, constraints) is not None
    except (KeyError, TypeError, ValueError, InvalidOperation, IndexError):
        return False


def ordinary(bet, constraints):
    try:
        result = _result(bet, constraints)
        return result is not None and not result['feature']
    except (KeyError, TypeError, ValueError, InvalidOperation, IndexError):
        return False


# Exact official module bodies close over constructors and transitive helpers.
# Loader identifiers, game titles and IDs are excluded; dependency edges are
# resolved in the current source before using Config. Cosmetic/source changes
# intentionally require review instead of silently broadening this contract.
_SOURCE_BODIES = {'config': 'function l(){t.call(this)}return '
           'e.extend(l,t),l.prototype.parseSlotConfig=function(e){t.prototype.parseSlotConfig.call(this,e),i.parseBetCost(e.Config.CoinsPerBet),n.parseSpinCmd(e.Config.CoinsPerBet),o.parseMultiplierValues(e.Config.MultipliersPerLevel),a.parseMinClusterSize(e.Config.MinClusterSize)},l.prototype.parseSymbolPrizes=function(t){for(var '
           'e in '
           't.Config.PrizesPerIcon)t.Config.PrizesPerIcon.hasOwnProperty(e)&&(s.symbols[e].prize=t.Config.PrizesPerIcon[e])},l.prototype.parsePaylines=function(){r.paylines=[],r.paylinesOrientations=[]},l',
 'symbols': 'function n(){t.apply(this,arguments)}return e.extend(n,t),n.prototype.isHigh=function(t){return '
            'this._isOfKind(t,i.HIGH)},n.prototype.isMid=function(t){return '
            'this._isOfKind(t,i.MID)},n.prototype.isLow=function(t){return '
            'this._isOfKind(t,i.LOW)},n.prototype.isScatter=function(t){return '
            'this._isOfKind(t,i.FREE_SPIN)},n.prototype.isMutiny=function(t){return '
            'this._isOfKind(t,i.MUTINY)},n.prototype.getSymbolPrize=function(t){return '
            'this.symbols[t].prize},n.prototype._isOfKind=function(t,e){return new RegExp(e,"i").test(t)},n',
 'paytable': 'function a(){}return a.SYMBOL_ALIAS_MAP={".":"dot",",":"comma"," '
             '":"whitespace",$:"USD","€":"EUR","₽":"RUB","£":"GBP"},a.getPaytableContent=function(){var t=[];return '
             't.push(this.getGameLogo()),t.push(this.getDropdownWinsSection()),t.push(this.getTsunamiSection()),t.push(this.getMultiplierSection()),t.push(this.getMutinySection()),t.push(this.getCannonBlastSection()),t.push(this.getFreeSpinsSection()),t.push(this.getSymbolsSection()),t.push(this.getMalfunctionSection()),t},a.getGameLogo=function(){return{sectionClass:"paytableLogo",sectionTitle:"",sectionDescription:this.getPageImage("paytable_logo")}},a.getDropdownWinsSection=function(){return{sectionClass:"dropDownWinsSection",sectionTitle:t.get("paytable_dropdownTitle"),sectionDescription:this.getDropDownDescription()}},a.getTsunamiSection=function(){return{sectionClass:"tsunamiSection",sectionTitle:t.get("paytable_tsunamiTitle"),sectionDescription:this.getTsunamiDescription()}},a.getMutinySection=function(){return{sectionClass:"mutinySection",sectionTitle:t.get("paytable_mutinyTitle"),sectionDescription:this.getMutinyDescription()}},a.getMultiplierSection=function(){return{sectionClass:"multiplierSection",sectionTitle:t.get("paytable_multiplierTitle"),sectionDescription:this.getMultiplierDescription()}},a.getCannonBlastSection=function(){return{sectionClass:"cannonBlastSection",sectionTitle:t.get("paytable_cannonBlastTitle"),sectionDescription:this.getCannonBlastDescription()}},a.getFreeSpinsSection=function(){return{sectionClass:"freeSpinsSection",sectionTitle:t.get("paytable_freespinsTitle"),sectionDescription:this.getFreeSpinsDescription()}},a.getSymbolsSection=function(){return{sectionClass:"symbolsSection",sectionTitle:t.get("paytable_symbolsTitle"),sectionDescription:this.getSymbolsDescription()}},a.getMalfunctionSection=function(){return{sectionClass:"malfunctionSection",sectionTitle:"",sectionDescription:this.getMalfunctionDescription()}},a.getDropDownDescription=function(){return[this.getTextInYellow("paytable_dropdownDesc1"),this.getPageImage("image_1"),this.getTextInYellow("paytable_dropdownDesc2"),this.getPageImages(["image_2","image_3"]),this.getTextInYellow("paytable_dropdownDesc3")].join("")},a.getTsunamiDescription=function(){return[this.getTextInYellow("paytable_tsunamiDesc1"),this.getPageImages(["image_8","image_9","image_10"])].join("")},a.getMultiplierDescription=function(){return[this.getTextInYellow("paytable_multiplierDesc1"),this.getPageImages(["image_4","image_5"])].join("")},a.getCannonBlastDescription=function(){return[this.getTextInYellow("paytable_cannonBlastDesc1"),this.getPageImage("image_11")].join("")},a.getMutinyDescription=function(){return[this.getTextInYellow("paytable_mutinyDesc1"),this.getPageImages(["image_6","image_7"]),this.getTextInYellow("paytable_mutinyDesc2")].join("")},a.getFreeSpinsDescription=function(){return[this.getTextInYellow("paytable_freespinsDesc1"),this.getPageImages(["scatter","scatter","scatter"],"imagesAlignCenter"),this.getTextInYellow("paytable_freespinsDesc2"),this.getPageImage("image_12")].join("")},a.getSymbolsDescription=function(){for(var '
             't=["HIGH","MID","LOW"],e="",i=0;i<t.length;i++)e+=this.getSymbolsLayout(this.getSymbolsData(t[i]));return '
             'e},a.getMalfunctionDescription=function(){return[n.showMobileUI?"":t.get("infoPages_malfunctionInfo"),this.getPageImage("crab")].join("")},a.getSymbolsData=function(t){for(var '
             'n=[],o=e.toArray(i.symbols),a=0;a<o.length;a++){var s=o[a];0===s.name.indexOf(t)&&n.push(s)}return '
             'n},a.getSymbolsLayout=function(t){for(var '
             'e="",i=0;i<t.length;i++)e+=this.getPaytableSymbolContainer(t[i]);return"<div '
             'class=\'symbolsContainer\'>"+e+"</div>"},a.getPaytableSymbolContainer=function(t){return"<div '
             "class='paytableSymbolContainer'><div "
             'class=\'symbolImageContainer\'>"+this.getSymbolImage(t)+"</div><div '
             'class=\'symbolRewardContainer\'>"+this.getSymbolsRewards(t)+"</div></div>"},a.getSymbolImage=function(t){return"<div '
             'class=\'"+t.name.toLowerCase()+"\'></div>"},a.getSymbolsRewards=function(t){for(var '
             'e=[1,25],n=i.getSymbolPrize(t.name),a="",s=0;s<e.length;s++){var r=e[s];a+="<div '
             'class=\'paytableReward\'>",a+="<div class=\'paytableRewardNumber\'><div '
             'class=\'number_"+r+"\'></div></div>",a+="<div '
             'class=\'paytableRewardValue\'>"+this.getSymbolPrizeNumbers(o.formatPrize(n*r,!0))+"</div>",a+="</div>"}return '
             'a},a.getSymbolPrizeNumbers=function(t){for(var '
             'e,i="",n=t.toString(),o=0;o<n.length;o++)e=n.charAt(o),i+="<div class=\'windowNumber '
             'paytable_number_"+(e=a.SYMBOL_ALIAS_MAP[e]||e)+"\'></div>";return '
             'i},a.getTextInYellow=function(e){return"<div class=\'textContainer\'>"+t.get(e,"<span '
             'class=\'yellowText\'>","</span>")+"</div>"},a.getTextInWhiteAndYellow=function(e){return"<div '
             'class=\'textContainer\'>"+t.get(e,"<span class=\'whiteText\'>","</span>","<span '
             'class=\'yellowText\'>","</span>")+"</div>"},a.getPageImage=function(t){return"<div class=\'pageImage '
             '"+t+"\'></div>"},a.getPageImages=function(t,e){for(var i="<div class=\'pageImagesContainer '
             '"+(e=e||"")+"\'>",n=0;n<t.length;n++)i+=this.getPageImage(t[n]);return '
             'i+"</div>"},a.getMobileSuffix=function(){return n.showMobileUI&&!n.isTablet?"_mobile":""},a',
 'display': 'function s(){t.apply(this,arguments)}return e.extend(s,t),s.prototype.formatTotalBet=function(){return '
            'this.showCurrency?i.format(n.totalBet):a.coinsPerBet},s.prototype.isCurrencyWinSupported=function(){return '
            'o.isCurrencyWinSupported()&&this.showCurrency},s.prototype.formatPrize=function(e){return '
            't.prototype.formatPrize.call(this,e).toString()},s',
 'base_display': 'function '
                 'h(){t.call(this),this.property("showCurrency"),this.property("displayedTotalBet"),this.on("showCurrency/changed",function(){s.add(s.SHOW_CURRENCY,this.showCurrency)}.bind(this))}return '
                 'e.extend(h,t),h.prototype.init=function(){this.showCurrency=!a.isRewatch()},h.prototype.toggle=function(){a.isRewatch()||a.hasCurrencyCoinsOption()&&(this.showCurrency=!this.showCurrency)},Object.defineProperty(h.prototype,"showCoins",{get:function(){return!this.showCurrency},set:function(t){this.showCurrency=!t}}),h.prototype.formatTotalBet=function(){return '
                 'this.showCurrency?r.format(i.totalBet):o.lines},h.prototype.formatMoney=function(t,e){return '
                 'this.showCurrency?this.getCashBalance(t):this.getCoinsBalance(t,e)},h.prototype.getAmountInCoins=function(t){if(a.isRewatch())return '
                 'Math.round(t);var e=Number(Math.round(t/n.bet+"e2")+"e-2");return '
                 'Math.round(e)},h.prototype.getCashBalance=function(t,e){return '
                 'r.format(Math.max(0,t),e)},h.prototype.getCoinsBalance=function(t,e){return '
                 'e?Math.max(0,this.getAmountInCoins(t)):r.formatNumber(Math.max(0,this.getAmountInCoins(t)))},h.prototype.formatPrize=function(t){return '
                 'a.isCurrencyWinSupported()?this.formatMoney(t*n.bet):t},h.prototype.showCurrencyInBetSelector=function(){return '
                 'this.onlyCashBets()||this.showCurrency},h.prototype.onlyCashBets=function(){return!1},h',
 'bet': 'function '
        'a(){t.apply(this,arguments),o.off("lines/changed",this.updateTotalBet),i.on("coinsPerBet/changed",this.updateTotalBet)}return '
        'e.extend(a,t),a.prototype.updateTotalBet=function(){this.totalBet=Number(i.bet)*i.coinsPerBet},a.prototype.setTotalBet=function(t){n.add(n.SET_TOTAL_BET),this.totalBet=t,i.bet=Number((Number(t)/i.coinsPerBet).toPrecision(3))},a.prototype.setMinTotalBet=function(t){for(var '
        'e=0;e<i.availableBets.length;e++){var '
        'o=i.availableBets[e];if(o*i.coinsPerBet>=t){n.add(n.SET_MIN_TOTAL_BET),i.bet=o;break}}},a.prototype.getCoinBet=function(){return '
        'i.coinsPerBet},a',
 'coin': 'function i(){t.apply(this,arguments),this.property("coinsPerBet")}return '
         'e.extend(i,t),i.prototype.parseBetCost=function(t){this.coinsPerBet=t[0]},i',
 'command': 'function n(){e.call(this),this.PLAY_COMMAND={CMD:"",COINS_PER_BET:0}}return '
            't.extend(n,e),n.prototype.parseSpinCmd=function(t){this.PLAY_COMMAND.COINS_PER_BET=t[0]},n.prototype.getTimeToStopMachine=function(){if(this.shouldUsePreCalculatedStopTimes())return '
            'this.getStopTime()-this.getTimeFromStart();var '
            't=this.getStopTimeForColumn(i.getColumns()-1),e=this.columnStopTimes.reduce(function(t,e){return '
            't+e});return Math.max(0,t-e)},n',
 'request': 'function n(){e.apply(this,arguments)}return t.extend(n,e),n.prototype.getParams=function(){var '
            't=e.prototype.getParams.call(this);return '
            't.cmd=i.PLAY_COMMAND.CMD,t.coins=i.PLAY_COMMAND.COINS_PER_BET,t},n',
 'paid_request': 'function n(){t.apply(this,arguments)}return e.extend(n,t),n.prototype.getParams=function(){var '
                 'e=t.prototype.getParams.call(this);return e.coins=i.coinsPerBet,e},n',
 'base_paid_request': 'function s(){e.apply(this,arguments)}return t.extend(s,e),s.prototype.getParams=function(){var '
                      't=e.prototype.getParams.call(this);return '
                      't.amount=n.totalBet,t.lines=o.getSelectedLinesAsString(),t.coin=i.bet,t},s.prototype.getRequestMethod=function(){return '
                      'r.spin},s',
 'avalanche': 'function '
              'o(){t.bindAll(this),this._step=0,this._avalanches=[],this._winningSymbol=null,this._irrelevantFeatures=[n.CANNON_BLAST]}return '
              'o.prototype.parseNextSmallSpin=function(t){this._avalanches=this._parseAvalanches(t.response.clientData.listAvalanche),this._winningSymbol=t.response.clientData.winningSymbol},o.prototype.hasAvalanches=function(){return '
              'this._avalanches.length>0},o.prototype.getAvalanchesCount=function(){return '
              'this._avalanches.length},o.prototype.getAvalanche=function(t){return '
              't=t||this._step,this._avalanches[t]},o.prototype.getNextAvalanche=function(){return '
              'this._avalanches[this._step+1]},o.prototype.getLastAvalanche=function(){return '
              'this._avalanches[this._avalanches.length-1]},o.prototype.setStep=function(t){this._step=t},o.prototype.getWinningSymbol=function(){return '
              'this._winningSymbol},o.prototype.hasMutinyInAvalanches=function(){return '
              'this._avalanches.find(function(t){return '
              't.features[n.MUTINY]})},o.prototype.hasTsunamiInAvalanches=function(){return '
              'this._avalanches.find(function(t){return '
              't.features[n.TSUNAMI]})},o.prototype.hasScattersInAvalanches=function(){return!!this._avalanches.find(function(t){return '
              't.collectedScatters.after>0})},o.prototype.getStep=function(){return '
              'this._step},o.prototype.clear=function(){this._step=0,this._avalanches=[],this._winningSymbol=null},o.prototype._parseAvalanches=function(t){var '
              'e=this._filterRelevantFeatures(t);return '
              'this._groupFeatures(e).map(i.parse)},o.prototype._filterRelevantFeatures=function(t){return '
              't.filter(function(t){return!e.contains(this._irrelevantFeatures,t.type)},this)},o.prototype._groupFeatures=function(t){for(var '
              'e=[],i=0,o=0;o<t.length;o++){var '
              'a=t[o],s=t[o+1];e[i]=e[i]||[],e[i].push(a),(a.type===n.CASCADE&&s&&s.type!==n.TSUNAMI||a.type===n.TSUNAMI)&&i++}return '
              'e},o',
 'parser': 'function i(){}return '
           'i.parse=function(n){return{collectedScatters:i._parseCollectedScatters(n),totalMultiplier:i._parseMultiplier(n),features:new '
           'e(t.CASCADE,i._parseCascadeFeature(n),t.CLUSTER_MUTATION,i._parseClusterFeature(n),t.MUTINY,i._parseMutinyFeature(n),t.TSUNAMI,i._parseTsunamiFeature(n))}},i._parseCollectedScatters=function(t){return{before:t[0].collectedScattersBefore,after:t[t.length-1].collectedScattersAfter}},i._parseMultiplier=function(e){var '
           'i=e.find(function(e){return e.type===t.CASCADE}),n=e.find(function(e){return '
           'e.type===t.TSUNAMI});return{before:e[0].multiplierBefore,after:n?n.multiplierAfter:i.multiplierAfter}},i._parseCascadeFeature=function(e){var '
           'i=e.find(function(e){return e.type===t.CASCADE});return '
           'i?{initialBoard:i.initialIntermediateBoard,cascadeBoard:i.cascadeIntermediateBoard,finalBoard:i.finalIntermediateBoard,shifts:i.shifts,newSymbols:i.newIcons,multiplier:{before:i.multiplierBefore,after:i.multiplierAfter}}:{}},i._parseClusterFeature=function(e){var '
           'i=e.find(function(e){return e.type===t.CLUSTER_MUTATION});return '
           'i?{clusters:i.clusters}:null},i._parseMutinyFeature=function(e){var i=e.find(function(e){return '
           'e.type===t.MUTINY});return '
           'i?{mutinyPositions:i.mutinyPositions,initialBoard:i.initialIntermediateBoard,finalBoard:i.finalIntermediateBoard}:null},i._parseTsunamiFeature=function(e){var '
           'i=e.find(function(e){return e.type===t.TSUNAMI});return '
           'i?{finalBoard:i.finalIntermediateBoard,cascadeBoard:i.cascadeIntermediateBoard,multiplier:{before:i.multiplierBefore,after:i.multiplierAfter}}:null},i',
 'cascade': 'function i(){}return i.prototype.getWinSymbols=function(){return '
            't.getAvalanche().features[e.CASCADE].shifts.map(function(t){return '
            't.origin})},i.prototype.getShiftSymbols=function(){return '
            't.getAvalanche().features[e.CASCADE].shifts.filter(function(t){return '
            't.origin.column===t.target.column&&t.origin.row!==t.target.row}).sort(function(t,e){return '
            't.origin.row<e.origin.row?1:-1})},i.prototype.getNewSymbols=function(){var '
            'i=t.getAvalanche().features[e.CASCADE],n=i.newSymbols,o=i.finalBoard;return n.sort(function(t,e){return '
            't.column>e.column?1:-1}),n.map(function(t){var '
            'e=t.column,i=t.row;return{column:e,row:i,type:o[e][i]}})},i.prototype.getEmptySymbols=function(){for(var '
            'i=t.getAvalanche().features[e.CASCADE].initialBoard,n=[],o=0;o<i.length;o++)for(var '
            'a=i[o],s=0;s<a.length;s++)"EMPTY"===i[o][s]&&n.push({column:o,row:s});return n.sort(function(t,e){return '
            't.column>e.column?1:-1})},i',
 'mutiny': 'function a(){}return a.prototype.hasMutiny=function(){return '
           't.getAvalanchesCount()&&!!t.getAvalanche().features[e.MUTINY]},a.prototype.getMutinyPositions=function(){return '
           't.getAvalanche().features[e.MUTINY].mutinyPositions},a.prototype.getMutinyCenter=function(){var '
           't=this.getMutinyPositions();return '
           't.sort(this._sortMutinyPositions),{column:t[4].column,row:t[4].row}},a.prototype.getFinalBoard=function(){return '
           't.getAvalanche().features[e.MUTINY].finalBoard},a.prototype.hasCascadeMutiny=function(){var '
           'i=t.getNextAvalanche();return i&&!!i.features[e.MUTINY]},a.prototype.getCascadeMutinyCenter=function(){var '
           't=this.getCascadeMutinyPositions();return '
           't.sort(this._sortMutinyPositions),{column:t[4].column,row:t[4].row}},a.prototype.getCascadeMutinyPositions=function(){return '
           't.getNextAvalanche().features[e.MUTINY].mutinyPositions},a.prototype.getMutinySymbolType=function(){return '
           'i.MUTINY+"_"+this.getSelectedHighSymbol()},a.prototype.getCascadeMutinySymbolType=function(){return '
           'i.MUTINY+"_"+n.winningSymbolType},a.prototype.getMutinyFreeSpinsSymbolType=function(){return '
           'i.MUTINY+"_"+o.freeSpinsPrevalentSymbol},a.prototype.getSelectedHighSymbol=function(){var '
           't=this.getFinalBoard(),e=this.getMutinyCenter();return '
           't[e.column][e.row]},a.prototype._sortMutinyPositions=function(t,e){return '
           't.column-e.column||t.row-e.row},a',
 'mutiny_action': 'function h(){t.bindAll(this),e.on(i.MUTINY_PHASE.START,this._processPhase)}return '
                  'h.prototype._processPhase=function(){o.hasMutiny()?this._processMutinyFeature():this._endPhase()},h.prototype._processMutinyFeature=function(){var '
                  't=o.getMutinyCenter(),e=this._getMytinySymbolType(),i=s.machine.mutinyPresentation,n=a.serial();n.add(a.syncCall(i.hideMutinySymbol,[t])),this._isHighSymbolExist()?n.add(a.syncCall(i.showColossalSymbolStatic,[t,e],i)):n.add(new '
                  'r(t,e)),n.add(a.syncCall(this._rearrangeBoard)),n.add(a.delay(.55)),n.add(a.parallel([a.asyncCall(this._showUpdatedSymbols),a.asyncCall(i.hideColossalSymbol)])),n.run(this._endPhase)},h.prototype._isHighSymbolExist=function(){return '
                  'n.getStep()||l.isDuringFreeSpins},h.prototype._getMytinySymbolType=function(){return '
                  'l.isDuringFreeSpins?o.getMutinyFreeSpinsSymbolType():o.getMutinySymbolType()},h.prototype._rearrangeBoard=function(){var '
                  't=o.getMutinyPositions(),e=o.getSelectedHighSymbol();s.machine.mutinyPresentation.changeMutinySymbolsType(t,e),s.symbolsContainer.shuffleSymbolsLayerOrder()},h.prototype._showUpdatedSymbols=function(t){var '
                  'e=o.getMutinyPositions();s.machine.mutinyPresentation.showReplacedSymbols(t,e)},h.prototype._endPhase=function(){s.machine.mutinyPresentation.clear(),e.emit(i.MUTINY_PHASE.END)},h',
 'mutiny_render': 'function '
                  'r(){PIXI.Container.call(this),e.bindAll(this),this._colossalMutinyAnimation=null,this._colossalMutinyStatic=null}return '
                  't.extend(r,PIXI.Container),r.ANIMATIONS_SOUNDS=new '
                  's(a.MUTINY_HIGH_1,"red_pirate_2",a.MUTINY_HIGH_2,"purple_pirate_2",a.MUTINY_HIGH_3,"green_pirate_2",a.MUTINY_HIGH_4,"blue_pirate_2"),r.prototype.showColossalSymbolAnimation=function(t,e,i){this._colossalMutinyAnimation=this._createColossalMutinyAnimation(e,i),this._colossalMutinyAnimation.showWinner(t)},r.prototype.showColossalSymbolStatic=function(t,e){this._colossalMutinyStatic=this._createColossalMutinySymbol(t,e)},r.prototype.hideColossalSymbol=function(t){var '
                  'e=this._colossalMutinyStatic||this._colossalMutinyAnimation;TweenMax.to(e,.35,{alpha:0,onComplete:t})},r.prototype.skipColossalSymbolAnimation=function(){this._colossalMutinyAnimation&&this._colossalMutinyAnimation.skip()},r.prototype.changeMutinySymbolsType=function(t,e){return '
                  't.forEach(function(t){var '
                  'n=i.symbolsContainer.getSymbol(t.column,t.row);n.setType(e),n.alpha=0,n.showStaticImage()},this)},r.prototype.showReplacedSymbols=function(t,e){var '
                  'n=e.map(function(t){return '
                  'i.symbolsContainer.getSymbol(t.column,t.row)});TweenMax.to(n,.35,{alpha:1,onComplete:t})},r.prototype.hideMutinySymbol=function(t){i.symbolsContainer.getSymbol(t.column,t.row).hideStaticImage()},r.prototype.clear=function(){this.removeChildren(),this._colossalMutinyAnimation=null,this._colossalMutinyStatic=null},r.prototype._createColossalMutinyAnimation=function(t,e){var '
                  'a=i.symbolsContainer.getSymbol(t.column,t.row),s=new n(e);return '
                  's.position.set(a.position.x,a.position.y),s.once(n.WHITE_SOLID_END_EVENT,function(){o.play("sounds/"+r.ANIMATIONS_SOUNDS[e]+".mp3")}),this.addChild(s)},r.prototype._createColossalMutinySymbol=function(t,e){var '
                  'n=i.symbolsContainer.getSymbol(t.column,t.row),o=PIXI.Sprite.fromFrame("images/symbols/"+e.toLowerCase()+".png");return '
                  'o.anchor.set(.5),o.position.set(n.position.x,n.position.y),this.addChild(o)},r',
 'win': 'function '
        'n(){t.call(this),this.winningSymbolType="",this._finalPrize={coins:0,cash:""},this._preMultipliedPrize={coins:0,cash:""},this._freeSpinsWin={coins:0,cash:0}}return '
        'e.extend(n,t),n.prototype.parseNextSmallSpinWin=function(t){this.winningSymbolType=t.response.clientData.winningIcon,this._finalPrize.coins=this.wonCoins,this._finalPrize.cash=this.wonMoney;var '
        'e=t.response.clientData.wtw[0];this._preMultipliedPrize.coins=e?e[4]:0,this._preMultipliedPrize.cash=e?e[5]:"",i.isDuringFreeSpins&&(this._freeSpinsWin.coins+=t.response.clientData.wonCoins,this._freeSpinsWin.cash+=parseFloat(t.response.clientData.wonMoney))},n.prototype.hasAnyWin=function(){return '
        'this.getTotalWin()>0},n.prototype.getFinalPrize=function(){return '
        'this._finalPrize},n.prototype.getPreMultipliedPrize=function(){return '
        'this._preMultipliedPrize},n.prototype.getAccumulatedFreeSpinsWinInCash=function(){return '
        'this._freeSpinsWin.cash},n.prototype.getAccumulatedFreeSpinsWinInCoins=function(){return '
        'this._freeSpinsWin.coins},n.prototype.hasBaseGameWins=function(){return '
        'this.getAccumulatedWinInCoins()-this.getAccumulatedFreeSpinsWinInCoins()>0},n.prototype.clear=function(){t.prototype.clear.call(this),this._finalPrize={coins:0,cash:""},this._preMultipliedPrize={coins:0,cash:""},this._freeSpinsWin={coins:0,cash:0}},n.prototype.getDifferentiatedWinPopupTime=function(){return.5},n',
 'multiplier': 'function n(){this._multiplierValues=[],this._globalMultiplier={before:0,after:0}}return '
               'n.prototype.parseMultiplierValues=function(t){this._multiplierValues=[t[1],t[2],t[3],t[4],t[5]]},n.prototype.parseNextSmallSpin=function(t){this._globalMultiplier.before=t.response.clientData.globalMultiBefore,this._globalMultiplier.after=t.response.clientData.globalMultiAfter},n.prototype.getMultiplierValues=function(){return '
               'this._multiplierValues},n.prototype.getTsunamiMultiplier=function(){return '
               't.getAvalanche().features[i.TSUNAMI].multiplier.after},n.prototype.getCascadeMultiplier=function(){return '
               't.getAvalanche().features[i.CASCADE].multiplier.after},n.prototype.getLocalMultiplier=function(){return '
               't.getAvalanche().totalMultiplier.after},n.prototype.getFinalMultiplier=function(){return '
               'e.isDuringFreeSpins?this.getGlobalMultiplier():this.getLocalMultiplier()},n.prototype.getGlobalMultiplier=function(){return '
               'this._globalMultiplier.after},n',
 'minimum': 'function n(){this.MIN_CLUSTER_SIZE=6}return '
            'n.prototype.parseMinClusterSize=function(t){this.MIN_CLUSTER_SIZE=t||this.MIN_CLUSTER_SIZE},n.prototype.hasClustersToMutate=function(){return!!t.getAvalanche().features[i.CLUSTER_MUTATION]},n.prototype.getClustersToMutate=function(){var '
            'n=[],o=t.getAvalanche().features[i.CLUSTER_MUTATION].clusters;for(var a in '
            'o)o.hasOwnProperty(a)&&a!==e.winningSymbolType&&n.push(o[a]);return n},n',
 'free': 'function i(){e.call(this),this.SCATTERS_COUNT_TO_TRIGGER=3,this.freeSpinsPrevalentSymbol=null}return '
         't.extend(i,e),i.prototype.parseNextSmallSpin=function(t){this.freeSpinsAwarded=t.eventdata.response.clientData.freeSpinsAwarded||0,this.freeSpinsLeft=t.eventdata.response.clientData.freeSpins||0,this.firstSpin=this.freeSpinsAwarded>0&&1===t.step,this.freeSpinsPrevalentSymbol=t.eventdata.response.clientData.freeSpinsPrevalentSymbol||null},i.prototype.isFirstFreeSpin=function(){return '
         'this.firstSpin},i.prototype.isLastFreeSpin=function(){return '
         'this.isDuringFreeSpins&&0===this.freeSpinsLeft},i',
 'animation': 'function '
              '_(t,i){PIXI.Container.apply(this,arguments),e.bindAll(this),this._preMultipliedPrize=t,this._finalPrize=i,this._animation=null,this.counter=this._createCounter(),this.multiplier=null}return '
              't.extend(_,PIXI.Container),_.prototype.start=function(t){u.getFinalMultiplier()>1?(this.multiplier=this._createMultiplier(u.getLocalMultiplier()),this._animation=new '
              'h(this,this._getWinningSymbols(t),this._preMultipliedPrize,this._finalPrize)):this._animation=new '
              'l(this,this._getWinningSymbols(t),this._preMultipliedPrize),this._animation.addCallback(this._onCountUpComplete,"countupComplete"),this._animation.eventCallback("onComplete",this._complete)},_.prototype.skip=function(){this._animation.skip()},_.prototype._onCountUpComplete=function(){this.emit("countupFinished"),this._playWinSound()},_.prototype._complete=function(){this.counter.clear(),this.emit("complete")},_.prototype._playWinSound=function(){switch(c.getWinType()){case '
              'c.WIN_TYPE.SMALL:o.play("sounds/win_small.mp3");break;case '
              'c.WIN_TYPE.MEDIUM:o.play("sounds/win_medium.mp3");break;case '
              'c.WIN_TYPE.LARGE:o.play("sounds/win_large.mp3")}},_.prototype._createCounter=function(){return '
              'this.addChild(new a)},_.prototype._createMultiplier=function(t){var e=new '
              's("x",t),i=this.toLocal(p.machine.multiplierPanel.getItemGlobalPosition(t));return '
              'e.alpha=0,e.position.copy(i),this.addChild(e.particle),this.addChild(e)},_.prototype._getWinningSymbols=function(t){for(var '
              'e=[],i=0;i<d.getColumns();i++)for(var n=0;n<d.getRows();n++){var '
              'o=p.symbolsContainer.getSymbol(i,n);o.type===t&&e.push(o)}return '
              'e.sort(this._sortInBottomToTopLeftToRightZigzag)},_.prototype._sortInBottomToTopLeftToRightZigzag=function(t,e){return '
              't.row===e.row?n.isEven(t.row)?t.column-e.column:e.column-t.column:e.row-t.row},_',
 'formatter': 'return function(){function e(t){_classCallCheck(this,e),this._rows=t}return '
              '_createClass(e,[{key:"formatBet",value:function(e,n,i){if(e.betdata&&"C"===e.betdata.cmd)return e;var '
              'o=t.clone(e);return '
              'o.eventdata.response={coinWin:n.accC,cashWin:n.accWa},o.eventdata.response.clientData=n,o.eventdata.response.clientData.initialBoard=n.reels,o.eventdata.response.clientData.finalBoard=n.finalBoard||n.reels,o.eventdata.response.clientData.win=this.convertWTWToWinObject(n,i),o.eventdata.response.clientData.reels={reelStopPositions:n.rpos,reelSetName:n.reelSet},delete '
              'n.freeSpinsLeft,n.hasOwnProperty("freeSpins")&&(o.eventdata.response.clientData.freeSpinsLeft=n.freeSpins),o}},{key:"formatBetFromLegacyImplementedSlot",value:function(e,n,i){if(e.betdata&&"C"===e.betdata.cmd)return '
              'e;var o=t.clone(e);return '
              'o.eventdata.response.coinWin=n.accC,o.eventdata.response.cashWin=n.accWa,o.eventdata.response.clientData.initialBoard=n.reels,o.eventdata.response.clientData.hasOwnProperty("finalBoard")||(o.eventdata.response.clientData.finalBoard=n.reels),o.eventdata.response.clientData.win=this.convertWTWToWinObject(n,i),o.eventdata.response.clientData.reels={reelStopPositions:n.rpos,reelSetName:n.reelSet},delete '
              'n.freeSpinsLeft,n.hasOwnProperty("freeSpins")&&(o.eventdata.response.clientData.freeSpinsLeft=n.freeSpins),o}},{key:"convertWTWToWinObject",value:function(t,e){return{prizes:this.convertWTWToPrizes(t.wtw||[],e),wonCoins:t.wonCoins,wonCash:t.wonCash||t.wonMoney,accumulatedWonCoins:t.accC,accumulatedWonCash:parseFloat(t.accWa)}}},{key:"convertWTWToPrizes",value:function(t,e){var '
              'n=this;return '
              't.map(function(t){return{cash:t[3]?parseFloat(t[3]):t[1]*e,coins:t[1],payline:t[0]-1,positions:n.convertWTWPatternToPositions(t[2]),symbols:t[2]}})}},{key:"convertWTWPatternToPositions",value:function(t){var '
              'e=this,n=[];return t.split("").map(function(t,i){if("1"===t){var '
              'o=Math.floor(i/e._rows),r=i-o*e._rows;n.push({x:o,y:r})}}),n}}]),e}()',
 'facade': 'return function(){function i(o,r,s){_classCallCheck(this,i),this._loadFormatter=new '
           't(o,r,s),this._spinFormatter=new e(o,r,s),this._collectFormatter=new n(o,r)}return '
           '_createClass(i,[{key:"getFormattedLoadResponseData",value:function(t){return '
           'this._loadFormatter.getFormattedData(t)}},{key:"getFormattedSpinResponseData",value:function(t){return '
           'this._spinFormatter.getFormattedData(t)}},{key:"getFormattedCollectResponseData",value:function(t){return '
           'this._collectFormatter.getFormattedData(t)}}]),i}()',
 'spin_formatter': 'return function(i){function o(t,e,i){var r;return '
                   '_classCallCheck(this,o),(r=_callSuper(this,o,[t,e]))._betFormatter=new '
                   'n(i),r.formatFromLegacySlot=r.formatFromLegacySlot.bind(_assertThisInitialized(r)),r.formatFromLegacyImplementedSlot=r.formatFromLegacyImplementedSlot.bind(_assertThisInitialized(r)),r}return '
                   '_inherits(o,t),_createClass(o,[{key:"formatFromLegacySlot",value:function(t){for(var '
                   'n=e.clone(t),i=Number(n.wager.bets[0].betdata.coin),o=0;o<n.wager.bets.length;o++){var '
                   'r=n.wager.bets[o];n.wager.bets[o]=this._betFormatter.formatBet(r,r.eventdata,i)}return '
                   'n}},{key:"formatFromLegacyImplementedSlot",value:function(t){for(var '
                   'n=e.clone(t),i=Number(n.wager.bets[0].betdata.coin),o=0;o<n.wager.bets.length;o++){var '
                   'r=n.wager.bets[o];n.wager.bets[o]=this._betFormatter.formatBetFromLegacyImplementedSlot(r,r.eventdata.response.clientData,i)}return '
                   'n}}]),o}()',
 'load_formatter': 'return function(i){function o(t,e,i){var r;return '
                   '_classCallCheck(this,o),(r=_callSuper(this,o,[t,e]))._betFormatter=new '
                   'n(i),r.formatFromLegacySlot=r.formatFromLegacySlot.bind(_assertThisInitialized(r)),r.formatFromLegacyImplementedSlot=r.formatFromLegacyImplementedSlot.bind(_assertThisInitialized(r)),r}return '
                   '_inherits(o,t),_createClass(o,[{key:"formatFromLegacySlot",value:function(t){var '
                   'n=e.clone(t);n.settings.slotConfig.Config=e.clone(n.settings.slotConfig);var '
                   'i=n.settings.slotConfig.Prizes?n.settings.slotConfig.Prizes:[];if(n.settings.slotConfig.Config.symbols=this._formatSymbolsData(n.settings.slotConfig.Icons,n.settings.slotConfig.IconTypes,i),n.settings.slotConfig.Config.paylines=n.settings.slotConfig.Paylines,n.settings.slotConfig.Config.reelSets=t.settings.slotConfig,n.wagers.data.length>0)for(var '
                   'o=Number(n.wagers.data[0].bets[0].betdata.coin),r=0;r<n.wagers.data[0].bets.length;r++){var '
                   's=n.wagers.data[0].bets[r];n.wagers.data[0].bets[r]=this._betFormatter.formatBet(s,s.eventdata,o)}return '
                   'n.settings.slotConfig.Config.Config=e.clone(n.settings.slotConfig.Config),n}},{key:"formatFromLegacyImplementedSlot",value:function(t){var '
                   'n=e.clone(t);n.settings.slotConfig.Config=e.clone(n.settings.slotConfig);var '
                   'i=n.settings.slotConfig.Config.Config,o=i.Prizes?i.Prizes:[];if(n.settings.slotConfig.Config.symbols=this._formatSymbolsData(i.Icons,i.IconTypes,o),n.settings.slotConfig.Config.paylines=i.Paylines,n.settings.slotConfig.Config.reelSets=i,n.wagers.data.length>0)for(var '
                   'r=Number(n.wagers.data[0].bets[0].betdata.coin),s=0;s<n.wagers.data[0].bets.length;s++){var '
                   'a=n.wagers.data[0].bets[s];a.eventdata.response&&(n.wagers.data[0].bets[s]=this._betFormatter.formatBetFromLegacyImplementedSlot(a,a.eventdata.response.clientData,r))}return '
                   'n}},{key:"_formatSymbolsData",value:function(t,e,n){for(var '
                   'i={},o=0;o<t.length;o++)i[t[o]]={type:e[o],prizes:n?n[o]:[]};for(var r=0;r<n.length;r++){var '
                   's=n[r][0];n[r].shift(),i[s]&&(i[s].prizes=n[r])}return i}}]),o}()',
 'base_win': 'function '
             'a(){this.ALL_LINES_TIME=1.2,this.DELAY=.1,this.SINGLE_LINE_TIME=1.5,this.CLEAR_IMMEDIATELY_TIME=.2,this.wonCoins=0,this.accCoins=0,this.wonMoney=0,this.clear()}return '
             'a.prototype.clear=function(){this.wins=[],this.specialWins=[]},a.prototype.parseNextSmallSpin=function(e,n){e&&(this.winPositions=n,this.wins=e.prizes.filter(function(e){return '
             't.isValidPayline(e.payline)}),this.specialWins=e.prizes.filter(function(e){return!t.isValidPayline(e.payline)}),this.totalWin=e.accumulatedWonCash||e.accumulatedWonCoins,this.accCoins=e.accumulatedWonCoins||0,this.wonCoins=e.wonCoins||0,this.wonMoney=e.wonCash||0,this.currentLineToHighlight=0)},a.prototype.parseSpinEnd=function(){var '
             't=i.getCurrentBet(),e=t.wonamount||0,n=t.betdata?t.betdata.coin:1;this.wonAmount=Math.round(e/n)},a.prototype.sortWins=function(){this.wins=this.wins.sort(function(t,e){return '
             't.payline-e.payline})},a.prototype.compactWins=function(){for(var t=this.wins,e=0;e<t.length;e++)for(var '
             'n=0;n<t.length;n++)if(t[n].lines=t[n].lines||[t[n].payline],e!==n&&JSON.stringify(t[e].positions)===JSON.stringify(t[n].positions)){t[n].payline=Math.min(t[e].payline,t[n].payline),t[n].lines.push(t[e].payline),t[n].cash+=t[e].cash,t[n].coins+=t[e].coins,t.splice(e,1),e--;break}this.sortWins()},a.prototype.getCurrentLineToHighlight=function(){return '
             'this.wins[this.currentLineToHighlight]},a.prototype.participateInCurrentWin=function(t,e){return '
             'this.participateInWin(t,e,this.currentLineToHighlight)},a.prototype.participateInWin=function(t,e,n){return '
             'this.wins[n].positions.filter(function(n){return '
             'n.x===t&&n.y===e}).length>0},a.prototype.participateInAnyWin=function(t,e){for(var '
             'n=!1,i=0;i<this.wins.length&&!n;i++)n=this.participateInWin(t,e,i);return '
             'n},a.prototype.participateInAnyWinOnColumn=function(t){for(var '
             'e=n.getRows(),i=0;i<e;i++)if(this.participateInAnyWin(t,i))return!0;return!1},a.prototype.participateInNextWins=function(t,e,n){for(var '
             'i=!1,o=n+1;o<this.wins.length&&!i;o++)i=this.participateInWin(t,e,o);return '
             'i},a.prototype.participateInPreviousWins=function(t,e,n){for(var '
             'i=0;i<n;i++)if(this.participateInWin(t,e,i))return!0;return!1},a.prototype.getAccumulatedWinInCoins=function(){return '
             'Math.round(this.totalWin/e.bet)},a.prototype.getAccumulatedWin=function(){return '
             'this.totalWin},a.prototype.getWonAmount=function(){return '
             'this.wonAmount},a.prototype.getGrandTotal=function(){return '
             'i.getCurrentClientData().grandTotal},a.prototype.getTotalSpecialWin=function(){for(var '
             't=0,e=0;e<this.specialWins.length;e++)t+=this.specialWins[e].coins;return '
             't},a.prototype.getTotalLineWin=function(){for(var '
             't=0,e=0;e<this.wins.length;e++)t+=this.wins[e].coins;return '
             't},a.prototype.getTotalLineWinInMoney=function(){for(var '
             't=0,e=0;e<this.wins.length;e++)t+=this.wins[e].cash;return '
             't},a.prototype.getNumberOfWinningLines=function(){return '
             'this.wins.length},a.prototype.hasWinningLines=function(){return '
             'this.getNumberOfWinningLines()>0},a.prototype.getAllLinesToHighlight=function(){return '
             'this.wins},a.prototype.nextLine=function(){this.currentLineToHighlight++,this.currentLineToHighlight>=this.wins.length&&(this.currentLineToHighlight=0)},a.prototype.getWinningSymbolsInWin=function(t){return '
             'this.wins[t].positions},a.prototype.getWinPaylines=function(){return this.wins.map(function(t){return '
             't.payline})},a.prototype.getSpinPrize=function(){return '
             'this.showAccumulatedWin()?this.getAccumulatedWinInCoins():this.getTotalWin()},a.prototype.getSpinPrizeInMoney=function(){return '
             'this.showAccumulatedWin()?this.totalWin:this.wonMoney},a.prototype.showAccumulatedWin=function(){return '
             'r.SHOW_ACCUMULATED_WIN},a.prototype.getLastWin=function(){return '
             'o.isCurrencyWinSupported()?this.getSpinPrizeInMoney():this.getSpinPrize()*e.bet},a.prototype.getTotalPrize=function(){if(o.isRewatch())return '
             'parseInt(i.getLastBet().woncoins);for(var t=0,e=0;e<i.bets.length;e++){var '
             'n=i.bets[e].prizes||[];n=n.filter(function(t){return"BOOST"!==t.type});for(var '
             'r=0;r<n.length;r++)t+=parseFloat(n[r].wonamount||n[r].woncoins)}return '
             't},a.prototype.getTotalWin=function(){return '
             'this.getTotalLineWin()+this.getTotalSpecialWin()},a.prototype.isSmallWin=function(){return!0},a.prototype.getBigWinThreshold=function(){return '
             '200},a.prototype.getDifferentiatedWinPopupTime=function(){return '
             '1.5},a.prototype.shouldShowDifferentiatedWin=function(){return '
             'o.isWinDifferentiated&&this.getSpinPrize()<=s.getCoinBet()&&this.getSpinPrize()>0},a',
 'base_config': 'function b(){t.bindAll(this)}return b.prototype.parse=function(){var '
                't=this.getData();this.parseAuthentication(t);var '
                'e=t.settings;this.parseSlotConfig(e.slotConfig.Config),this.parseLines(),this.parseBets(e.organizationConfig),this.parseTranslations(t.translations),i.isReplayMode()&&this.parseReplay(t.wagers),i.isRestore()&&this.parseRestore(t.wagers)},b.prototype.parseAuthentication=function(t){},b.prototype.parseSlotConfig=function(t){this.parseSymbols(t),this.parsePaylines(t),this.parseMachine(t),this.parseSymbolPrizes(t)},b.prototype.parseReplay=function(t){r.parse(t),s.bet=Number(t.data[0].bets[0].betdata.coin)},b.prototype.parseRestore=function(t){if(0!==t.size){var '
                'e=t.data[0].bets,n=e[e.length-1];n.eventdata=n.eventdata||{},t.wager=t.data[0],"Pending"===t.wager.status&&this.restoreBet(n),f.parse(t)}},b.prototype.restoreBet=function(t){var '
                'e=Number(t.betdata.coin);s.availableBets.indexOf(e)>=0&&(s.bet=e)},b.prototype.parseTranslations=function(t){for(var '
                'e in t){var n=t[e];for(var i in n){var '
                'o=i.substring(i.lastIndexOf(":")+1),r=!a.has(o);("game"===e||r)&&a.set(o,n[i])}}},b.prototype.parseSymbols=function(t){for(var '
                'e in t.symbols){var '
                'n=u.clone(t.symbols[e]),i=n.type,o=n.prizes;h.symbols[e]={name:e,type:i,prizes:o?o.sort(function(t,e){return '
                'e-t}):0}}},b.prototype.parsePaylines=function(t){p.paylines=t.paylines,p.paylinesOrientations=t.NormalOri||l.PAYLINES_ORIENTATION},b.prototype.parseMachine=function(t){for(var '
                'e in n.reels){var '
                'i=n.reels[e];d.addReels(i,t.reelSets[i])}d.setReels(n.getDefaultReelsName())},b.prototype.parseSymbolPrizes=function(t){},b.prototype.parseBets=function(t){if(s.availableBets=g.parse(t.Denoms)[i.currency],m.isExternalPrepaid())y.setTotalBet(m.getExternalPrepaidBet()),s.defaultBet=s.bet;else{var '
                'e=g.parse(t.DefaultDenom)[i.currency][0];s.defaultBet=s.availableBets.indexOf(e)>=0?e:s.availableBets[0],s.selectDefault()}},b.prototype.parseLines=function(){c.availableLines=[p.getNumberOfPaylines()],c.lines=p.getNumberOfPaylines()},b.prototype.getData=function(){return '
                'S.getFormattedLoadResponseData(e.getData())},b',
 'flow': 'function l(){t.bindAll(this),i.on(s.SPIN.END,this._processSpinEndFlow,i.PRIORITY_LOW)}return '
         'l.prototype._processSpinEndFlow=function(){var '
         't=e.serial();n.hasCannonBlast()?t.add(this._createFlowPhase(s.CANNON_BLAST_PHASE)):t.add(this._createFlowPhase(s.INITIAL_SCATTERS_COLLECT_PHASE)),o.hasAvalanches()&&(t.add(this._createFlowPhase(s.INITIAL_HIGHLIGHT_PHASE)),t.add(this._createAvalancheFlow())),t.add(this._createFlowPhase(s.FINAL_SCATTERS_COLLECT_PHASE)),t.add(this._createFlowPhase(s.WIN_PRESENTATION_PHASE)),t.add(this._createFlowPhase(s.FS_TRANSITION_PHASE)),t.add(this._clearAvalancheFlow()),t.run(this._dispatchSpinEndFlowComplete)},l.prototype._createAvalancheFlow=function(){for(var '
         't=e.serial(),i=0;i<o.getAvalanchesCount();i++)t.add(e.serial([e.syncCall(o.setStep,[i]),this._createFlowPhase(s.AVALANCHE_SCATTERS_COLLECT_PHASE),this._createFlowPhase(s.MUTINY_PHASE),this._createFlowPhase(s.CLUSTER_MUTATION_PHASE),this._createFlowPhase(s.CASCADE_PHASE),this._createFlowPhase(s.TSUNAMI_PHASE)]));return '
         't},l.prototype._createFlowPhase=function(t){return '
         'e.asyncCall(this._processPhase,[t])},l.prototype._processPhase=function(t,e){i.once(e.END,t),i.emit(e.START)},l.prototype._clearAvalancheFlow=function(){return '
         'e.syncCall(o.clear)},l.prototype._dispatchSpinEndFlowComplete=function(){i.emit(s.SPIN_END_FLOW_COMPLETE),i.emit(r.INITIAL_ANIMATION.CLEAR_ALL_PAYLINES),i.emit(r.INITIAL_ANIMATION.END)},l',
 'flow_phases': 'var '
                'i=t.assign({},e,{SPIN_END_FLOW_COMPLETE:"spin/end:flowComplete",MESSAGE_WINDOW:{OPEN:"messageWindow/open"},CANNON_BLAST_PHASE:{START:"cannonBlastPhase/start",END:"cannonBlastPhase/end"},INITIAL_SCATTERS_COLLECT_PHASE:{START:"initialScattersCollectPhase/start",END:"initialScattersCollectPhase/end"},INITIAL_HIGHLIGHT_PHASE:{START:"initialHighlightPhase/start",END:"initialHighlightPhase/end"},AVALANCHE_SCATTERS_COLLECT_PHASE:{START:"avalancheScattersCollectPhase/start",END:"avalancheScattersCollectPhase/end"},FINAL_SCATTERS_COLLECT_PHASE:{START:"finalScattersCollectPhase/start",END:"finalScattersCollectPhase/end"},CLUSTER_MUTATION_PHASE:{START:"clusterMutationPhase/start",END:"clusterMutationPhase/end"},CASCADE_PHASE:{START:"cascadePhase/start",END:"cascadePhase/end"},WIN_PRESENTATION_PHASE:{START:"winPresentationPhase/start",END:"winPresentationPhase/end"},MUTINY_PHASE:{START:"mutinyPhase/start",END:"mutinyPhase/end"},TSUNAMI_PHASE:{START:"tsunamiPhase/start",END:"tsunamiPhase/end"},FS_TRANSITION_PHASE:{START:"freeSpinsTransitionPhase/start",END:"freeSpinsTransitionPhase/end"},AVALANCHE:{START:"avalanche/start",END:"avalanche/end",SYMBOL_READY:"avalanche/symbolReady",DROP_DOWN_SYMBOLS:"avalanche/dropDownSymbols",SYMBOL_FLYOVER_START:"avalanche/symbolFlyoverStart"}});return '
                'i.FREE_SPINS.OUTRO={STARTED:"freeSpins/outroStarted"},i.BIG_WIN.END="bigWin/end",i',
 'cascade_action': 'function p(){t.bindAll(this),i.on(h.CASCADE_PHASE.START,this._processPhase)}return '
                   'p.prototype._processPhase=function(){var '
                   't=e.serial([e.asyncCall(this._hideOldSymbols),e.asyncCall(this._shiftWinSymbols)]);t.add(e.syncCall(this._shuffleSymbolsOrder)),r.hasCascadeMutiny()&&!l.hasTsunami()?(t.add(e.syncCall(this._changeMutinySymbolOrder)),t.add(e.asyncCall(this._showNewSymbolsWithMutiny))):t.add(e.asyncCall(this._showNewSymbols)),s.getCascadeMultiplier()&&(t.add(e.delay(.2)),t.add(e.syncCall(n.machine.multiplierPanel.activateItem,[s.getCascadeMultiplier()])),t.add(e.delay(.3))),t.run(this._endPhase)},p.prototype._endPhase=function(){i.emit(h.CASCADE_PHASE.END)},p.prototype._hideOldSymbols=function(t){var '
                   'e=o.getEmptySymbols();n.machine.cascadePresentation.hideSymbols(t,e)},p.prototype._shiftWinSymbols=function(t){var '
                   'e=o.getShiftSymbols();n.machine.cascadePresentation.shiftSymbols(t,e)},p.prototype._showNewSymbols=function(t){var '
                   'e=o.getNewSymbols();i.emit(h.AVALANCHE.DROP_DOWN_SYMBOLS),n.machine.cascadePresentation.showSymbols(t,e)},p.prototype._showNewSymbolsWithMutiny=function(t){var '
                   'e=o.getNewSymbols(),a=r.getCascadeMutinyCenter(),s=r.getCascadeMutinySymbolType();i.emit(h.AVALANCHE.DROP_DOWN_SYMBOLS),n.machine.cascadePresentation.showSymbolsWithMutiny(t,e,a,s)},p.prototype._shuffleSymbolsOrder=function(){n.symbolsContainer.shuffleSymbolsLayerOrder()},p.prototype._changeMutinySymbolOrder=function(){var '
                   't=r.getCascadeMutinyCenter(),e=n.symbolsContainer.getSymbol(t.column,t.row);n.symbolsContainer.addChild(e)},p',
 'cannon': 'function '
           'i(){t.bindAll(this),this._isFeatureExist=!1,this._initialBoard=[],this._finalBoard=[],this._shifts=[],this._newSymbols=[]}return '
           'i.prototype.parseNextSmallSpin=function(t){var '
           'e=this._filterFeatureData(t);e?this._parse(e):this.clear()},i.prototype.hasCannonBlast=function(){return '
           'this._isFeatureExist},i.prototype.getShiftSymbols=function(){return this._shifts.filter(function(t){return '
           't.origin.column===t.target.column&&t.origin.row!==t.target.row}).sort(function(t,e){return '
           't.origin.row<e.origin.row?1:-1})},i.prototype.getEmptySymbols=function(){for(var '
           't=[],e=0;e<this._initialBoard.length;e++)for(var '
           'i=this._initialBoard[e],n=0;n<i.length;n++)"EMPTY"===this._initialBoard[e][n]&&t.push({column:e,row:n});return '
           't.sort(function(t,e){return t.column>e.column?1:-1})},i.prototype.getNewSymbols=function(){var '
           't=this._newSymbols,e=this._finalBoard;return t.sort(function(t,e){return '
           't.column>e.column?1:-1}),t.map(function(t){var '
           'i=t.column,n=t.row;return{column:i,row:n,type:e[i][n]}})},i.prototype.clear=function(){this._isFeatureExist=!1,this._initialBoard=[],this._finalBoard=[],this._shifts=[],this._newSymbols=[]},i.prototype._filterFeatureData=function(t){var '
           'i=t.response.clientData.listAvalanche;return i?i.find(function(t){return '
           't.type===e.CANNON_BLAST}):null},i.prototype._parse=function(t){this._initialBoard=t.initialIntermediateBoard,this._finalBoard=t.finalIntermediateBoard,this._shifts=t.shifts,this._newSymbols=t.newIcons,this._isFeatureExist=!0},i'}

_SOURCE_ARGS = {'config': ('t', 'e', 'i', 'n', 'o', 'a', 's', 'r'),
 'symbols': ('t', 'e', 'i'),
 'paytable': ('t', 'e', 'i', 'n', 'o'),
 'display': ('t', 'e', 'i', 'n', 'o', 'a'),
 'base_display': ('t', 'e', 'n', 'i', 'o', 'r', 's', 'a'),
 'bet': ('t', 'e', 'i', 'n', 'o'),
 'coin': ('t', 'e'),
 'command': ('t', 'e', 'i'),
 'request': ('t', 'e', 'i'),
 'paid_request': ('t', 'e', 'i'),
 'base_paid_request': ('t', 'e', 'n', 'i', 'o', 'r'),
 'avalanche': ('t', 'e', 'i', 'n'),
 'parser': ('t', 'e'),
 'cascade': ('t', 'e'),
 'mutiny': ('t', 'e', 'i', 'n', 'o'),
 'mutiny_action': ('t', 'e', 'i', 'n', 'o', 'a', 's', 'r', 'l'),
 'mutiny_render': ('t', 'e', 'i', 'n', 'o', 'a', 's'),
 'win': ('t', 'e', 'i'),
 'multiplier': ('t', 'e', 'i'),
 'minimum': ('t', 'e', 'i'),
 'free': ('t', 'e'),
 'animation': ('t', 'e', 'i', 'n', 'o', 'a', 's', 'r', 'l', 'h', 'p', 'c', 'u', 'd'),
 'formatter': ('t',),
 'facade': ('t', 'e', 'n'),
 'spin_formatter': ('t', 'e', 'n'),
 'load_formatter': ('t', 'e', 'n'),
 'base_win': ('t', 'e', 'n', 'i', 'o', 'r', 's'),
 'base_config': ('t', 'e', 'n', 'i', 'o', 'r', 's', 'a', 'h', 'l', 'u', 'p', 'c', 'd', 'f', 'g', 'y', 'm', 'S'),
 'flow': ('t', 'e', 'i', 'n', 'o', 'a', 's', 'r'),
 'flow_phases': ('t', 'e'),
 'cascade_action': ('t', 'e', 'i', 'n', 'o', 'a', 's', 'r', 'l', 'h'),
 'cannon': ('t', 'e')}

_SOURCE_LINKS = [('config', 's', 'symbols'),
 ('config', 'i', 'coin'),
 ('config', 'n', 'command'),
 ('config', 'o', 'multiplier'),
 ('config', 'a', 'minimum'),
 ('paytable', 'i', 'symbols'),
 ('paytable', 'o', 'display'),
 ('display', 't', 'base_display'),
 ('base_display', 'n', 'coin'),
 ('bet', 'i', 'coin'),
 ('request', 'i', 'command'),
 ('paid_request', 'i', 'coin'),
 ('paid_request', 't', 'base_paid_request'),
 ('base_paid_request', 'i', 'coin'),
 ('base_paid_request', 'n', 'bet'),
 ('avalanche', 'i', 'parser'),
 ('cascade', 't', 'avalanche'),
 ('mutiny', 't', 'avalanche'),
 ('mutiny_action', 'o', 'mutiny'),
 ('multiplier', 't', 'avalanche'),
 ('animation', 'u', 'multiplier'),
 ('facade', 'e', 'spin_formatter'),
 ('facade', 't', 'load_formatter'),
 ('spin_formatter', 'n', 'formatter'),
 ('load_formatter', 'n', 'formatter'),
 ('win', 't', 'base_win'),
 ('config', 't', 'base_config'),
 ('base_paid_request', 'e', 'request'),
 ('flow', 'o', 'avalanche'),
 ('flow', 's', 'flow_phases'),
 ('flow', 'n', 'cannon'),
 ('cascade_action', 'o', 'cascade'),
 ('cascade_action', 'a', 'avalanche'),
 ('cascade_action', 's', 'multiplier'),
 ('cascade_action', 'r', 'mutiny'),
 ('cascade_action', 'h', 'flow_phases'),
 ('mutiny_action', 'i', 'flow_phases')]
