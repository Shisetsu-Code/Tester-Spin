"""Consume a current cash/collector award without charging another purchase."""
from .cash_collect import cash_result,close
from .protocol import command_values
from .supermeter import num

STATE_FIELDS={'freespinsRemaining','freespinsPlayed','accumulatedFishermen','accumulatedWins','goldenBet','buyBonus','variant'}


def family(state):
    try:
        ed=state['bets'][-1]['eventdata'];cd=ed['response']['clientData']
        return isinstance(cd,dict) and {'screen','cashPrizes','modifiersData','bonusData'}<=set(cd)
    except (KeyError,TypeError,AttributeError):return False


def _player(state):
    return (isinstance(state,dict) and set(state)==STATE_FIELDS and
        all(type(state[k]) is int and 0<=state[k]<=1000000 for k in ('freespinsRemaining','freespinsPlayed','accumulatedFishermen','variant')) and
        state['freespinsRemaining']<=1000 and state['accumulatedFishermen']<=state['freespinsPlayed'] and
        type(state['buyBonus']) is bool and state['goldenBet'] is False and num(state['accumulatedWins'])>=0)


def _quote(bet,constraints):
    bd=bet['betdata'];quotes=constraints['purchase_quotes']
    candidates=[quotes[bd['cmd']]] if bd['cmd'] in quotes else list(quotes.values()) if bd['cmd']=='FREESPIN' else []
    matching=[quote for quote in candidates if num(bd['coin'])==num(quote['coin']) and num(bd['cashBet'])==num(quote['amount'])]
    return matching[0] if len(matching)==1 else None


def awarded(bet,constraints):
    try:
        if 'cash_collect_definition' not in constraints:return False
        bd=bet['betdata'];ed=bet['eventdata'];quote=_quote(bet,constraints)
        if quote is None or bd['cmd'] not in constraints['purchase_quotes'] or bet['step']!=1 or bet['status']!='RESULTED' or bet['betcurrency']!=constraints['currency'] or num(bet['betamount'])!=num(quote['amount']) or num(bet['wonamount'])!=0:return False
        if set(ed)!={'accC','accWa','initialPlayerState','playerState','nextCmds','response'}:return False
        result=cash_result(ed['response'],constraints,awarded=True)
        if result is None or result['cash']!=0 or result['collected'] or num(result['modifiers']['activeMultiplier'])!=1:return False
        if ed['response']['clientData']['winningRows']!=[]:return False
        initial=ed['initialPlayerState'];final=ed['playerState']
        if not _player(initial) or not _player(final) or initial['variant']!=final['variant']:return False
        if initial['freespinsRemaining']!=0 or initial['buyBonus'] or final['buyBonus'] is not True or final['freespinsRemaining']!=result['awarded']:return False
        if any(state[k]!=0 for state in (initial,final) for k in ('freespinsPlayed','accumulatedFishermen')):return False
        if any(num(value)!=0 for value in (ed['accC'],bd['accC'],ed['accWa'],bd['accWa'],final['accumulatedWins'])):return False
        commands=command_values(ed['nextCmds'])
        return command_values(bd.get('cmds'))==commands and (commands==[bd['cmd']] or set(commands)=={'FREESPIN','GAMBLE'} and len(commands)==2)
    except (KeyError,TypeError,ValueError,AttributeError,ArithmeticError):return False


def active(bet,constraints):
    try:
        if 'cash_collect_definition' not in constraints:return False
        bd=bet['betdata'];ed=bet['eventdata'];quote=_quote(bet,constraints)
        if quote is None or type(bet['step']) is not int or bet['step']<=1 or bet['status']!='RESULTED' or bet['betcurrency']!=constraints['currency'] or num(bet['betamount'])!=0 or num(bet['wonamount'])!=0:return False
        if set(ed)-{'nextCmds'}!={'accC','accWa','initialPlayerState','playerState','response'}:return False
        result=cash_result(ed['response'],constraints)
        if result is None:return False
        initial=ed['initialPlayerState'];final=ed['playerState']
        if not _player(initial) or not _player(final) or initial['variant']!=final['variant']:return False
        if initial['buyBonus'] is not True or final['buyBonus'] is not True or initial['freespinsRemaining']<=0:return False
        caught=int(result['collected'])
        if final['freespinsRemaining']!=initial['freespinsRemaining']-1+caught or final['freespinsPlayed']!=initial['freespinsPlayed']+1 or final['accumulatedFishermen']!=initial['accumulatedFishermen']+caught:return False
        expected=num(initial['accumulatedWins'])+result['cash']
        if any(not close(value,expected) for value in (final['accumulatedWins'],ed['accWa'],bd['accWa'])) or num(ed['accC'])!=0 or num(bd['accC'])!=0:return False
        commands=command_values(ed.get('nextCmds'))
        expected_commands=[bd['cmd']] if final['freespinsRemaining']>0 else ['C'] if expected>0 else []
        return commands==expected_commands and command_values(bd.get('cmds'))==commands
    except (KeyError,TypeError,ValueError,AttributeError,ArithmeticError):return False


def request(state,constraints):
    try:
        if state['terminal'] or not family(state):return None
        bet=state['bets'][-1]
        if not (awarded(bet,constraints) or active(bet,constraints)) or bet['eventdata']['playerState']['freespinsRemaining']<=0:return None
        offered=command_values(bet['eventdata']['nextCmds'])
        if state['commands']!=offered:return None
        commands=[value for value in offered if value!='GAMBLE']
        if len(commands)!=1:return None
        return {'cmd':commands[0],'type':'bonus','amount':'0','wagerid':state['wagerid'],'step':str(state['max_step']+1),'betid':str(state['root_step'])}
    except (KeyError,TypeError,ValueError,AttributeError,ArithmeticError):return None


def validate_transition(before,after,chosen,constraints):
    if chosen.get('type')!='bonus' or not family(before):return False
    expected=request(before,constraints)
    if expected is None or chosen!=expected:raise ValueError('Unlearned cash award continuation')
    prior=before['bets'][-1]['eventdata']
    bet=next(b for b in after['bets'] if b['step']==int(chosen['step']))
    if not active(bet,constraints):raise ValueError('Cash award outcome disagrees with current state or ledger')
    current=bet['eventdata']
    if current['initialPlayerState']!=prior['playerState']:raise ValueError('Cash award state chain changed')
    previous=prior['response']['clientData']['modifiersData'];now=current['response']['clientData']['modifiersData']
    multiplier=num(now['activeMultiplier'])
    if multiplier!=1 and multiplier not in previous['currentMultipliers']:raise ValueError('Cash award used an undeclared active multiplier')
    factor=2 if now['collectFish'] else 1
    if now['currentMultipliers']!=[value*factor for value in previous['currentMultipliers']]:raise ValueError('Cash award multiplier chain changed')
    if not close(num(prior['accWa'])+num(current['response']['cashWin']),current['accWa']):raise ValueError('Cash award accrued money changed')
    return True
