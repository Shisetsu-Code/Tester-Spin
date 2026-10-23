"""Legacy zero-bet controllers whose trigger comes from the active parser.

The configured parser, parsed-data getter and controller are linked through
webpack imports. An unrelated predicate or a raw response flag is not authority.
"""
import re
from .static_bindings import IDENT,class_record,enum_literal,module_id
from .async_lifecycle import _owner,_import,_writes,_class_unmodified
from .action_spins_context import _game_modules
from .event_actions import _class_at,_method_map,_root_position,_bridge,_event_type
from .lifecycle import expressions,_paren_end,proves_zero_bet

_REF=IDENT+r'\.'+IDENT
_FIELDS=('ZERO_BETS','SERVER_PARSER','PARSED_GAME_DATA')


def _initializers(body):
    """A condition's comma prefix is evaluated before either conditional arm."""
    output=[]
    for part in expressions(body):
        if part.startswith('if('):
            close=_paren_end(part,2)
            if close is not None:output.extend(expressions(part[3:close]))
            break
        if re.search(r'\b(return|throw|yield|for|while|switch|try)\b',part):break
        output.append(part)
    return output


def _configured(source,registry,block):
    owner=_owner(source,registry.start(),block)
    containing=_class_at(source,registry.start(),block)
    if not owner or not containing or not containing[2]:return None
    header,module,_=owner;body,offset,name=containing
    record=(body,None,offset)
    members=_method_map(body,offset,block)
    if not members or 'constructor' not in members:return None
    if not _class_unmodified(source,record,block,methods=_FIELDS):return None
    constructor=members['constructor'];parts=_initializers(constructor[1]);values={}
    for field in _FIELDS:
        if any(key in members for key in ('get '+field,'set '+field)):return None
        if len(_writes(body,{'this'},field))!=1:return None
        matches=[part[len('this.'+field+'='):] for part in parts if part.startswith('this.'+field+'=')]
        if len(matches)!=1 or len(re.findall(r'this\.'+field+r'\b',body))!=1:return None
        values[field]=matches[0]
    controller=re.fullmatch(r'\[\(\)=>new ('+_REF+r')(?:\(\))?\]',values['ZERO_BETS'])
    parser=re.fullmatch(r'\(\)=>new ('+_REF+r')(?:\(\))?',values['SERVER_PARSER'])
    data=re.fullmatch(r'\(('+IDENT+r'),('+IDENT+r')\)=>new ('+_REF+r')\(\1,\2\)',values['PARSED_GAME_DATA'])
    if not controller or not parser or not data or data[1]==data[2]:return None
    exports=re.findall(re.escape(header[3])+r'\.('+IDENT+r')='+re.escape(name)+r'(?=[,;}])',module)
    if len(exports)!=1:return None
    configurations=_game_modules(source,record,exports[0],block)
    if not configurations:return None
    singletons=0
    for module_header,content,refs,aliases in configurations:
        for write in _writes(content,aliases,'instance'):
            if module_id(module_header[1])!=module_id(header[1]) or not _root_position(content,write.start()):return None
            if not re.match(r'new '+re.escape(name)+r'(?=[,;}]|$)',content[write.end():]):return None
            singletons+=1
        from .async_lifecycle import _aliases
        instances=_aliases(content,{alias+'.instance' for alias in aliases})
        if instances is None or any(_writes(content,instances,field) for field in _FIELDS):return None
    if singletons!=1:return None
    consumers=[]
    for match in re.finditer(r'constructor\(\)\{super\(('+_REF+r')\.instance\)\}',source):
        imported=_import(source,match.start(),match[1],block)
        if imported and module_id(imported[0][1])==module_id(header[1]) and imported[2]==exports[0]:consumers.append(match)
    if len(consumers)!=1:return None
    return constructor[2],controller[1],parser[1],data[3]


def _members_inherited(source,position,reference,block,depth=0):
    if depth>5:return None
    record=class_record(source,position,reference,block)
    if not record or not record[0]:return None
    own=_method_map(record[0],record[2],block)
    if not own or not _class_unmodified(source,record,block,methods=tuple(name.removeprefix('get ').removeprefix('set ') for name in own)):return None
    if any(_writes(record[0],{'this'},name) for name in own if not name.startswith(('get ','set '))):return None
    inherited={}
    if record[1]:
        inherited=_members_inherited(source,record[2],record[1],block,depth+1)
        if inherited is None:return None
    constructor=own.get('constructor')
    if constructor and constructor[1] not in ('','super()','this.addEventListeners()'):return None
    inherited.update(own)
    return inherited


def _dispatches(source,members,block):
    trigger=members.get('get isTriggered');received=members.get('onGameDataParsed');listeners=members.get('addEventListeners');handle=members.get('handleZeroBetCounter')
    if not trigger or trigger[:2]!=('', 'return this._isTriggered') or not received or not listeners or not handle:return False
    arg=received[0]
    if not re.fullmatch(IDENT,arg) or received[1]!='this._isTriggered=this.calculateIsTriggered('+arg+'),this._zeroBetNumberLeft=this.getZeroBetNumberLeft('+arg+')':return False
    parts=expressions(listeners[1])
    if len(parts)!=2:return False
    events=set()
    for part in parts:
        match=re.fullmatch(r'('+_REF+r')\.addEventListener\(this,('+_REF+r')\.(INIT_DATA_PARSED|GAME_DATA_PARSED),('+IDENT+r')=>this\.onGameDataParsed\(\4\.params\[0\]\)\)',part)
        if not match:return False
        events.add(match[3])
    if events!={'INIT_DATA_PARSED','GAME_DATA_PARSED'}:return False
    dispatch=r'('+_REF+r')\.dispatchEvent\(new ('+_REF+r')\(('+_REF+r')\.ZERO_BET,(?:this\._zeroBetNumberLeft|-1)\)\)'
    normalized=handle[1];matches=list(re.finditer(dispatch,normalized))
    if len(matches)!=2:return False
    for match in reversed(matches):
        if not _event_type(source,handle[2],match[2],block) or not _bridge(source,match[1],match[3],handle[2],block):return False
        normalized=normalized[:match.start()]+'known.betHandler.zeroBet()'+normalized[match.end():]
    return proves_zero_bet('{start(){'+normalized+'}}',block)


def _inputs_unmodified(body,parameters):
    """A constructor cannot replace the parser or alter the raw predicate input."""
    from .async_lifecycle import _aliases
    aliases=_aliases(body,set(parameters))
    if aliases is None:return False
    names='(?:'+'|'.join(map(re.escape,aliases))+')'
    direct='(?:'+'|'.join(map(re.escape,parameters))+')'
    assignment=r'\s*(?:[+*/&|?^\-]?=(?![=>])|\+\+|--)'
    properties=r'(?:\.'+IDENT+r'|\[[^\]]+\])+'
    if re.search(r'(?<![\w$.])'+direct+assignment,body):return False
    if re.search(r'(?<![\w$.])'+names+properties+assignment,body):return False
    if re.search(r'\bdelete '+names+properties,body):return False
    if re.search(r'Object\.(?:assign|defineProperty|defineProperties|setPrototypeOf)\('+names+r'(?=[,)])',body):return False
    return True


def _predicate_phase(source,position,parser_reference,data_reference,field,block):
    data=class_record(source,position,data_reference,block)
    parser=class_record(source,position,parser_reference,block)
    if not data or not parser:return None
    available=_method_map(data[0],data[2],block);parsers=_method_map(parser[0],parser[2],block)
    if not available or not parsers:return None
    getter=available.get('get '+field);constructor=available.get('constructor')
    if not getter or not constructor or 'set '+field in available:return None
    member=re.fullmatch(r'return this\.('+IDENT+r')',getter[1])
    args=constructor[0].split(',')
    if not member or len(args)!=2 or len(set(args))!=2 or not all(re.fullmatch(IDENT,arg) for arg in args):return None
    if not _inputs_unmodified(constructor[1],args):return None
    private=member[1]
    from .async_lifecycle import _aliases
    aliases=_aliases(data[0],{'this'})
    if aliases is None or len(_writes(data[0],aliases,private))!=1:return None
    pattern=r'this\.'+re.escape(private)+'='+re.escape(args[1])+r'\.('+IDENT+r')\('+re.escape(args[0])+r'\)'
    bindings=[re.fullmatch(pattern,part) for part in _initializers(constructor[1])]
    bindings=[item for item in bindings if item]
    if len(bindings)!=1:return None
    method=parsers.get(bindings[0][1])
    if not method or not re.fullmatch(IDENT,method[0]):return None
    if not _class_unmodified(source,data,block,methods=(field,private)) or not _class_unmodified(source,parser,block,methods=(bindings[0][1],)):return None
    if _writes(parser[0],{'this'},bindings[0][1]):return None
    equality=re.fullmatch(r'return '+re.escape(method[0])+r'\.nextMode==={0,1}('+_REF+r'\.'+IDENT+r')',method[1])
    return enum_literal(source,method[2],equality[1],block) if equality else None


def parsed_controller_command(source,answer,block,*,direct_demo_transport=False):
    if direct_demo_transport is not True:return None
    phase=(answer.get('game') or {}).get('nextMode')
    if not isinstance(phase,str) or phase=='NORMAL':return None
    candidates=[]
    for registry in re.finditer(r'this\.ZERO_BETS=\[',source):
        config=_configured(source,registry,block)
        if not config:continue
        position,controller,parser,data=config
        members=_members_inherited(source,position,controller,block)
        if not members or not _dispatches(source,members,block):continue
        trigger=members.get('calculateIsTriggered')
        if not trigger or not re.fullmatch(IDENT,trigger[0]):continue
        arg=re.escape(trigger[0])
        predicate=re.fullmatch(r'return (?:this\.'+IDENT+'='+arg+r'\.nextMode,)?'+arg+r'\.('+IDENT+r')',trigger[1])
        if not predicate:continue
        declared=_predicate_phase(source,position,parser,data,predicate[1],block)
        if declared==phase:candidates.append(declared)
    return {'type':'zeroBet','bet':'0.00'} if len(candidates)==1 else None
