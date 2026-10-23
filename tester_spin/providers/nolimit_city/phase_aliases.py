"""Resolve immutable, imported enum aliases independently of export order."""
import re
from functools import lru_cache
from .static_bindings import IDENT,class_record,enum_literal,module_id
from .async_lifecycle import _import,_writes,_class_unmodified
from .action_spins_context import _game_modules
from .event_actions import _root_position


def _immutable(source,position,owner,field,value,block):
    record=class_record(source,position,owner,block)
    imported=_import(source,position,owner,block)
    if not record or record[0]!='{}' or not imported or not _class_unmodified(source,record,block):return False
    modules=_game_modules(source,record,imported[2],block)
    if not modules:return False
    writes=0
    for header,module,refs,aliases in modules:
        names='(?:'+'|'.join(map(re.escape,aliases))+')'
        if re.search(r'Object\.(?:assign|defineProperty|defineProperties|setPrototypeOf)\('+names+r'(?=[,)])',module):return False
        if re.search(names+r'\[[^\]]+\]\s*=(?!=)',module):return False
        if re.search(r'\bdelete '+names+r'\.'+re.escape(field)+r'\b',module):return False
        for write in _writes(module,aliases,field):
            if module_id(header[1])!=module_id(imported[0][1]) or not _root_position(module,write.start()):return False
            if not re.match(re.escape('"'+value+'"')+r'(?=[,;}]|$)',module[write.end():]):return False
            writes+=1
    return writes==1


@lru_cache(maxsize=2)
def aliases_for(source,value,block):
    # Only keys whose explicit static literal equals this wire phase are
    # candidates. Each complete reference must resolve in every scope where
    # the text occurs, so a minifier name cannot borrow another module's enum.
    keys=set(re.findall(r'\b'+IDENT+r'\.('+IDENT+r')="'+re.escape(value)+r'"(?=[,;}])',source))
    if not keys:return ()
    keys='(?:'+'|'.join(map(re.escape,sorted(keys)))+')'
    pattern=r'(?<![\w$.])('+IDENT+r'\.'+IDENT+r')\.('+keys+r')\b'
    references={};checked={}
    for match in re.finditer(pattern,source):
        reference=match[0]
        if references.get(reference) is False:continue
        if enum_literal(source,match.start(),reference,block)!=value:
            references[reference]=False;continue
        record=class_record(source,match.start(),match[1],block)
        if not record:references[reference]=False;continue
        identity=(record[2],match[2])
        if identity not in checked:checked[identity]=_immutable(source,match.start(),match[1],match[2],value,block)
        references[reference]=checked[identity]
    return tuple(sorted(reference for reference,valid in references.items() if valid))
