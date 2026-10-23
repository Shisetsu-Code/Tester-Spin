"""Indexed host reels and counted guest state from current declarations.

The public client maps INDX entries through each response reelMap and groups
adjacent synchronized columns. Known guest rounds retain feature status until
the guest leaves; only stable, guest-free rounds can prove ordinary play.
Unlearned transformations remain unsupported.
"""
from decimal import Decimal
import re

from .named_actions import _number
from .protocol import command_values


def declaration(props):
    icons=props.get('Icons');height=props.get('WindowHeight')
    joining=props.get('GuestJoiningProbabilities')
    minimum=props.get('MinimumNumberOfSpinsInModeWithGuest')
    if not isinstance(icons,list) or not 1<=len(icons)<=256 or any(not isinstance(v,str) or not 1<=len(v)<=128 for v in icons) or len(set(icons))!=len(icons):return None
    if type(height) is not int or not 1<=height<=64:return None
    if not isinstance(joining,list) or not 1<=len(joining)<=20 or not all(_number(v) for v in joining):return None
    count=len(joining)
    if not isinstance(minimum,list) or len(minimum)!=count or any(not isinstance(row,list) or len(row)!=count or any(type(v) is not int or not 0<=v<=1000 for v in row) for row in minimum):return None
    paylines={name:value for name,value in props.items() if isinstance(name,str) and re.fullmatch(r'Paylines[0-9]*',name)}
    widths=set()
    for lines in paylines.values():
        if not isinstance(lines,list) or not 1<=len(lines)<=4096:return None
        for line in lines:
            if not isinstance(line,list) or not 1<=len(line)<=20 or any(type(v) is not int or not 0<=v<height for v in line):return None
            widths.add(len(line))
    if len(widths)!=1:return None
    strips={}
    for name,value in props.items():
        if not isinstance(value,list) or not value or not all(isinstance(v,str) and re.fullmatch(r'INDX[0-9]{1,3}',v) for v in value):continue
        if not isinstance(name,str) or not 1<=len(name)<=128 or len(value)>100000:return None
        indexes=[int(v[4:]) for v in value]
        if any(v>=len(icons) for v in indexes):return None
        strips[name]=indexes
    if not strips:return None
    types=props.get('IconTypes');prizes=props.get('Prizes');width=widths.pop()
    if not isinstance(types,list) or len(types)!=len(icons) or any(v not in ('S','W','N') for v in types):return None
    if not isinstance(prizes,list) or not prizes or len(prizes)>len(icons):return None
    awards={}
    for row in prizes:
        if not isinstance(row,list) or not 2<=len(row)<=width+1 or row[0] not in icons or row[0] in awards or any(not _number(v) for v in row[1:]):return None
        awards[row[0]]={str(width-len(row)+2+i):str(value) for i,value in enumerate(row[1:])}
    return {'icons':icons,'wilds':[icon for icon,role in zip(icons,types) if role=='W'],'awards':awards,'height':height,'width':width,'hosts':count,'minimum_guest_spins':minimum,'paylines':paylines,'strips':strips}


def ordinary(bet,constraints):
    return _valid(bet,constraints,include_guest=False)


def known(bet,constraints):
    return _valid(bet,constraints,include_guest=True)


def _valid(bet,constraints,*,include_guest):
    try:
        definition=constraints['host_guest_definition'];width=definition['width'];height=definition['height']
        if bet['step']!=1 or bet['status']!='RESULTED' or bet['betcurrency']!=constraints['currency'] or not _number(bet['betamount'],positive=True) or Decimal(str(bet['betamount']))!=Decimal(str(constraints['basic_amount'])):return False
        bd=bet['betdata'];coin=Decimal(str(constraints['basic_coin']))
        if bd.get('cmd') not in (None,'') or not _number(bd.get('coin'),positive=True) or Decimal(str(bd['coin']))!=coin:return False
        ed=bet['eventdata']
        fields={'accC','accWa','features','gameModeCurrent','gameModeNext','paylineSet','reelMap','reelSet','reels','rpos','wonCoins','wts','wtw'}
        if not isinstance(ed,dict) or set(ed)-{'nextCmds','doubleAmount','doubleCount','realmChanged'}!=fields:return False
        if {'doubleAmount','doubleCount'}&set(ed):
            if not {'doubleAmount','doubleCount'}<=set(ed) or type(ed['doubleCount']) is not int or ed['doubleCount'] not in (0,1) or not _number(ed['doubleAmount']) or not _number(ed['accWa']) or Decimal(str(ed['doubleAmount']))!=Decimal(str(ed['accWa'])):return False
        if command_values(ed.get('nextCmds')) not in ([],['C'],['C','*']):return False
        state_fields={'currentHost','currentGuest','currentGuestFeature','remainingSpinInMode','betAmount','coin','paylineSet'}
        before=ed['gameModeCurrent'];after=ed['gameModeNext']
        if not isinstance(before,dict) or not isinstance(after,dict) or set(before)!=state_fields or set(after)!=state_fields:return False
        for state in (before,after):
            host=state['currentHost'];guest=state['currentGuest'];feature=state['currentGuestFeature'];remaining=state['remainingSpinInMode']
            if type(host) is not int or not 0<=host<definition['hosts'] or type(guest) is not int or not 0<=guest<=definition['hosts'] or guest==host:return False
            if type(feature) is not int or type(remaining) is not int or remaining<0:return False
            if guest==definition['hosts']:
                if feature!=-1 or remaining!=0:return False
            elif not include_guest or not 0<=feature<=255 or remaining>definition['minimum_guest_spins'][host][guest]:return False
            if type(state['betAmount']) is not int or state['betAmount']<=0 or not _number(state['coin'],positive=True) or Decimal(str(state['coin']))!=coin or state['paylineSet']!=ed['paylineSet'] or ed['paylineSet'] not in definition['paylines']:return False
        if before['betAmount']!=after['betAmount']:return False
        changed_host=before['currentHost']!=after['currentHost']
        if ('realmChanged' in ed)!=(changed_host) or changed_host and ed['realmChanged'] is not True:return False
        if not include_guest and before!=after:return False
        identity=('currentHost','currentGuest','currentGuestFeature')
        if all(before[key]==after[key] for key in identity):
            if after['remainingSpinInMode']!=max(0,before['remainingSpinInMode']-1):return False
        else:
            if before['remainingSpinInMode']!=0:return False
            if changed_host:
                if after['currentGuest']!=before['currentHost']:return False
            elif before['currentGuest']!=definition['hosts'] and after['currentGuest']!=definition['hosts']:return False
            if after['currentGuest']!=definition['hosts'] and after['remainingSpinInMode']!=definition['minimum_guest_spins'][after['currentHost']][after['currentGuest']]-1:return False
        names=ed['reelSet'].split(',');maps=ed['reelMap'];board=ed['reels'];stops=ed['rpos']
        if len(names)!=width or not all(isinstance(v,list) and len(v)==width for v in (maps,board,stops)):return False
        for name,mapping,column,stop in zip(names,maps,board,stops):
            strip=definition['strips'].get(name)
            if strip is None or type(stop) is not int or not 0<=stop<len(strip):return False
            if not isinstance(mapping,list) or len(mapping)!=len(definition['icons']) or any(not isinstance(v,str) or v not in definition['icons'] for v in mapping):return False
            if not isinstance(column,list) or len(column)!=height:return False
            if column!=[mapping[strip[(stop+row)%len(strip)]] for row in range(height)]:return False
        features=ed['features'];feature_map={}
        if not isinstance(features,list) or len(features)>3:return False
        for item in features:
            if not isinstance(item,dict) or len(item)!=1:return False
            name=next(iter(item))
            if name not in ('synchedReels','spreadingWilds','stackedSymbol') or name in feature_map:return False
            feature_map[name]=item[name]
        if 'stackedSymbol' in feature_map:
            stacked=feature_map['stackedSymbol']
            if type(stacked) is not int or not 0<=stacked<len(definition['icons']):return False
            if any(mapping[0]!=definition['icons'][stacked] for mapping in maps):return False
        if 'synchedReels' in feature_map:
            sync=feature_map['synchedReels']
            if not isinstance(sync,dict) or set(sync)!={'reelsToSync'}:return False
            columns=sync['reelsToSync']
            if not isinstance(columns,list) or not 2<=len(columns)<=width or any(type(v) is not int or not 0<=v<width for v in columns) or columns!=sorted(set(columns)):return False
            groups=[]
            for col in columns:
                if groups and col==groups[-1][-1]+1:groups[-1].append(col)
                else:groups.append([col])
            if any(len(group)<2 for group in groups):return False
            for group in groups:
                first=group[0]
                if any((names[col],maps[col],stops[col],board[col])!=(names[first],maps[first],stops[first],board[first]) for col in group):return False
        final=[list(column) for column in board]
        if 'spreadingWilds' in feature_map:
            spread=feature_map['spreadingWilds']
            if not isinstance(spread,dict) or set(spread)!={'positions','icons'}:return False
            positions=spread['positions'];seen_sources=set();seen_targets=set()
            if not isinstance(positions,list) or not 1<=len(positions)<=width*height:return False
            for item in positions:
                if not isinstance(item,dict) or set(item)!={'from','to'}:return False
                origin=item['from'];targets=item['to']
                if type(origin) is not int or not 0<=origin<width*height or origin in seen_sources:return False
                seen_sources.add(origin);col,row=divmod(origin,height);symbol=board[col][row]
                if symbol not in definition['wilds'] or not isinstance(targets,list) or not 1<=len(targets)<=width*height:return False
                for target in targets:
                    if type(target) is not int or not 0<=target<width*height or target in seen_targets:return False
                    seen_targets.add(target);col,row=divmod(target,height)
                    if board[col][row] in definition['wilds']:return False
                    final[col][row]=symbol
            matrix=spread['icons']
            if not isinstance(matrix,list) or len(matrix)!=height or any(not isinstance(row,list) or len(row)!=width or any(type(v) is not int or not 0<=v<len(definition['icons']) for v in row) for row in matrix):return False
            if final!=[[definition['icons'][matrix[row][col]] for row in range(height)] for col in range(width)]:return False
        wins=ed['wtw'];masks=ed['wts']
        paylines=definition['paylines'][ed['paylineSet']]
        if not isinstance(wins,list) or len(wins)>256 or not isinstance(masks,list) or len(masks)!=2 or any(not isinstance(v,str) or not set(v)<={'0','1'} for v in masks):return False
        if len(masks[0])!=len(paylines) or len(masks[1])!=width*height:return False
        total=Decimal(0);winning_lines=set();winning_positions=0
        for win in wins:
            if not isinstance(win,list) or len(win)!=3 or type(win[0]) is not int or not 1<=win[0]<=len(definition['paylines'][ed['paylineSet']]) or not _number(win[1],positive=True):return False
            mask=win[2]
            if not isinstance(mask,str) or not 1<=len(mask)<=(width*height+3)//4 or not re.fullmatch(r'[0-9a-fA-F]+',mask):return False
            encoded=int(mask,16)
            if encoded<=0 or encoded>=2**(width*height):return False
            if win[0] in winning_lines:return False
            winning_lines.add(win[0]);winning_positions|=encoded
            binary=format(encoded,f'0{width*height}b');positions=[divmod(i,height) for i,value in enumerate(binary) if value=='1']
            columns=[col for col,row in positions]
            if columns!=list(range(len(columns))):return False
            line=definition['paylines'][ed['paylineSet']][win[0]-1]
            if any(line[col]!=row for col,row in positions):return False
            symbols={final[col][row] for col,row in positions}-set(definition['wilds'])
            if len(symbols)!=1:return False
            award=definition['awards'].get(symbols.pop(),{}).get(str(len(positions)))
            if award is None or Decimal(str(win[1]))!=Decimal(award):return False
            total+=Decimal(str(win[1]))
        if masks!=[''.join('1' if i+1 in winning_lines else '0' for i in range(len(paylines))),format(winning_positions,f'0{width*height}b')]:return False
        if not all(_number(ed[k]) for k in ('accC','accWa','wonCoins')):return False
        return Decimal(str(ed['accC']))==Decimal(str(ed['wonCoins']))==total and Decimal(str(ed['accWa']))==total*coin
    except (KeyError,TypeError,ValueError,AttributeError,ArithmeticError):return False
