"""Synthetic client bindings: no captured code or private session fields."""
import copy
import hashlib
from decimal import Decimal

import pytest

from tester_spin.providers.nolimit_city.extra_choices import literal_domain, confirm_literal
from tester_spin.providers.nolimit_city.errors import Unlearned

CHOICES = 'yes(){n.Game.apiPlugin.betHandler.zeroBet({playExtraSpin:"yes"})}no(){n.Game.apiPlugin.betHandler.zeroBet({playExtraSpin:"no"})}'
SOURCE = CHOICES + 'e.Auto=class{start(t){n.Game.apiPlugin.betHandler.zeroBet(),t.finish()}};const P=new C.Auto;g.gameFlowController.addGameModeFlowStatePresentationMap("UNSEEN_RETURN",new Map([[l.FlowState.IDLE,P]]));'
OFFER = {'mode':'UNRELATED_OFFER','nextMode':'EXTRA_SPIN','isExtraSpin':False,'extraSpinCost':3,'accumulatedRoundWin':10}
ACK = {'game':{'mode':'EXTRA_SPIN','nextMode':'UNSEEN_RETURN','isExtraSpin':True,'extraSpinCost':3,'win':-3,'accumulatedRoundWin':7,'freespinsLeft':0}}


def test_literal_return_uses_exact_client_binding_instead_of_offer_phase():
    domain = literal_domain(SOURCE, OFFER)
    assert confirm_literal(domain, 'yes', ACK) == Decimal('-3')
    assert domain['return_binding_sha256'] == hashlib.sha256(SOURCE.encode()).hexdigest()


@pytest.mark.parametrize('key,value', [('nextMode','UNRELATED_OFFER'),('nextMode','UNSEEN_RETUR'),('freespinsLeft',2),('freespinsLeft',True),('isExtraSpin',False),('extraSpinCost',4),('win',-2),('accumulatedRoundWin',8),('accumulatedRoundWin',None)])
def test_bound_extra_never_weakens_debit_counter_accumulation_or_identity(key,value):
    domain=literal_domain(SOURCE,OFFER)
    answer=copy.deepcopy(ACK);answer['game'][key]=value
    with pytest.raises(Unlearned):confirm_literal(domain,'yes',answer)


def test_conditional_zero_bet_is_not_authority_for_different_return():
    source=SOURCE.replace('n.Game.apiPlugin.betHandler.zeroBet(),t.finish()', 'if(this.enabled)n.Game.apiPlugin.betHandler.zeroBet();t.finish()')
    domain=literal_domain(source,OFFER)
    with pytest.raises(Unlearned):confirm_literal(domain,'yes',ACK)


def test_real_wire_phase_names_are_unnecessary():
    source=SOURCE.replace('UNSEEN_RETURN','ANOTHER_STATIC_STATE')
    ack=copy.deepcopy(ACK);ack['game']['nextMode']='ANOTHER_STATIC_STATE';ack['game']['freespinsLeft']=1
    assert confirm_literal(literal_domain(source,OFFER),'yes',ack)==Decimal('-3')


def test_bound_source_cannot_fall_back_to_the_unproven_legacy_offer_target():
    answer=copy.deepcopy(ACK)
    answer['game'].update(nextMode=OFFER['mode'],freespinsLeft=1)
    with pytest.raises(Unlearned):confirm_literal(literal_domain(SOURCE,OFFER),'yes',answer)


def test_source_probe_does_not_mutate_the_offer_or_ack():
    before_offer=copy.deepcopy(OFFER);before_ack=copy.deepcopy(ACK)
    domain=literal_domain(SOURCE,OFFER)
    confirm_literal(domain,'yes',ACK)
    assert OFFER==before_offer and ACK==before_ack


def test_explicit_server_return_quote_cannot_be_replaced_by_other_client_binding():
    offer={**OFFER,'nextModeForExtraSpin':'QUOTED_BONUS'}
    with pytest.raises(Unlearned):confirm_literal(literal_domain(SOURCE,offer),'yes',ACK)


def test_explicit_server_return_quote_and_ack_may_agree():
    offer={**OFFER,'nextModeForExtraSpin':'UNSEEN_RETURN'}
    assert confirm_literal(literal_domain(SOURCE,offer),'yes',ACK)==Decimal('-3')


def test_outer_counter_and_explicit_remaining_alias_agree_for_paid_respin():
    answer=copy.deepcopy(ACK)
    answer['game']['freespinsRemaining']=answer['game'].pop('freespinsLeft')
    answer['remainingFreeSpins']=0
    assert confirm_literal(literal_domain(SOURCE,OFFER),'yes',answer)==Decimal('-3')
    from tester_spin.providers.nolimit_city.runtime import normalized_response
    assert normalized_response(answer,allow_unresolved_state=True)['game']['freespinsLeft']==0


@pytest.mark.parametrize('counter',[1,True,None])
def test_counter_alias_conflict_never_authorizes_extra(counter):
    answer=copy.deepcopy(ACK)
    answer['game']['freespinsRemaining']=answer['game'].pop('freespinsLeft')
    answer['remainingFreeSpins']=counter
    with pytest.raises(ValueError):confirm_literal(literal_domain(SOURCE,OFFER),'yes',answer)
