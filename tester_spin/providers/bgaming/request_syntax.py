from __future__ import annotations

import json
import re
from typing import Any

_COMMAND = re.compile(
    r'(?:["\']?command["\']?)\s*:\s*["\']([A-Za-z_][A-Za-z0-9_.:-]{0,95})["\']'
)
_LITERAL = re.compile(
    r'^\s*(?:["\'](?P<s>[^"\']*)["\']|(?P<n>-?\d+(?:\.\d+)?)|(?P<b>true|false)|(?P<z>null))\s*$',
    re.I,
)
_CALL_OBJECT = re.compile(
    r'(?P<callee>[A-Za-z_$][A-Za-z0-9_$]*(?:\s*\.\s*[A-Za-z_$][A-Za-z0-9_$]*)*)\s*\(\s*\{',
    re.S,
)


def _balanced_object_span(
    text: str,
    open_index: int,
    limit: int = 12000,
) -> tuple[int, str]:
    if open_index < 0 or open_index >= len(text) or text[open_index] != '{':
        return -1, ''
    quote = ''
    escaped = False
    depth = 0
    for index in range(open_index, min(len(text), open_index + limit)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = ''
            continue
        if char in "\"'":
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return index, text[open_index + 1:index]
    return -1, ''


def _balanced_object(text: str, open_index: int, limit: int = 12000) -> str:
    _close, body = _balanced_object_span(text, open_index, limit)
    return body


def _split_fields(body: str) -> list[tuple[str, str]]:
    chunks: list[str] = []
    start = 0
    quote = ''
    escaped = False
    depth = 0
    for index, char in enumerate(body):
        if quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = ''
            continue
        if char in "\"'":
            quote = char
        elif char in '([{':
            depth += 1
        elif char in ')]}' and depth:
            depth -= 1
        elif char == ',' and depth == 0:
            chunks.append(body[start:index])
            start = index + 1
    chunks.append(body[start:])

    result: list[tuple[str, str]] = []
    pattern = re.compile(
        r'\s*(?:["\']([^"\']+)["\']|([A-Za-z_$][A-Za-z0-9_$]*))\s*:\s*(.*?)\s*$',
        re.S,
    )
    for chunk in chunks:
        match = pattern.match(chunk)
        if match:
            result.append((str(match.group(1) or match.group(2)), str(match.group(3))))
    return result


def _literal(raw: str) -> tuple[bool, Any]:
    match = _LITERAL.match(raw)
    if not match:
        return False, None
    if match.group('s') is not None:
        return True, match.group('s')
    if match.group('n') is not None:
        text = str(match.group('n'))
        return True, float(text) if '.' in text else int(text)
    if match.group('b') is not None:
        return True, str(match.group('b')).lower() == 'true'
    return True, None


def _command_literal(raw: str) -> str:
    ok, value = _literal(raw)
    return str(value) if ok and isinstance(value, str) else ''


def _direct_call_envelope(
    source: str,
    command_pos: int,
    command: str,
) -> tuple[str, str] | None:
    """Return (callee, options expression) for a real call object.

    The command and options fields must be siblings in the *same object* and that
    object must be the direct object argument of a call. This prevents response
    payloads or configuration objects containing their own command/options keys
    from being mistaken for outbound request serializers.
    """
    start = max(0, command_pos - 1800)
    prefix = source[start:command_pos + 1]
    matches = list(_CALL_OBJECT.finditer(prefix))
    for match in reversed(matches):
        open_index = start + match.end() - 1
        close_index, body = _balanced_object_span(source, open_index)
        if close_index < 0 or not (open_index < command_pos < close_index):
            continue
        fields = _split_fields(body)
        command_value = ''
        options_raw: str | None = None
        for field, raw in fields:
            if field == 'command':
                command_value = _command_literal(raw)
            elif field == 'options':
                options_raw = raw.strip()
        if command_value != command or options_raw is None:
            continue
        callee = re.sub(r'\s+', '', str(match.group('callee') or ''))
        return callee, options_raw
    return None


def _wrapper_before(source: str, command_pos: int, parameter: str) -> str:
    before = source[max(0, command_pos - 1800):command_pos]
    patterns = (
        rf'([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s+)?\(?\s*{re.escape(parameter)}\s*\)?\s*=>[^;]{{0,1400}}$',
        rf'([A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*{re.escape(parameter)}\s*\)\s*\{{[^{{}}]{{0,1400}}$',
        rf'function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*{re.escape(parameter)}\s*\)\s*\{{[^{{}}]{{0,1400}}$',
    )
    for pattern in patterns:
        matches = list(re.finditer(pattern, before, re.S))
        if matches:
            return str(matches[-1].group(1))
    return ''


def _callsites(
    source: str,
    wrapper: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    exact: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    fields: list[str] = []
    if not wrapper:
        return exact, unresolved, fields
    pattern = re.compile(rf'(?:\.|\b){re.escape(wrapper)}\s*\(\s*\{{')
    for match in list(pattern.finditer(source))[:128]:
        open_index = source.find('{', match.start(), min(len(source), match.end() + 3))
        body = _balanced_object(source, open_index)
        if not body:
            continue
        literals: dict[str, Any] = {}
        dynamic: list[str] = []
        for field, raw in _split_fields(body):
            if field not in fields:
                fields.append(field)
            ok, value = _literal(raw)
            if ok:
                literals[field] = value
            else:
                dynamic.append(field)
        if dynamic:
            unresolved.append(
                {'literal_options': literals, 'unresolved_fields': dynamic}
            )
        else:
            exact.append({'options': literals})
    return exact, unresolved, fields


def _append_unique(target: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    seen = {
        json.dumps(item, ensure_ascii=False, sort_keys=True)
        for item in target
        if isinstance(item, dict)
    }
    for item in rows:
        marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            target.append(item)


def scan_request_syntax(source: str) -> dict[str, dict[str, Any]]:
    """Find outbound-looking command/options call envelopes statically.

    A hit is accepted only when command and options are sibling fields in the
    same object passed directly to a function/method call. If options forwards a
    local parameter, one wrapper hop is followed to object-literal callsites.

    No JavaScript is evaluated and no network request is emitted.
    """
    commands: dict[str, dict[str, Any]] = {}
    for occurrence in _COMMAND.finditer(source or ''):
        command = str(occurrence.group(1))
        envelope = _direct_call_envelope(source, occurrence.start(), command)
        if envelope is None:
            continue
        callee, options_raw = envelope

        row = commands.setdefault(
            command,
            {
                'hits': 0,
                'option_fields': [],
                'literal_variants': [],
                'unresolved_variants': [],
                'wrappers': [],
                'callees': [],
            },
        )
        row['hits'] = int(row['hits']) + 1
        if callee and callee not in row['callees']:
            row['callees'].append(callee)

        if options_raw.startswith('{'):
            body = _balanced_object(options_raw, 0)
            literals: dict[str, Any] = {}
            dynamic: list[str] = []
            for field, raw in _split_fields(body):
                if field not in row['option_fields']:
                    row['option_fields'].append(field)
                ok, value = _literal(raw)
                if ok:
                    literals[field] = value
                else:
                    dynamic.append(field)
            if dynamic:
                _append_unique(
                    row['unresolved_variants'],
                    [{'literal_options': literals, 'unresolved_fields': dynamic}],
                )
            else:
                _append_unique(row['literal_variants'], [{'options': literals}])
            continue

        forwarded = re.match(r'([A-Za-z_$][A-Za-z0-9_$]*)\b', options_raw)
        if not forwarded:
            continue
        parameter = str(forwarded.group(1))
        wrapper = _wrapper_before(source, occurrence.start(), parameter)
        if wrapper and wrapper not in row['wrappers']:
            row['wrappers'].append(wrapper)
        exact, unresolved, fields = _callsites(source, wrapper)
        for field in fields:
            if field not in row['option_fields']:
                row['option_fields'].append(field)
        _append_unique(row['literal_variants'], exact)
        _append_unique(row['unresolved_variants'], unresolved)

    return commands


__all__ = ['scan_request_syntax']
