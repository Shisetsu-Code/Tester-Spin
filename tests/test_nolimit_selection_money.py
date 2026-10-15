"""Signed result adjustments require an authorized selection and settled money."""
import copy,json
from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger
from tester_spin.providers.nolimit_city.contracts import resolve_operation

ROW=json.loads((Path(__file__).parent/'fixtures/nolimit_selection_loss.json').read_text())
SOURCE='options:()=>[{id:1},{id:2}],type:c.ASBonusPickOptions.PICK_MODE,pickNeededForModes:[m.SUPER_FREESPIN_END]'

SOURCE+=';e.Auto=class{start(t){n.Game.apiPlugin.betHandler.zeroBet(),t.finish()}};g.gameFlowController.addGameModeFlowStatePresentationMap(b.Mode.SUPER_FREESPIN_AVALANCHE,new Map([[l.FlowState.IDLE,new C.Auto]]));'

def pending():
    ledger=RoundLedger(ROW['before'],ROW['mode'])
    for step in ROW['steps'][:-1]:
        assert not ledger.accept(copy.deepcopy(step['response']),request=step['request'])
    previous=ROW['steps'][-2]['response']
    return ledger,resolve_operation(previous,ROW['mode'],client_source=SOURCE)

def test_client_declared_selection_can_settle_a_lost_accumulated_prize():
    ledger,operation=pending();last=copy.deepcopy(ROW['steps'][-1])
    assert ledger.accept(last['response'],request=last['request'],operation=operation)
    assert str(ledger.win)=='0.00' and str(ledger.after)=='9799.30'

@pytest.mark.parametrize('mutation',['missing_contract','wrong_phase','wrong_ack','wrong_option','charged_request','wrong_balance','wrong_accumulated','excess_loss','missing_balance','pending_win'])
def test_selection_loss_never_bypasses_action_or_money_checks(mutation):
    ledger,operation=pending();last=copy.deepcopy(ROW['steps'][-1]);answer=last['response'];request=last['request']
    if mutation=='missing_contract':operation=None
    elif mutation=='wrong_phase':answer['game']['mode']='OTHER'
    elif mutation=='wrong_ack':answer['game']['playerSelect']=1
    elif mutation=='wrong_option':request['playerInteraction']['selectedIndex']='8'
    elif mutation=='charged_request':request['bet']='1.00'
    elif mutation=='wrong_balance':answer['balance']='9800.30';answer['balances']['TOTAL_BALANCE']='9800.30'
    elif mutation=='wrong_accumulated':answer['game']['accumulatedRoundWin']=1
    elif mutation=='excess_loss':answer['game']['thisSpinWinning']=-44;answer['game']['totalSpinWinnings']=-44
    elif mutation=='missing_balance':answer.pop('balance');answer.pop('balances')
    elif mutation=='pending_win':answer['pendingWin']=True
    with pytest.raises(ValueError):ledger.accept(answer,request=request,operation=operation)


def test_corpus_and_har_analyzer_use_the_authorized_selection_money_contract():
    from tester_spin.providers.nolimit_city.corpus import audit_exchanges
    from tester_spin.providers.nolimit_city.protocol import analyze_messages
    exchanges=[{'request':{'type':'init'},'response':copy.deepcopy(ROW['init'])}]+copy.deepcopy(ROW['steps'])
    report=audit_exchanges(exchanges,client_source=SOURCE)
    assert report['closed_rounds']==1 and not report['money_failures']
    assert not report['unresolved_actions']
    assert not report['ok_certified']
    rows=[]
    for n,pair in enumerate(exchanges):
        request={'type':'init'} if n==0 else {'type':'normal','content':pair['request']}
        rows.extend([{'direction':'sent','message':{**request,'id':str(n)}},
            {'direction':'received','message':{**pair['response'],'id':str(n)}}])
    report=analyze_messages(rows,client_source=SOURCE)
    assert report['closed_rounds']==1 and report['total_win']=='0.00'
    assert not report['pending_round'] and not report['ok_certified']
