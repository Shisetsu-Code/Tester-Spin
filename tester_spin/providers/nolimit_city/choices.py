"""Bounded client-declared choice domains; no JavaScript execution or guesses."""
import re
from .protocol import MAX_BODY

def _modes(text):
    return set(re.findall(r'\.([A-Z][A-Z0-9_]+)\b|"([A-Z][A-Z0-9_]+)"',text))

def _contains_mode(text,mode):
    return any(mode in pair for pair in _modes(text))

def choice_domain(source,answer):
    if not isinstance(source,str) or len(source)>MAX_BODY:raise ValueError('Nolimit City: cliente de elecciones inválido')
    game=answer.get('game') or {};mode=game.get('nextMode');candidates=[]
    static=r'options:\(\)=>\[(.{0,2000}?)\],type:\w+\.ASBonusPickOptions\.PICK_MODE,pickNeededForModes:\[([^\]]+)\]'
    for match in re.finditer(static,source):
        if not _contains_mode(match[2],mode):continue
        ids=[int(value) for value in re.findall(r'\bid:(\d+)\b',match[1])]
        if not ids or len(ids)>32 or len(ids)!=len(set(ids)) or type(game.get('playerSelect')) is not int:continue
        candidates.append({'state':mode,'options':ids,'available':ids,'ack_field':'playerSelect','source':'CLIENT_STATIC_IDS'})
    automatic=r'automaticPickGame:\{[^{}]{0,1000}?optionSelection:(\w+)=>this\.(\w+)\(\1\)[^{}]{0,1000}?pickNeededForModes:\[([^\]]+)\]'
    for match in re.finditer(automatic,source):
        if not _contains_mode(match[3],mode):continue
        function=re.search(r'\b'+re.escape(match[2])+r'\((\w+)\)\{(.{0,1200}?)return \w+\}',source)
        if not function:continue
        field=re.search(r'-1=='+re.escape(function[1])+r'\.(\w+)\[(\w+)\]&&\(\w+=\2\)',function[2])
        if not field:continue
        bounds=re.search(r'(?:let|const|var)\s+(\w+)=[\w$.]+\.randomIntInRange\(0,(\d+)\)',function[2])
        if not bounds or bounds[1]!=field[2] or int(bounds[2])>=32:continue
        values=game.get(field[1]);available=[]
        if not isinstance(values,list) or not values or len(values)!=int(bounds[2])+1 or any(type(value) is not int or value<-1 for value in values):continue
        available=[i for i,value in enumerate(values) if value==-1]
        if available:candidates.append({'state':mode,'options':list(range(len(values))),'available':available,'ack_field':field[1],'before':list(values),'source':'SERVER_UNPICKED_ARRAY'})
    if len(candidates)!=1:raise ValueError('Nolimit City: elección sin dominio único declarado por cliente y servidor: '+str(mode))
    return candidates[0]

def confirm_choice(domain,selected,answer):
    game=answer.get('game') or {};field=domain['ack_field'];value=game.get(field)
    if selected not in domain['available']:raise ValueError('Nolimit City: elección fuera de su dominio')
    if domain['source']=='CLIENT_STATIC_IDS':
        if type(value) is not int or value!=selected:raise ValueError('Nolimit City: elección no confirmada por servidor')
    else:
        if (not isinstance(value,list) or len(value)!=len(domain['options'])
                or any(type(item) is not int or item<-1 for item in value) or value[selected]<0
                or any(old>=0 and value[index]!=old for index,old in enumerate(domain['before']))):
            raise ValueError('Nolimit City: elección no aplicada o dominio del servidor modificado')
