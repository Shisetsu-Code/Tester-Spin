"""Recognize the modern API-v2 purchase-level identity chain without JS eval.

The server still supplies the finite feature/level/price domain. This module
only proves that a selected name and level can reach the JSON POST unchanged.
"""
from __future__ import annotations

import re

from tester_spin.providers.bgaming.forwarded_request import _lexical_source, _unique_assignment
from tester_spin.providers.bgaming.forwarded_features import _definition
from tester_spin.providers.bgaming.server_guided import _split_js_object_pairs

_ID = r"[A-Za-z_$][A-Za-z0-9_$]*"


def _end(code: str, opening: int, left: str = '{', right: str = '}') -> int:
    depth = 1
    for index in range(opening+1, len(code)):
        depth += (code[index] == left) - (code[index] == right)
        if not depth:
            return index+1
    return 0


def _classes(text: str, code: str):
    for match in re.finditer(rf'\bclass\s+({_ID})(?:\s+extends\s+{_ID})?\s*\{{', code):
        finish = _end(code, match.end()-1)
        if not finish:
            continue
        assignment = re.search(rf'(?<![\w$.])({_ID})\s*=\s*$', code[max(0, match.start()-120):match.start()])
        yield (match[1], assignment[1] if assignment else '',
               text[match.end():finish-1], code[match.end():finish-1])


def _method(text: str, code: str, name: str):
    found = {}
    for match in re.finditer(rf'(?<![\w$.]){re.escape(name)}\(([^()]*)\)\{{', code):
        if code[:match.start()].count('{') != code[:match.start()].count('}'):
            continue
        finish = _end(code, match.end()-1)
        if finish:
            value = (text[match.start()+len(name)+1:match.end()-2], text[match.end():finish-1], code[match.end():finish-1])
            found[value[:2]] = value
    return next(iter(found.values())) if len(found) == 1 else None


def _calls(text: str, code: str, name: str):
    for match in re.finditer(re.escape(name)+r'\(', code):
        finish = _end(code, match.end()-1, '(', ')')
        if finish:
            yield match.start(), finish, _split_js_object_pairs(text[match.end():finish-1])


def _selector_unchanged(code: str, options: str, *, allowed_bare=()) -> bool:
    root = rf'(?<![\w$.]){re.escape(options)}(?![\w$])'
    if re.search(
        rf'(?:{root}\s*(?:[+*/%&|^?-]?=(?!=|>)|\+\+|--)|'
        rf'{root}\s*\[|'
        rf'delete\s+{root}\.purchased_feature_level|'
        rf'{root}\.purchased_feature_level\s*(?:[+*/%&|^?-]?=(?!=)|\+\+|--)|'
        rf'(?:\+\+|--)\s*{root}\.purchased_feature_level)', code):
        return False
    # Every bare object reference must be a demonstrated forwarding argument.
    # Unknown calls, aliases, spreads and reflection can all change the level.
    for use in re.finditer(root, code):
        if any(start <= use.start() < finish for start, finish in allowed_bare):
            continue
        tail = code[use.end():]
        if re.match(r'\s*(?:==|!=)=?\s*null\b', tail):
            continue
        if re.match(rf'\.{_ID}', tail) and not re.match(rf'(?:\.{_ID})+\s*\(', tail):
            continue
        return False
    return True


def _variant_request(code: str, options: str = _ID):
    return re.search(
        rf'!(?P<options>{options})\.bonus&&!(?P<context>{_ID})\.data\.isNextSpinFree&&'
        rf'\((?P=options)\.bet=(?P=context)\.data\.bet/(?P<config>{_ID})\.currentConfig\.base_bet\*'
        rf'(?P<variants>{_ID})\[0\]\.base_bet\),(?P=context)\.data\.isNextSpinFree\|\|'
        rf'\((?P=options)\.mode=(?P=config)\.currentVariantId\.toString\(\)\)', code)


def _spin_wire(text: str, code: str):
    method = _method(text, code, 'spinRequest')
    if not method:
        return False
    _arguments, body, mask = method
    header = re.match(rf'return\s+{_ID}\(this,arguments,function\*\(({_ID}),({_ID})=\{{\}}\)\{{', mask)
    if not header:
        return False
    options = header[2]
    finish = _end(mask, header.end()-1)
    body, mask = body[header.end():finish-1], mask[header.end():finish-1]
    root = rf'(?<![\w$.]){re.escape(options)}(?![\w$])'
    for start, finish, args in _calls(body, mask, 'this.requestCommand'):
        if len(args) != 3 or args[2] != options or not re.fullmatch(_ID, args[0]):
            continue
        if not re.search(rf'\blet\s+{re.escape(args[0])}=["\']spin["\'];', body[:start]):
            continue
        # The request may acquire only the proven bet/mode fields and the
        # selected configuration. Other calls receiving it would escape this
        # identity proof, even if they are adjacent to a valid serializer.
        permitted = [(start, finish)]
        forwarded = [(finish-len(options)-1, finish-1)]
        normalized = _variant_request(mask, re.escape(options))
        if normalized and normalized.end() <= start:
            permitted.append(normalized.span())
            branch = re.match(
                rf',{re.escape(normalized["config"])}\.currentConfig\.requestOptions&&'
                rf'\(delete {re.escape(options)}\.mode,{re.escape(normalized["context"])}\.data\.isNextSpinFree\|\|'
                rf'Object\.assign\({re.escape(options)},{re.escape(normalized["config"])}\.currentConfig\.requestOptions\)\)',
                mask[normalized.end():])
            if branch:
                permitted.append((normalized.end(), normalized.end()+branch.end()))
                merge = re.search(rf'Object\.assign\(({re.escape(options)}),', branch[0])
                forwarded.append((normalized.end()+merge.start(1), normalized.end()+merge.end(1)))
        if not _selector_unchanged(mask, options, allowed_bare=forwarded):
            continue
        valid = True
        for use in re.finditer(root, mask):
            if any(first <= use.start() < last for first, last in permitted):
                continue
            prop = re.match(rf'\.({_ID})', mask[use.end():])
            if not prop:
                valid = False
                break
            tail = mask[use.end()+prop.end():]
            write = re.match(r'\s*(?:[+*/%&|^?<>-]*=(?!=)|\+\+|--|\()', tail)
            prefix_write = re.search(r'(?:\bdelete\s+|\+\+|--)\s*$', mask[:use.start()])
            if write or prefix_write:
                valid = False
                break
        if valid:
            return True
    return False


def _property_initializer(text: str, code: str, name: str) -> bool:
    """The emitted class-field helper stores precisely its third argument."""
    value = _definition(text, code, name)
    wrapper = re.fullmatch(
        rf'\((?P<object>{_ID}),(?P<key>{_ID}),(?P<value>{_ID})\)=>(?P<put>{_ID})'
        rf'\((?P=object),typeof (?P=key)!=["\']symbol["\']\?(?P=key)\+["\']["\']:(?P=key),(?P=value)\)', value)
    if not wrapper:
        return False
    put = _definition(text, code, wrapper['put'])
    direct = re.fullmatch(
        rf'\((?P<object>{_ID}),(?P<key>{_ID}),(?P<value>{_ID})\)=>(?P=key) in (?P=object)\?'
        rf'(?P<define>{_ID})\((?P=object),(?P=key),\{{enumerable:!0,configurable:!0,writable:!0,value:(?P=value)\}}\)'
        rf':(?P=object)\[(?P=key)\]=(?P=value)', put)
    return bool(direct and _definition(text, code, direct['define']) == 'Object.defineProperty')


def _replay_reader_preserves_payload(api_body: str, api_code: str, module) -> bool:
    """Bind the optional replay reader and prove every use of its input."""
    if not module:
        return False
    text, code = module
    constructor = _method(api_body, api_code, 'constructor')
    if not constructor:
        return False
    _args, body, mask = constructor
    bindings = []
    for match in re.finditer(rf'this\.replays=new\s+({_ID})(?![\w$])', mask):
        bindings.append(match[1])
    for match in re.finditer(rf'({_ID})\(this,["\']replays["\'],new\s+({_ID})\)', body):
        if mask[match.start()].strip() and _property_initializer(text, code, match[1]):
            bindings.append(match[2])
    if len(bindings) != 1:
        return False
    # The installed reader cannot escape through this field or be replaced.
    for use in re.finditer(r'this\.replays(?![\w$])', api_code):
        tail = api_code[use.end():]
        if re.match(r'=(?!=)', tail):
            if not re.match(rf'=new\s+{re.escape(bindings[0])}(?![\w$])', tail):
                return False
        elif not re.match(r'\.(?:initData\(\)|getReplayData\()', tail):
            return False
    target, seen = bindings[0], set()
    classes = list(_classes(text, code))
    while target not in seen:
        seen.add(target)
        matches = [(name, holder, body, mask) for name, holder, body, mask in classes
                   if target == holder or not holder and target == name]
        if matches:
            distinct = {(body, mask) for _name, _holder, body, mask in matches}
            if len(distinct) != 1 or matches[0][1] and not _unique_assignment(text, code, target):
                return False
            reader_body, reader_code = next(iter(distinct))
            reader = _method(reader_body, reader_code, 'getReplayData')
            if not reader or not re.fullmatch(_ID, reader[0]):
                return False
            argument, read_body, read_code = reader
            root = rf'(?<![\w$.]){re.escape(argument)}(?![\w$])'
            allowed = []
            # The request object/options are only tested for truthiness; its
            # command is only compared to a literal. Neither reference escapes.
            for use in re.finditer(root, read_code):
                before, after = read_code[:use.start()], read_code[use.end():]
                truth_test = (re.search(r'(?:\bif\(|&&|\|\||,)\s*$', before)
                              and re.match(r'(?:\.options)?\)+\s*\{', after))
                comparison = (re.search(r'(?:\bif\(|&&|\|\|)\s*$', before)
                              and re.match(r'\.command\s*===\s*["\'][A-Za-z_]+["\']', read_body[use.end():]))
                if not truth_test and not comparison:
                    return False
                allowed.append(use.span())
            # No replacement or computed lookup of the demonstrated method.
            if reader_body.count('getReplayData') != 1 or re.search(r'\[["\']getReplayData["\']\]', text):
                return False
            if re.search(r'\.getReplayData\s*=(?!=)', code):
                return False
            return bool(allowed)
        alias = _definition(text, code, target)
        if not re.fullmatch(_ID, alias):
            return False
        target = alias
    return False


def _json_post(text: str, code: str, *, module=None) -> bool:
    command = _method(text, code, 'requestCommand')
    request = _method(text, code, 'request')
    if not command or not request or not _spin_wire(text, code):
        return False
    arguments, body, mask = command
    args = _split_js_object_pairs(arguments)
    if len(args) < 3 or not all(re.fullmatch(_ID, arg) for arg in args[:3]):
        return False
    payload = rf'this\.request\(window\.__OPTIONS__\.api,\{{command:{re.escape(args[0])},options:{re.escape(args[2])}\}}'
    match = re.search(payload, mask)
    if not match:
        return False
    outside = mask[:match.start()] + ' '*(match.end()-match.start()) + mask[match.end():]
    if re.search(rf'(?<![\w$.]){re.escape(args[2])}(?![\w$])', outside):
        return False
    arguments, body, mask = request
    args = _split_js_object_pairs(arguments)
    if len(args) < 2 or not all(re.fullmatch(_ID, arg) for arg in args[:2]):
        return False
    payload_root = rf'(?<![\w$.]){re.escape(args[1])}(?![\w$])'
    if re.search(payload_root + rf'(?:\.{_ID}|\[[^\]]*\])*\s*(?:[+*/%&|^?-]?=(?!=|>)|\+\+|--)', mask):
        return False
    post = re.search(rf'(?<![\w$.])({_ID})=\{{body:JSON\.stringify\({re.escape(args[1])}\),method:["\']POST["\'],headers:{_ID}\}}', body)
    if not post or not mask[post.start()].strip():
        return False
    payload = re.escape(args[1])
    permitted = [match.span(1) for match in re.finditer(rf'\breturn\s+({payload})&&', mask[:post.start()])]
    serialized = re.search(rf'JSON\.stringify\(({payload})\)', mask[post.start():post.end()])
    permitted.append((post.start()+serialized.start(1), post.start()+serialized.end(1)))
    readers = list(re.finditer(rf'this\.replays\.getReplayData\(({payload})\)', mask[:post.start()]))
    if readers:
        if not _replay_reader_preserves_payload(text, code, module):
            return False
        permitted.extend(match.span(1) for match in readers)
    # A property reference can itself be an alias to the mutable options. Only
    # these exact boolean, proven-reader and serializer uses are authorized.
    if any(not any(start <= use.start() < finish for start, finish in permitted)
           for use in re.finditer(payload_root, mask[:post.end()])):
        return False
    if not _unique_assignment(body, mask, post[1]):
        return False
    fetch = re.search(rf'\.fetch\([^,;]+,{re.escape(args[0])},["\']json["\'],{re.escape(post[1])},', body[post.end():])
    if not fetch or not mask[post.end()+fetch.start()].strip():
        return False
    between = mask[post.end():post.end()+fetch.start()]
    return not re.search(rf'(?<![\w$.]){re.escape(post[1])}(?![\w$])', between)


def _notification_consumers_preserve_level(source: str, hook: str) -> bool:
    """Every use of a notification hook must bind a known local handler."""
    if hook not in source:
        return True
    text, code = _lexical_source(source)
    remaining = text
    for _name, _holder, body, mask in _classes(text, code):
        for registration in re.finditer(
                rf'{_ID}\.data\.game\.{re.escape(hook)}\(this\.({_ID})\)', mask):
            callback = _method(body, mask, registration[1])
            if not callback:
                return False
            argument, _callback_body, callback_mask = callback
            rebound = re.sub(
                rf'this\.{re.escape(registration[1])}=this\.{re.escape(registration[1])}\.bind\(this\)',
                '', code)
            if (not re.fullmatch(_ID, argument)
                    or not _selector_unchanged(callback_mask, argument)
                    or re.search(rf'\.{re.escape(registration[1])}\s*=(?!=)', rebound)):
                return False
            value = body[registration.start():registration.end()]
            remaining = remaining.replace(value, ' '*len(value))
    return hook not in remaining


def _notification_arguments(text: str, code: str, class_body: str, class_code: str,
                            body: str, mask: str, options: str, other_sources) -> list[tuple[int, int]]:
    """Allow a notification only with absent or selector-preserving consumers.

    Several modern clients emit an optional pre-request event. It is not an
    identity forwarder if a collected script takes its registration hook or
    installs an unknown/mutating consumer. Inspect each module independently.
    """
    permitted = []
    for _start, finish, args in _calls(body, mask, 'this.emit'):
        if len(args) != 2 or args[1] != options or not re.fullmatch(_ID, args[0]):
            continue
        event = args[0]
        literal = _definition(text, code, event)
        if not re.fullmatch(r'["\'][A-Za-z0-9_]+["\']', literal):
            continue
        wrappers = list(re.finditer(
            rf'(?P<name>{_ID})\((?P<first>{_ID}),(?P<second>{_ID})\)\{{this\.(?:on|off)'
            rf'\({re.escape(event)},(?P=first),(?P=second)\)\}}', class_code))
        if not wrappers:
            continue
        valid = True
        for wrapper in wrappers:
            name = wrapper['name']
            expected = class_body[wrapper.start():wrapper.end()]
            if (not _method(class_body, class_code, name)
                    or not _notification_consumers_preserve_level(text.replace(expected, ' '*len(expected)), name)
                    or any(literal[1:-1] in source or not _notification_consumers_preserve_level(source, name)
                           for source in other_sources)):
                valid = False
                break
        if not valid:
            continue
        event_root = rf'(?<![\w$.]){re.escape(event)}(?![\w$])'
        registrations = [match.span() for match in re.finditer(
            rf'{_ID}\({_ID},{_ID}\)\{{this\.(?:on|off)\({re.escape(event)},{_ID},{_ID}\)\}}', code)]
        for use in re.finditer(event_root, code):
            if re.match(r'\s*=(?!=|>)', code[use.end():]):
                continue
            if re.search(r'this\.emit\(\s*$', code[:use.start()]):
                continue
            if any(start <= use.start() < end for start, end in registrations):
                continue
            valid = False
            break
        if valid:
            permitted.append((finish-len(options)-1, finish-1))
    return permitted


def modern_purchase_level_supported(source: str, *, other_sources=()) -> bool:
    """Require UI selection, game forwarding, the same API class and JSON POST."""
    text, code = _lexical_source(source or '')
    classes = list(_classes(text, code))
    aliases = set()
    for name, holder, body, mask in classes:
        if not _json_post(body, mask, module=(text, code)):
            continue
        names = {name}
        if holder and _unique_assignment(text, code, holder):
            names.add(holder)
        aliases.update(names)
        for match in re.finditer(rf'\b(?:let|var|const)\s+({_ID})=({_ID})(?=[,;])', code):
            if match[2] in names and _unique_assignment(text, code, match[1]):
                aliases.add(match[1])
    if not aliases:
        return False
    ui = re.search(rf'(?P<context>{_ID})\.data\.game\.spin\(\{{purchased_feature:(?P<entry>{_ID})\.name,purchased_feature_level:(?P=entry)\.level\}}\)', code)
    if not ui:
        return False
    for _name, _holder, body, mask in classes:
        spin, forwarded = _method(body, mask, 'spin'), _method(body, mask, 'spinRequest')
        if not spin or not forwarded:
            continue
        constructors = set(re.findall(rf'this\.api=new\s+({_ID})(?![\w$])', mask))
        if not constructors or not constructors <= aliases:
            continue
        if any(not re.match(rf'new\s+({_ID})(?![\w$])', mask[m.end():])
               for m in re.finditer(r'this\.api=(?!=)', mask)):
            continue
        argument, spin_body, spin_mask = spin
        spin_calls = [(finish-len(argument)-1, finish-1)
                      for _start, finish, args in _calls(spin_body, spin_mask, 'this.spinRequest')
                      if args == [argument]]
        if (not re.fullmatch(_ID, argument) or not spin_calls
                or not _selector_unchanged(spin_mask, argument, allowed_bare=spin_calls)):
            continue
        arguments, request_body, request_mask = forwarded
        param = re.fullmatch(rf'({_ID})=\{{\}}', arguments)
        if not param:
            continue
        request_calls = [(finish-len(param[1])-1, finish-1)
                         for _start, finish, args in _calls(request_body, request_mask, 'this.api.spinRequest')
                         if len(args) == 2 and args[1] == param[1]]
        if not request_calls:
            continue
        notifications = _notification_arguments(text, code, body, mask, request_body, request_mask, param[1], other_sources)
        if _selector_unchanged(request_mask, param[1], allowed_bare=request_calls+notifications):
            return True
    return False
