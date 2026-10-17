"""Static observation bindings for NGM offline clients; never evaluates source.

Bindings describe non-pausing logpoints in a freshly loaded official demo.
They do not authorize wagers or certify the purchase inventory/round closure.
"""
import re
from .client_sources import _function_bodies

NAME = r"[A-Za-z_$][\w$]*"


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
        if not re.search(r"\.vf\(" + re.escape(args[1]) + r"\)", body):
            continue
        returns = list(re.finditer(r"return (" + NAME + r")", body))
        if returns:
            dispatchers.append((name, args[1], returns[-1]))
    if len(dispatchers) == 1:
        name, request, last = dispatchers[0]
        point("offline.request", name, 0, request)
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
