import copy
from tester_spin.providers.playtech.ngm_contracts import analyze_har
from test_playtech_ngm_contracts import har, CLIENT, MANIFEST

LOADER="""
function features(reader,target){var table,rows,it,key,item;table=new Map;rows=reader.data.read('features');if(rows){for(it=rows.keys().iterator();it.more();){key=it.next();item=decode(rows.read(key));item.name==null&&(item.name=key);key==null?put(table.nulls,null,item):put(table.entries,key,item)}}target.features=table}
function dispatch(engine,q){var out,handlers,it,item;out=new List;handlers=lookup(engine.registry,q.kind);if(!handlers)return out;for(it=iter(handlers);it.more();){item=it.callback(q);append(out,item)}return out}
function registerHandler(engine,type,handler){var handlers;handlers=lookup(engine.registry,type);if(!handlers){handlers=new List;store(engine.registry,type,handlers)}handlers.add(handler)}
function initialize(engine){registerHandler(engine,spin,new MathHandler);registerHandler(engine,bonus,new BonusHandler)}
function sendSpin(engine,phase,cost,coins){var q;q=new Spin;q.phase=phase;q.cost=cost;q.coins=coins;transport(engine,q)}
function gameSpin(owner){sendSpin(owner,'regular',20,1)}
"""


def complete_har():
    data=har()
    data['log']['entries'][0]['response']['content']['text']=CLIENT+LOADER
    # The only entry feature is the explicitly paid normal spin. Its bonus is free.
    doc=copy.deepcopy(MANIFEST)
    doc['ui']={'spin':{'id':'spin','type':'ibutton'}}
    doc['config']['engine']={'calculators':{'default':{'type':'default'}}}
    doc['config']['features']={'regular':{'type':'reels-spin','free':False},'free-spins':{'type':'free-spins','spins-count':5}}
    import json
    data['log']['entries'][1]['response']['content']['text']=json.dumps(doc)
    return data


def test_complete_config_and_wire_contract_declare_empty_economic_domains():
    plan=analyze_har(complete_har(),'example')['execution_plan']
    assert plan['complete'] is True
    assert plan['domains']['purchase']['complete'] is True
    assert plan['domains']['ante']['options']==[]
    assert plan['domains']['purchase']['declaration_state']=='DECLARED_EMPTY'
    assert plan['features'][1]['kind']=='NATURAL_BONUS'
    assert plan['source_sha256']


def test_unknown_feature_or_price_cannot_become_zero_purchases():
    import json
    for extra in [{'special':{'type':'reels-spin','free':False}}, {'regular':{'type':'reels-spin','free':False,'costOptions':[1,100]}}]:
        data=complete_har();entry=data['log']['entries'][1]['response']['content'];doc=json.loads(entry['text']);doc['config']['features'].update(extra);entry['text']=json.dumps(doc)
        plan=analyze_har(data,'example')['execution_plan']
        assert plan['complete'] is False
        assert plan['domains']['purchase']['declaration_state']=='UNKNOWN'
        assert plan['unresolved']


def test_missing_loader_or_unknown_serializer_keeps_inventory_unknown():
    for text in [CLIENT, CLIENT+LOADER+"function Unknown(){base.call(this,box(9090))}register(999,105,{999:1},Unknown);var unknown=type(ns,'BuyRequest',999,parent);"]:
        data=complete_har();data['log']['entries'][0]['response']['content']['text']=text
        plan=analyze_har(data,'example')['execution_plan']
        assert not plan['complete']


def test_additional_spin_selector_and_dynamic_handler_registration_block_empty_inventory():
    for old,new in [("v=model.phase;", "v=model.selector;v!=null&&put(out,'purchase',number(v));v=model.phase;"), ('registerHandler(engine,spin,', 'registerHandler(engine,chooseType(),')]:
        data=complete_har();content=data['log']['entries'][0]['response']['content'];content['text']=content['text'].replace(old,new)
        assert not analyze_har(data,'example')['execution_plan']['complete']


import pytest
@pytest.mark.parametrize('tamper,expected',[(None,'OK'),('source','PARCIAL'),('manifest','PARCIAL'),('round','PARCIAL'),('demo','PARCIAL')])
def test_executor_consumes_current_har_plan_and_never_promotes_bad_evidence(tmp_path,tamper,expected):
    import threading,json,hashlib
    from tester_spin.models import Game
    from tester_spin.providers.playtech.adapter import PlaytechProvider
    from test_playtech_ngm_execution import apply,round_events
    data=complete_har();source=data['log']['entries'][0]['response']['content']['text']
    report=analyze_har(data,'example')
    class Session:
        contract={'fields':{'bet':'cost'}};errors=[];demo_verified=tamper!='demo'
        source_hashes=[hashlib.sha256(source.encode()).hexdigest() if tamper!='source' else 'different']
        manifest=copy.deepcopy(report['manifest'])
        if tamper=='manifest':manifest['configuration']['coin_sizes']=[999]
        def __init__(self,code,directory,*args):self.directory=directory
        def __enter__(self):return self
        def __exit__(self,*args):(self.directory/'session.har').write_text(json.dumps(data),encoding='utf-8')
        def spin(self):
            if tamper=='round':raise ValueError('ROUND_NOT_CLOSED')
            return apply(round_events()).summary()
    provider=PlaytechProvider(tmp_path);provider.ngm_session_factory=Session
    result=provider.test_game(Game('playtech','game-example','Example','https://www.playtechone.com/games/example',symbol='example'),spins=1,timeout_s=10,stop_event=threading.Event(),progress=lambda x:None)
    assert result.status==expected
    if expected=='OK':
        assert result.feature_domains['purchase']['complete'] is True
        assert result.feature_domains['ante']['declaration_state']=='DECLARED_EMPTY'
        assert 'NGM_FEATURE_INVENTORY_UNKNOWN' not in result.error
        assert result.structural_map['playtech_protocol']['execution_plan']['complete'] is True
        saved=json.loads((__import__('pathlib').Path(result.run_dir)/'result.json').read_text(encoding='utf-8'))
        assert saved['status']=='OK'
        finalized=provider.finalize_test_result(result,progress=lambda x:None)
        assert finalized.status=='OK'
        from tester_spin.feature_summary import _feature_summary
        assert _feature_summary(finalized.to_dict(),counts_only=True)==(0,0)


def test_nested_prices_controls_and_invalid_feature_values_cannot_prove_absence():
    import json
    patches=[lambda d:d['config'].update({'unreviewed_extension':{'value':100}}),
             lambda d:d['config']['engine']['calculators']['default'].update({'debit':100}),
             lambda d:d['ui'].update({'buy':{'type':'ibutton','id':'buy','action':'buy','cost':100}}),
             lambda d:d['config'].update({'menus':{'purchase':{'cost':100}}}),
             lambda d:d['config']['features']['regular'].update({'auto-spin':{'cost':100}}),
             lambda d:d['ui'].update({'unbound':{'type':'ibutton','id':'unrecognized-control'}}),
             lambda d:d['config'].update({'engine':{'calculators':{'special':{'type':'unknown-buy-engine'}}}})]
    for patch in patches:
        data=complete_har();content=data['log']['entries'][1]['response']['content'];doc=json.loads(content['text']);patch(doc);content['text']=json.dumps(doc)
        assert not analyze_har(data,'example')['execution_plan']['complete']


def test_spin_field_names_without_closed_selector_values_are_insufficient():
    data=complete_har();content=data['log']['entries'][0]['response']['content']
    content['text']=content['text'].replace("sendSpin(owner,'regular'", "sendSpin(owner,'purchase'")
    assert not analyze_har(data,'example')['execution_plan']['complete']


@pytest.mark.parametrize('assignment',["q.phase=phase;q.phase='purchase';", "q.phase=phase+'purchase';", "q.phase=phase;q['phase']='purchase';"])
def test_selector_assignment_cannot_be_overwritten_or_transformed(assignment):
    data=complete_har();content=data['log']['entries'][0]['response']['content'];content['text']=content['text'].replace('q.phase=phase;',assignment)
    assert not analyze_har(data,'example')['execution_plan']['complete']


def test_enum_selector_requires_the_complete_closed_expression():
    phase="(same(current(owner.features,null).id,freeName)?(v=(enumInit(),freeValue)):active(owner.features,'re-spin')?(v=(enumInit(),reValue)):(v=(enumInit(),regularValue)),(v.name!=null?v.name:''+v.index).toLowerCase())"
    extra="var freeName='free-spins';function Phase(name,index){this.name=name;this.index=index}function enumInit(){enumInit=noop;regularValue=new Phase('REGULAR',0);freeValue=new Phase('FREE',1);reValue=new Phase('RE',2)}"
    for suffix,expected in [('',True),("+'purchase'",False)]:
        data=complete_har();content=data['log']['entries'][0]['response']['content'];content['text']=content['text'].replace("sendSpin(owner,'regular',",'sendSpin(owner,'+phase+suffix+',')+extra
        assert analyze_har(data,'example')['execution_plan']['complete'] is expected
    for mutation in [lambda s:s.replace('v.name','v.purchase'), lambda s:s+"freeValue=new Phase('PURCHASE',3);", lambda s:s+"freeValue.name='purchase';"]:
        data=complete_har();content=data['log']['entries'][0]['response']['content'];content['text']=mutation(content['text'].replace("sendSpin(owner,'regular',",'sendSpin(owner,'+phase+',')+extra)
        assert not analyze_har(data,'example')['execution_plan']['complete']


def test_feature_loader_resolves_semantic_constant_like_serializers():
    data=complete_har();content=data['log']['entries'][0]['response']['content'];content['text']="var featureKey='features';"+content['text'].replace("read('features')",'read(featureKey)')
    assert analyze_har(data,'example')['execution_plan']['complete']
