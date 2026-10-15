"""Conservative normalization of client lifecycle effects.

Only root expressions and known callback lifecycles are traversed. An effect
inside a condition, ternary, paused timeline or unknown callback is not proof.
This is a recognizer, not a JavaScript interpreter.
"""
import re


def expressions(text):
    """Split root comma/semicolon expressions, respecting strings and ternaries."""
    stack=[];quote=None;escaped=False;ternary=0;start=0;out=[];i=0
    while i<len(text):
        char=text[i]
        if quote:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char==quote:quote=None
        elif char in ('"',"'",'`'):quote=char
        elif text.startswith('//',i):return []
        elif text.startswith('/*',i):return []
        elif char in '([{':stack.append(char)
        elif char in ')]}':
            if not stack or '([{'.index(stack.pop())!=')]}'.index(char):return []
        elif not stack:
            if char=='?' and text[i:i+2] not in ('?.','??') and text[max(0,i-1):i+1]!='??':ternary+=1
            elif char==':' and ternary:ternary-=1
            elif char==';' or char==',' and not ternary:
                out.append(text[start:i].strip());start=i+1
                if char==';':ternary=0
        i+=1
    if quote or stack or ternary:return []
    out.append(text[start:].strip())
    return [part for part in out if part]


def methods(body,block):
    result={};i=1
    while i<len(body)-1:
        match=re.match(r'(\w+)\(([^)]*)\)\{',body[i:])
        if not match:return {}
        value=block(body,i+match.end()-1)
        if not value:return {}
        if match[1] in result:return {}
        result[match[1]]=(match[2],value[1:-1]);i+=match.end()-1+len(value)
    return result


def proves_zero_bet(body,block,*,entry="start"):
    available=methods(body,block)
    if not available:return False
    zero=r'[\w$.]+\.betHandler\.zeroBet\(\)'

    def callback(value,depth):
        match=re.fullmatch(r'\(\)=>\{(.*)\}',value,re.S)
        if match:return effects(match[1],depth+1)
        match=re.fullmatch(r'\(\)=>(.*)',value,re.S)
        return bool(match and effects(match[1],depth+1))

    def effects(text,depth=0):
        if depth>3:return False
        timelines=set();parts=expressions(text)
        for part in parts:
            if re.match(r'^(if|else|for|while|switch|try|do)\b',part):return False
            direct=part.removeprefix('return ').strip()
            if re.fullmatch(zero,direct):return True
            # An unassigned, playing timeline completes through its declared
            # callback. A paused/cancelled timeline cannot authorize an action.
            completion=re.fullmatch(r'\w+\.gsap\.timeline\(\{(.*)\}\)',direct,re.S)
            config=expressions(completion[1]) if completion else []
            if (len(config)==1 and config[0].startswith('onComplete:')
                    and callback(config[0][len('onComplete:'):],depth)):return True
            # Known methods invoked unconditionally by the active lifecycle.
            invoked=re.fullmatch(r'this\.(\w+)\([^()]*\)',direct)
            if invoked and invoked[1] in available and invoked[1] not in ('start','getAnimation'):
                if effects(available[invoked[1]][1],depth+1):return True
            timeline=re.fullmatch(r'(?:const|let|var) (\w+)=(?:\w+\.gsap\.timeline\((.*)\)|new \w+\.TimelineLite(?:\((.*)\))?)',part,re.S)
            if timeline:
                config=timeline[2] if timeline[2] is not None else timeline[3] or ''
                name=re.escape(timeline[1])
                mutated=any(other!=part and re.search(r'\b'+name+r'(?:\s*=(?!=)|\.(?:pause|kill|stop|clear|reverse|reversed|timeScale)\()',other) for other in parts)
                if not mutated and 'paused' not in config and not re.search(r'\bon(?:Start|Update|Repeat)\b',config):timelines.add(timeline[1])
                continue
            added=re.fullmatch(r'(\w+)\.add\((.*)\)',direct,re.S)
            if added and added[1] in timelines:
                args=expressions(added[2])
                if args and callback(args[0],depth):return True
            runner=re.fullmatch(r'\w+\.SimplePresentationRunner\.run\((.*)\)',direct,re.S)
            if runner:
                args=expressions(runner[1])
                if len(args)>=2 and callback(args[1],depth):return True
            # An earlier return, throw or branch that can exit invalidates later
            # root calls. Conditional UI work without exits does not grant action.
            if re.search(r'\b(return|throw|break|continue)\b',part):return False
        return False

    return entry in available and effects(available[entry][1])
