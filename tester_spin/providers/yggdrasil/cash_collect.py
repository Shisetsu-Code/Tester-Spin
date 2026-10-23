"""Current-stake numeric cash rows with inactive collection and free-spin state.

The client assigns payout to both amount and multipliedAmount. Displayed
cash-prize symbols are not paid until the explicit collection control is set.
"""
from decimal import Decimal
import math

from .protocol import command_values
from .supermeter import num


def close(left,right):
    values=[num(left),num(right)]
    if not all(math.isfinite(float(value)) for value in values):return False
    tolerance=sum((Decimal(str(math.ulp(float(value))))*4 for value in values),Decimal(0))
    return abs(values[0]-values[1])<=tolerance


def cash_result(response,constraints,*,awarded=False):
    """Validate displayed positions and the already multiplied cash ledger."""
    try:
        if not isinstance(response,dict) or set(response)!={'coinWin','cashWin','clientData'} or num(response['coinWin'])!=0:return None
        cd=response['clientData'];geometry=constraints['growing_ways_geometry']
        if not isinstance(cd,dict) or set(cd)!={'screen','winningRows','cashPrizes','modifiersData','bonusData','wagerId'}:return None
        if not isinstance(cd['wagerId'],str) or not 1<=len(cd['wagerId'])<=4096:return None
        board=cd['screen'];height=geometry['initial_heights'];width=geometry['width']
        if not isinstance(board,list) or len(board)!=width or not all(isinstance(col,list) and all(type(v) is int and 0<=v<=4096 for v in col) for col in board) or list(map(len,board))!=height:return None
        mod=cd['modifiersData'];bonus=cd['bonusData']
        if not isinstance(mod,dict) or set(mod)!={'currentMultipliers','activeMultiplier','collectFish','collectedCashPrize'} or type(mod['collectFish']) is not bool:return None
        multipliers=mod['currentMultipliers'];active=num(mod['activeMultiplier'])
        if not isinstance(multipliers,list) or len(multipliers)!=width or any(type(v) is not int or not 1<=v<=1000000 for v in multipliers) or any(b!=a*2 for a,b in zip(multipliers,multipliers[1:])):return None
        if not 1<=active<=1000000 or active!=active.to_integral_value():return None
        if not isinstance(bonus,dict) or set(bonus)!={'bonusTriggered','freespinsAwarded'} or bonus['bonusTriggered'] is not awarded or type(bonus['freespinsAwarded']) is not int:return None
        if not (1<=bonus['freespinsAwarded']<=1000 if awarded else bonus['freespinsAwarded']==0):return None
        roles=constraints.get('cash_collect_definition');prizes=cd['cashPrizes'];seen_prizes=set();prize_total=Decimal(0)
        if not isinstance(prizes,list) or len(prizes)>sum(height):return None
        for prize in prizes:
            if not isinstance(prize,dict) or set(prize)!={'cashPrize','position'}:return None
            pos=prize['position']
            if not isinstance(pos,dict) or set(pos)!={'reel','row'} or any(type(v) is not int for v in pos.values()):return None
            col=pos['reel'];row=pos['row'];key=(col,row)
            if not 0<=col<width or not 0<=row<height[col] or key in seen_prizes or num(prize['cashPrize'])<=0:return None
            seen_prizes.add(key);prize_total+=num(prize['cashPrize'])
        if roles is not None:
            expected={(col,row) for col,values in enumerate(board) for row,value in enumerate(values) if value==roles['cash']}
            collectors=[(col,row) for col,values in enumerate(board) for row,value in enumerate(values) if value==roles['collector']]
            if expected!=seen_prizes or len(collectors)>1 or bool(collectors)!=mod['collectFish']:return None
        elif mod['collectFish']:return None
        collected=num(mod['collectedCashPrize'])
        expected=prize_total*num(constraints['basic_amount'])*active if mod['collectFish'] else Decimal(0)
        if not close(collected,expected) or mod['collectFish'] and not seen_prizes:return None
        rows=cd['winningRows'];total=collected;symbols=set()
        if not isinstance(rows,list) or len(rows)>256:return None
        for win in rows:
            if not isinstance(win,dict) or set(win)!={'symbol','winning_ways','payout','positions'} or type(win['symbol']) is not int or not 0<=win['symbol']<=4096 or win['symbol'] in symbols:return None
            symbols.add(win['symbol']);positions=win['positions'];seen=set();columns={}
            if not isinstance(positions,list) or not 1<=len(positions)<=sum(height):return None
            for pos in positions:
                if not isinstance(pos,dict) or set(pos)!={'reel','row'} or any(type(v) is not int for v in pos.values()):return None
                col=pos['reel'];row=pos['row']
                if not 0<=col<width or not 0<=row<height[col] or (col,row) in seen:return None
                seen.add((col,row));columns[col]=columns.get(col,0)+1
            if sorted(columns)!=list(range(len(columns))) or type(win['winning_ways']) is not int or win['winning_ways']!=math.prod(columns.values()):return None
            allowed={win['symbol']}|({roles['wild']} if roles is not None else set())
            if not all(board[col][row] in allowed for col,row in seen) or not any(board[col][row]==win['symbol'] for col,row in seen):return None
            payout=num(win['payout'])
            if payout<=0:return None
            total+=payout
        cash=num(response['cashWin'])
        if cash<0 or not close(cash,total):return None
        return {'cash':cash,'collected':mod['collectFish'],'modifiers':mod,'awarded':bonus['freespinsAwarded']}
    except (KeyError,TypeError,ValueError,AttributeError,ArithmeticError):return None


def ordinary(bet,constraints):
    try:
        geometry=constraints['growing_ways_geometry']
        if bet['step']!=1 or bet['status']!='RESULTED' or bet['betcurrency']!=constraints['currency'] or num(bet['betamount'])!=num(constraints['basic_amount']):return False
        bd=bet['betdata'];ed=bet['eventdata']
        if bd.get('cmd')!='BASE_SPIN' or num(bd['cashBet'])!=num(constraints['basic_amount']) or num(bd['coin'])!=num(constraints['basic_coin']):return False
        fields={'accC','accWa','boostData','initialPlayerState','playerState','response'}
        if not isinstance(ed,dict) or set(ed) not in (fields,fields|{'nextCmds'}):return False
        result=cash_result(ed['response'],constraints)
        if result is None or result['collected']:return False
        state_fields={'freespinsRemaining','freespinsPlayed','accumulatedFishermen','accumulatedWins','goldenBet','buyBonus','variant'}
        initial=ed['initialPlayerState'];final=ed['playerState']
        for state in (initial,final):
            if not isinstance(state,dict) or set(state)!=state_fields:return False
            if type(state['freespinsRemaining']) is not int or state['freespinsRemaining']!=0:return False
            if any(type(state[k]) is not int or not 0<=state[k]<=1000000 for k in ('freespinsPlayed','accumulatedFishermen')) or state['accumulatedFishermen']>state['freespinsPlayed']:return False
            if type(state['goldenBet']) is not bool or type(state['buyBonus']) is not bool or type(state['variant']) is not int or not 0<=state['variant']<=4096 or num(state['accumulatedWins'])<0:return False
        if final['goldenBet'] or final['buyBonus'] or final['freespinsPlayed'] or final['accumulatedFishermen']:return False
        if initial['variant']!=final['variant']:return False
        cash=result['cash']
        if any(not close(v,cash) for v in (bd['accWa'],ed['accWa'],final['accumulatedWins'])):return False
        if any(num(v)!=0 for v in (bd['accC'],ed['accC'])):return False
        boost=ed['boostData']
        if not isinstance(boost,dict) or set(boost)!={'winningSpins','collectFishSpins','multiplierx4Spins'} or any(type(v) is not int or v not in (0,1) for v in boost.values()):return False
        if boost['winningSpins']!=int(cash>0) or boost['collectFishSpins']!=0:return False
        multiplier=num(result['modifiers']['activeMultiplier'])
        # Only the observed below-four / four telemetry relationship is known.
        # Higher display multipliers cannot establish this counter's semantics.
        if multiplier not in (1,2,4) or boost['multiplierx4Spins']!=int(multiplier==4):return False
        commands=command_values(ed.get('nextCmds'))
        return commands==(['C'] if cash>0 else []) and command_values(bd.get('cmds'))==commands
    except (KeyError,TypeError,ValueError,AttributeError,ArithmeticError):return False


def neutral_ante(bet,constraints):
    """A current priced ante with no award or carried feature is known, not base.

    The current request constructor binds the command to the golden flag and
    amount == coin. This limited branch does not infer a payout scale or bonus
    continuation for a winning/awarded ante.
    """
    try:
        command=constraints['cash_collect_definition']['ante_command']
        quote=constraints['ante_quotes'][command]
        bd=bet['betdata'];ed=bet['eventdata']
        if bet['step']!=1 or bet['status']!='RESULTED' or bet['betcurrency']!=constraints['currency'] or num(bet['betamount'])!=num(quote['amount']) or num(bet['wonamount'])!=0:return False
        if quote['cmd']!=command or num(quote['amount'])!=num(quote['coin']) or num(quote['coins'])!=1 or num(quote['amount'])<=num(constraints['basic_amount']):return False
        if bd.get('cmd')!=command or num(bd['cashBet'])!=num(quote['amount']) or num(bd['coin'])!=num(quote['coin']) or command_values(bd.get('cmds')):return False
        if set(ed)!={'accC','accWa','initialPlayerState','playerState','response'}:return False
        result=cash_result(ed['response'],constraints)
        if result is None or result['cash']!=0 or result['collected'] or num(result['modifiers']['activeMultiplier'])!=1 or result['modifiers']['currentMultipliers'][0]!=1:return False
        if ed['response']['clientData']['winningRows']!=[]:return False
        initial=ed['initialPlayerState'];final=ed['playerState']
        fields={'freespinsRemaining','freespinsPlayed','accumulatedFishermen','accumulatedWins','goldenBet','buyBonus','variant'}
        if not isinstance(initial,dict) or set(initial)!=fields or initial['goldenBet'] is not False or initial['buyBonus'] is not False:return False
        if any(type(initial[key]) is not int or initial[key]!=0 for key in ('freespinsRemaining','freespinsPlayed','accumulatedFishermen')):return False
        if type(initial['variant']) is not int or not 0<=initial['variant']<=4096 or num(initial['accumulatedWins'])!=0:return False
        if not isinstance(final,dict) or final!={**initial,'goldenBet':True} or final['goldenBet'] is not True:return False
        if final['buyBonus'] is not False or any(type(final[key]) is not int for key in ('freespinsRemaining','freespinsPlayed','accumulatedFishermen','variant')):return False
        return all(num(value)==0 for value in (bd['accC'],ed['accC'],bd['accWa'],ed['accWa']))
    except (KeyError,TypeError,ValueError,AttributeError,ArithmeticError):return False
