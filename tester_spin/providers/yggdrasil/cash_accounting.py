"""Reconcile paid debits, zero-cost advances and final cash settlement.

This applies only to the newly declared host, cash and cluster families. The
exact prize and the currency-rounded credit remain separate ledger values.
"""
from decimal import Decimal,ROUND_HALF_EVEN
import re

from .cash_collect import close
from .cash_purchase import family as cash_family
from .supermeter import num


def _scope(state,constraints):
    if not isinstance(constraints,dict):return False
    if constraints.get('cash_collect_definition') and cash_family(state):return True
    from .indexed_output import family as indexed_output_family
    if constraints.get('indexed_output_definition') and indexed_output_family(state):return True
    from .cluster_cascades import family as cluster_cascade_family
    if constraints.get('cluster_cascade_definition') and cluster_cascade_family(state):return True
    try:
        event=state['bets'][-1]['eventdata']
        return bool(constraints.get('host_guest_definition')) and isinstance(event,dict) and {'gameModeCurrent','gameModeNext'}<=set(event)
    except (KeyError,TypeError):return False


def _balances(state):
    values=state['cash_balances'];buy=num(values['buy']);result=num(values['result'])
    if min(buy,result)<0:raise ValueError('Negative cash ledger balance')
    return buy,result


def _unit(state,constraints):
    definition=constraints.get('indexed_output_definition')
    if definition:
        places=definition.get('currency_decimal_places')
        if type(places) is not int or not 0<=places<=8:raise ValueError('Current currency precision is missing')
        return Decimal(1).scaleb(-places)
    # Preserve the paid ledger's wire precision across zero-cost steps. The
    # textual formatting of a later zero cannot reduce a known currency unit.
    previous=state.get('cash_accounting_proof',{}).get('settlement_precision')
    if previous is not None:return num(previous)
    amount=state['bets'][0]['betamount']
    if not isinstance(amount,str) or not re.fullmatch(r'[0-9]+\.[0-9]{1,8}',amount):raise ValueError('Undeclared cash settlement precision')
    return Decimal(1).scaleb(Decimal(amount).as_tuple().exponent)


def paid(state,constraints):
    if not _scope(state,constraints):return None
    root=state['bets'][0];initial=num(root['betdata']['initialBalance'])
    buy,result=_balances(state);stake=sum((num(bet['betamount']) for bet in state['bets']),Decimal(0))
    credit=sum((num(bet['wonamount']) for bet in state['bets']),Decimal(0))
    if initial-buy!=stake or result-buy!=credit or credit<0:raise ValueError('Paid debit or credited win disagrees with cash ledger')
    return {'schema':'current-cash-ledger/v1','debit':str(stake),'credit':str(credit),'balance_delta_verified':True,'settlement_precision':str(_unit(state,constraints))}


def transition(before,after,request,constraints):
    if not _scope(before,constraints):return None
    _,previous_result=_balances(before);buy,result=_balances(after)
    generated=[bet for bet in after['bets'] if bet['step']>before['max_step']]
    if len(after['bets'])!=1 or len(generated)!=1 or generated[0]['step']!=before['max_step']+1:
        raise ValueError('Unlearned multiple or skipped cash result steps')
    credit=sum((num(bet['wonamount']) for bet in generated),Decimal(0))
    if not generated or previous_result!=buy or result-buy!=credit or credit<0:raise ValueError('Zero-cost continuation changed cash balance or credit')
    unit=_unit(before,constraints)
    proof={'schema':'current-cash-ledger/v1','debit':'0','credit':str(credit),'balance_delta_verified':True,'settlement_precision':str(unit)}
    if request['cmd']!='C':return proof
    prior=before['bets'][-1];current=next(b for b in generated if b['step']==int(request['step']))
    if not after['terminal'] or after['commands'] or current['status']!='RESULTED':raise ValueError('Cash collect did not finish the wager')
    exact=num(prior['eventdata']['accWa']);event=current['eventdata']
    if set(event)!={'exactWon'} or not close(event['exactWon'],exact):raise ValueError('Collected exact win changed the accrued prize')
    settled=num(current['wonamount'])
    if settled!=exact.quantize(unit,rounding=ROUND_HALF_EVEN):raise ValueError('Rounded collected prize disagrees with exact win')
    bd=current['betdata']
    for key in ('accWa','doubleA'):
        if key in bd and not close(bd[key],exact):raise ValueError('Collect echo changed the accrued prize')
    prizes=current['prizes']
    if not isinstance(prizes,list) or len(prizes)!=1:raise ValueError('Unlearned cash prize settlement')
    prize=prizes[0]
    if prize.get('type')!='FIXED' or prize.get('wonAspect')!='CASH' or prize.get('woncurrency')!=current['betcurrency'] or num(prize['wonamount'])!=settled or num(prize['netamount'])!=settled:raise ValueError('Cash prize or net credit changed at settlement')
    proof.update(exact_win=str(exact),settled_win=str(settled),settlement_precision=str(unit))
    return proof
