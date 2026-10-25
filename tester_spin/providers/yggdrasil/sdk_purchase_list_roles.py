"""Bind current SDK purchase menus to current server multiplier indices.

The source declares menu membership and both payment bindings. The caller must
resolve the extracted indices against current Config and compare every current
price domain before enabling a quote. No command name is a purchase by itself.
"""
import hashlib
import json
import re

IDENT = r'[A-Za-z_$][\w$]*'
SCOPE = r'[A-Za-z_$][\w.$]*'
COMMAND = re.compile(r'[A-Z][A-Z0-9_]{0,63}')


def methods(source, name):
    pattern = '(' + SCOPE + r')\.prototype\.' + re.escape(name) + r'=function\(([^)]*)\)\{'
    for match in re.finditer(pattern, source):
        depth, quote, escaped, end = 1, None, False, match.end()
        while depth and end < min(len(source), match.end() + 10000):
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
                break
            else:
                depth += int(char == '{') - int(char == '}')
            end += 1
        if not depth:
            yield match.group(1), match.group(2).split(',') if match.group(2) else [], source[match.end():end - 1]


def _method(source, owner, name):
    matches = [(args, body) for scope, args, body in methods(source, name) if scope == owner]
    return matches[0] if len(matches) == 1 else ([], '')


def source_roles(source, modes):
    if not isinstance(source, str) or not isinstance(modes, dict) or 'BASIC' not in modes or len(modes) > 256:
        return None
    lists = list(re.finditer('(' + SCOPE + r')\.prototype\.BUY_BONUS_MODES=(\[[^\]\n]{1,2048}\])', source))
    if len(lists) != 1:
        return None
    owner = lists[0].group(1)
    basics = re.findall(re.escape(owner) + r'\.prototype\.BUY_BONUS_MODES_BASIC=(\[[^\]\n]{1,2048}\])', source)
    if len(basics) != 1:
        return None
    try:
        menu, basic = json.loads(lists[0].group(2)), json.loads(basics[0])
    except ValueError:
        return None
    if any(not isinstance(values, list) or not values or any(not isinstance(value, str) or not COMMAND.fullmatch(value) or value == 'BASIC' for value in values) or len(set(values)) != len(values) for values in (menu, basic)):
        return None
    if not set(basic) < set(menu) or not set(modes) <= {'BASIC', *menu} or len(modes) < 2:
        return None
    # This request builder sends amount == coin == the total cash bet.
    if any(not isinstance(name, str) or not COMMAND.fullmatch(name) or not isinstance(record, dict) or type(record.get('coinsPerBet')) is not int or record['coinsPerBet'] != 1 for name, record in modes.items()):
        return None
    args, body = _method(source, owner, 'setupBuyBonus')
    if len(args) != 1 or not re.fullmatch(IDENT, args[0]):
        return None
    data = re.escape(args[0])
    setup = (r'var (' + IDENT + r')=this;this\.configUpdate\.slot\.buyBonus=\[\],'
             + data + r'\.settings\.modes\.([A-Z][A-Z0-9_]*)&&\(this\.configUpdate\.slot\.buyBonusValues='
             + data + r'\.settings\.modes\.\2\.coins\.map\(function\((' + IDENT + r')\)\{return\+\3\}\)\),'
             r'Object\.keys\(' + data + r'\.settings\.modes\)\.forEach\(function\((' + IDENT + r')\)\{'
             r'\1\.BUY_BONUS_MODES\.includes\(\4\)&&\1\.configUpdate\.slot\.buyBonus\.push\(\{enabled:!'
             + data + r'\.settings\.isBuyBonusDisabled,bets:' + data + r'\.settings\.modes\[\4\]\.coins,rtp:'
             + data + r'\.settings\.slotConfig\.RTPs\[\4\],active:!1,cmd:\4,limitationEnabled:!0,multiplier:\1\.getBuyBonusMultiplier\('
             + data + r',\4\)\}\)\}\)')
    setup_match = re.fullmatch(setup, body)
    if setup_match is None or setup_match.group(2) not in basic:
        return None
    args, body = _method(source, owner, 'getBuyBonusMultiplier')
    if len(args) != 2 or any(not re.fullmatch(IDENT, value) for value in args):
        return None
    data, command = map(re.escape, args)
    factor = (r'var (' + IDENT + r'),(' + IDENT + r')=1;return null!=\(\1=' + data
              + r'\.settings\.slotConfig\.Config\)&&\1\.buyInCost\?\2=' + data
              + r'\.settings\.slotConfig\.Config\.buyInCost:null!=\(\1=' + data
              + r'\.settings\.slotConfig\.Config\)&&null!=\(\1=\1\.buyInConfig\)&&\1\.multipliers&&\(\2=null==\(\1='
              + data + r'\.settings\.slotConfig\.Config\)\|\|null==\(' + data
              + r'=\1\.buyInConfig\)\?void 0:' + data + r'\.multipliers\[this\.BUY_BONUS_MODES_BASIC\.includes\('
              + command + r'\)\?0:1\]\),\2')
    if not re.fullmatch(factor, body):
        return None
    selected = [(scope, args, body) for scope, args, body in methods(source, 'getBuyBonusCmd') if not args and re.fullmatch(r'return this\.scope\.game\.buyBonus\.find\(function\((' + IDENT + r')\)\{return \1\.active\}\)\.cmd', body)]
    if len(selected) != 1:
        return None
    game_owner = selected[0][0]
    args, body = _method(source, game_owner, 'getBuyBonusPrice')
    if len(args) != 1 or not re.fullmatch(IDENT, args[0]):
        return None
    requested = re.escape(args[0])
    price = (r'var (' + IDENT + r')=this\.scope\.game\.buyBonus\.find\(function\(\1\)\{return '
             + requested + r'\?\1\.cmd===' + requested + r':\1\.active\}\),\1=\(\1\|\|this\.scope\.game\.buyBonus\.find\(function\(\1\)\{return \1\}\)\)\.multiplier;return this\.getBuyBonusBet\(\)\*\1')
    if not re.fullmatch(price, body):
        return None
    args, body = _method(source, game_owner, 'getBuyBonusBet')
    if args or not re.fullmatch(r'return this\.scope\.game\.buyBonus\.find\(function\((' + IDENT + r')\)\{return \1\}\)\.currentBet\|\|this\.getTotalBet\(\)', body):
        return None
    payments = []
    for _, _, body in methods(source, 'getSpinRequestParams'):
        binding = re.search(r'this\.game\.isBuyBonusActive\(\)\?\(this\.gambleCheatStack=\[\],(' + IDENT + r')\.cmd=this\.game\.getBuyBonusCmd\(\),\1\.amount=this\.game\.getBuyBonusPrice\(\),\1\.coin=this\.game\.getBuyBonusPrice\(\)\)', body)
        if binding:
            payments.append(binding.group(1))
    if len(payments) != 1:
        return None
    return {
        'profile': 'sdk.currentPurchaseList/indexedCurrentMultipliers/v1',
        'roles': {name: 'SPIN' if name == 'BASIC' else 'BUY_BONUS' for name in modes},
        'purchase_price_factor_indices': {name: 0 if name in basic else 1 for name in modes if name != 'BASIC'},
        'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
    }


def price_factors(proof, config):
    """Resolve a proven source index; never provide an implicit/default price."""
    if not isinstance(config, dict) or config.get('buyInCost'):
        raise ValueError('Current indexed purchase pricing is absent or overridden')
    purchase = config.get('buyInConfig')
    if not isinstance(purchase, dict) or purchase.get('enabled') is not True:
        raise ValueError('Current indexed purchase menu is not enabled')
    multipliers = purchase.get('multipliers')
    if not isinstance(multipliers, list) or len(multipliers) != 2 or any(type(value) is not int or value <= 1 for value in multipliers):
        raise ValueError('Current indexed purchase multipliers are missing or malformed')
    return {name: multipliers[index] for name, index in proof['purchase_price_factor_indices'].items()}
