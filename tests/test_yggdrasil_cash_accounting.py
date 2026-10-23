from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from tester_spin.providers.yggdrasil.runtime import DemoRuntime,Unsupported,wager_state,validate_transition,configuration
from tester_spin.providers.yggdrasil.cash_collect_source import declaration

ROOT=Path(__file__).parent/'fixtures'
DATA=json.loads((ROOT/'yggdrasil_cash_settlement.json').read_text())
CASH=json.loads((ROOT/'yggdrasil_cash_purchase.json').read_text())['context']
CASH={**CASH,'cash_collect_definition':declaration((ROOT/'yggdrasil_cash_collect_source.js').read_text())}
HOST=configuration(json.loads((ROOT/'yggdrasil_host_guest.json').read_text())['game'],'20001','EUR')['ordinary_constraints']


@pytest.mark.parametrize('family,context',[('cash',CASH),('host',HOST)])
@pytest.mark.parametrize('mutation',['won','exact','prize','credit','new_debit','nonterminal'])
def test_final_collect_reconciles_exact_payout_prize_credit_and_balance(family,context,mutation):
    sequence=deepcopy(DATA[family][0]);before=wager_state(sequence[-2]);payload=sequence[-1]
    bet=payload['data']['wager']['bets'][-1]
    if mutation=='won':bet['wonamount']='999.99'
    if mutation=='exact':bet['eventdata']['exactWon']='999.99'
    if mutation=='prize':bet['prizes'][0]['netamount']='999.99'
    if mutation=='credit':payload['data']['resultBal']['cash']='99999.99'
    if mutation=='new_debit':payload['data']['buyBal']['cash']='99999.99'
    if mutation=='nonterminal':payload['data']['wager']['status']='Pending'
    after=wager_state(payload);request={'cmd':'C','amount':'0','wagerid':before['wagerid'],'step':str(bet['step']),'betid':'1'}
    with pytest.raises(Unsupported):validate_transition(before,after,request,context)


@pytest.mark.parametrize('family,context',[('cash',CASH),('host',HOST)])
def test_paid_round_rejects_a_balance_debit_different_from_its_echoed_stake(tmp_path,family,context):
    sequence=deepcopy(DATA[family][0]);sequence[0]['data']['buyBal']['cash']='99999.99'
    runtime=DemoRuntime(None,'20001',1,threading.Event(),gate=None)
    runtime.config={'ordinary_constraints':context}
    replies=iter(sequence);runtime.call=lambda *args,**kwargs:next(replies)
    template={'coin':context['basic_coin'],'amount':context['basic_amount'],'coins':'50' if family=='host' else '1'}
    if family=='host':template['lines']='1'*len(context['host_guest_definition']['paylines']['Paylines'])
    with pytest.raises(Unsupported):runtime.round(template,tmp_path)


@pytest.mark.parametrize('family,context',[('cash',CASH),('host',HOST)])
def test_recorded_complete_rounds_reconcile_every_cash_advance_and_settlement(tmp_path,family,context):
    for index,sequence in enumerate(DATA[family]):
        root=sequence[0]['data']['wager']['bets'][0];bd=root['betdata']
        runtime=DemoRuntime(None,'20001',1,threading.Event(),gate=None)
        runtime.config={'ordinary_constraints':context}
        replies=iter(deepcopy(sequence));runtime.call=lambda *args,**kwargs:next(replies)
        template={'coin':bd['coin'],'amount':root['betamount'],'coins':'50' if family=='host' else '1'}
        if family=='host':template['lines']=bd['lines']
        if bd.get('cmd') not in (None,'','BASE_SPIN'):template['cmd']=bd['cmd']
        result=runtime.round(template,tmp_path/str(index))
        assert result['terminal'] and result['known']
        evidence=json.loads((tmp_path/str(index)/f'step-{len(sequence):03d}-response.json').read_text())
        assert evidence['cash_accounting']['balance_delta_verified']
        assert evidence['cash_accounting']['credit']==sequence[-1]['data']['wager']['bets'][-1]['wonamount']
        assert evidence['cash_accounting']['settled_win']==evidence['cash_accounting']['credit']
        if family=='host':
            assert evidence['cash_accounting']['exact_win']=='0.272'
            assert evidence['cash_accounting']['settled_win']=='0.27'


@pytest.mark.parametrize('family,context',[('cash',CASH),('host',HOST)])
@pytest.mark.parametrize('position',['paid','collect'])
def test_zero_cost_unproved_extra_steps_cannot_hide_behind_a_closed_known_root(tmp_path,family,context,position):
    values=deepcopy(DATA[family][0])
    target=values[0] if position=='paid' else values[-1]
    wager=target['data']['wager']
    wager['status']='Finished'
    wager['bets'].append({'step':max(bet['step'] for bet in wager['bets'])+1,'status':'RESULTED',
        'betamount':'0.00','betcurrency':'EUR','wonamount':'0.00',
        'betdata':{'cmd':'UNLEARNED_AUTOMATIC_STEP'},'eventdata':{'pendingCounter':1}})
    runtime=DemoRuntime(None,'20001',1,threading.Event(),gate=None)
    runtime.config={'ordinary_constraints':context}
    replies=iter(values);runtime.call=lambda *args,**kwargs:next(replies)
    root=values[0]['data']['wager']['bets'][0];bd=root['betdata']
    template={'coin':bd['coin'],'amount':root['betamount'],'coins':'50' if family=='host' else '1'}
    if family=='host':template['lines']=bd['lines']
    if bd.get('cmd') not in (None,'','BASE_SPIN'):template['cmd']=bd['cmd']
    with pytest.raises(Unsupported,match='multiple|step|batch'):
        runtime.round(template,tmp_path)
