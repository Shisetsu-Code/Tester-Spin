"""Bounded static recognition of GPAS command families; never executes JS.

Wire shape alone is useful to audit a capture. A new executable family also
needs its current policy, context dispatch, and bootstrap path to agree.
The Quickspin recognizer accepts the observed static structure, with captured
private identifiers, and rejects unsupported/dynamic alternatives.
"""
import ast
import re
from functools import lru_cache

COROSIN_CLASS = 'com.pt.gpas.platform.game.OgwCorosinGameCommand'
QUICKSPIN_CLASS = 'quickspin.game.playMoney'
_IDENT = re.compile(r'[A-Za-z_$][\w$]*\Z')
_LEX = re.compile(
    r'''\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|[A-Za-z_$][\w$]*|\d+(?:\.\d+)?|===|!==|=>|\+\+|--|&&|\|\||==|!=|\+=|-=|[^\s]''')
_REGEXP_PREFIX = {'=', '(', '[', '{', ',', ':', ';', '?', '!', '~', '+', '-', '*',
                  '&&', '||', '=>', 'return', 'throw', 'case', 'typeof', 'void', 'delete'}


def _regexp_end(source, start):
    in_class = escaped = False
    for index in range(start + 1, len(source)):
        char = source[index]
        if char in '\r\n':
            return None
        if escaped:
            escaped = False
        elif char == '\\':
            escaped = True
        elif char == '[':
            in_class = True
        elif char == ']':
            in_class = False
        elif char == '/' and not in_class:
            end = index + 1
            while end < len(source) and source[end].isascii() and source[end].isalpha():
                end += 1
            return end
    return None


def _tokens(source):
    if len(source) > 8 * 1024 * 1024:
        return []
    result = []
    position = 0
    while position < len(source):
        match = _LEX.match(source, position)
        if match is None:
            return []
        position = match.end()
        token = match[0]
        if token.isspace() or token.startswith(('//', '/*')):
            continue
        if token == '/' and (not result or result[-1] in _REGEXP_PREFIX):
            end = _regexp_end(source, match.start())
            if end is not None:
                result.append('regexp:' + source[match.start():end])
                position = end
                continue
        if token.startswith(('"', "'")):
            try:
                token = 'string:' + ast.literal_eval(token)
            except (ValueError, SyntaxError):
                token = 'opaque:' + token
        elif token.startswith('`'):
            token = 'template:' + token
        result.append(token)
    return result


@lru_cache(maxsize=128)
def _pattern(source):
    return _tokens(source)


def _match(tokens, start, pattern, bindings=None):
    wanted = _pattern(pattern)
    if start + len(wanted) > len(tokens):
        return None
    values = dict(bindings or {})
    for actual, expected in zip(tokens[start:start + len(wanted)], wanted):
        template = re.fullmatch(r'template:`\$\{(\$[A-Za-z_][\w$]*)\}`', expected)
        if template:
            expression = re.fullmatch(r'template:`\$\{([A-Za-z_$][\w$]*)\}`', actual)
            if expression is None:
                return None
            expected, actual = template[1], expression[1]
        if expected.startswith('$'):
            if not _IDENT.fullmatch(actual):
                return None
            if expected in values and values[expected] != actual:
                return None
            values[expected] = actual
        elif actual != expected:
            return None
    return values


def _root_indexes(tokens):
    closing = {'{': '}', '(': ')', '[': ']'}
    stack = []
    for index, token in enumerate(tokens):
        if not stack:
            yield index
        if token in closing:
            stack.append(closing[token])
        elif token in closing.values():
            if not stack or stack.pop() != token:
                return


def _find(tokens, pattern, bindings=None, *, root=False):
    indexes = _root_indexes(tokens) if root else range(len(tokens))
    for index in indexes:
        if root and index and tokens[index - 1] not in (';', '}'):
            continue
        if root and tokens[index] in ('return', 'throw'):
            # Later statements in this body cannot establish an active path.
            return
        found = _match(tokens, index, pattern, bindings)
        if found is not None:
            yield index, found


def _end(tokens, start):
    opening = tokens[start] if start < len(tokens) else None
    closing = {'{': '}', '(': ')', '[': ']'}.get(opening)
    if closing is None:
        return None
    depth = 1
    for index in range(start + 1, len(tokens)):
        if tokens[index] == opening:
            depth += 1
        elif tokens[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    return None


def _program(tokens):
    # Current assets are a UMD factory called directly or registered with AMD.
    # Only this explicit envelope is unwrapped. An unused function / false
    # branch containing the same literals is not an active program root.
    prefix = '''(function($factory){typeof define==="function"&&define.amd?
                define($factory):$factory();})(function(){'''
    if _match(tokens, 0, prefix) is not None:
        start = len(_pattern(prefix)) - 1
        end = _end(tokens, start)
        if end is not None and tokens[end + 1:] == [')', ';']:
            return tokens[start + 1:end]
        return []
    return tokens


def _declarations(tokens):
    classes, functions = {}, {}
    for index in _root_indexes(tokens):
        if index and tokens[index - 1] in ('=', ',', ':', '('):
            # Names of class/function expressions belong to those expressions,
            # not to the program's declaration environment.
            continue
        if tokens[index] == 'class' and index + 2 < len(tokens):
            name = tokens[index + 1]
            if not _IDENT.fullmatch(name):
                continue
            start = index + 2
            if tokens[start] == '{':
                end = _end(tokens, start)
                if end is not None:
                    if name in classes:
                        return {}, {}
                    classes[name] = tokens[start + 1:end]
        elif tokens[index] == 'function' and index + 2 < len(tokens):
            name = tokens[index + 1]
            if not _IDENT.fullmatch(name) or tokens[index + 2] != '(':
                continue
            args_end = _end(tokens, index + 2)
            if args_end is None or args_end + 1 >= len(tokens) or tokens[args_end + 1] != '{':
                continue
            end = _end(tokens, args_end + 1)
            if end is not None:
                if name in functions:
                    return {}, {}
                functions[name] = (tokens[index + 3:args_end], tokens[args_end + 2:end])
    return classes, functions


def _methods(tokens):
    result = {}
    for index in _root_indexes(tokens):
        if not _IDENT.fullmatch(tokens[index]) or index + 1 >= len(tokens) or tokens[index + 1] != '(':
            continue
        args_end = _end(tokens, index + 1)
        if args_end is None or args_end + 1 >= len(tokens) or tokens[args_end + 1] != '{':
            continue
        end = _end(tokens, args_end + 1)
        if end is not None:
            if tokens[index] in result:
                return {}
            result[tokens[index]] = tokens[index + 2:args_end], tokens[args_end + 2:end]
    return result


_POLICY = '''if($info.roundInProgress){
    GLU.game.playOut($command,{ID:48775,parameters:null});
}else{GLU.game.report.stake($info.roundCost);
    GLU.game.playMoney($command,{ID:40021,parameters:null},$info.featureType);}'''
_DISPATCH = '''this.$policies.get($get_context()).play({
    roundInProgress:this.$continuing,roundCost:$get_cost(),featureType:$get_feature()});'''
_COLLECTOR = '''const $result=new Set();let $prefix=$name;
    if($options.includes($prefix)){$result.add($prefix);let $more=true;let $index=2;
      while($more){if($options.includes($prefix+$index)){
        $result.add($prefix+$index);$index++;
      }else{$more=false;}}}return $result;'''
_OPTIONS_GETTER = '''const $output=[];$parse();
    if($domain.size>0){$domain.forEach(($option)=>{
      const cost=$get_cost($option);
      const $descriptor={enabled:$enabled($option),cost};
      $output.push($descriptor);
    });}return $output;'''
_OPTION_MATCHER = '''const $config=$configs.get($context()).get("default");
    const $options=$config.game.activeBetOptions;let $found="";
    $options.forEach(($option)=>{let $remaining=$option;let $count=0;
      $requested.forEach(($item)=>{
        const $name=$item.featureName+($item.option===1?"":$item.option);
        let $regexp=new RegExp(`${$name}`,"i");
        if($remaining.match($regexp)){$remaining=$remaining.replace($regexp,"");$count++;}
      });
      if($remaining===""&&$count===$requested.length){$found=$option;}
    });return $found;'''


def _getter(functions, name):
    spec = functions.get(name)
    if spec and not spec[0] and len(spec[1]) == 3:
        match = _match(spec[1], 0, 'return $value;')
        return match.get('$value') if match else None
    return None


def _bootstrap_bound(program, functions, bridge_class):
    for factory, (args, body) in functions.items():
        if len(args) != 1:
            continue
        wanted = '''switch($type){case "qs":case "gpas":
                    $instance=new $bridge();break;}'''
        match = _match(body, 0, wanted, {'$type': args[0], '$bridge': bridge_class})
        if match is None or len(body) != len(_pattern(wanted)):
            continue
        getters = [name for name in functions if _getter(functions, name) == match['$instance']]
        for getter in getters:
            for bootstrap, (_, boot_body) in functions.items():
                if not list(_find(boot_body, '$factory("gpas");', {'$factory': factory}, root=True)):
                    continue
                for _, value in _find(boot_body, 'const $bridge=$get();', {'$get': getter}, root=True):
                    if not list(_find(boot_body, '$bridge.bootstrap();', value, root=True)):
                        continue
                    # Invocation must be at the active factory/program root.
                    if list(_find(program, '$boot({', {'$boot': bootstrap}, root=True)):
                        return True
    return False


def _feature_activation(methods, functions, get_context, get_feature):
    """Prove that the bridge writes the same selector its money policy reads."""
    activation = methods.get('setActivateFeature')
    if not activation or len(activation[0]) != 1:
        return None
    activate_path = '''$activate($options);this.$update($context());
        this.$events.dispatchEvent($event_names.BET_MODE_UPDATED);'''
    bound = _match(activation[1], 0, activate_path,
                   {'$options': activation[0][0], '$context': get_context})
    if bound is None or len(activation[1]) != len(_pattern(activate_path)):
        return None
    handler = functions.get(bound['$activate'])
    if not handler or len(handler[0]) != 1:
        return None
    normalize = '''if(!Array.isArray($options)){$options=[$options];}
        let $type=$match($options);$set($type||"default");'''
    called = _match(handler[1], 0, normalize, {'$options': handler[0][0]})
    if called is None or len(handler[1]) != len(_pattern(normalize)):
        return None
    setter = functions.get(called['$set'])
    target = _getter(functions, get_feature)
    if not setter or len(setter[0]) != 1 or not target:
        return None
    if _match(setter[1], 0, '$target=$value;',
              {'$target': target, '$value': setter[0][0]}) is None or len(setter[1]) != 4:
        return None
    matcher = functions.get(called['$match'])
    if not matcher or len(matcher[0]) != 1 or len(matcher[1]) != len(_pattern(_OPTION_MATCHER)):
        return None
    return _match(matcher[1], 0, _OPTION_MATCHER,
                  {'$requested': matcher[0][0], '$context': get_context})


def _feature_getters(methods, functions):
    exposed = methods.get('getAvailableFeatureConfig')
    if not exposed or len(exposed[0]) != 1:
        return {}
    forwarding = 'return $api($feature);'
    call = _match(exposed[1], 0, forwarding, {'$feature': exposed[0][0]})
    if call is None or len(exposed[1]) != len(_pattern(forwarding)):
        return {}
    api = functions.get(call['$api'])
    if not api or len(api[0]) != 1:
        return {}
    prefix = 'let $output;switch($feature){'
    dispatch = _match(api[1], 0, prefix, {'$feature': api[0][0]})
    if dispatch is None:
        return {}
    start = len(_pattern(prefix)) - 1
    end = _end(api[1], start)
    if end is None or api[1][end + 1:] != ['return', dispatch['$output'], ';']:
        return {}
    cases = api[1][start + 1:end]
    result = {}
    position = 0
    case = 'case $name:$output=$getter();break;'
    fallback = 'default:$output=[];break;'
    while position < len(cases):
        branch = _match(cases, position, case, dispatch)
        if branch is not None:
            if branch['$name'] in result:
                return {}
            result[branch['$name']] = branch['$getter']
            position += len(_pattern(case))
        elif _match(cases, position, fallback, dispatch) is not None and position + len(_pattern(fallback)) == len(cases):
            return result
        else:
            return {}
    return {}


def _feature_prefixes(program, functions, methods, get_context, get_feature):
    activation = _feature_activation(methods, functions, get_context, get_feature)
    if activation is None:
        return {}
    getters = _feature_getters(methods, functions)
    collectors = {}
    for name, (args, body) in functions.items():
        if len(args) == 3 and args[1] == ',':
            match = _match(body, 0, _COLLECTOR, {'$name': args[0], '$options': args[2]})
            if match is not None and len(body) == len(_pattern(_COLLECTOR)):
                collectors[name] = True
    result = {}
    for prefix, kind in (('buyFeature', 'PURCHASE'), ('extraBet', 'ANTE_BET')):
        declaration = 'const $prefix=' + repr(prefix) + ';'
        for _, constant in _find(program, declaration, root=True):
            getter = functions.get(getters.get(constant['$prefix']))
            if not getter or getter[0] or len(getter[1]) != len(_pattern(_OPTIONS_GETTER)):
                continue
            consumed = _match(getter[1], 0, _OPTIONS_GETTER)
            parser = functions.get(consumed['$parse']) if consumed else None
            if not parser or parser[0]:
                continue
            pattern = '''const $config=$configs.get($context()).get("default");
                         const $options=$config.game.activeBetOptions;'''
            context = _match(parser[1], 0, pattern,
                             {'$context': get_context, '$configs': activation['$configs']})
            if context is None:
                continue
            # Only the observed collector assignments may follow the read.
            # Overwrites or later filters invalidate the domain certificate.
            statement = '$domain=$collector($prefix,$options);'
            position = len(_pattern(pattern))
            domains = {}
            while position < len(parser[1]):
                assignment = _match(parser[1], position, statement,
                                    {'$options': context['$options']})
                if assignment is None or assignment['$domain'] in domains:
                    domains = {}
                    break
                domains[assignment['$domain']] = assignment
                position += len(_pattern(statement))
            domain = domains.get(consumed['$domain'])
            if domain and domain['$prefix'] == constant['$prefix'] and domain['$collector'] in collectors:
                result[prefix] = kind
    return result


def _policy_map_bound(bridge_body, methods, binding):
    """Account for every reference to the private policy map in its class.

    Its only supported uses are one construction, the context registrations,
    and the already bound dispatch. An extra mutation, alias escape, or computed
    member access cannot silently preserve a certificate for an earlier set().
    """
    if 'string:' + binding['$policies'] in bridge_body:
        return False
    reference = 'this.$policies'
    all_references = {index for index, _ in _find(bridge_body, reference, binding)}
    accounted = 0
    for name, (_, body) in methods.items():
        references = {index for index, _ in _find(body, reference, binding)}
        permitted = set()
        if name == 'constructor':
            permitted = {index for index, _ in _find(body, 'this.$policies=new Map();', binding, root=True)}
            if len(permitted) != 1:
                return False
        elif name == 'bootstrap':
            default = 'this.$policies.set($contexts.Context.Default,new $policy());'
            permitted = {index for index, _ in _find(body, default, binding, root=True)}
            if len(permitted) != 1:
                return False
            freespin = 'this.$policies.set($contexts.Context.Freespin,new $free_policy());'
            other_context = {index for index, _ in _find(body, freespin, binding, root=True)}
            if len(other_context) > 1:
                return False
            permitted.update(other_context)
        elif name == 'requestGameData':
            permitted = {index for index, _ in _find(body, _DISPATCH, binding)}
            if len(permitted) != 1:
                return False
        if references != permitted:
            return False
        accounted += len(references)
    return accounted == len(all_references)


def _quickspin_binding(source):
    program = _program(_tokens(source))
    classes, functions = _declarations(program)
    bindings = []
    for _, alias in _find(program, 'const $command="quickspin.game.playMoney";', root=True):
        for policy_name, policy_body in classes.items():
            play = _methods(policy_body).get('play')
            if not play or len(play[0]) != 1 or len(play[1]) != len(_pattern(_POLICY)):
                continue
            policy = _match(play[1], 0, _POLICY, dict(alias, **{'$info': play[0][0]}))
            if policy is None:
                continue
            for bridge_name, bridge_body in classes.items():
                methods = _methods(bridge_body)
                bootstrap = methods.get('bootstrap')
                request = methods.get('requestGameData')
                constructor = methods.get('constructor')
                if not bootstrap or not request or not constructor:
                    continue
                registration = '''this.$policies.set($contexts.Context.Default,new $policy());'''
                registrations = list(_find(bootstrap[1], registration, root=True))
                if len(registrations) != 1 or registrations[0][1]['$policy'] != policy_name:
                    continue
                for _, registered in registrations:
                    if not list(_find(constructor[1], 'this.$policies=new Map();', registered, root=True)):
                        continue
                    wrapper = 'return new Promise(($resolve,$reject)=>{'
                    if _match(request[1], 0, wrapper) is None:
                        continue
                    start = len(_pattern(wrapper)) - 1
                    end = _end(request[1], start)
                    if end is None or request[1][end + 1:] != [')', ';']:
                        continue
                    callback = request[1][start + 1:end]
                    for _, dispatch in _find(callback, _DISPATCH, registered, root=True):
                        if not _policy_map_bound(bridge_body, methods, dispatch):
                            continue
                        context = _getter(functions, dispatch['$get_context'])
                        feature = _getter(functions, dispatch['$get_feature'])
                        if not context or not feature:
                            continue
                        if not list(_find(program, 'let $current=$contexts.Context.Default;',
                                          dict(dispatch, **{'$current': context}), root=True)):
                            continue
                        if not list(_find(program, 'let $current="default";', {'$current': feature}, root=True)):
                            continue
                        if _bootstrap_bound(program, functions, bridge_name):
                            bindings.append(_feature_prefixes(program, functions, methods,
                                dispatch['$get_context'], dispatch['$get_feature']))
    if len(bindings) > 1:
        raise ValueError('CLIENT_COMMAND_BINDING_AMBIGUOUS')
    return bindings[0] if bindings else None


def source_command_family(manifest, sources):
    """Return source-certified wire metadata, preserving existing Corosin checks."""
    text = '\n'.join(sources)
    corosin = COROSIN_CLASS in text and all(re.search(r'\b' + str(n) + r'\b', text)
                                            for n in (40021, 48775))
    quickspin = [_quickspin_binding(source) for source in sources if QUICKSPIN_CLASS in source]
    quickspin = [binding for binding in quickspin if binding is not None]
    if len(quickspin) > 1 or (quickspin and corosin):
        raise ValueError('CLIENT_COMMAND_BINDING_AMBIGUOUS')
    if not quickspin and not corosin:
        raise ValueError('CLIENT_COMMAND_BINDING_UNKNOWN')
    setup = manifest.get('setup', {})
    legacy = setup.get('usesLegacyBetApi')
    if quickspin:
        if legacy is True or not (legacy is False or setup.get('useExtendedBetApi') is True):
            raise ValueError('CLIENT_BET_API_UNKNOWN')
        dialect, command_class = 'modern', QUICKSPIN_CLASS
        family, feature_prefixes = 'quickspin-modern', quickspin[0]
    else:
        if legacy is True and 'GLU.game.bet' in text and 'stakeCostUuid' in text:
            dialect = 'legacy'
        elif legacy is not True and 'GLU.game.playMoney' in text and (
                legacy is False or setup.get('useExtendedBetApi') is True or 'GLU.game.bet' not in text):
            dialect = 'modern'
        else:
            raise ValueError('CLIENT_BET_API_UNKNOWN')
        family, command_class, feature_prefixes = 'corosin-' + dialect, COROSIN_CLASS, {}
    return {'command_family': family, 'dialect': dialect, 'class': command_class,
            'entry_id': 40021, 'continuation_id': 48775,
            'command_binding_validated': True, 'binding_source': 'current_client_source',
            'feature_prefix_bindings': feature_prefixes}
