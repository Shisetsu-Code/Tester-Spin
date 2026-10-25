"""Finite, non-feature API-v2 variants with client-declared stake conversion."""
from __future__ import annotations

import json
import math
import re

from tester_spin.providers.bgaming.forwarded_features import _definition
from tester_spin.providers.bgaming.forwarded_request import _assignment_value, _lexical_source, _unique_assignment
from tester_spin.providers.bgaming.modern_api_v2 import _classes, _end, _json_post, _method, _variant_request
from tester_spin.providers.bgaming.server_guided import _split_js_object_pairs

_ID = r"[A-Za-z_$][A-Za-z0-9_$]*"


def _math_constructor_preserves_stake(text: str, code: str, constructor: str) -> bool:
    classes = {name: (name, holder, body, mask)
               for name, holder, body, mask in _classes(text, code)}
    classes.update({item[1]: item for item in list(classes.values()) if item[1]})
    visited = set()
    while constructor not in visited:
        visited.add(constructor)
        if constructor not in classes:
            alias = _definition(text, code, constructor)
            if not re.fullmatch(_ID, alias):
                return False
            constructor = alias
            continue
        name, holder, body, mask = classes[constructor]
        if holder and not _unique_assignment(text, code, holder):
            return False
        protected = r'(?:base_bet|bet_adding|requestOptions)'
        if (re.search(rf'\.{protected}\s*(?:[+*/%&|^?<>-]*=(?!=)|\+\+|--)', mask)
                or re.search(rf'(?:delete\s+|\+\+|--)\s*(?:this\.)?{_ID}\.{protected}', mask)
                or re.search(rf'\[["\']{protected}["\']\]\s*(?:[+*/%&|^?<>-]*=(?!=)|\+\+|--)', body)):
            return False
        # The retained configuration cannot escape to arbitrary consumers.
        for use in re.finditer(r'this\.options(?![\w$])', mask):
            tail = mask[use.end():]
            if re.match(r'\s*=(?!=|>)', tail):
                continue
            if not re.match(rf'\.{_ID}', tail) or re.match(rf'\.{_ID}\s*\(', tail):
                return False
        method = _method(body, mask, 'constructor')
        if method:
            argument, _body, constructor_mask = method
            if argument:
                if not re.fullmatch(_ID, argument):
                    return False
                allowed = [(m.start(), m.end()) for m in re.finditer(
                    rf'(?:super\({re.escape(argument)}\)|this\.options={re.escape(argument)}(?![\w$]))', constructor_mask)]
                for use in re.finditer(rf'(?<![\w$.]){re.escape(argument)}(?![\w$])', constructor_mask):
                    if any(start <= use.start() < finish for start, finish in allowed):
                        continue
                    if not re.match(rf'\.{_ID}', constructor_mask[use.end():]):
                        return False
            elif re.search(r'\barguments\b', constructor_mask.replace('super(...arguments)', '')):
                return False
        inheritance = re.search(rf'\bclass\s+{re.escape(name)}\s+extends\s+({_ID})\s*\{{', code)
        if not inheritance:
            return True
        constructor = inheritance[1]
    return False


def _stable_symbol(text: str, code: str, name: str, *, array: bool = False, domain: str = '') -> bool:
    root = rf'(?<![\w$.]){re.escape(name)}(?![\w$])'
    if re.search(root + rf'(?:\.{_ID}|\[[^\]]*\])+\s*(?:[+*/%&|^?-]?=(?!=)|\+\+|--)', code):
        return False
    if re.search(rf'Object\.(?:assign|defineProperty)\(\s*{root}[,)]|delete\s+{root}', code):
        return False
    permitted = []
    if array:
        for binding in re.finditer(rf'{_ID}\({_ID},["\']allOptions["\'],{re.escape(name)}\)', text):
            if code[binding.start()].strip():
                permitted.append(binding.span())
        for mapping in re.finditer(rf'{root}\.map\((?P<item>{_ID})=>new\s+(?P<constructor>{_ID})\((?P=item)\)\)', code):
            if _math_constructor_preserves_stake(text, code, mapping['constructor']):
                permitted.append(mapping.span())
    elif domain:
        declaration = re.search(rf'(?<![\w$.]){re.escape(domain)}=\[{_ID}(?:,{_ID})+\]', code)
        if declaration:
            permitted.append(declaration.span())
    helpers = {}
    for use in re.finditer(root, code):
        if any(start <= use.start() < finish for start, finish in permitted):
            continue
        tail = code[use.end():]
        if re.match(r'\s*:', tail) and re.search(r'[,{]\s*$', code[:use.start()]):
            continue
        if re.match(r'\s*(?:===|!==)', tail) or re.search(r'(?:===|!==)\s*$', code[:use.start()]):
            continue
        if re.match(r'\s*=(?!=|>)', tail):
            continue
        if re.match(r'\s*[.\[]', tail):
            if re.match(rf'\s*\.{_ID}\s*\(', tail):
                return False
            continue
        # A configuration can be read by the already-proven cloning helper.
        # All other escapes could mutate a price or selector through an alias.
        call = re.search(rf'(?<![\w$.])({_ID})\(\s*$', code[:use.start()])
        if not array and call and re.match(r'\s*,', tail):
            if call[1] not in helpers:
                helpers[call[1]] = _merge_helper(text, code, call[1])
            if helpers[call[1]]:
                continue
        return False
    return True


def _function(text: str, code: str, name: str):
    definitions = {}
    for match in re.finditer(rf'\bfunction\s+{re.escape(name)}\(({_ID}),({_ID})\)\{{', code):
        finish = _end(code, match.end()-1)
        if finish:
            body = text[match.end():finish-1]
            definitions[body] = (match[1], match[2], body, code[match.end():finish-1])
    if re.search(rf'(?<![\w$.]){re.escape(name)}\s*=(?!=)', code):
        return None
    return next(iter(definitions.values())) if len(definitions) == 1 else None


def _merge_helper(text: str, code: str, name: str, seen=()) -> bool:
    if name in seen or len(seen) > 8:
        return False
    function = _function(text, code, name)
    if not function:
        return False
    parent, extra, body, mask = function
    p, e = re.escape(parent), re.escape(extra)
    cloned = re.fullmatch(
        rf'const\s+(?P<copy>{_ID})=JSON\.parse\(JSON\.stringify\({p}\)\);return\s+'
        rf'{e}=JSON\.parse\(JSON\.stringify\({e}\)\),'
        rf'(?:(?P=copy)\.custom&&{e}\.custom&&\({e}\.custom=Object\.assign\(\{{\}},(?P=copy)\.custom,{e}\.custom\)\),)?'
        rf'Object\.assign\((?P=copy),{e}\),'
        rf'(?:{p}!=={_ID}&&{e}\.base_bet&&{e}\.base_bet!=={p}\.base_bet&&'
        rf'\({e}\.default_bet\|\|\((?P=copy)\.default_bet={p}\.default_bet/{p}\.base_bet\*{e}\.base_bet\)\),)?'
        rf'(?P=copy)', body)
    if cloned:
        return True
    # Some clients rotate only the copied reels after the same proven merge.
    # The copied object's bet/selector properties cannot be read or altered by
    # this wrapper, nor may the object escape to an unknown call.
    wrapper = re.match(rf'(?:var\s+{_ID};)?const\s+({_ID})=({_ID})\({p},{e}\);', mask)
    if not wrapper or not _merge_helper(text, code, wrapper[2], (*seen, name)):
        return False
    output = wrapper[1]
    if not re.search(rf'\breturn\s+{re.escape(output)}$', mask):
        return False
    tail = mask[wrapper.end():]
    for use in re.finditer(rf'(?<![\w$.]){re.escape(output)}(?![\w$])', tail):
        if re.match(r'\.(?:reels|layout)(?![\w$])', tail[use.end():]):
            continue
        if re.search(r'\breturn\s*$', tail[:use.start()]) and not tail[use.end():].strip():
            continue
        return False
    return True


def _properties(value: str):
    if not value.startswith('{') or not value.endswith('}'):
        return None
    result = {}
    for part in _split_js_object_pairs(value[1:-1]):
        pair = re.fullmatch(rf'\s*(?:({_ID})|["\']({_ID})["\'])\s*:(.*)', part, re.S)
        if not pair:
            return None
        key = pair[1] or pair[2]
        if key in result:
            return None
        result[key] = pair[3].strip()
    return result


def _config(text: str, code: str, name: str, domain: str, seen=()):
    if name in seen or len(seen) > 16 or not _stable_symbol(text, code, name, domain=domain):
        return None
    value = _definition(text, code, name)
    inherited = {}
    properties = _properties(value)
    if properties is None:
        call = re.fullmatch(rf'({_ID})\((.*)\)', value, re.S)
        if not call or not _merge_helper(text, code, call[1]):
            return None
        args = _split_js_object_pairs(call[2])
        if len(args) != 2 or not re.fullmatch(_ID, args[0]):
            return None
        inherited = _config(text, code, args[0], domain, (*seen, name))
        properties = _properties(args[1])
        if inherited is None or properties is None:
            return None
    result = dict(inherited)
    for key in ('base_bet', 'bet_adding', 'requestOptions'):
        if key in properties:
            result[key] = properties[key]
    return result


def _aliases(text: str, code: str, name: str, holder: str):
    names = {name}
    if holder and _unique_assignment(text, code, holder):
        names.add(holder)
    out = set(names)
    for match in re.finditer(rf'\b(?:let|var|const)\s+({_ID})=({_ID})(?=[,;])', code):
        if match[2] not in names:
            continue
        root = rf'(?<![\w$.]){re.escape(match[1])}(?![\w$])'
        assignments = {_assignment_value(text, code, item.end())
                       for item in re.finditer(root + r'\s*=(?!=|>)', code)}
        mutated = re.search(root + r'\s*(?:\+\+|--|[+*/%&|^?-]=)', code)
        # Short minified module aliases can also name parameters in unrelated
        # functions. Check shadowing at the consuming method below, while any
        # conflicting assignment anywhere still makes this alias ambiguous.
        if assignments == {match[2]} and not mutated:
            out.add(match[1])
    return out


def modern_variant_contract(source: str) -> dict:
    text, code = _lexical_source(source or '')
    classes = list(_classes(text, code))
    contracts = []
    for _api_name, _api_holder, api_body, api_code in classes:
        if not _json_post(api_body, api_code, module=(text, code)):
            continue
        method = _method(api_body, api_code, 'spinRequest')
        _args, body, mask = method
        request = _variant_request(mask)
        if not request:
            continue
        config_name = re.escape(request['config'])
        prefix = mask[:request.start()]
        if (re.search(rf'(?<![\w$]){config_name}(?![\w$])', _args)
                or re.search(rf'\([^()]{{0,500}}(?<![\w$]){config_name}(?![\w$])[^()]{{0,500}}\)\s*(?:=>|\{{)', prefix)
                or re.search(rf'\b(?:let|var|const)\s+{config_name}(?![\w$])', prefix)):
            continue
        array = request['variants']
        values = _definition(text, code, array)
        if not re.fullmatch(rf'\[{_ID}(?:,{_ID})+\]', values) or not _stable_symbol(text, code, array, array=True):
            continue
        symbols = values[1:-1].split(',')
        if not 2 <= len(symbols) <= 32 or len(set(symbols)) != len(symbols):
            continue
        bound = False
        for name, holder, config_body, config_code in classes:
            if not re.search(rf'static get currentConfig\(\)\{{return\s+{re.escape(array)}\[this\.currentVariantId\]\}}', config_code):
                continue
            if request['config'] not in _aliases(text, code, name, holder):
                continue
            field = re.search(rf'{_ID}\({re.escape(holder or name)},["\']allOptions["\'],{re.escape(array)}\)', text)
            if field and code[field.start()].strip():
                bound = True
                break
        if not bound:
            continue
        bets = []
        for symbol in symbols:
            config = _config(text, code, symbol, array)
            if not config or 'requestOptions' in config or config.get('bet_adding', '0') != '0':
                break
            raw = config.get('base_bet', '')
            if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', raw):
                break
            value = float(raw)
            if value <= 0 or not math.isfinite(value):
                break
            bets.append(value)
        if len(bets) != len(symbols):
            continue
        choices = [str(index) for index in range(len(bets))]
        contracts.append({'spin_options': {'mode': choices[0]},
            'spin_option_choices': {'mode': choices},
            'effective_bet_selector': 'mode',
            'effective_bet_multipliers': {key: bet/bets[0] for key, bet in zip(choices, bets)}})
    distinct = {json.dumps(contract, sort_keys=True) for contract in contracts}
    return contracts[0] if len(distinct) == 1 else {}
