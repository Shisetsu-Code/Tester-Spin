"""Current renderer geometry/roles and current server awards for indexed output."""
import hashlib
import json
import re

from .sdk_purchase_list_roles import IDENT, SCOPE, methods, _method
from .supermeter import num


def declaration(props, source):
    if not isinstance(source, str) or not isinstance(props, dict):
        return None
    candidates = []
    for owner, args, body in methods(source, 'mapAdditionalSymbols'):
        if len(args) != 3 or '.outcome.reelLengthByIndex=' not in body:
            continue
        if any(not re.fullmatch(IDENT, value) for value in args):
            continue
        output, symbol, index = map(re.escape, args)
        geometry = re.findall(output + r'\.outcome\.reelLengthByIndex=(\[[0-9,]+\])', body)
        coordinates = re.search(r'var (' + IDENT + r'),' + symbol + r'=this\.mapSymbol\(' + symbol + r'\),(' + IDENT + r')=' + index + r'%this\.numberOfReels,(' + IDENT + r')=Math\.floor\(' + index + r'/this\.numberOfReels\);', body)
        if len(geometry) != 1 or coordinates is None or '.wildSymbols.push' in body:
            continue
        heights = json.loads(geometry[0])
        if not 1 <= len(heights) <= 16 or len(set(heights)) != 1 or not 1 <= heights[0] <= 16:
            continue
        value, col, row = map(re.escape, coordinates.groups())
        roles = {}
        for role, container, field in [('fish', 'fishSymbols', 'fishValues'), ('treasure', 'treasureSym', 'treasureValues')]:
            match = re.findall(r'"sym([0-9]+)"==' + symbol + r'&&\(' + value + r'=' + output + r'\.' + field + r'\[' + index + r'\+1\],.{0,180}?' + output + r'\.outcome\.' + container + r'\.push\(\{reelIndex:' + col + r',symbolIndex:' + row + r',prize:' + value + r',sym:' + symbol + r'\}\)', body)
            if len(match) == 1:
                roles[role] = int(match[0])
        for role, container in [('collector', 'fishermanSymbol'), ('diver', 'diverWoman')]:
            match = re.findall(r'"sym([0-9]+)"==' + symbol + r'&&' + output + r'\.outcome\.' + container + r'\.push\(\{reelIndex:' + col + r',symbolIndex:' + row + r',sym:' + symbol + r'\}\)', body)
            if len(match) == 1:
                roles[role] = int(match[0])
        scatter = re.findall(r'"sym([0-9]+)"==' + symbol + r'&&\(' + output + r'\.outcome\.totalScatterCount\+\+,' + output + r'\.outcome\.scatterCount\[' + col + r'\]\+\+,' + output + r'\.outcome\.bonusSym\.push\(\{reelIndex:' + col + r',symIndex:' + row + r',sym:' + symbol + r'\}\)', body)
        if len(scatter) == 1:
            roles['scatter'] = int(scatter[0])
        if len(roles) != 5 or len(set(roles.values())) != 5 or max(roles.values()) > 4096:
            continue
        parents = re.findall(re.escape(owner) + r'\.prototype=Object\.create\((' + SCOPE + r')\.prototype\)', source)
        if len(parents) != 1 or any(scope == owner for method in ('mapSymbol', 'mapWins') for scope, _, _ in methods(source, method)):
            continue
        parent = parents[0]
        params, mapping = _method(source, parent, 'mapSymbol')
        if len(params) != 1 or mapping != 'return ' + params[0] + '?"sym"+Number(' + params[0] + ').pad(2):void 0':
            continue
        params, wins = _method(source, parent, 'mapWins')
        if len(params) != 2:
            continue
        win = re.escape(params[1])
        if not re.search(r'(' + IDENT + r')\.amount=' + win + r'\.creditsWon,\1\.multiplier=' + win + r'\.multiplier,\1\.multipliedAmount=' + win + r'\.creditsWon\*\(' + win + r'\.multiplier\|\|1\),', wins):
            continue
        if not re.search(r'(' + IDENT + r')\.forEach\(function\((' + IDENT + r')\)\{var \2=\2-1,(' + IDENT + r')=\2%(' + IDENT + r')\.numberOfReels,\2=Math\.floor\(\2/\4\.numberOfReels\)', wins):
            continue
        params, multiplier = _method(source, owner, 'mapDoubleMax')
        if len(params) != 2 or multiplier != params[0] + '.outcome.activeMultiplier=' + params[1] + '.multiplier,' + params[0] + '.outcome.doubleMax={consecutive:' + params[1] + '.consecutive}':
            continue
        params, dispatch = _method(source, owner, 'mapAdditionalFeatures')
        if len(params) != 2:
            continue
        feature = re.findall(r'case"([^"\\]{1,64})":this\.mapDoubleMax\(' + re.escape(params[0]) + ',' + re.escape(params[1]) + r'\);break;', dispatch)
        if len(feature) != 1:
            continue
        defaults = []
        for _, _, code in methods(source, 'setFeatureIncome'):
            defaults.extend(re.findall(r'this\.scope\.game\.currentMultipliersAboveReels=(\[[0-9,]+\])', code))
        resets = [code for _, _, code in methods(source, 'spin') if 'this.scope.game.doubleMax=null,this.scope.game.activeMultiplier=null' in code and 'this.spinLeanderInterface.bind(this,' in code]
        if len(defaults) != 1 or len(resets) != 1:
            continue
        multipliers = json.loads(defaults[0])
        if len(multipliers) != len(heights) or multipliers != [2 ** index for index in range(len(heights))]:
            continue
        candidates.append({'width': len(heights), 'height': heights[0], 'symbols': roles, 'multipliers': multipliers, 'multiplier_feature': feature[0]})
    if len(candidates) != 1:
        return None
    definition = candidates[0]
    config = props.get('Config')
    if not isinstance(config, dict) or type(config.get('betDivisor')) is not int or config['betDivisor'] <= 0 or type(config.get('currencyDecimalPlaces')) is not int or not 0 <= config['currencyDecimalPlaces'] <= 8:
        return None
    table = config.get('payTable')
    if not isinstance(table, dict) or not 1 <= len(table) <= 256:
        return None
    awards = {}
    try:
        for key, record in table.items():
            if not isinstance(key, str) or not key.isdigit() or str(int(key)) != key or not isinstance(record, dict) or set(record) != {'id', 'values'} or type(record['id']) is not int or record['id'] != int(key):
                return None
            values = record['values']
            if not isinstance(values, dict) or set(values) != {str(n) for n in range(1, definition['width'] + 1)}:
                return None
            awards[key] = {count: str(num(amount)) for count, amount in values.items()}
            if any(num(value) < 0 for value in awards[key].values()):
                return None
    except (ValueError, TypeError, ArithmeticError):
        return None
    if any(str(value) not in awards for value in definition['symbols'].values()):
        return None
    return {'schema': 'indexed-output/current-renderer-and-awards/v1', **definition, 'bet_divisor': config['betDivisor'], 'currency_decimal_places': config['currencyDecimalPlaces'], 'awards': awards, 'source_sha256': hashlib.sha256(source.encode()).hexdigest()}
