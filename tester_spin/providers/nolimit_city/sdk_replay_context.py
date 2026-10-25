"""Bind a game's inherited API reference to the launcher's real replay getter."""
import re
from .static_bindings import IDENT,class_record,module_id
from .async_lifecycle import _owner,_import,_writes,_class_unmodified,_aliases
from .action_spins_context import _game_modules
from .event_actions import _root_position
from .lifecycle import expressions,_paren_end


def _name(source,record):
    match=re.search(r'class ('+IDENT+r')(?: extends '+IDENT+r'\.'+IDENT+r')?$',source[max(0,record[2]-200):record[2]])
    return match[1] if match else None


def _method(record,name,block,*,getter=False):
    pattern=(r'get ' if getter else '')+re.escape(name)+r'\(([^)]*)\)\{'
    matches=[m for m in re.finditer(pattern,record[0]) if _root_position(record[0],m.start())]
    if len(matches)!=1:return None
    match=matches[0];body=block(record[0],match.end()-1,len(record[0]))
    return (match[1],body[1:-1],record[2]+match.end()-1) if body else None


def _field_writes(source,record,export,field,block):
    modules=_game_modules(source,record,export,block)
    if not modules:return None
    result=[]
    for header,module,refs,aliases in modules:
        names='(?:'+'|'.join(map(re.escape,aliases))+')'
        if re.search(names+r'\[[^\]]+\]\s*=(?!=)',module):return None
        if re.search(r'Object\.(?:assign|defineProperty|defineProperties|setPrototypeOf)\('+names+r'(?=[,)])',module):return None
        result.extend((header.end()-1+write.start(),module[write.end():]) for write in _writes(module,aliases,field))
    return result


def _non_api_constructor(source,position,expression,block,seen=()):
    """Other registry entries must be bound classes without the API fields."""
    match=re.match(r'new ('+IDENT+r'\.'+IDENT+r')(?=$|\()',expression)
    if not match:return False
    if match.end()<len(expression):
        if _paren_end(expression,match.end())!=len(expression)-1:return False
        if any(not _non_api_constructor(source,position,argument,block,seen)
               for argument in expressions(expression[match.end()+1:-1])):return False
    record=class_record(source,position,match[1],block)
    while record:
        if record[2] in seen or not _class_unmodified(source,record,block,methods=('communication','slotStates')):return False
        seen=(*seen,record[2])
        aliases=_aliases(record[0],{'this'})
        if aliases is None:return False
        names='(?:'+'|'.join(map(re.escape,aliases))+')'
        if re.search(names+r'(?:\.(?:communication|slotStates)\b|\[)',record[0]):return False
        if re.search(r'(?:get|set) (?:communication|slotStates)\(',record[0]):return False
        if re.search(r'Object\.(?:assign|defineProperty|defineProperties|setPrototypeOf)\('+names+r'(?=[,)])',record[0]):return False
        if not record[1]:return True
        record=class_record(source,record[2],record[1],block)
    return False


def _registry_additions(source,launcher,export,block):
    """Account for every push/concat source rather than only registry writes."""
    modules=_game_modules(source,launcher,export,block)
    if not modules:return False
    launch=_method(launcher,'launch',block)
    for header,module,refs,aliases in modules:
        names='(?:'+'|'.join(map(re.escape,aliases))+')'
        registries={alias+'.plugins' for alias in aliases}
        copies=_aliases(module,registries)
        if copies is None or copies!=registries:return False
        for use in re.finditer(names+r'\.plugins\b',module):
            tail=module[use.end():]
            if re.match(r'\[[^\]]+\](?:\.'+IDENT+r'|\[[^\]]+\])*\s*(?:[+*/&|?^\-]?=(?!=)|\+\+|--)',tail):return False
            call=re.match(r'\.('+IDENT+r')\(',tail)
            if not call:continue
            opening=use.end()+call.end()-1;end=_paren_end(module,opening)
            if end is None:return False
            argument=module[opening+1:end]
            position=header.end()-1+use.start()
            if call[1]=='push':
                if argument in {alias+'.apiPlugin' for alias in aliases}:continue
                if not _non_api_constructor(source,position,argument,block):return False
            elif call[1]=='concat':
                if (not launch or not re.fullmatch(IDENT,launch[0]) or argument!=launch[0]
                        or not launch[2]<position<launch[2]+len(launch[1])):return False
            elif call[1]=='pop':
                if argument:return False
            elif call[1]=='splice':
                if len(expressions(argument))!=2:return False
            else:return False
        # launch() may extend the registry only with a finite literal list of
        # imported non-API constructors. An arbitrary array could replace the
        # last match selected by the SDK's structural isApiPlugin predicate.
        for use in re.finditer(names+r'\.instance\.launch\b',module):
            if not module.startswith('(',use.end()):return False
            end=_paren_end(module,use.end())
            if end is None:return False
            argument=module[use.end()+1:end]
            if not argument.startswith('[') or not argument.endswith(']'):return False
            if any(not _non_api_constructor(source,header.end()-1+use.start(),entry,block)
                   for entry in expressions(argument[1:-1])):return False
    return True


def replay_options_preserved(source,record,export,block):
    """Consumer modules may read option values, never take the options object."""
    modules=_game_modules(source,record,export,block)
    if not modules:return False
    for _header,module,_refs,aliases in modules:
        apis=_aliases(module,{alias+'.apiPlugin' for alias in aliases})
        if apis is None:return False
        roots='(?:'+'|'.join(map(re.escape,apis))+')'
        for use in re.finditer(roots+r'\.options\b',module):
            tail=module[use.end():]
            field=re.match(r'\.('+IDENT+r')',tail)
            if not field:return False
            if field[1]=='replay':
                if re.match(r'\s*(?:[+*/&|?^\-]?=(?!=)|\+\+|--|\(|\[|\.)',tail[field.end():]):return False
                if re.search(r'(?:\bdelete\s+|\+\+|--)\s*$',module[:use.start()]):return False
    return True


def _analytics_projection_module(content,module_argument):
    """A complete, alpha-renamable grammar for the scalar-copy consumer.

    The fixed key array and every operation on the exported adapter are part
    of the proof. Validating only init's prefix would miss a replaced forEach,
    a duplicate getter or a later override of the exported function.
    """
    grammar=(
        '{const @keys=["game","version","cdn","device","operator","currency","language","environment"];'
        'let @channel,@ready,@active=!1;function @send(@kind,@data){@active&&@channel.port1.postMessage({hitType:@kind,eventData:@data})}'
        'const @adapter={init:function(@input){return void 0===@ready&&(!1===@input.googleAnalytics?@ready=Promise.resolve():('
        '@adapter.options=function(@project){const @copy={};return @keys.forEach(@key=>{@project[@key]&&(@copy[@key]=@project[@key])}),@copy}(@input),'
        '@ready=new Promise((@input,@reject)=>{@channel=new MessageChannel;const @frame=document.createElement("iframe");'
        '@frame.setAttribute("frameBorder","0"),@frame.style.width="0",@frame.style.height="0",@frame.id="nolimit-analytics",'
        '@frame.onload=function(){@frame.contentWindow.postMessage(JSON.stringify(@adapter.options),@adapter.options.cdn,[@channel.port2]),@active=!0,@input(@frame)},'
        '@frame.onerror=function(@failure){@reject(@failure.message)},'
        '@frame.src="{CDN}/analytics/analytics.html".replace("{CDN}",@adapter.options.cdn).replace("{GAME}",@adapter.options.game),'
        'document.body.appendChild(@frame)}))),@ready},'
        'screenView(@screen){@active&&@send("screenview",{screenName:@screen})},'
        'event(@action,@label,@value){if(@active){const @event={eventCategory:@adapter.options.game+"@"+@adapter.options.device,eventAction:@action};'
        '@label&&("number"==typeof @label?@event.eventValue=@label:@event.eventLabel=String(@label)),@value&&(@event.eventValue=@value),@send("event",@event)}},'
        'exception(@description,@fatal){@active&&@send("exception",{exDescription:@description,exFatal:@fatal})},'
        'timing(@category,@variable,@duration,@timing_label){if(@active){const @timing={timingCategory:@category,timingVar:@variable,timingValue:@duration};'
        '@timing_label&&(@timing.timingLabel=@timing_label),@send("timing",@timing)}}};@module.exports=@adapter}')
    names=set();pattern=[];cursor=0
    for token in re.finditer(r'@([a-z_]+)',grammar):
        pattern.append(re.escape(grammar[cursor:token.start()]))
        name=token[1]
        pattern.append('(?P='+name+')' if name in names else '(?P<'+name+'>'+IDENT+')')
        names.add(name);cursor=token.end()
    pattern.append(re.escape(grammar[cursor:]))
    match=re.fullmatch(''.join(pattern),content)
    if not match or match['module']!=module_argument:return False
    # Names in the same lexical scope cannot replace a captured dependency.
    distinct=(('module','keys','channel','ready','active','send','adapter'),
        ('kind','data','active','channel'),('input','ready','adapter','keys','channel','active'),
        ('project','copy','keys'),('project','copy','key'),
        ('input','reject','frame','channel','active','adapter'),('failure','reject'),
        ('screen','active','send'),('action','label','value','event','active','send','adapter'),
        ('description','fatal','active','send'),
        ('category','variable','duration','timing_label','active','send'),
        ('category','variable','duration','timing_label','timing','send'))
    if any(len({match[key] for key in group})!=len(group) for group in distinct):return False
    globals_={'Promise','MessageChannel','document','JSON','String'}
    return not any(match[name] in globals_ for name in names)


def _analytics_options_projection(source,api,namespace,block):
    """Bind the sole import, call and complete immutable projection adapter."""
    owner=_owner(source,api[2],block)
    if not owner or not owner[0][4]:return False
    header,module,_=owner
    prefix=module[:api[2]-header.end()+1]
    imports=list(re.finditer(r'(?<![\w$.])'+re.escape(namespace)+'='+re.escape(header[4])+r'\(([0-9]+)\)',prefix))
    if len(imports)!=1:return False
    constructor=_method(api,'constructor',block)
    if not constructor:return False
    parts=expressions(constructor[1]);call=namespace+'.init(this.options)'
    publication='this.analytics='+namespace
    if parts.count(call)!=1 or parts.count(publication)!=1 or parts.index(publication)<parts.index(call):return False
    allowed=[imports[0].span()]
    for expression in (call,publication):
        start=constructor[2]+1+constructor[1].index(expression)-(header.end()-1)
        allowed.append((start,start+len(expression)))
    for use in re.finditer(r'(?<![\w$.])'+re.escape(namespace)+r'(?![\w$])',module):
        if not any(start<=use.start()<end for start,end in allowed):return False
    # Another importing module could replace init before construction. It is
    # not an authorized consumer of the input merely because its ID matches.
    consumers=[]
    for use in re.finditer(r'(?<![\w$.])('+IDENT+r')\(([0-9]+(?:e[0-9]{1,3})?)\)',source):
        if module_id(use[2])!=module_id(imports[0][1]):continue
        consumer=_owner(source,use.start(),block)
        if not consumer or consumer[0][4]!=use[1]:return False
        consumers.append(consumer[0].start())
    if consumers!=[header.start()]:return False
    # Analytics is a CommonJS module with a single module argument.
    headers=list(re.finditer(r'(?:^|[,{])'+imports[0][1]+r'\(('+IDENT+r')\)\{',source))
    if len(headers)!=1:return False
    content=block(source,headers[0].end()-1,len(source))
    return bool(content and _analytics_projection_module(content,headers[0][1]))


def _launch_options_normalizer(source,supplier,block):
    """Recognize the complete SDK normalization, including its two callees.

    Only the declared scalar/default transforms are allowed. Each method has a
    complete body grammar: an extra operation, alias, callback or replacement
    return cannot inherit the fresh transport's original replay value.
    """
    name=_name(source,supplier)
    methods={key:_method(supplier,key,block) for key in ('getOptions','verifyOptions','getServerHost')}
    if (not name or supplier[1] or not all(methods.values())
            or not _class_unmodified(source,supplier,block,statics=tuple(methods))):return False
    if any(not re.fullmatch(IDENT,item[0]) or item[0] in (name,'JSON','Error') for item in methods.values()):return False
    arg,body,_=methods['verifyOptions']
    if body!=f'if(!{arg}||!{arg}.game)throw new Error("Missing nolimit.options.game: "+JSON.stringify({arg}))':return False
    arg,body,_=methods['getServerHost']
    declaration=re.search(r';const ('+IDENT+r')='+re.escape(arg)+r'\.environment;',body)
    if not declaration or declaration[1] in (arg,name):return False
    local=declaration[1]
    server=(f'if({arg}.serverHost)return {arg}.serverHost.replace(/\\/$/,"");const {local}={arg}.environment;'
        f'return-1==={local}.indexOf(".")?"https://"+{local}+".nolimitcity.com":"https://"+'
        f'{local}.replace("nolimitcdn","nolimitcity").replace("-us.nlccdn.com",".nlcus.com")'
        '.replace("nlccdn","nlcgames").replace("nlcasiacdn","nlcasia")')
    if body!=server:return False
    arg,body,_=methods['getOptions']
    preserved_languages=('verbose','succinct','zh-Hant','zh-hant','pt-BR','pt-br','us-sweepstakes','us-nonfree','de-x-sweep')
    language_guard='&&'.join(f'"{language}"!=={arg}.language' for language in preserved_languages)
    normalized=[
        f'{name}.verifyOptions({arg})',
        f'{arg}.device={arg}.device||"desktop"',
        f'{arg}.language&&({arg}.language={arg}.language.replace(/_/g,"-"))',
        language_guard+f'&&({arg}.language=({arg}.language||"en").substring(0,2).toLowerCase())',
        f'{arg}.serverHost={name}.getServerHost({arg})',
        f'!0!=={arg}.hideCurrency&&"true"!=={arg}.hideCurrency||({arg}.hideCurrency=!0)',
        f'{arg}.quality&&({arg}.quality={arg}.quality.toLowerCase())',
        f'{arg}.smartLoading={arg}.smartLoading&&!1!=={arg}.smartLoading',
        f'{arg}.showDialogs=!1!=={arg}.showDialogs',
        f'{arg}.funMode=!{arg}.token',
        f'{arg}.realityCheck={arg}.realityCheck||{{}}',arg,
    ]
    return body=='return '+','.join(normalized)


def _published_launch_options(source,api,initializer,block):
    """The global alias has only the bound input and same-object publications.

    Unknown reads are rejected too: passing the options or its containing
    object to another consumer would escape the normalization proof.
    """
    allowed=[]
    if initializer is not None:allowed.append(initializer)
    publication='window.nolimit.options=this.options'
    constructor=_method(api,'constructor',block)
    bodies=[]
    if constructor:bodies.append((constructor[1],constructor[2]+1,publication))
    initialization=_method(api,'init',block)
    if initialization:
        prefix=re.match(r'return new Promise\(\('+IDENT+r','+IDENT+r'\)=>\{',initialization[1])
        callback=block(initialization[1],prefix.end()-1,len(initialization[1])) if prefix else None
        if callback:
            conditional=('void 0!==this.options.replay&&(window.nolimit=window.nolimit||{},'
                'window.nolimit.api=window.nolimit.api||{},'+publication+')')
            bodies.append((callback[1:-1],initialization[2]+1+prefix.end(),conditional))
    for body,offset,expression in bodies:
        if expression not in expressions(body):continue
        for match in re.finditer(re.escape(expression),body):
            if _root_position('{'+body+'}',match.start()+1):
                allowed.append((offset+match.start(),offset+match.end()))
    # The SDK initializes/reset its global container and publishes independent
    # API services. These operations neither receive nor replace options.
    operations=(r'window\.nolimit=window\.nolimit\|\|\{\}',
        r'window\.nolimit=void 0',
        r'window\.nolimit\.api=window\.nolimit\.api\|\|\{\}',
        r'window\.nolimit\.api\.(?:settings|error)=this\.(?:settings|error\.external)')
    for pattern in operations:
        for match in re.finditer(r'(?<![\w$.])'+pattern+r'(?=[,;)}])',source):
            # Container setup may precede the class, in its defining module.
            allowed.append(match.span())
    # Any spelling of a named nolimit member must resolve to these exact uses;
    # aliases, bracket access, additional properties and opaque calls fail.
    for use in re.finditer(r'(?<![\w$\\])'+IDENT+r'\s*(?:\.\s*nolimit\b|\[\s*["\']nolimit["\']\s*\])',source):
        # The development-preference module uses a window alias but only
        # reads/writes these independent boolean fields, never the container.
        flag=re.match(r'\.(?:development|developmentTools)(?![\w$])',source[use.end():])
        if flag and not re.match(r'\s*[.\[(]',source[use.end()+flag.end():]):continue
        if not any(start<=use.start() and use.end()<=end for start,end in allowed):return False
    return True


def _sdk_launch_options(source,api,block):
    if re.search(r'(?:get|set) options\(',api[0]):return False
    receivers=_aliases(api[0],{'this'})
    if receivers is None:return False
    options=_aliases(api[0],{receiver+'.options' for receiver in receivers})
    if options is None or _writes(api[0],options,'replay'):return False
    names='(?:'+'|'.join(map(re.escape,options))+')'
    if re.search(r'(?:delete |\+\+|--)'+names+r'(?:\.replay|\[)',api[0]):return False
    writes=_writes(api[0],receivers,'options')
    constructor=_method(api,'constructor',block)
    for use in re.finditer(names+r'\b',api[0]):
        tail=api[0][use.end():]
        if re.match(r'\.'+IDENT,tail):continue
        if any(use.start()==write.start() for write in writes):continue
        before=api[0][:use.start()]
        if re.search(r'window\.nolimit\.options=$',before):continue
        consumer=re.search(r'(?<![\w$.])('+IDENT+r')\.init\($',before)
        if (consumer and constructor and constructor[2]<api[2]+use.start()<constructor[2]+len(constructor[1])
                and _analytics_options_projection(source,api,consumer[1],block)):continue
        return False
    if not writes:return _published_launch_options(source,api,None,block)
    if len(writes)!=1 or not constructor:return False
    write=writes[0];position=api[2]+write.start()
    if not constructor[2]<position<constructor[2]+len(constructor[1]):return False
    initializer=re.match(r'('+IDENT+r'\.'+IDENT+r')\.getOptions\(window\.nolimit\.options\)(?=[,;}])',api[0][write.end():])
    if not initializer:return False
    supplier=class_record(source,position,initializer[1],block)
    input_start=api[2]+write.end()+initializer[0].index('window.nolimit.options')
    input_range=(input_start,input_start+len('window.nolimit.options'))
    return bool(supplier and _launch_options_normalizer(source,supplier,block)
                and _published_launch_options(source,api,input_range,block))


def inherited_sdk_replay(source,game,block):
    if not game[1]:return False
    base=class_record(source,game[2],game[1],block)
    imported=_import(source,game[2],game[1],block)
    if not base or not imported or base[1] or not _class_unmodified(source,base,block,methods=('fetchPlugins','apiPlugin')):return False
    if not replay_options_preserved(source,base,imported[2],block):return False
    if re.search(r'(?:get|set) apiPlugin\(',base[0]):return False
    name=_name(source,base);fetch=_method(base,'fetchPlugins',block)
    if not name or not fetch or fetch[0]:return False
    loop=re.match(r'for\(let ('+IDENT+r') of ('+IDENT+r'\.'+IDENT+r')\.plugins\)',fetch[1])
    if not loop:return False
    receiver=re.escape(loop[1]);assignment=re.escape(name)+r'\.apiPlugin='+receiver
    guard=re.search(r'\(0,('+IDENT+r'\.'+IDENT+r')\)\('+receiver+r'\)&&\('+assignment+r'\)',fetch[1])
    if not guard:return False
    end=fetch[1].find(';',loop.end())
    body=fetch[1][loop.end():end] if end>=0 else ''
    if guard[0] not in expressions(body) or re.search(r'(?<![\w$.])'+receiver+r'\s*=(?!=)',body):return False
    writes=_field_writes(source,base,imported[2],'apiPlugin',block)
    if writes is None or len(writes)!=1 or not (fetch[2]<writes[0][0]<fetch[2]+len(fetch[1])):return False
    predicate=_import(source,base[2],guard[1],block)
    if not predicate:return False
    header,module,export=predicate
    property_name=re.escape(header[3]+'.'+export)
    effective=re.sub(property_name+r'=void 0(?=[,;])','',module)
    pattern=property_name+r'=function\(('+IDENT+r')\)\{return void 0!==\1\.communication&&void 0!==\1\.slotStates\}'
    if len(re.findall(property_name+r'=(?!=)',effective))!=1 or not re.search(pattern,effective):return False
    launcher=class_record(source,base[2],loop[2],block)
    launcher_import=_import(source,base[2],loop[2],block)
    if not launcher or not launcher_import or not _class_unmodified(source,launcher,block):return False
    launcher_name=_name(source,launcher);constructor=_method(launcher,'constructor',block)
    if not launcher_name or not constructor:return False
    owner=re.escape(launcher_name)
    initialized=re.search(owner+r'\.plugins=\[\],'+owner+r'\.apiPlugin=new ('+IDENT+r'\.'+IDENT+r')(?:\(\))?,'+owner+r'\.plugins\.push\('+owner+r'\.apiPlugin\)',constructor[1])
    if not initialized:return False
    writes=_field_writes(source,launcher,launcher_import[2],'apiPlugin',block)
    if writes is None or len(writes)!=1 or not (constructor[2]<writes[0][0]<constructor[2]+len(constructor[1])):return False
    registry=_field_writes(source,launcher,launcher_import[2],'plugins',block)
    if registry is None:return False
    initial=[write for write in registry if constructor[2]<write[0]<constructor[2]+len(constructor[1])]
    if len(initial)!=1 or not initial[0][1].startswith('[],'):return False
    for position,tail in registry:
        if not launcher[2]<position<launcher[2]+len(launcher[0]):return False
        if not re.match(r'(?:\[\]|'+owner+r'\.plugins\.concat\('+IDENT+r'\))(?=[,;}])',tail):return False
    if not _registry_additions(source,launcher,launcher_import[2],block):return False
    if not replay_options_preserved(source,launcher,launcher_import[2],block):return False
    api=class_record(source,launcher[2],initialized[1],block)
    if not api or not _class_unmodified(source,api,block,methods=('isReplay',)):return False
    if not _sdk_launch_options(source,api,block):return False
    getter=_method(api,'isReplay',block,getter=True)
    return bool(getter and getter[:2]==('', 'return null!=this.options.replay')
        and not re.search(r'set isReplay\(',api[0]) and not _writes(api[0],{'this'},'isReplay'))
