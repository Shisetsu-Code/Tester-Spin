import pytest
from tester_spin.providers.playtech.primitives import discover_modes, entry_command
from tester_spin.providers.playtech.client_sources import script_dependencies

CONTRACT={'dialect':'modern','class':'C','entry_id':40021,'base_selector':None}

def test_static_variable_loader_selects_modern_without_evaluation():
    source='''var isModern="noModule" in HTMLScriptElement.prototype;var fileName=isModern?"bundle.js":"bundle-legacy.js",src="../game/js/"+fileName;script.setAttribute("src",src);'''
    assert script_dependencies(source)==['../game/js/bundle.js']

def test_unknown_expression_is_not_executed_or_guessed():
    assert script_dependencies('var src=evil();script.setAttribute("src",src);')==[]

def test_declared_scope_selects_wire_feature_not_display_alias():
    g={'baseCostMultipliers':[1],'costConfiguration':[{'uuid':'a','name':'defaultLow','cost':10},{'uuid':'b','name':'extraX2Low','cost':20},{'uuid':'c','name':'BF2','cost':700}],
       'activeBetOptions':['defaultLow','extraX2Low','BF2'], 'namedScopes':{'defaultLow':{'betType':'default','featureType':'defaultLow'},'extraX2Low':{'betType':'default','featureType':'extraX2Low'},'BF2':{'betType':'default','featureType':'BF2'}}}
    p=discover_modes({'game':g},CONTRACT,['ExtraBetsModule BuyFeatureModule currentVolatilitySuffix'])
    assert not p['unresolved']
    assert [m['kind'] for m in p['modes']]==['SPIN','ANTE_BET','PURCHASE']
    assert entry_command(p['modes'][2],CONTRACT)['featureType']=='BF2'

def test_scope_alone_does_not_certify_purchase():
    g={'baseCostMultipliers':[1],'costConfiguration':[{'uuid':'a','name':'default','cost':10},{'uuid':'b','name':'BF2','cost':1000}], 'namedScopes':{'BF2':{'betType':'default','featureType':'BF2'}}}
    assert discover_modes({'game':g},CONTRACT,[])['unresolved']

def test_line_domains_are_normal_wagers_with_matching_parameters():
    rows=[{'uuid':str(i),'name':str(i),'cost':i,'parameters':{'startingMode':'Standard','winline':str(i)}} for i in (1,2,3)]
    p=discover_modes({'game':{'baseCostMultipliers':[1],'costConfiguration':rows}},dict(CONTRACT,dialect='legacy'),['stakeCostUuid winline'])
    assert not p['unresolved']
    assert all(m['kind']=='SPIN' for m in p['modes'])

def test_line_like_name_without_declaration_stays_unknown():
    rows=[{'uuid':str(i),'name':str(i),'cost':i} for i in (1,2)]
    assert discover_modes({'game':{'baseCostMultipliers':[1],'costConfiguration':rows}},CONTRACT,['winline'])['unresolved']


def test_targeted_reentry_selects_missing_option_first():
    from tester_spin.providers.playtech.primitives import PickState
    state=PickState({'phase':3})
    data={'nextRound':'phase','listPickPlayerPickOptions':[{'index':1},{'index':2},{'index':3}],
          'playStack':[{'round':'phase','modeType':'LIST_PICK','remainingPlayCount':1}]}
    assert state.parameters(data,True)==[{'key':'pick','value':'3'}]


def test_client_descriptor_binds_purchase_without_name_heuristic():
    g={'baseCostMultipliers':[1],'costConfiguration':[{'uuid':'a','name':'default','cost':10},{'uuid':'b','name':'AnyDeclaredLabel','cost':100}]}
    source='baseCostName:"AnyDeclaredLabel",betParams:{betType:Z.uu.BONUS}'
    p=discover_modes({'game':g},CONTRACT,[source])
    assert [m['kind'] for m in p['modes']]==['SPIN','PURCHASE']


def test_compiled_pick_binding_follows_key_and_continuation_serializer():
    from tester_spin.providers.playtech.client_sources import compiled_pick_binding
    source='''var key="pick";_.next=48775;
function send(c,id,json){var data={ID:id,parameters:JSON.parse(json)};GLU.game.playOut(c,data)}
function resume(n,t){send(n.cls,n.next,encode(t))}
function put(n,k,v){return store(n.map,k,v)}
function choose(n){var t=new Map;put(t,key,n.index);resume(n.adapter,t)}'''
    assert compiled_pick_binding(source)
    assert not compiled_pick_binding(source.replace('48775','40021'))
    assert not compiled_pick_binding(source.replace('resume(n.adapter,t)','unrelated(n.adapter,t)'))


def test_singular_extra_controller_and_declared_scaled_purchase():
    g={'baseCostMultipliers':[1],'activeBetOptions':['default','extra','BuyFeature2X'],'featureBetEnabled':True,
       'costConfiguration':[{'uuid':'a','name':'default','cost':10},{'uuid':'b','name':'extra','cost':12},{'uuid':'c','name':'BuyFeature2X','cost':2000}]}
    p=discover_modes({'game':g},CONTRACT,['ExtraBetModule BuyFeatureController'])
    assert not p['unresolved']
    assert [m['kind'] for m in p['modes']]==['SPIN','ANTE_BET','PURCHASE']


def test_explicit_scope_overrides_generic_base_alias():
    row={'uuid':'a','name':'defaultLow','cost':10}
    g={'baseCostMultipliers':[1],'costConfiguration':[row], 'namedScopes':{'defaultLow':{'betType':'default','featureType':'defaultLow'}}}
    m=discover_modes({'game':g},dict(CONTRACT,base_selector='default'),['currentVolatilitySuffix'])['modes'][0]
    assert entry_command(m,CONTRACT)['featureType']=='defaultLow'
