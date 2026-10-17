"""Offline NGM declarations from captured client code and JMM, never replay."""
import ast
import base64
import hashlib
import json
import re
import warnings
from urllib.parse import urlsplit

from .client_sources import _function_bodies

NAME = r'[A-Za-z_$][\w$]*'
STRING = r"(?:'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")"
MAX_BODY = 8*1024*1024


def _constants(source):
    constants = {}
    for match in re.finditer(r'(?<![\w$])('+NAME+r')=('+STRING+r')', source):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', SyntaxWarning)
                literal = ast.literal_eval(match[2])
            constants.setdefault(match[1], set()).add(literal)
        except (ValueError, SyntaxError):
            pass
    return constants


def source_declarations(source):
    constants = _constants(source)
    concrete = {match[1] for match in re.finditer(
        NAME+r'\((\d+),\d+,(?:\{[^{}]*\}|'+NAME+r'),'+NAME+r'\)', source)}
    rows = []
    for match in re.finditer(NAME+r"\(("+NAME+r"),['\"]([^'\"]+Request)['\"],(\d+),[^;()]*\)", source):
        values = constants.get(match[1], set())
        rows.append(dict(name=match[2], namespace=next(iter(values)) if len(values) == 1 else None,
                         concrete=match[3] in concrete))
    platform_namespaces = {row['namespace'] for row in rows
                           if row['name'] == 'PlatformRequest' and row['namespace']}
    for row in rows:
        row['channel'] = 'platform' if row['namespace'] and any(
            row['namespace'] == prefix or row['namespace'].startswith(prefix+'.')
            for prefix in platform_namespaces) else 'wire_or_unbound'
    return rows


def request_catalog(source):
    """Class + constructor + serializer bindings, with unbound fields explicit."""
    if len(source.encode('utf-8')) > MAX_BODY:
        return []
    functions = _function_bodies(source)
    constants = _constants(source)
    registrations = {}
    for match in re.finditer(NAME+r'\((\d+),\d+,(?:\{[^{}]*\}|'+NAME+r'),('+NAME+r')\)', source):
        registrations.setdefault(match[1], set()).add(match[2])
    declarations = {}
    for match in re.finditer(NAME+r"\([^;()]*['\"]([^'\"]+Request)['\"],(\d+),[^;()]*\)", source):
        declarations.setdefault(match[1], set()).add(match[2])
    rows = []
    for label, type_ids in declarations.items():
        if len(type_ids) != 1:
            continue
        type_id = next(iter(type_ids))
        constructors = registrations.get(type_id, set())
        if len(constructors) != 1:
            continue
        constructor = next(iter(constructors))
        body = functions.get(constructor, ([], ''))[1]
        ids = re.findall(r'\.call\(this,'+NAME+r'\((\d+)\)\)', body)
        if len(ids) != 1:
            continue
        serializers = [(fn, args, body) for fn, (args, body) in functions.items()
                       if len(args) == 2 and re.search(NAME+r'\('+re.escape(args[0])+','+type_id+r'\)', body)]
        if len(serializers) != 1:
            continue
        serializer, args, body = serializers[0]
        aliases = re.findall(r'\b('+NAME+r')='+re.escape(args[0])+r';', body)
        if len(aliases) != 1:
            continue
        fields, declared, unresolved = {}, set(), set()
        recognized_output_uses = set()
        for call in re.finditer(NAME+r'\('+re.escape(args[1])+r',('+STRING+'|'+NAME+r'),', body):
            recognized_output_uses.add(body.index('('+args[1]+',', call.start())+1)
            token = call[1]
            if token.startswith(('"', "'")):
                semantic = ast.literal_eval(token)
            elif len(constants.get(token, set())) == 1:
                semantic = next(iter(constants[token]))
            else:
                unresolved.add(token)
                continue
            declared.add(semantic)
            prefix = body[:call.start()]
            assignment = re.search(r'('+NAME+r')=(?:'+NAME+r'\()?'+re.escape(aliases[0])+
                                   r'\.('+NAME+r')\)?;(?:\1!=null|!!\1)&&$', prefix)
            if assignment is None:
                array_arg = re.match(r'('+NAME+r')\)', body[call.end():])
                if array_arg:
                    assignment = re.search(r'('+NAME+r')='+re.escape(aliases[0])+r'\.('+NAME+
                        r');if\(\1!=null\)\{('+NAME+r')=\1;'+re.escape(array_arg[1])+r'=new '+NAME+
                        r'(?:\(\))?;[^{}]{0,128}for\('+NAME+r'=\3\.'+NAME+r'\(\);[^{}]{0,128}\)\{([^{}]{0,256})\}$', prefix)
                    if assignment and not re.search(NAME+r'\('+re.escape(array_arg[1])+',', assignment[4]):
                        assignment = None
            if assignment:
                previous = fields.get(semantic)
                if previous is not None and previous != assignment[2]:
                    unresolved.add(semantic)
                else:
                    fields[semantic] = assignment[2]
        masked = re.sub(STRING, lambda match: ' '*len(match[0]), body)
        output_uses = {match.start() for match in re.finditer(
            r'(?<![\w$.])'+re.escape(args[1])+r'(?![\w$])', masked)}
        if output_uses-recognized_output_uses:
            unresolved.add('OUTPUT_USE_UNBOUND')
        for key in unresolved:
            fields.pop(key, None)
        rows.append(dict(name=label, message_id=int(ids[0]), class_id=int(type_id),
            constructor=constructor, serializer=serializer, fields=fields,
            declared_fields=sorted(declared), unresolved_fields=sorted((declared-set(fields)) | unresolved)))
    counts = {}
    for row in rows:
        counts[row['constructor']] = counts.get(row['constructor'], 0)+1
    return sorted((row for row in rows if counts[row['constructor']] == 1),
                  key=lambda row: (row['message_id'], row['name']))


def functional_manifest(document, code):
    config = document.get('config') if isinstance(document, dict) else None
    if not isinstance(config, dict) or config.get('game_code') != code:
        raise ValueError('NGM_MANIFEST_IDENTITY_MISMATCH')
    controls, math_resources = [], []
    config = dict(config)
    # Mathematical tables remain in the original HAR. Keep betting/menu
    # declarations inline; these references remove neither fields nor provenance.
    for key in ('reels', 'wild_state_to_reel_weights', 'fs_sequences_weights', 'paytable'):
        if key in config:
            encoded = json.dumps(config[key], ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            if len(encoded) > 4096:
                ref = '/config/'+key
                math_resources.append(dict(source_ref=ref, bytes=len(encoded), sha256=hashlib.sha256(encoded).hexdigest()))
                config[key] = dict(source_ref=ref)
    visual = {'pos', 'size', 'format', 'background', 'slice', 'slices', 'animations', 'animation', 'content'}

    def walk(value, path):
        if isinstance(value, dict):
            kind = value.get('type', '')
            if isinstance(kind, str) and ('button' in kind or any(k in value for k in ('action', 'command', 'choices', 'options'))):
                controls.append(dict(ref=path, **{k: v for k, v in value.items() if k not in visual and k != 'ref'}))
            for key, child in value.items():
                walk(child, path+'/'+str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, path+'/'+str(index))

    for root in ('ui', 'scenes'):
        walk(document.get(root, {}), '/'+root)
    return dict(game_code=code, configuration=config, controls=controls, math_resources=math_resources,
                inventory_state='UNKNOWN', control_presence_is_not_purchase_evidence=True)


def passive_request_roles(catalog):
    """Observe reviewed non-entry messages, never execute them or infer prices."""
    metadata = {'windowId', 'ID', 'umid'}
    contracts = {'LogUserPreferencesRequest': ('aux', metadata | {'value'}),
                 'StartBonusGameRequest': ('continuation', metadata)}
    roles = {}
    for row in catalog:
        spec = contracts.get(row['name'])
        if not spec or row.get('unresolved_fields'):
            continue
        declared = set(row.get('declared_fields', []))
        if declared and declared <= spec[1] and declared == set(row.get('fields', {})):
            roles[row['name']] = spec[0]
    return roles


def _body(entry):
    content = entry.get('response', {}).get('content', {})
    text = content.get('text')
    if not isinstance(text, str) or len(text) > MAX_BODY*2:
        raise ValueError('NGM_BODY_MISSING_OR_TOO_LARGE')
    if content.get('encoding') == 'base64':
        raw = base64.b64decode(text, validate=True)
        if len(raw) > MAX_BODY:
            raise ValueError('NGM_BODY_TOO_LARGE')
        text = raw.decode('utf-8')
    elif content.get('encoding') not in (None, ''):
        raise ValueError('NGM_BODY_ENCODING_UNSUPPORTED')
    if len(text.encode('utf-8')) > MAX_BODY:
        raise ValueError('NGM_BODY_TOO_LARGE')
    declared_size = content.get('size')
    if type(declared_size) is int and declared_size > len(text.encode('utf-8')):
        raise ValueError('NGM_BODY_TRUNCATED')
    return text


def analyze_har(har, code):
    """Report only; imports no captured sessions and makes no network calls."""
    sources, manifests, unresolved = [], [], []
    for index, entry in enumerate(har.get('log', {}).get('entries', [])):
        parsed = urlsplit(entry.get('request', {}).get('url', ''))
        if parsed.scheme != 'https' or parsed.hostname != 'cachedownload.playtechone.com':
            continue
        if '/ngmdistributed/' not in parsed.path or '/'+code+'/' not in parsed.path:
            continue
        if entry.get('response', {}).get('status') != 200:
            continue
        ref = 'http:'+str(index)
        try:
            if parsed.path.endswith('.cache.js'):
                source = _body(entry)
                catalog = request_catalog(source)
                if catalog:
                    declarations = source_declarations(source)
                    sources.append((ref, source, catalog, declarations))
                    names = {row['name'] for row in declarations if row['concrete'] and row['channel'] != 'platform'}
                    unresolved.extend('NGM_REQUEST_CONTRACT_UNBOUND:'+name
                                      for name in sorted(names-{row['name'] for row in catalog}))
            elif parsed.path.endswith('.jmm'):
                document = json.loads(_body(entry))
                if isinstance(document, dict) and isinstance(document.get('config'), dict):
                    manifests.append((ref, functional_manifest(document, code)))
        except (ValueError, UnicodeError, TypeError) as exc:
            unresolved.append(ref+':'+str(exc))
    report = dict(schema='tester-spin/ngm-static-contracts/v1', game_code=code,
                  network_used=False, scripts_executed=False, certifies_game_ok=False,
                  request_count=0, unresolved=unresolved)
    if len(sources) == 1:
        ref, source, catalog, declarations = sources[0]
        report.update(source_ref=ref, source_sha256=hashlib.sha256(source.encode('utf-8')).hexdigest(),
                      requests=catalog, request_count=len(catalog), source_declarations=declarations)
    else:
        unresolved.append('NGM_CLIENT_SOURCE_MISSING' if not sources else 'NGM_CLIENT_SOURCE_AMBIGUOUS')
    if len(manifests) == 1:
        report.update(manifest_ref=manifests[0][0], manifest=manifests[0][1])
    else:
        unresolved.append('NGM_MANIFEST_MISSING' if not manifests else 'NGM_MANIFEST_AMBIGUOUS')
    return report


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Extract NGM declarations offline; never sends wagers.')
    parser.add_argument('har', type=Path)
    parser.add_argument('--code', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.suffix.lower() != '.json' or args.out.resolve() == args.har.resolve() or (
            args.out.exists() and args.har.samefile(args.out)):
        parser.error('Output must be a separate JSON report; the source HAR is never replaced')
    if args.har.stat().st_size > 256*1024*1024:
        parser.error('HAR exceeds 256 MiB')
    report = analyze_har(json.loads(args.har.read_text(encoding='utf-8-sig')), args.code)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(output=str(args.out.resolve()), request_count=report['request_count'], unresolved=report['unresolved'])))


if __name__ == '__main__':
    main()
