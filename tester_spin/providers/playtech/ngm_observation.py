"""Static observation bindings for NGM offline clients; never evaluates source.

Bindings describe non-pausing logpoints in a freshly loaded official demo.
They do not authorize wagers or certify the purchase inventory/round closure.
"""
import re
from .client_sources import _function_bodies

NAME = r"[A-Za-z_$][\w$]*"


def spin_action_binding(source):
    """Find the declared UI SpinEvent and its unique live event dispatcher."""
    declarations = list(re.finditer(
        r"\b"+NAME+r"\([^;()]*['\"]SpinEvent['\"],(\d+),[^;()]*\)", source))
    if len(declarations) != 1:
        return None
    registrations = list(re.finditer(NAME+r"\("+declarations[0][1]+
        r",\d+,(?:\{[^{}]*\}|"+NAME+r"),("+NAME+r")\)", source))
    if len(registrations) != 1:
        return None
    constructor = registrations[0][1]
    dispatchers = set(re.findall(r"\b("+NAME+r")\(new "+re.escape(constructor)+r"(?:\(\))?\)", source))
    if len(dispatchers) != 1:
        return None
    dispatcher = dispatchers.pop()
    args, body = _function_bodies(source).get(dispatcher, ([], ''))
    if len(args) != 1 or not re.fullmatch(NAME+r"\("+NAME+","+re.escape(args[0])+r"\)", body):
        return None
    header = re.search(r"function "+re.escape(dispatcher)+r"\([^)]*\)\{", source)
    if not header:
        return None
    offset = header.end()
    return dict(constructor=constructor, function=dispatcher,
                lineNumber=source.count('\n', 0, offset),
                columnNumber=offset-source.rfind('\n', 0, offset)-1)


def spin_request_contract(source):
    """Bind opaque fields through the client's named class and serializer."""
    functions = _function_bodies(source)
    declarations = list(re.finditer(
        r"\b"+NAME+r"\([^;()]*['\"]SpinRequest['\"],(\d+),[^;()]*\)", source))
    if len(declarations) != 1:
        return None
    type_id = declarations[0][1]
    registrations = list(re.finditer(
        NAME+r"\("+type_id+r",\d+,(?:\{[^{}]*\}|"+NAME+r"),("+NAME+r")\)", source))
    if len(registrations) != 1:
        return None
    constructor = registrations[0][1]
    body = functions.get(constructor, ([], ""))[1]
    ids = re.findall(r"\.call\(this,"+NAME+r"\((\d+)\)\)", body)
    if len(ids) != 1:
        return None
    candidates = []
    for _, (args, body) in functions.items():
        if len(args) != 2 or not re.search(
            NAME+r"\("+re.escape(args[0])+","+type_id+r"\)", body):
            continue
        aliases = re.findall(r"\b("+NAME+r")="+re.escape(args[0])+r";", body)
        if len(aliases) != 1:
            continue
        fields = {}
        for semantic in ("bet", "numCoins", "spinType"):
            pattern = (r"("+NAME+r")=(?:"+NAME+r"\()?"+re.escape(aliases[0])+
                       r"\.("+NAME+r")\)?;\1!=null&&"+NAME+r"\("+
                       re.escape(args[1])+r",['\"]"+semantic+r"['\"],"+NAME+r"\(\1\)\)")
            matches = list(re.finditer(pattern, body))
            if len(matches) == 1:
                fields[semantic] = matches[0][2]
        if len(fields) == 3 and len(set(fields.values())) == 3:
            candidates.append(fields)
    if len(candidates) != 1:
        return None
    return dict(constructor=constructor, message_id=int(ids[0]), fields=candidates[0])


def observation_points(source):
    functions = _function_bodies(source)
    points = []

    def point(kind, name, offset, expression):
        header = re.search(r"function " + re.escape(name) + r"\([^)]*\)\{", source)
        if header is None:
            return
        position = header.end() + offset
        points.append(dict(type=kind, function=name,
                           lineNumber=source.count("\n", 0, position),
                           columnNumber=position-source.rfind("\n", 0, position)-1,
                           expression=expression))

    dispatchers = []
    for name, (args, body) in functions.items():
        if len(args) != 2 or "for(" not in body:
            continue
        returns = list(re.finditer(r"return (" + NAME + r")", body))
        if not returns:
            continue
        result = returns[-1][1]
        if not re.search(re.escape(result)+r"=new "+NAME+r"(?:\(\))?;", body):
            continue
        calls = list(re.finditer(r"("+NAME+r")="+NAME+r"\."+NAME+r"\("+re.escape(args[1])+r"\)", body))
        if len(calls) == 1 and re.search(NAME+r"\("+re.escape(result)+","+re.escape(calls[0][1])+r"\)", body):
            dispatchers.append((name, args[1], returns[-1]))
    if len(dispatchers) == 1:
        name, request, last = dispatchers[0]
        expression = request
        contract = spin_request_contract(source)
        if contract:
            fields = ",".join(key+":"+request+"."+value
                              for key, value in contract['fields'].items())
            expression = ("({raw:"+request+",spin:"+request+" instanceof "+
                          contract['constructor']+"?{"+fields+"}:null})")
        point("offline.request", name, 0, expression)
        point("offline.response", name, last.start(), last[1])

    # Require a linked payout sum -> credit wrapper -> result construction.
    # A balance delta alone is deliberately insufficient evidence.
    sums = set()
    for name, (args, body) in functions.items():
        if len(args) != 1 or "for(" not in body:
            continue
        match = re.search(r"("+NAME+r")\+=("+NAME+r")\.("+NAME+r")\}", body)
        if match and re.search(re.escape(match[1])+r"=0;", body):
            sums.add(name)
    candidates = []
    for name, (args, body) in functions.items():
        if len(args) != 2:
            continue
        last = re.search(r"return ("+NAME+r")$", body)
        if not last:
            continue
        paid = last[1]
        if not any(re.search(re.escape(total)+r"\("+re.escape(args[1])+r"\)", body) for total in sums):
            continue
        if not re.search(re.escape(paid)+r"="+NAME+r"\(", body):
            continue
        # The credited value and payout collection must flow together into
        # a result constructor; merely finding an unrelated sum is not enough.
        for outer, (_, outer_body) in functions.items():
            call = re.search(r"("+NAME+r")="+re.escape(name)+r"\(("+NAME+r"(?:\."+NAME+r")*),("+NAME+r")\)", outer_body)
            if call and re.search(r"new "+NAME+r"\("+re.escape(call[2])+","+re.escape(call[1])+","+re.escape(call[3])+r"\)", outer_body):
                candidates.append((name, last, paid))
                break
    if len(candidates) == 1:
        name, last, paid = candidates[0]
        point("offline.payout", name, last.start(), "({calculatedWin:"+paid+"})")
    return points
