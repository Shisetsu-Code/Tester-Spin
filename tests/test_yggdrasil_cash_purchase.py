from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from tester_spin.providers.yggdrasil.runtime import continuation_request, validate_transition, Unsupported
from tester_spin.providers.yggdrasil.cash_collect_source import declaration

ROOT=Path(__file__).parent/'fixtures'
DATA=json.loads((ROOT/'yggdrasil_cash_purchase.json').read_text())
CONTEXT={**DATA['context'],'cash_collect_definition':declaration((ROOT/'yggdrasil_cash_collect_source.js').read_text())}


def state(bet):
    bd=bet['betdata'];ed=bet['eventdata']
    commands=bd.get('cmds',[])
    return {'wagerid':'same-round','terminal':False,'bets':[bet],'commands':commands,'max_step':bet['step'],'root_step':1,'cash_balances':{'buy':'1000','result':'1000'}}


def test_current_awarded_cash_purchase_uses_zero_amount_same_command():
    request=continuation_request(state(DATA['awarded']),CONTEXT)
    assert request=={'cmd':'BUYMAXBONUS','type':'bonus','amount':'0','wagerid':'same-round','step':'2','betid':'1'}


@pytest.mark.parametrize('mutation',['state_chain','extra_stake','free_count','played_count','fisherman_count','cash_total','accrued_total','collected_total','wrong_symbol','multiplier_chain','unknown_outcome'])
def test_cash_purchased_transition_rejects_inconsistent_award_or_money(mutation):
    before=state(deepcopy(DATA['free_sequence'][0]));after=state(deepcopy(DATA['free_sequence'][1]))
    b=after['bets'][0];ed=b['eventdata'];cd=ed['response']['clientData']
    if mutation=='state_chain':ed['initialPlayerState']['accumulatedWins']=1
    if mutation=='extra_stake':b['betamount']='20'
    if mutation=='free_count':ed['playerState']['freespinsRemaining']=7
    if mutation=='played_count':ed['playerState']['freespinsPlayed']=2
    if mutation=='fisherman_count':ed['playerState']['accumulatedFishermen']=0
    if mutation=='cash_total':ed['response']['cashWin']='13.21'
    if mutation=='accrued_total':ed['accWa']='13.21'
    if mutation=='collected_total':cd['modifiersData']['collectedCashPrize']=13.21
    if mutation=='wrong_symbol':cd['screen'][0][2]=4096
    if mutation=='multiplier_chain':cd['modifiersData']['currentMultipliers']=[4,8,16,32,64]
    if mutation=='unknown_outcome':cd['bonusChoice']=['ACCEPT']
    request={'cmd':'FREESPIN','type':'bonus','amount':'0','wagerid':'same-round','step':'2','betid':'1'}
    with pytest.raises(Unsupported):validate_transition(before,after,request,CONTEXT)


def test_actual_purchased_free_spins_preserve_award_counts_and_collected_cash():
    for before,after in zip(DATA['free_sequence'],DATA['free_sequence'][1:]):
        chosen=continuation_request(state(before),CONTEXT)
        validate_transition(state(before),state(after),chosen,CONTEXT)


def test_awarded_purchase_requires_current_renderer_and_current_quote():
    for removed in ('cash_collect_definition','purchase_quotes'):
        context={key:value for key,value in CONTEXT.items() if key!=removed}
        with pytest.raises(Unsupported):continuation_request(state(DATA['awarded']),context)


def test_purchase_evidence_keeps_replayable_ledger_without_private_references(tmp_path):
    from tester_spin.providers.yggdrasil.runtime import DemoRuntime
    runtime=DemoRuntime(None,'20002',1,threading.Event(),gate=None)
    runtime.config={'ordinary_constraints':CONTEXT}
    bet=deepcopy(DATA['free_sequence'][1]);bet['betdata']['initialBalance']='private-initial-balance'
    bet['eventdata']['response']['clientData']['wagerId']='private-presentation-reference'
    value={**state(bet),'status':'Pending','wagerid':'private-round-reference'}
    runtime.save(tmp_path,1,{'cmd':'FREESPIN','type':'bonus','amount':'0'},value,transition_validated=True)
    text=(tmp_path/'step-001-response.json').read_text()
    assert 'private-' not in text
    outcome=json.loads(text)['cash_award_outcomes'][0]
    assert outcome['bet']['eventdata']['playerState']['accumulatedWins']==13.2
    assert outcome['bet']['betamount']=='0.00'
