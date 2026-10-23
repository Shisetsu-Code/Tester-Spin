"""Exclude a bound SDK replay-only method from a fresh demo selector scan.

The method name is irrelevant. Its sole constructed instance, every caller and
the SDK replay guard must be bound by module identity. A capture cannot supply
the independent fresh-transport context required by the caller.
"""
import re
from functools import lru_cache
from .static_bindings import IDENT,class_record
from .async_lifecycle import _owner,_aliases,_writes,_class_unmodified
from .action_spins_context import _game_modules
from .event_actions import _class_at,_method_map,_root_position


def _export(source,record,name,block):
    owner=_owner(source,record[2],block)
    if not owner or not name:return None
    exports=re.findall(re.escape(owner[0][3])+r'\.('+IDENT+r')='+re.escape(name)+r'(?=[,;}])',owner[1])
    return exports[0] if len(exports)==1 else None


def _display_registration(source,position,reference,block):
    """The sole permitted instance escape only inserts the view in a PIXI layer."""
    record=class_record(source,position,reference,block)
    if not record:
        # A minifier can reuse an imported identifier in a different method.
        # Resolve the enclosing class's lexical import only when this method
        # does not shadow or assign that identifier itself.
        enclosing=_class_at(source,position,block)
        if not enclosing:return False
        members=_method_map(enclosing[0],enclosing[1],block)
        inside=[value for value in (members or {}).values() if value[2]<position<value[2]+len(value[1])+2]
        alias=reference.split('.',1)[0]
        if len(inside)!=1 or re.search(r'\b'+re.escape(alias)+r'\b',inside[0][0]):return False
        if re.search(r'(?<![\w$.])'+re.escape(alias)+r'\s*=(?!=)',inside[0][1]):return False
        record=class_record(source,enclosing[1],reference,block)
    if not record or not _class_unmodified(source,record,block,statics=('addLayerAt',)):return False
    matches=[match for match in re.finditer(r'static addLayerAt\(([^)]*)\)\{',record[0]) if _root_position(record[0],match.start())]
    if len(matches)!=1:return False
    match=matches[0];body=block(record[0],match.end()-1,len(record[0]))
    if not body:return False
    args=re.fullmatch(r'('+IDENT+r'),('+IDENT+r'),('+IDENT+r')=0',match[1])
    if not args or len(set(args.groups()))!=3:return False
    name,view,index=map(re.escape,args.groups())
    pattern=(r'('+IDENT+r')\._instance\._layers\['+name+r'\]='+view+','+view+r'\.name='+name
        +r',\1\._instance\.stage\.addChildAt\('+view+','+index+r'\),"Keypad"=='+name
        +r'&&\1\._instance\._keypadLayer\.addChildAt\('+view+','+index+r'\)')
    return bool(re.fullmatch(pattern,body[1:-1]))


def _only_replay_callers(source,record,name,method,block):
    exported=_export(source,record,name,block)
    if not exported or not _class_unmodified(source,record,block,methods=(method,)):return False
    local=_aliases(record[0],{'this'})
    if local is None:return False
    local_refs='(?:'+'|'.join(map(re.escape,local))+')'
    if re.search(local_refs+r'(?:\.'+re.escape(method)+r'\b|\[[^\]]+\])',record[0]):return False
    modules=_game_modules(source,record,exported,block)
    if not modules:return False
    creations=[]
    for header,module,references,aliases in modules:
        names='(?:'+'|'.join(map(re.escape,aliases))+')'
        if re.search(names+r'\.prototype\b',module):return False
        prototypes=_aliases(module,{alias+'.prototype' for alias in aliases})
        if prototypes is None or _writes(module,prototypes,method):return False
        if re.search(r'Object\.(?:assign|defineProperty|defineProperties|setPrototypeOf)\('+names+r'(?:\.prototype)?(?=[,)])',module):return False
        for match in re.finditer(r'new '+names+r'(?=[,;)}\](])',module):
            before=module[:match.start()]
            assigned=re.search(r'(?<![\w$.])('+IDENT+r')\.('+IDENT+r')=$',before)
            after=module[match.end():]
            if not assigned or not re.match(r'(?:\(\))?(?=[,;}])',after):return False
            game=class_record(source,header.end()-1+match.start(),assigned[1],block)
            if not game:return False
            creations.append((game,assigned[1],assigned[2],header.end()-1+assigned.start()))
    if len(creations)!=1:return False
    game,game_name,field,initialization=creations[0]
    from .sdk_replay_context import inherited_sdk_replay,replay_options_preserved
    if not inherited_sdk_replay(source,game,block):return False
    game_export=_export(source,game,game_name,block)
    if not game_export or not _class_unmodified(source,game,block,statics=('apiPlugin',)):return False
    if not replay_options_preserved(source,game,game_export,block):return False
    game_members=_method_map(game[0],game[2],block)
    if not game_members or any(key in game_members for key in ('get '+field,'set '+field,'get apiPlugin','set apiPlugin')):return False
    game_modules=_game_modules(source,game,game_export,block)
    if not game_modules:return False
    writes=[];calls=0
    for header,module,references,aliases in game_modules:
        if _writes(module,aliases,'apiPlugin'):return False
        writes.extend(header.end()-1+match.start() for match in _writes(module,aliases,field))
        names='(?:'+'|'.join(map(re.escape,aliases))+')'
        if re.search(names+r'\[[^\]]+\]',module):return False
        instances={alias+'.'+field for alias in aliases}
        instance_aliases=_aliases(module,instances)
        if instance_aliases is None or instance_aliases!=instances:return False
        targets='(?:'+'|'.join(map(re.escape,instance_aliases))+')'
        if re.search(targets+r'\[[^\]]+\]',module) or _writes(module,instance_aliases,method):return False
        if re.search(r'Object\.(?:assign|defineProperty|defineProperties|setPrototypeOf)\('+targets+r'(?=[,)])',module):return False
        registrations=[]
        registration=r'('+IDENT+r'\.'+IDENT+r')\.addLayerAt\(('+targets+r')\.name,\2,0\)'
        for match in re.finditer(registration,module):
            if _display_registration(source,header.end()-1+match.start(),match[1],block):registrations.append((match.start(),match.end()))
        for match in re.finditer(targets+r'\b',module):
            if any(start<=match.start()<end for start,end in registrations):continue
            after=module[match.end():]
            if after.startswith('.') and not re.match(r'\.(?:constructor|__proto__)\b',after):continue
            if header.end()-1+match.start()==initialization and after.startswith('=new '):continue
            return False
        protected=[]
        # Keep the condition and both receivers identical. A negated guard,
        # a disjunction or the ELSE arm does not prove inactivity.
        pattern=(r'('+names+r')\.apiPlugin\.isReplay\?\1\.'+re.escape(field)+r'\.'+re.escape(method)
                 +r'\((this\.'+IDENT+r'|'+IDENT+r')\):\1\.'+re.escape(field)+r'\.('+IDENT+r')\(\2\)')
        for match in re.finditer(pattern,module):
            if match.start() and module[match.start()-1] not in '{(,;?:':continue
            if match[3]==method:continue
            start=module.index('.'+method+'(',match.start(),match.end())
            protected.append(start)
        for match in re.finditer(targets+r'\.'+re.escape(method)+r'\b',module):
            member=match.end()-len(method)-1
            if member not in protected:return False
            calls+=1
    return writes==[initialization] and calls==1


@lru_cache(maxsize=2)
def selector_source(source,field,block):
    """Return a scan projection, preserving the original source for contracts."""
    from .protocol import MAX_BODY
    if not isinstance(source,str) or len(source)>MAX_BODY:return source
    # The supported SDK getter tests a launch replay option, not a game flag.
    getters=list(re.finditer(r'get isReplay\(\)\{return null!=this\.options\.replay\}',source))
    if len(getters)!=1 or len(re.findall(r'get isReplay\(',source))!=1:return source
    if re.search(r'set isReplay\(|\.isReplay\s*=(?!=)|\[["\']isReplay["\']\]',source):return source
    replacements={}
    for match in re.finditer(r'zeroBet\(\{'+re.escape(field)+r':('+IDENT+r')\}\)',source):
        enclosing=_class_at(source,match.start(),block)
        if not enclosing:continue
        body,offset,name=enclosing;record=(body,None,offset)
        members=_method_map(body,offset,block)
        if not members:continue
        containing=[(key,value) for key,value in members.items() if value[2]<match.start()<value[2]+len(value[1])+2]
        if len(containing)!=1:continue
        method,(_,content,position)=containing[0]
        if method=='constructor' or method.startswith(('get ','set ')):continue
        if not _only_replay_callers(source,record,name,method,block):continue
        replacements[position]=(position+len(content)+2,'{}')
    for start,(end,value) in sorted(replacements.items(),reverse=True):source=source[:start]+value+source[end:]
    return source
