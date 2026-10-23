"""Trace finite feature selections through a store and identity play wrapper.

These are client declarations, never guesses from generic init vocabulary or
observed wallet debits. Any incomplete link leaves the existing mode unresolved.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

from tester_spin.providers.bgaming.forwarded_request import (
    _assignment_value,
    _lexical_source,
    _two_argument_builder_bindings,
    _unique_assignment,
)

_IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*"
_VALUE = r"[A-Za-z0-9_]+"


def _definition(text: str, code: str, name: str) -> str:
    if not _unique_assignment(text, code, name):
        return ""
    match = re.search(rf"(?<![\w$.]){re.escape(name)}\s*=(?!=|>)", code)
    return _assignment_value(text, code, match.end()) if match else ""


def _immutable_domain(code: str, name: str, *, menu: bool = False) -> bool:
    root = rf"(?<![\w$.]){re.escape(name)}(?![\w$])"
    if re.search(root + rf"(?:\.{_IDENT}|\[[^\]]*\])+\s*(?:[+*/%&|^?-]?=(?!=)|\+\+|--)", code):
        return False
    # Passing the table/array itself elsewhere permits aliases and mutations
    # that this bounded proof cannot follow. Property reads remain supported.
    for use in re.finditer(root, code):
        if not re.match(r'\s*(?:[.\[]|=(?!=|>))', code[use.end():]):
            return False
    methods = re.findall(root + rf"\.({_IDENT})\s*\(", code)
    if any(method != "forEach" or not menu for method in methods):
        return False
    if menu:
        for use in re.finditer(root + r'\.forEach\s*\(', code):
            callback = re.match(rf'\(({_IDENT}),{_IDENT}\)=>\{{', code[use.end():])
            if not callback:
                return False
            opening = use.end() + callback.end() - 1
            depth, end = 1, opening + 1
            while end < len(code) and depth:
                depth += (code[end] == '{') - (code[end] == '}')
                end += 1
            body = code[opening+1:end-1]
            item = rf'(?<![\w$.]){re.escape(callback[1])}(?![\w$])'
            if depth or re.search(item + rf'(?:\.{_IDENT}|\[[^\]]*\])+\s*(?:[+*/%&|^?-]?=(?!=)|\+\+|--)', body):
                return False
    return not re.search(rf"(?:delete\s+{root}|\bObject\.(?:assign|defineProperty)\({re.escape(name)}\b)", code)


def _prices(text: str, code: str, name: str) -> dict[str, float]:
    value = _definition(text, code, name)
    if not _immutable_domain(code, name) or not re.fullmatch(r"\{[^{}]*\}", value):
        return {}
    result = {}
    for entry in value[1:-1].split(','):
        pair = re.fullmatch(rf'\s*({_VALUE})\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*', entry)
        if not pair or pair.group(1) in result:
            return {}
        number = float(pair.group(2))
        if not math.isfinite(number) or number <= 0:
            return {}
        result[pair.group(1)] = number
    return result


def _menu_values(text: str, code: str, name: str, key: str) -> list[str]:
    value = _definition(text, code, name)
    if not _immutable_domain(code, name, menu=True) or not value.startswith('['):
        return []
    # This narrow family declares plain literal records. Reject expressions,
    # spread, computed keys and accessors instead of treating them as exhaustive.
    quoted = re.sub(rf'(?<=[{{,])\s*({_IDENT})\s*:', r'"\1":', value)
    try:
        records = json.loads(quoted)
    except (ValueError, TypeError):
        return []
    if not isinstance(records, list) or not records:
        return []
    values = []
    for record in records:
        if not isinstance(record, dict) or not re.fullmatch(_VALUE, str(record.get(key) or '')):
            return []
        values.append(record[key])
    return values if len(values) == len(set(values)) else []


def _cost_contracts(text: str, code: str) -> list[dict[str, Any]]:
    ident = _IDENT
    pattern = (
        rf'(?<![\w$.])(?P<cost>{ident})=(?P<req>{ident})=>["\']freebet["\']===(?P=req)\.bet_type\?0:'
        rf'(?P=req)\.purchased_feature\?(?P=req)\.bet\*\(\((?P<feature>{ident}),(?P<level>{ident})\)=>\{{'
        rf'if\(["\'](?P<chance>{_VALUE})["\']===(?P=feature)\)return\s+(?P<scalar>{ident});'
        rf'if\(["\'](?P<purchase>{_VALUE})["\']===(?P=feature)\)\{{if\(!(?P=level)\)throw new Error\(["\'][^"\']*["\']\);'
        rf'return\s+(?P<table>{ident})\[(?P=level)\]\}}return 1\}}\)'
        rf'\((?P=req)\.purchased_feature,(?P=req)\.feature_id\):(?P=req)\.bet'
    )
    out = []
    for match in re.finditer(pattern, text):
        if not code[match.start()].strip() or not _unique_assignment(text, code, match['cost']):
            continue
        price_map = _prices(text, code, match['table'])
        scalar = _definition(text, code, match['scalar'])
        if not price_map or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', scalar):
            continue
        price = float(scalar)
        if price <= 0 or not math.isfinite(price):
            continue
        out.append(dict(helper=match['cost'], chance=match['chance'], purchase=match['purchase'],
                        chance_price=price, prices=price_map))
    return out


def _price_consumed(text: str, code: str, call: re.Match, builder: str, cost: dict) -> bool:
    ident = _IDENT
    pattern = (
        rf'const\s+(?P<state>{ident})={re.escape(call["store"])}\.getState\(\),'
        rf'(?P<req>{ident})=(?:(?P<runtime>{ident})\.replayRoundId\?(?P=runtime)\.runnerReplaySteps\[0\]\.req:)?'
        rf'{re.escape(call["modifier"])}\({re.escape(builder)}\(\),'
        rf'\{{purchased_feature:(?P=state)\.{re.escape(call["toggle"])}\?["\']{re.escape(call["chance"])}["\']:'
        rf'(?P=state)\.purchased_feature,feature_id:(?P=state)\.feature_id\}}\),'
        rf'(?P<debit>{ident})={re.escape(cost["helper"])}\((?P=req)\),'
        rf'(?P<balance>{ident})=(?P=state)\.balance-(?P=debit)(?![\w$])'
    )
    for match in re.finditer(pattern, text):
        if not code[match.start()].strip():
            continue
        setter = re.search(
            rf'{re.escape(call["store"])}\.setState\(\{{[^{{}}]{{0,400}}\bbalance:{re.escape(match["balance"])}(?=[,}}])',
            text[match.end():match.end()+700])
        if setter and code[match.end()+setter.start()].strip():
            return True
    return False


def forwarded_feature_modes(source: str) -> list[dict[str, Any]]:
    text, code = _lexical_source(source or '')
    ident = _IDENT
    bindings = set(_two_argument_builder_bindings(text, code))
    costs = _cost_contracts(text, code)
    candidates: list[list[dict[str, Any]]] = []
    for wrapper, builder, normal in bindings:
        if not normal:
            continue
        # Same store snapshot -> modifier -> local request -> same identity
        # wrapper. No statement can modify the request between build and send.
        call_pattern = (
            rf'const\s+(?P<state>{ident})=(?P<store>{ident})\.getState\(\),'
            rf'(?P<req>{ident})=(?P<modifier>{ident})\({re.escape(builder)}\(\),'
            rf'\{{purchased_feature:(?P=state)\.(?P<toggle>{ident})\?["\'](?P<chance>{_VALUE})["\']:'
            rf'(?P=state)\.purchased_feature,feature_id:(?P=state)\.feature_id\}}\),'
            rf'{ident}=await\s+{re.escape(wrapper)}\((?P=req),{ident}\.{ident}\)'
        )
        for call in re.finditer(call_pattern, text):
            if not code[call.start()].strip() or not _unique_assignment(text, code, call['store']):
                continue
            modifier = _definition(text, code, call['modifier'])
            modifier_pattern = (
                rf'\((?P<req>{ident}),(?P<selection>{ident})\)=>\(["\']{re.escape(normal)}["\']===(?P=req)\.bet_type&&'
                rf'\((?P=req)\.purchased_feature=(?P=selection)\.purchased_feature,'
                rf'(?P=req)\.feature_id=(?P=selection)\.feature_id\),(?P=req)\)'
            )
            if not re.fullmatch(modifier_pattern, modifier):
                continue
            boost = re.search(
                rf'\.onPress\.connect\(\(\)=>\{{{re.escape(call["store"])}\.setState\(\{{'
                rf'{re.escape(call["toggle"])}:!0,feature_id:void\s*0\}}\)', text)
            if not boost or not code[boost.start()].strip():
                continue
            for cost in costs:
                if cost['chance'] != call['chance'] or not _price_consumed(text, code, call, builder, cost):
                    continue
                menu_pattern = rf'(?<![\w$.])(?P<menu>{ident})\.forEach\(\((?P<item>{ident}),{ident}\)=>\{{'
                for menu in re.finditer(menu_pattern, text):
                    if not code[menu.start()].strip():
                        continue
                    # Bound to this callback's braces, not a neighbouring menu.
                    opening = menu.end()-1
                    depth, end = 1, opening+1
                    while end < len(code) and depth:
                        depth += (code[end] == '{') - (code[end] == '}')
                        end += 1
                    if depth:
                        continue
                    body = text[opening+1:end-1]
                    setter = re.search(
                        rf'{ident}\.onPress\.connect\(\(\)=>\{{{re.escape(call["store"])}\.setState\(\{{purchased_feature:["\']{re.escape(cost["purchase"])}["\'],'
                        rf'feature_id:{re.escape(menu["item"])}\.(?P<key>{ident}),(?P<tail>[^{{}}]*)\}}\)', body)
                    if (not setter or not code[opening+1+setter.start()].strip()
                            or not re.search(rf'(?:^|,){re.escape(call["toggle"])}:!1(?:,|$)', setter['tail'])):
                        continue
                    # UI registration must execute for every declared menu
                    # item. A conditional/unreachable handler is not a domain.
                    prefix = code[opening+1:opening+1+setter.start()]
                    if re.search(r'\b(?:if|switch|for|while|return|throw|try)\b|&&|\|\||\?', prefix):
                        continue
                    values = _menu_values(text, code, menu['menu'], setter['key'])
                    if not values or set(values) != set(cost['prices']):
                        continue
                    specs = [(cost['chance'], None, cost['chance_price'])]
                    specs.extend((cost['purchase'], value, cost['prices'][value]) for value in values)
                    modes = []
                    for feature, value, multiplier in specs:
                        request = {'bet_type': normal, 'purchased_feature': feature}
                        mode_id = 'PURCHASE_' + feature.upper()
                        if value is not None:
                            request['feature_id'] = value
                            mode_id += '_FEATURE_ID_' + value.upper()
                        modes.append(dict(id=mode_id, kind='PURCHASE', request=request,
                                          expected_multiplier=multiplier, executable=True,
                                          coverage_required=True,
                                          discovery_state='CLIENT_PROVEN_FEATURE_DOMAIN',
                                          source='live-client-store+modifier+menu+price'))
                    candidates.append(modes)
    distinct = {json.dumps(candidate, sort_keys=True) for candidate in candidates}
    return candidates[0] if len(distinct) == 1 else []
