import copy,json
from pathlib import Path
from decimal import Decimal
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger
ROW=json.loads((Path(__file__).parent/'fixtures/nolimit_paid_annotation.json').read_text())

def pending():
    ledger=RoundLedger(ROW['before'],ROW['mode'])
    for step in ROW['steps'][:-1]:assert not ledger.accept(copy.deepcopy(step['answer']),request=step['request'])
    return ledger

def test_paid_normal_settlement_is_not_reopened_by_a_feature_annotation():
    ledger=pending();last=ROW['steps'][-1]
    assert ledger.accept(copy.deepcopy(last['answer']),request=last['request'])
    assert ledger.after==ledger.before-ledger.cost+ledger.win
    assert ledger.last_answer['feature_observation']['kind']=='PAID_SETTLEMENT_ANNOTATION'

@pytest.mark.parametrize('mutation',['pending_win','pending_counter','unknown_menu','different_next_phase','missing_balance','missing_credit'])
def test_annotation_is_not_ignored_without_independent_paid_settlement(mutation):
    ledger=pending();last=copy.deepcopy(ROW['steps'][-1]);answer=last['answer']
    if mutation=='pending_win':answer['pendingWin']=True
    elif mutation=='pending_counter':answer['game']['respinsLeft']=1
    elif mutation=='unknown_menu':answer['features']['available']=['PICK_NEW']
    elif mutation=='different_next_phase':answer['game']['nextMode']='CHOICE'
    elif mutation=='missing_balance':answer.pop('balance');answer.pop('balances')
    elif mutation=='missing_credit':answer['balance']=str(ledger.before-ledger.cost);answer['balances']['TOTAL_BALANCE']=answer['balance']
    try:closed=ledger.accept(answer,request=last['request'])
    except ValueError:closed=False
    assert not closed
