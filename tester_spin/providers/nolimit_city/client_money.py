"""Read monetary field declarations from the exact client without executing JS."""
import re
from functools import lru_cache
from .client_actions import _block
from .lifecycle import methods,expressions
from .protocol import MAX_BODY


def _object_properties(value):
    if not value.startswith('{') or _block(value,0)!=value:return []
    return expressions(value[1:-1])


def monetary_fields(source):
    """Resolve one unambiguous exported parser and its direct spin getter."""
    if not isinstance(source,str) or len(source)>MAX_BODY:return None
    fields=_monetary_fields(source)
    return dict(fields) if fields else None


@lru_cache(maxsize=2)
def _monetary_fields(source):
    candidates=[]
    for export in re.finditer(r'\b\w+\.\w+=class\{',source):
        body=_block(source,export.end()-1)
        if not body or 'getParsedData:' not in body:continue
        available=methods(body,_block)
        options=available.get('getActionSpinOptions')
        if not options or not options[1].startswith('return{'):continue
        properties=_object_properties(options[1][len('return'):])
        parsers=[value for value in properties if value.startswith('getParsedData:')]
        if len(parsers)!=1:continue
        parser=re.fullmatch(r'getParsedData:\((\w+),(\w+),(\w+)\)=>\((.*)\)',parsers[0],re.S)
        if not parser:continue
        args=parser.groups()[:3];data=re.escape(args[0])
        returned=expressions(parser[4])
        if not returned:continue
        # The observed comma prefix only stores a UI flag on this object.
        # Unknown calls or writes to response arguments are not transparent.
        prefix=(data+r'\.\w+===\w+\.\w+\.[A-Z][A-Z0-9_]*&&\(this\.\w+='+data+r'\.\w+\)')
        if any(not re.fullmatch(prefix,value) for value in returned[:-1]):continue
        # The final comma expression must return the literal monetary object.
        # Nested history functions and string properties are never observations.
        output=_object_properties(returned[-1])
        if any(not re.match(r'[A-Za-z_$][A-Za-z0-9_$]*:',value) for value in output):continue
        if any(sum(value.startswith(key+':') for value in output)!=1 for key in ('totalWin','totalSpinWinnings')):continue
        totals=[match[1] for value in output if (match:=re.fullmatch(r'totalWin:'+data+r'\.(\w+)',value))]
        getters=[match[1] for value in output if (match:=re.fullmatch(r'totalSpinWinnings:this\.(\w+)\('+','.join(map(re.escape,args))+r'\)',value))]
        if len(totals)!=1 or len(getters)!=1:continue
        getter=available.get(getters[0])
        if not getter or getter[0]!=','.join(args):continue
        if any(re.search(r'\b'+re.escape(arg)+r'\s*=(?!=)',value) for arg in args for value in returned[:-1]):continue
        value=re.fullmatch(r'return '+data+r'\.(\w+)',getter[1])
        if value and not any('balance' in field.lower() for field in (value[1],totals[0])):
            candidates.append({'spin':value[1],'round':totals[0]})
    return candidates[0] if len(candidates)==1 else None
