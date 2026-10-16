import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger
from tester_spin.providers.nolimit_city.contracts import resolve_operation
from tests.test_nolimit_extra_dialects import LITERAL,BIND

MODE={'kind':'SPIN','stake':'.20','price_multiplier':1}
ROOT={'game':{'mode':'NORMAL','nextMode':'EXTRA_SPIN','playedBetValue':'.20','win':10,'accumulatedRoundWin':10,
              'freespinsLeft':0,'extraSpinCost':3},'balance':'9999.80','features':{'available':[]},'pendingWin':True}
ACK={'game':{'mode':'EXTRA_SPIN','nextMode':'UNSEEN_AVALANCHE','extraSpinCost':3,'accumulatedRoundWin':7,'win':-3,'freespinsLeft':0},
     'features':{'available':[]},'pendingWin':True}


def test_verified_flagless_purchase_funds_exactly_its_followup_without_invented_flag():
    ledger=RoundLedger('10000',MODE)
    assert not ledger.accept(ROOT,request={'type':'normalBet','bet':'.20'})
    choice=resolve_operation(ledger.last_answer,MODE,raw_answer=ROOT,client_source=LITERAL+BIND)
    assert not ledger.accept(ACK,request={'type':'zeroBet','bet':'0.00','playerInteraction':{'playExtraSpin':'yes'}},operation=choice)
    followup=resolve_operation(ledger.last_answer,MODE,raw_answer=ACK,client_source=LITERAL+BIND)
    assert followup['family']=='FUNDED_EXTRA_CONTINUATION'
    final={'game':{'mode':'UNSEEN_AVALANCHE','nextMode':'NORMAL','win':2,'accumulatedRoundWin':9,'freespinsLeft':0},
           'balance':'10008.80','features':{'available':[]}}
    assert ledger.accept(final,request=followup['request'],operation=followup)
    assert 'isExtraSpin' not in ledger.last_answer['game']
