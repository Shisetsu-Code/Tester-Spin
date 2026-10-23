"""Trace a finite UI choice through an event, debit, dispatch and JSON POST."""
from __future__ import annotations

import json
import math
import re

from tester_spin.providers.bgaming.forwarded_features import _definition
from tester_spin.providers.bgaming.forwarded_request import _lexical_source
from tester_spin.providers.bgaming.modern_api_v2 import _classes, _method
from tester_spin.providers.bgaming.server_guided import _split_js_object_pairs

_ID = r"[A-Za-z_$][A-Za-z0-9_$]*"
_VALUE = r"[A-Za-z0-9_]+"


def _purchase_post(text: str, code: str, name: str):
    value = _definition(text, code, name)
    prefix = re.match(rf'({_ID})=>({_ID})=>', value)
    if not prefix:
        return None
    source, mask = _lexical_source(value)
    selected = prefix[1]
    envelope = re.search(
        rf'(?P<envelope>{_ID})=\{{id:["\'][^"\']+["\'],jsonrpc:["\']2\.0["\'],method:["\']play["\'],'
        rf'params:\{{req:\{{bet:Math\.round\((?P<wager>{_ID})\*(?P<units>{_ID})\),'
        rf'bet_type:["\'](?P<bet_type>{_VALUE})["\'],(?P<flag>{_ID}):(?P<normal>[0-9]+)!=={re.escape(selected)},'
        rf'purchased_feature:["\'](?P<feature>{_VALUE})["\']\}},state_lock:{_ID},token:{_ID}\}}\}}', source)
    if not envelope or not mask[envelope.start()].strip():
        return None
    generator = list(re.finditer(r'function\*\(\)\{', mask[:envelope.start()]))
    if not generator:
        return None
    before = mask[generator[-1].end():envelope.start()]
    root = rf'(?<![\w$.]){re.escape(selected)}(?![\w$])'
    if re.search(root + r'\s*(?:[+*/%&|^?-]?=(?!=|>)|\+\+|--)', before):
        return None
    if any(selected in re.findall(_ID, m[1]) for m in re.finditer(r'\b(?:var|let)\s+([^;{}=]+);', before)):
        return None
    wager = re.search(rf'\{{wager:{re.escape(envelope["wager"])}(?:,[^{{}}]+)?\}}=(?P<store>{_ID})\.getState\(\)\.spinSlice', before)
    if not wager or not re.search(rf'{re.escape(envelope["units"])}={re.escape(wager["store"])}\.getState\(\)\.gameSlice\.currencyAttributes\.subunits', before):
        return None
    config = re.search(
        rf'(?P<config>{_ID})=\{{method:["\']POST["\'],(?P<extra>[^{{}}]{{0,800}})body:JSON\.stringify\({re.escape(envelope["envelope"])}\)\}}', source[envelope.end():])
    if not config or '...' in config['extra']:
        return None
    # Extra fetch settings cannot replace the method/body, contain duplicate
    # keys, or execute arbitrary expressions while constructing the request.
    keys = {'method', 'body'}
    for part in _split_js_object_pairs(config['extra'].rstrip(',')):
        pair = re.fullmatch(rf'({_ID}):(.+)', part)
        if not pair or pair[1] in keys:
            return None
        key, value = pair[1], pair[2]
        if key == 'headers':
            if not re.fullmatch(rf'(?:{_ID}|new Headers\({_ID}\))', value):
                return None
        elif key not in {'mode', 'redirect', 'referrerPolicy', 'credentials'} or not re.fullmatch(r'["\'][A-Za-z-]+["\']', value):
            return None
        keys.add(key)
    start = envelope.end()+config.end()
    fetch = re.search(rf'\byield\s+{_ID}\({_ID}\(\),{re.escape(config["config"])},{_ID}\)', mask[start:start+200])
    if not fetch:
        return None
    between = (mask[envelope.end():envelope.end()+config.start()] +
               ' '*(config.end()-config.start()) + mask[start:start+fetch.start()])
    # The serializer is the only permitted use of the envelope, and the
    # matching yield is the first permitted use of its HTTP configuration.
    # Reject all other references, including aliases and bracket mutations.
    for name in (envelope['envelope'], config['config']):
        if re.search(rf'(?<![\w$.]){re.escape(name)}(?![\w$])', between):
            return None
    return {'store': wager['store'], 'normal': int(envelope['normal']),
        'flag': envelope['flag'], 'bet_type': envelope['bet_type'], 'feature': envelope['feature']}


def event_feature_modes(source: str) -> list[dict]:
    text, code = _lexical_source(source or '')
    classes = list(_classes(text, code))
    candidates = []
    for _class, _holder, body, mask in classes:
        # The handler which receives the UI choice must debit the same wager
        # that the dispatched request serializes, with an explicit coefficient.
        for listener in re.finditer(rf'(?P<bus>{_ID})\.on\((?P<event>{_ID}\.{_ID}),this\.(?P<handler>{_ID}),this\)', mask):
            method = _method(body, mask, listener['handler'])
            if not method:
                continue
            selected, handler, handler_code = method
            if not re.fullmatch(_ID, selected):
                continue
            debit = re.match(
                rf'const\{{wager:(?P<wager>{_ID})\}}=(?P<store>{_ID})\.getState\(\)\.spinSlice,'
                rf'\{{balance:(?P<balance>{_ID})(?:,[^{{}}]+)?\}}=(?P=store)\.getState\(\)\.gameSlice,'
                rf'(?P<price>{_ID})=(?P<coefficient>[0-9]+(?:\.[0-9]+)?)\*(?P=wager);', handler)
            if not debit:
                continue
            coefficient = float(debit['coefficient'])
            if coefficient <= 0 or not math.isfinite(coefficient):
                continue
            charge = re.search(rf'this\.{_ID}\.updateBalance\({re.escape(debit["balance"])}-{re.escape(debit["price"])}\*{re.escape(selected)}\)', handler_code)
            dispatch = re.search(rf'{re.escape(debit["store"])}\.dispatch\((?P<action>{_ID})\({re.escape(selected)}\)\)', handler_code)
            if not charge or not dispatch or charge.end() > dispatch.start():
                continue
            stable = True
            for field in (selected, debit['price'], debit['wager']):
                if re.search(rf'(?<![\w$.]){re.escape(field)}\s*(?:[+*/%&|^?-]?=(?!=|>)|\+\+|--)', handler_code[debit.end():dispatch.start()]):
                    stable = False
            if not stable:
                continue
            contract = _purchase_post(text, code, dispatch['action'])
            if not contract or contract['store'] != debit['store']:
                continue
            for _popup, _holder, ui_body, ui_code in classes:
                for emit in re.finditer(rf'{re.escape(listener["bus"])}\.emit\({re.escape(listener["event"])},({_ID})\)', ui_code):
                    argument = emit[1]
                    # Locate the exact one-argument event method; other event
                    # consumers such as analytics do not form a purchase path.
                    for declaration in re.finditer(rf'(?<![\w$.])({_ID})\({re.escape(argument)}\)\{{', ui_code):
                        click = _method(ui_body, ui_code, declaration[1])
                        if not click:
                            continue
                        _args, click_body, click_code = click
                        expected = rf'this\.{_ID}&&\({re.escape(listener["bus"])}\.emit\({re.escape(listener["event"])},{re.escape(argument)}\),this\.{_ID}\(\)\)'
                        if not re.fullmatch(expected, click_code):
                            continue
                        subscription = _method(ui_body, ui_code, 'subscribe')
                        if not subscription:
                            continue
                        _args, subscribe, subscribe_code = subscription
                        if re.search(r'\bif\((?:false|!1|0)\)', subscribe_code):
                            continue
                        calls = re.findall(rf'this\.{re.escape(declaration[1])}\(([^()]*)\)', subscribe_code)
                        if not calls or any(not re.fullmatch(r'[0-9]+', item) for item in calls):
                            continue
                        choices = sorted(set(map(int, calls)))
                        if len(choices) != 2 or contract['normal'] not in choices or any(item <= 0 for item in choices):
                            continue
                        # Only subscribed UI callbacks supply the finite set.
                        if len(re.findall(rf'this\.{re.escape(declaration[1])}\(', ui_code)) != len(calls):
                            continue
                        modes = []
                        for choice in choices:
                            flag = choice != contract['normal']
                            modes.append({'id': 'PURCHASE_'+contract['feature'].upper()+'_'+contract['flag'].upper()+'_'+str(flag).upper(),
                                'kind': 'PURCHASE', 'request': {'bet_type': contract['bet_type'],
                                'purchased_feature': contract['feature'], contract['flag']: flag},
                                'expected_multiplier': coefficient*choice, 'executable': True,
                                'coverage_required': True, 'source': 'live-client-event+dispatch+selector+price',
                                'discovery_state': 'CLIENT_PROVEN_FEATURE_DOMAIN'})
                        candidates.append(modes)
    distinct = {json.dumps(candidate, sort_keys=True) for candidate in candidates}
    return candidates[0] if len(distinct) == 1 else []
