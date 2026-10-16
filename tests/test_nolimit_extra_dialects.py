import copy
from decimal import Decimal
import pytest
from tester_spin.providers.nolimit_city.extra_choices import literal_domain, confirm_literal, numeric_domain, confirm_numeric
from tester_spin.providers.nolimit_city.errors import Unlearned

BIND='e.Auto=class{start(t){n.Game.apiPlugin.betHandler.zeroBet(),t.finish()}};g.gameFlowController.addGameModeFlowStatePresentationMap("UNSEEN_AVALANCHE",new Map([[l.FlowState.IDLE,new C.Auto]]));'
LITERAL='yes(){n.Game.apiPlugin.betHandler.zeroBet({playExtraSpin:"yes"})}no(){n.Game.apiPlugin.betHandler.zeroBet({playExtraSpin:"no"})}'
NUMERIC='yes(){n.Game.apiPlugin.betHandler.zeroBet({playerSelectedExtraSpin:1})}no(){n.Game.apiPlugin.betHandler.zeroBet({playerSelectedExtraSpin:0})}'
OFFER={'mode':'FREESPIN','nextMode':'EXTRA_SPIN','extraSpinCost':3,'accumulatedRoundWin':10}
ACK={'game':{'mode':'EXTRA_SPIN','nextMode':'UNSEEN_AVALANCHE','extraSpinCost':3,'accumulatedRoundWin':7,'win':-3,'freespinsLeft':0}}

def test_missing_flag_is_unknown_and_client_bound_receipt_proves_literal_acceptance():
    domain=literal_domain(LITERAL+BIND,OFFER)
    assert domain['history_extra'] is None
    assert domain['flag_contract']=='NONE'
    assert confirm_literal(domain,'yes',ACK)==Decimal('-3')

@pytest.mark.parametrize('key,value',[('win',-2),('accumulatedRoundWin',8),('nextMode','UNSEEN_OTHER'),('freespinsLeft',2),('isExtraSpin',False),('isExtraSpin',None)])
def test_flagless_receipt_preserves_money_binding_counter_and_explicit_flag(key,value):
    domain=literal_domain(LITERAL+BIND,OFFER);answer=copy.deepcopy(ACK);answer['game'][key]=value
    with pytest.raises(ValueError):confirm_literal(domain,'yes',answer)

def test_client_that_consumes_flag_cannot_silently_become_flagless():
    with pytest.raises(Unlearned):literal_domain(LITERAL+BIND+'get extra(){return this.data.isExtraSpin}',OFFER)

def test_flagless_decline_is_confirmed_by_normal_zero_receipt():
    answer=copy.deepcopy(ACK);answer['game'].update(nextMode='NORMAL',win=0,accumulatedRoundWin=10)
    assert confirm_literal(literal_domain(LITERAL+BIND,OFFER),'no',answer)==0

def test_numeric_receipt_uses_client_bound_phase_and_counter_with_exact_accumulated_debit():
    domain=numeric_domain(NUMERIC+BIND,OFFER);answer=copy.deepcopy(ACK);answer['game']['wasExtraSpin']=True
    assert confirm_numeric(domain,1,answer)==Decimal('-3')
    answer['game']['accumulatedRoundWin']=8
    with pytest.raises(Unlearned):confirm_numeric(domain,1,answer)

def test_explicit_numeric_target_remains_authoritative_with_client_bindings():
    domain=numeric_domain(NUMERIC+BIND,{**OFFER,'nextModeForExtraSpin':'FREESPIN'})
    answer=copy.deepcopy(ACK);answer['game']['wasExtraSpin']=True
    with pytest.raises(Unlearned):confirm_numeric(domain,1,answer)

@pytest.mark.parametrize('value',[False,None,1])
def test_flagless_dialect_rejects_contradictory_or_malformed_secondary_receipt(value):
    answer=copy.deepcopy(ACK);answer['game']['wasExtraSpin']=value
    with pytest.raises(ValueError):confirm_literal(literal_domain(LITERAL+BIND,OFFER),'yes',answer)

def test_bound_literal_return_does_not_treat_offer_phase_as_an_explicit_quote():
    assert confirm_literal(literal_domain(LITERAL+BIND,{**OFFER,'mode':'NORMAL'}),'yes',ACK)==-3

def test_literal_counter_contract_snapshot_handles_independent_outer_total():
    source=LITERAL+BIND+'g.keypadPlugin.setZeroBetSpinCounter(g.model.data.freespinsRemaining)'
    domain=literal_domain(source,OFFER)
    assert domain['remaining_counter_contract']['field']=='freespinsRemaining'
    answer=copy.deepcopy(ACK);answer['game']['freespinsRemaining']=answer['game'].pop('freespinsLeft');answer['remainingFreeSpins']=1
    assert confirm_literal(domain,'yes',answer)==-3


@pytest.mark.parametrize('read', ['this.data["isExtraSpin"]',"this.data['wasExtraSpin']",'({isExtraSpin})=>isExtraSpin'])
def test_indirect_flag_access_cannot_enable_flagless_dialect(read):
    with pytest.raises(Unlearned):literal_domain(LITERAL+BIND+'read(){return '+read+'}',OFFER)
