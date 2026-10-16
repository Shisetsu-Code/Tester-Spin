import copy
from decimal import Decimal
import pytest
from tester_spin.providers.nolimit_city.extra_choices import numeric_domain, confirm_numeric
from tester_spin.providers.nolimit_city.contracts import resolve_operation

BIND='a.addGameModeFlowStatePresentationMap("NORMAL_AVALANCHE",new Map([[f.FlowState.IDLE,new C.Auto]]));z.Auto=class{start(g){g.apiPlugin.betHandler.zeroBet(),g.finish()}}'
SOURCE='yes(){g.Game.apiPlugin.betHandler.zeroBet({playerSelectedExtraSpin:"yes"})}no(){g.Game.apiPlugin.betHandler.zeroBet({playerSelectedExtraSpin:"no"})}'+BIND
OFFER={'mode':'NORMAL_AVALANCHE','nextMode':'EXTRA_SPIN','extraSpinCost':3,'accumulatedRoundWin':10,'wasExtraSpin':False}
ACK={'game':{'mode':'EXTRA_SPIN','nextMode':'NORMAL_AVALANCHE','extraSpinCost':3,'accumulatedRoundWin':7,'win':-3,'wasExtraSpin':True,'freespinsLeft':0}}

def test_selector_preserves_current_client_yes_no_wire_literals():
    domain=numeric_domain(SOURCE,OFFER)
    assert domain['options']==['no','yes']
    assert domain['request_field']=='playerSelectedExtraSpin'
    assert domain['wire_encoding']=='PRESERVE_LITERAL'
    assert confirm_numeric(domain,'yes',ACK)==Decimal('-3')
    rejected=copy.deepcopy(ACK);rejected['game'].update(nextMode='NORMAL',win=0,wasExtraSpin=False,accumulatedRoundWin=10)
    assert confirm_numeric(domain,'no',rejected)==0

@pytest.mark.parametrize('change',[{'wasExtraSpin':False},{'win':-2},{'accumulatedRoundWin':8},{'nextMode':'OTHER_PHASE'},{'isExtraSpin':False}])
def test_selector_keeps_receipt_and_money_checks(change):
    domain=numeric_domain(SOURCE,OFFER)
    assert domain is not None
    answer=copy.deepcopy(ACK);answer['game'].update(change)
    with pytest.raises(ValueError):confirm_numeric(domain,'yes',answer)

@pytest.mark.parametrize('source',[SOURCE+'other(){g.zeroBet({playerSelectedExtraSpin:1})}',SOURCE.replace('"no"','0'),SOURCE.replace('"yes"','"maybe"'),SOURCE.replace('playerSelectedExtraSpin','unrelatedChoice')])
def test_selector_rejects_mixed_incomplete_or_unrelated_domains(source):
    assert numeric_domain(source,OFFER) is None


@pytest.mark.parametrize('payload',['longnamespace.'*4+'choice','{choice:1}','getChoice()'])
def test_selector_never_ignores_a_different_payload_expression(payload):
    source=SOURCE+'other(){g.zeroBet({playerSelectedExtraSpin:'+payload+'})}'
    assert numeric_domain(source,OFFER) is None


@pytest.mark.parametrize('expression',["i?\"yes\":\"no\"","i?(j?\"yes\":\"no\"):\"no\""])
def test_replay_ternary_with_the_same_literal_values_does_not_create_a_mixed_domain(expression):
    source=SOURCE+'replay(){g.zeroBet({playerSelectedExtraSpin:'+expression+'})}'
    assert numeric_domain(source,OFFER)['options']==['no','yes']

@pytest.mark.parametrize('expression',["i?\"yes\":\"other\"","i?1:\"no\"","i?getChoice():\"no\""])
def test_ternary_cannot_hide_an_unsupported_value_or_wire_type(expression):
    source=SOURCE+'replay(){g.zeroBet({playerSelectedExtraSpin:'+expression+'})}'
    assert numeric_domain(source,OFFER) is None
