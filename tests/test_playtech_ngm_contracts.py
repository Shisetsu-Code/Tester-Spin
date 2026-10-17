import json
import pytest
from tester_spin.providers.playtech.ngm_contracts import request_catalog, functional_manifest, analyze_har

CLIENT="""
var windowKey='windowId';
function Spin(){base.call(this,box(40021))}
register(710,105,{710:1},Spin);var spin=type(ns,'SpinRequest',710,parent);
function spinWriter(req,out){var model,v;check(req,710);model=req;v=box(model.cost);v!=null&&put(out,'bet',number(v));v=box(model.coins);v!=null&&put(out,'numCoins',number(v));v=model.phase;v!=null&&put(out,'spinType',text(v))}
function Pref(){base.call(this,box(40908))}
register(716,105,{716:1},Pref);var pref=type(ns,'LogUserPreferencesRequest',716,parent);
function prefWriter(req,out){var model,v;check(req,716);model=req;v=model.settings;v!=null&&put(out,'preferences',text(v))}
function Bonus(){base.call(this,box(40029))}
register(712,105,{712:1},Bonus);var bonus=type(ns,'StartBonusGameRequest',712,parent);
function bonusWriter(req,out){var model,v;check(req,712);model=req;v=model.window;v!=null&&put(out,windowKey,text(v))}
"""
MANIFEST={'config':{'game_code':'example','features':{'regular':{'type':'reels-spin','free':False},'free-spins':{'type':'free-spins'},'fsb':{'type':'reels-spin'},'waves':{'supported':False}},'coin_sizes':[1,2]},'resources':{'images':{'big':'noise'}},'ui':{'button':{'id':'feature.btn','type':'ibutton','text':'Choose','pos':[1,2],'size':[2,3]}},'scenes':{}}

def test_request_catalog_resolves_ids_and_semantic_serializer_fields():
    rows={r['name']:r for r in request_catalog(CLIENT)}
    assert rows['SpinRequest']['message_id']==40021
    assert rows['SpinRequest']['fields']['bet']=='cost'
    assert rows['LogUserPreferencesRequest']['fields']=={'preferences':'settings'}
    assert rows['StartBonusGameRequest']['fields']=={'windowId':'window'}
    assert 'purchase' not in str(rows).lower()

def test_ambiguous_registration_does_not_produce_executable_binding():
    source=CLIENT+'register(716,105,{716:1},Different);'
    assert not any(r['name']=='LogUserPreferencesRequest' for r in request_catalog(source))

def test_manifest_preserves_features_and_controls_without_counting_them_as_buys():
    result=functional_manifest(MANIFEST,'example')
    assert result['configuration']['features']==MANIFEST['config']['features']
    assert result['controls'][0]['id']=='feature.btn'
    assert 'pos' not in result['controls'][0]
    assert 'images' not in result
    assert result['inventory_state']=='UNKNOWN'
    assert result['game_code']=='example'
    with pytest.raises(ValueError,match='IDENTITY'):functional_manifest(MANIFEST,'other')

def har():
    root='https://cachedownload.playtechone.com/ngmdistributed/ngm-desktop/igv/example/1/'
    def entry(path,mime,text):return {'request':{'url':root+path},'response':{'status':200,'content':{'mimeType':mime,'text':text}}}
    return {'log':{'entries':[entry('resources/a.cache.js','application/javascript',CLIENT),entry('resources/generic/jmm/example.default.jmm','application/json',json.dumps(MANIFEST))]}}

def test_har_report_is_offline_and_links_source_and_manifest_references():
    report=analyze_har(har(),'example')
    assert report['request_count']==3
    assert report['source_ref']=='http:0' and report['manifest_ref']=='http:1'
    assert report['network_used'] is False and report['scripts_executed'] is False
    assert report['certifies_game_ok'] is False
    assert report['manifest']['inventory_state']=='UNKNOWN'

def test_missing_source_or_conflicting_manifests_are_explicit():
    data=har();data['log']['entries'].pop(0)
    assert 'NGM_CLIENT_SOURCE_MISSING' in analyze_har(data,'example')['unresolved']
    data=har();data['log']['entries'].append(data['log']['entries'][1])
    assert 'NGM_MANIFEST_AMBIGUOUS' in analyze_har(data,'example')['unresolved']


def test_catalog_supports_dollar_identifiers_and_retains_unbound_fields():
    source=CLIENT.replace('windowKey','$key')
    bonus=next(r for r in request_catalog(source) if r['name']=='StartBonusGameRequest')
    assert bonus['fields']=={'windowId':'window'}

def test_large_math_tables_are_referenced_without_hiding_mode_options():
    document=json.loads(json.dumps(MANIFEST));document['config']['reels']={'general':[list(range(5000))]}
    document['config']['features']['custom']={'options':[{'cost':10,'selector':2}]}
    result=functional_manifest(document,'example')
    assert result['configuration']['reels']=={'source_ref':'/config/reels'}
    assert result['math_resources'][0]['source_ref']=='/config/reels'
    assert result['configuration']['features']['custom']['options']==[{'cost':10,'selector':2}]

def test_request_observation_carries_semantic_class_without_opaque_field_guessing():
    from tester_spin.providers.playtech.ngm_observation import observation_points
    source=CLIENT+'function dispatch(x,q){var out,h,v;out=new List;for(h=iter(q);h.more();){v=h.callback(q);append(out,v)}return out}'
    expression=observation_points(source)[0]['expression']
    assert 'LogUserPreferencesRequest' in expression and 'instanceof Pref' in expression


def test_passive_roles_require_complete_serializers_and_do_not_infer_purchases():
    from tester_spin.providers.playtech.ngm_contracts import passive_request_roles
    rows=request_catalog(CLIENT.replace("'preferences'","'value'"))
    roles=passive_request_roles(rows)
    assert roles=={'LogUserPreferencesRequest':'aux','StartBonusGameRequest':'continuation'}
    bonus=next(r for r in rows if r['name']=='StartBonusGameRequest')
    bonus['declared_fields'].append('price')
    assert 'StartBonusGameRequest' not in passive_request_roles(rows)


def test_array_fields_are_bound_through_the_serializer_loop():
    addition="v=model.active; if(v!=null){items=v;outArray=new ArrayType;index=0;for(it=items.iterator();it.more();){item=it.next();push(outArray,index++,number(item))}put(out,'lines',outArray)}"
    source=CLIENT.replace("v=model.phase;",addition.replace('; ',';')+"v=model.phase;")
    row=next(r for r in request_catalog(source) if r['name']=='SpinRequest')
    assert row['fields']['lines']=='active'
    assert row['unresolved_fields']==[]
    broken=source.replace('push(outArray,','push(otherArray,')
    row=next(r for r in request_catalog(broken) if r['name']=='SpinRequest')
    assert 'lines' in row['unresolved_fields']

def test_truthy_guard_fields_keep_their_semantic_name():
    source=CLIENT.replace("v!=null&&put(out,'bet'", "!!v&&put(out,'bet'")
    row=next(r for r in request_catalog(source) if r['name']=='SpinRequest')
    assert row['fields']['bet']=='cost'


def test_cli_refuses_to_replace_input_har(tmp_path,monkeypatch):
    import sys
    from tester_spin.providers.playtech.ngm_contracts import main
    source=tmp_path/'source.har';original=json.dumps(har());source.write_text(original,encoding='utf-8')
    monkeypatch.setattr(sys,'argv',['ngm_contracts',str(source),'--code','example','--out',str(source)])
    with pytest.raises(SystemExit):main()
    assert source.read_text(encoding='utf-8')==original


@pytest.mark.parametrize('extra',["put(out,chooseKey(model),number(model.cost));", "delegate(out,model);", "out.extra=model.cost;"])
def test_unknown_output_writes_cannot_certify_passive_serializer(extra):
    from tester_spin.providers.playtech.ngm_contracts import passive_request_roles
    source=CLIENT.replace("'preferences'","'value'").replace("v=model.settings;",extra+"v=model.settings;")
    rows=request_catalog(source)
    pref=next(r for r in rows if r['name']=='LogUserPreferencesRequest')
    assert pref['unresolved_fields']
    assert 'LogUserPreferencesRequest' not in passive_request_roles(rows)

def test_declared_request_without_complete_serializer_remains_pending():
    data=har();data['log']['entries'][0]['response']['content']['text']+="register(999,105,{999:1},Missing);var missing=type(ns,'MissingRequest',999,parent);"
    report=analyze_har(data,'example')
    assert 'NGM_REQUEST_CONTRACT_UNBOUND:MissingRequest' in report['unresolved']

def test_har_body_size_detects_truncated_source():
    data=har();content=data['log']['entries'][0]['response']['content'];content['size']=len(content['text'].encode())+100
    assert any('TRUNCATED' in x for x in analyze_har(data,'example')['unresolved'])


def test_platform_and_abstract_declarations_are_retained_separately_from_wire_requests():
    data=har();data['log']['entries'][0]['response']['content']['text']+="var platformNS='official.platform',platformRequestNS='official.platform.requests';register(48,1,flags);var basePlatform=type(platformNS,'PlatformRequest',48,parent);register(99,48,flags,UiCtor);var ui=type(platformRequestNS,'ShowHelpRequest',99,parent);"
    report=analyze_har(data,'example')
    assert report['unresolved']==[]
    declarations={r['name']:r for r in report['source_declarations']}
    assert declarations['ShowHelpRequest']['channel']=='platform'
    assert declarations['PlatformRequest']['concrete'] is False


def test_inherited_buttons_resolve_template_type_and_keep_provenance():
    document=json.loads(json.dumps(MANIFEST))
    document['ui']={'base':{'type':'ibutton','cursor':'hand'},'derived':{'@P':{'#ID':'ui/base'},'shortcut':'space'},'bar':{'content':[{'id':'start','@P':{'#ID':'ui/derived'}}]}}
    report=functional_manifest(document,'example')
    start=next(c for c in report['controls'] if c.get('id')=='start')
    assert start['type']=='ibutton' and start['shortcut']=='space'
    assert start['template_refs']==['/ui/derived','/ui/base']
    assert start['ref']=='/ui/bar/content/0'
    assert report['inventory_state']=='UNKNOWN'


def test_invalid_template_references_are_explicit_and_do_not_invent_controls():
    document=json.loads(json.dumps(MANIFEST))
    document['ui']={'a':{'@P':{'#ID':'ui/b'}},'b':{'@P':{'#ID':'ui/a'}},'bad':{'@P':{'#ID':'ui/missing'}}}
    report=functional_manifest(document,'example')
    assert report['unresolved_templates']
    assert not report['controls']


def test_wire_subclasses_without_request_suffix_resolve_boxed_enum_ids():
    source=CLIENT+"""
    register(105,1,flags);var parent=type(ns,'AbstractGameRequest',105,root);
    function Wrapper(v){this.value=v}
    function initialize(){initialize=noop;wire=(enumInit(),BonusEnum).value.value}
    function enumInit(){enumInit=noop;BonusEnum=new Wrapper(box(48265))}
    function Notice(){initialize();base.call(this,box(wire))}
    register(713,105,{713:1},Notice);var notice=type(ns,'ExampleBonusStarted',713,parent);
    function noticeWriter(req,out){var model,v;check(req,713);model=req;v=model.id;v!=null&&put(out,'ID',number(v))}
    """
    row=next(r for r in request_catalog(source) if r['name']=='ExampleBonusStarted')
    assert row['message_id']==48265 and row['fields']=={'ID':'id'}
    assert row['id_evidence']=='boxed_enum'
    ambiguous=source+'BonusEnum=new Wrapper(box(999));'
    assert not any(r['name']=='ExampleBonusStarted' for r in request_catalog(ambiguous))


def test_wire_message_without_request_suffix_remains_pending_if_unbound():
    data=har();data['log']['entries'][0]['response']['content']['text']+="register(105,1,flags);var parent=type(ns,'AbstractGameRequest',105,root);register(998,105,{998:1},Missing);var m=type(ns,'BonusNotice',998,parent);"
    assert 'NGM_REQUEST_CONTRACT_UNBOUND:BonusNotice' in analyze_har(data,'example')['unresolved']


def test_indirect_id_needs_constructor_initialization_not_just_a_global_table():
    source=CLIENT+"""
    register(105,1,flags);var parent=type(ns,'AbstractGameRequest',105,root);
    function Wrapper(v){this.value=v}
    function initialize(){wire=(enumInit(),BonusEnum).value.value}
    function enumInit(){BonusEnum=new Wrapper(box(48265))}
    function Notice(){base.call(this,box(wire))}
    register(713,105,{713:1},Notice);var notice=type(ns,'ExampleBonusStarted',713,parent);
    function noticeWriter(req,out){var model,v;check(req,713);model=req;v=model.id;v!=null&&put(out,'ID',number(v))}
    """
    assert not any(r['name']=='ExampleBonusStarted' for r in request_catalog(source))


def test_metadata_envelope_is_only_a_candidate_not_passive_authorization():
    from tester_spin.providers.playtech.ngm_contracts import passive_request_roles
    row={'name':'BuyFeature','wire_message':True,'fields':{'ID':'k','umid':'n','windowId':'j'},'declared_fields':['ID','umid','windowId'],'unresolved_fields':[]}
    assert passive_request_roles([row])=={'BuyFeature':'unhandled_candidate'}


def test_value_object_serializers_share_the_request_catalog_parser():
    source="function Bet(){}register(100,1,{100:1},Bet);var value=type(ns,'CommonBet',100,parent);function encode(a,out){var m,v;check(a,100);m=a;v=m.amount;v!=null&&put(out,'stake',number(v));v=m.kind;v!=null&&put(out,'type',text(v))}"
    row=request_catalog(source,value_classes=('CommonBet',))[0]
    assert row['fields']=={'stake':'amount','type':'kind'}
    assert row['message_id'] is None


def test_request_named_plain_dto_is_not_an_outbound_wire_contract():
    data=har();data['log']['entries'][0]['response']['content']['text']+="var obj=type(ns,'Object',1,null);register(105,1,flags);var wire=type(ns,'AbstractGameRequest',105,obj);function DTO(){}register(990,1,flags,DTO);var dto=type(ns,'LibraryPlaceBetsRequest',990,obj);"
    report=analyze_har(data,'example')
    assert 'NGM_REQUEST_CONTRACT_UNBOUND:LibraryPlaceBetsRequest' not in report['unresolved']
    assert next(r for r in report['source_declarations'] if r['name']=='LibraryPlaceBetsRequest')['channel']=='value_object'
