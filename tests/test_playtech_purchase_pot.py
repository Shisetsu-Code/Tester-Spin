from tester_spin.providers.playtech.primitives import discover_modes


def plan(source):
    config={'game':{'activeBetOptions':['default','BuyFeature1Pot','BuyFeature2Pot'],'namedScopes':{n:{'betType':'default','featureType':n} for n in ['BuyFeature1Pot','BuyFeature2Pot']},'baseCostMultipliers':[1],'costConfiguration':[{'name':n,'uuid':n,'cost':c} for n,c in [('default',10),('BuyFeature1Pot',290),('BuyFeature2Pot',535)]]}}
    return discover_modes(config,{'dialect':'modern'},[source])


def test_pot_purchases_require_declared_client_pattern_and_server_options():
    source=r'BuyFeatureController function pots(n){return new RegExp("^(BuyFeature\\d+Pot)$").test(n)}'
    result=plan(source)
    assert [m['kind'] for m in result['modes']]==['SPIN','PURCHASE','PURCHASE']
    assert not result['unresolved']


def test_similar_names_without_pattern_stay_unknown():
    assert plan('BuyFeatureController')['unresolved']
