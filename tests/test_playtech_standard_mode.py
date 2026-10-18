from tester_spin.providers.playtech.primitives import discover_modes


def test_server_standard_start_is_base_independent_of_display_name():
    config={'game':{'baseCostMultipliers':[1], 'costConfiguration':[{'name':'20','uuid':'a','cost':20,'parameters':{'startingMode':'Standard','startingPlays':'1'}},{'name':'extra','uuid':'b','cost':30,'parameters':{'startingMode':'Bonus','startingPlays':'1'}}]}}
    contract={'dialect':'modern','standard_start_bound':True}
    plan=discover_modes(config,contract,["ExtraBetWidget"])
    assert plan['modes'][0]['kind']=='SPIN'
    assert plan['modes'][0]['selector']=='default'
    assert plan['modes'][1]['kind']=='ANTE_BET'
    assert not plan['unresolved']
    assert plan['domains']['purchase']['options']==[]


def test_standard_label_without_source_binding_or_with_purchase_fields_is_unknown():
    config={'game':{'baseCostMultipliers':[1], 'costConfiguration':[{'name':'20','uuid':'a','cost':20,'parameters':{'startingMode':'Standard','startingPlays':'1'}},{'name':'special','uuid':'b','cost':200,'parameters':{'startingMode':'Bonus','startingPlays':'1'}}]}}
    assert discover_modes(config,{'dialect':'modern'},[])['modes'][0]['kind']=='UNKNOWN_FEATURE'
    config['game']['costConfiguration'][0]['parameters']['buyFeature']=True
    assert discover_modes(config,{'dialect':'modern','standard_start_bound':True},[])['modes'][0]['kind']=='UNKNOWN_FEATURE'


def test_source_binds_standard_start_only_from_recognized_comparison():
    from tester_spin.providers.playtech.primitives import client_contract,GAME_CLASS
    source=GAME_CLASS+' 40021 48775 GLU.game.playMoney stakeCostName startingMode function normal(v){return !equal(v,"Standard")}'
    c=client_contract({'setup':{'usesLegacyBetApi':False}},[source])
    assert c['standard_start_bound'] is True
    assert not client_contract({'setup':{'usesLegacyBetApi':False}},[source.replace('!equal(v,"Standard")','unknown(v)')])['standard_start_bound']


def test_multiple_standard_rows_need_their_own_line_selector_binding():
    config={'game':{'baseCostMultipliers':[1],'costConfiguration':[{'name':str(i),'uuid':str(i),'cost':i,'parameters':{'startingMode':'Standard','startingPlays':'1'}} for i in [10,20]]}}
    plan=discover_modes(config,{'dialect':'modern','standard_start_bound':True},[])
    assert plan['unresolved']
