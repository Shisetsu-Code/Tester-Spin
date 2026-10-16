import pytest
from tester_spin.providers.nolimit_city.extra_choices import literal_domain,confirm_literal
from tester_spin.providers.nolimit_city.contracts import resolve_operation,observed_request_matches

SOURCE='yes(){game.apiPlugin.betHandler.zeroBet({extraSpin:"yes"})}no(){game.apiPlugin.betHandler.zeroBet({extraSpin:"no"})}'
QUOTE={'mode':'FREESPIN','nextMode':'EXTRA_SPIN','isExtraSpin':False,'extraSpinCost':4,'accumulatedRoundWin':20,'freespinsLeft':0}


def test_alternate_literal_extra_request_field_is_preserved():
    contract=resolve_operation({'game':QUOTE},client_source=SOURCE)
    assert contract['family']=='QUOTED_LITERAL_EXTRA'
    assert contract['domain']['request_field']=='extraSpin'
    assert observed_request_matches(contract,{'type':'zeroBet','bet':'0.00','playerInteraction':{'extraSpin':'yes'}})==(True,'yes')
    assert not observed_request_matches(contract,{'type':'zeroBet','bet':'0.00','playerInteraction':{'playExtraSpin':'yes'}})[0]
    answer={'game':dict(QUOTE,mode='EXTRA_SPIN',nextMode='FREESPIN',freespinsLeft=1,isExtraSpin=True,win=-4,accumulatedRoundWin=16),'remainingFreeSpins':1,'features':{'available':[]}}
    assert confirm_literal(contract['domain'],'yes',answer)==-4


@pytest.mark.parametrize('source',[
 SOURCE.replace('extraSpin:"no"','differentField:"no"'),
 SOURCE+'other(){game.apiPlugin.betHandler.zeroBet({extraSpin:variable})}',
 SOURCE+'other(){game.apiPlugin.betHandler.zeroBet({playExtraSpin:"yes"})}no2(){game.apiPlugin.betHandler.zeroBet({playExtraSpin:"no"})}',
])
def test_literal_extra_fields_require_one_complete_unambiguous_domain(source):
    assert literal_domain(source,QUOTE) is None
