"""Bind numeric cash/collector/wild roles to the current official renderer.

Values are extracted from the renderer's symbol comparisons, never inferred
from an ID, a title, a command alias, or a previously observed board.
"""
import hashlib
import re


def _ante_command(source):
    from .sdk_purchase_list_roles import IDENT, methods
    commands=[]
    for _,args,body in methods(source,'getSpinRequestParams'):
        if args:continue
        pattern=(r'var ('+IDENT+r')=\{amount:this\.game\.getTotalBetInCash\(\),coin:this\.game\.getTotalBetInCash\(\)\};'
                 r'return!this\.scope\.game\.goldenBetActive\|\|this\.scope\.game\.feature&&this\.scope\.game\.feature\.active\|\|\(\1\.cmd="([A-Z][A-Z0-9_]{0,63})"\),'
                 r'this\.scope\.game\.buyBonusActivated&&!this\.scope\.game\.isMaxBuyBonus&&\(this\.communication\.lastFreespin=null,\1\.cmd="([A-Z][A-Z0-9_]{0,63})",\1\.amount\*=([1-9][0-9]{0,5}),\1\.coin\*=\4\),'
                 r'this\.scope\.game\.isMaxBuyBonus&&\(\1\.cmd="([A-Z][A-Z0-9_]{0,63})",\1\.amount\*=([1-9][0-9]{0,5}),\1\.coin\*=\6,this\.scope\.game\.maxBonusTriggered=!0\),\1')
        match=re.fullmatch(pattern,body)
        if match and len({match[2],match[3],match[5]})==3:commands.append(match[2])
    return commands[0] if len(commands)==1 else None


def _functions(source,method):
    pattern=r'([\w.]+)\.prototype\.'+method+r'=function\(([\w,]+)\)\{'
    for match in re.finditer(pattern,source):
        depth=1;end=match.end()
        while depth and end<min(len(source),match.end()+10000):
            value=source[end]
            # This learned renderer contains no literals/comments in these
            # functions. A different JS grammar needs a separate parser.
            if value in "'\"`" or source[end:end+2] in ('//','/*'):break
            depth+=int(value=='{')-int(value=='}');end+=1
        if depth==0:yield match.group(1),match.group(2).split(','),source[match.end():end-1]


def declaration(source):
    if not isinstance(source,str):return None
    matches=[]
    for scope,args,body in _functions(source,'mapReels'):
        if len(args)!=2:continue
        inp,out=map(re.escape,args)
        # forEach(function(column,reel){column.forEach(function(symbol,row){...})})
        coordinates=re.search(inp+r'\.screen&&'+inp+r'\.screen\.forEach\(function\((\w+),(\w+)\)\{\1\.length;\1\.forEach\(function\((\w+),(\w+)\)\{var (\w+),(\w+)=\4;',body)
        if coordinates is None:continue
        _,col,symbol,row,price,index=map(re.escape,coordinates.groups())
        roles={}
        patterns={
            'wild':r'(\d+)=='+symbol+r'&&'+out+r'\.wildSymbols\.push\(\{reelIndex:'+col+r',symbolIndex:'+index+r',symbol:'+symbol+r'\}\)',
            'collector':r'(\d+)=='+symbol+r'&&'+out+r'\.fishermanSymbol\.push\(\{reelIndex:'+col+r',symbolIndex:'+index+r',sym:this\.mapSymbol\('+symbol+r'\)\}\)',
            'scatter':r'(\d+)=='+symbol+r'&&\('+out+r'\.totalScatterCount\+\+,'+out+r'\.scatterCount\['+col+r'\]\+\+,'+out+r'\.bonusSym\.push\(\{reelIndex:'+col+r',symIndex:'+row+r',sym:this\.mapSymbol\('+symbol+r'\)\}\)\)',
            'cash':r'(\d+)=='+symbol+r'&&\('+price+r'=null,'+inp+r'\.cashPrizes\.forEach\(function\((\w+)\)\{\2\.position\.reel=='+col+r'&&\2\.position\.row=='+index+r'&&\('+price+r'=\2\.cashPrize\)\},this\),'+out+r'\.fishSymbols\.push\(\{reelIndex:'+col+r',symbolIndex:'+index+r',sym:this\.mapSymbol\('+symbol+r'\),prize:'+price+r'\}\)\)',
        }
        for role,pattern in patterns.items():
            values=list(re.finditer(pattern,body))
            if len(values)!=1:break
            roles[role]=int(values[0].group(1))
        if len(roles)!=4 or len(set(roles.values()))!=4 or max(roles.values())>4096:continue
        if args[1]+'.reels.middle['+coordinates.group(2)+']['+coordinates.group(6)+']=this.mapSymbol('+coordinates.group(3)+')' not in body:continue
        win_functions=[(params,code) for owner,params,code in _functions(source,'mapWinlines') if owner==scope]
        if len(win_functions)!=1:continue
        params,code=win_functions[0]
        if len(params)!=3:continue
        win=re.escape(params[2])
        if not re.search(r'(\w+)\.amount='+win+r'\.payout,\1\.multipliedAmount='+win+r'\.payout,\1\.symbol=this\.mapSymbol\('+win+r'\.symbol\),\1\.id='+win+r'\.winning_ways,\1\.positions=\[\],'+win+r'\.positions\.forEach\(',code):continue
        matches.append(roles)
    if len(matches)!=1:return None
    result={'schema':'numeric-cash-collector-renderer/v1',**matches[0],'source_sha256':hashlib.sha256(source.encode()).hexdigest()}
    ante=_ante_command(source)
    if ante is not None:result['ante_command']=ante
    return result
