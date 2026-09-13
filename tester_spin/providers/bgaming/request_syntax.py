from __future__ import annotations

import json
import re
from typing import Any

_COMMAND = re.compile(r'(?:["\']?command["\']?)\s*:\s*["\']([A-Za-z_][A-Za-z0-9_.:-]{0,95})["\']')
_LITERAL = re.compile(r'^\s*(?:["\'](?P<s>[^"\']*)["\']|(?P<n>-?\d+(?:\.\d+)?)|(?P<b>true|false)|(?P<z>null))\s*$', re.I)


def _balanced_object(text: str, open_index: int, limit: int = 5000) -> str:
    if open_index < 0 or open_index >= len(text) or text[open_index] != '{':
        return ''
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
                return text[open_index + 1:index]
    return ''


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
    pattern = re.compile(r'\s*(?:["\']([^"\']+)["\']|([A-Za-z_$][A-Za-z0-9_$]*))\s*:\s*(.*?)\s*$', re.S)
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


def _wrapper_before(source: str, command_pos: int, parameter: str) -> str:
    before = source[max(0, command_pos - 1400):command_pos]
    patterns = (
        rf'([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s+)?\(?\s*{re.escape(parameter)}\s*\)?\s*=>[^;]{{0,1000}}$',
        rf'([A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*{re.escape(parameter)}\s*\)\s*\{{[^{{}}]{{0,1000}}$',
        rf'function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*{re.escape(parameter)}\s*\)\s*\{{[^{{}}]{{0,1000}}$',
    )
    for pattern in patterns:
        matches = list(re.finditer(pattern, before, re.S))
        if matches:
            return str(matches[-1].group(1))
    return ''


def _callsites(source: str, wrapper: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    exact: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    fields: list[str] = []
    if not wrapper:
        return exact, unresolved, fields
    for match in list(re.finditer(rf'(?:\.|\b){re.escape(wrapper)}\s*\(\s*\{{', source))[:96]:
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
            unresolved.append({'literal_options': literals, 'unresolved_fields': dynamic})
        else:
            exact.append({'options': literals})
    return exact, unresolved, fields


def scan_request_syntax(source: str) -> dict[str, dict[str, Any]]:
    """Find command/options request envelopes and follow one wrapper hop.

    This is static parsing only: it never evaluates JavaScript and never emits a
    request. It is intentionally provider-local and title-agnostic.
    """
    commands: dict[str, dict[str, Any]] = {}
    for occurrence in _COMMAND.finditer(source or ''):
        command = str(occurrence.group(1))
        row = commands.setdefault(command, {
            'hits': 0,
            'option_fields': [],
            'literal_variants': [],
            'unresolved_variants': [],
            'wrappers': [],
        })
        row['hits'] = int(row['hits']) + 1
        window = source[occurrence.start():min(len(source), occurrence.start() + 2600)]
        option = re.search(r'(?:["\']?options["\']?)\s*:\s*', window)
        if not option:
            continue
        tail = window[option.end():]
        if tail.startswith('{'):
            body = _balanced_object(tail, 0)
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
                row['unresolved_variants'].append({'literal_options': literals, 'unresolved_fields': dynamic})
            else:
                row['literal_variants'].append({'options': literals})
            continue

        forwarded = re.match(r'([A-Za-z_$][A-Za-z0-9_$]*)', tail)
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
        row['literal_variants'].extend(exact)
        row['unresolved_variants'].extend(unresolved)

    for row in commands.values():
        for key in ('literal_variants', 'unresolved_variants'):
            unique: list[dict[str, Any]] = []
            seen: set[str] = set()
            for item in row[key]:
                marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
                if marker not in seen:
                    seen.add(marker)
                    unique.append(item)
            row[key] = unique
    return commands


__all__ = ['scan_request_syntax']
