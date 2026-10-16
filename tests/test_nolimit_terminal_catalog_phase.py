import copy
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger
from tester_spin.providers.nolimit_city.contracts import resolve_operation
from test_nolimit_bulk_observations import MODE, ANSWER, REQ


def round_pair():
    first=copy.deepcopy(ANSWER)
    first['features']={'available':[], 'active':'FREESPIN'}
    first['game'].update(nextMode='FREESPIN',freespinsLeft=1,win=1,accumulatedRoundWin=1)
    first['remainingFreeSpins']=1
    ledger=RoundLedger('10000',MODE)
    assert not ledger.accept(first,request=REQ)
    operation=resolve_operation(ledger.last_answer,MODE,raw_answer=first)
    final=copy.deepcopy(ANSWER)
    final['game'].update(mode='FREESPIN',win=2,accumulatedRoundWin=3)
    final['balance']='10002.80'
    return ledger,operation,final


def test_terminal_purchase_subset_after_acknowledged_bonus_continuation():
    ledger,op,final=round_pair()
    assert ledger.accept(final,request=op['request'],operation=op)
    assert ledger.last_answer['feature_observation']['kind']=='SETTLED_CATALOG_SUBSET'


@pytest.mark.parametrize('change',[
    lambda op,a,r:op['acknowledgment'].update(phase='OTHER'),
    lambda op,a,r:r.update(type='normalBet'),
    lambda op,a,r:a['game'].update(freespinsLeft=1),
    lambda op,a,r:a['features'].update(available=['UNKNOWN']),
    lambda op,a,r:a.update(pendingWin=True),
    lambda op,a,r:a.update(balance='10002.70'),
])
def test_bonus_catalog_subset_keeps_ack_money_and_pending_checks(change):
    ledger,op,final=round_pair();request=dict(op['request'])
    change(op,final,request)
    with pytest.raises(ValueError):
        ledger.accept(final,request=request,operation=op)


def test_bonus_catalog_subset_does_not_close_without_operation():
    ledger,op,final=round_pair()
    with pytest.raises(ValueError):ledger.accept(final,request=op['request'])



def test_terminal_subset_can_retain_acknowledged_current_purchase_label():
    mode=dict(MODE,kind='PURCHASE',selector='BASIC',price_multiplier=10)
    request={'type':'featureBet','bet':'.20','featureName':'BASIC','playerInteraction':{'featureName':'BASIC'}}
    answer=copy.deepcopy(ANSWER);answer['features']['active']='BASIC'
    answer['game'].update(wasFeatureBuy=True,win=3,accumulatedRoundWin=3)
    answer['balance']='10001.00'
    ledger=RoundLedger('10000',mode)
    assert ledger.accept(answer,request=request)


@pytest.mark.parametrize('label',['STRONG','UNKNOWN'])
def test_active_label_from_another_purchase_never_becomes_current_receipt(label):
    mode=dict(MODE,kind='PURCHASE',selector='BASIC',price_multiplier=10)
    request={'type':'featureBet','bet':'.20','featureName':'BASIC','playerInteraction':{'featureName':'BASIC'}}
    answer=copy.deepcopy(ANSWER);answer['features']['active']=label
    answer['game'].update(wasFeatureBuy=True,win=3,accumulatedRoundWin=3)
    answer['balance']='10001.00'
    with pytest.raises(ValueError):RoundLedger('10000',mode).accept(answer,request=request)
