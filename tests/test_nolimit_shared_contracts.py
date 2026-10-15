import copy,json
from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city import client_actions

def bound(body,phase='UNSEEN_PHASE'):
    return 'e.Auto=class'+body+';const P=new C.Auto;g.gameFlowController.addGameModeFlowStatePresentationMap(b.Mode.'+phase+',new Map([[l.FlowState.IDLE,P],[l.FlowState.BET,O]]));'

@pytest.mark.parametrize('body',[
    '{start(t){n.Game.apiPlugin.betHandler.zeroBet(),t.finish()}}',
    '{start(t){let e;n.Game.apiPlugin.betHandler.zeroBet(),this.updateUI(),t.finish()}}',
    '{start(t){const e=o.gsap.timeline({onComplete:()=>t.finish()});e.add(()=>n.SlotGame.apiPlugin.betHandler.zeroBet()),e.add(this.show())}}',
    '{start(t){this.controller=t;n.SimplePresentationRunner.run(this.presentations,()=>this.complete(),e=>t.setSkipCallback(e))}complete(){this.updateUI(),n.Game.apiPlugin.betHandler.zeroBet(),this.controller.finish()}}',
])
def test_equivalent_unconditional_lifecycles_normalize_to_one_action(body):
    answer={'game':{'mode':'NORMAL','nextMode':'UNSEEN_PHASE','win':0}}
    assert client_actions.automatic_command(bound(body),answer)=={'type':'zeroBet','bet':'0.00'}

@pytest.mark.parametrize('body',[
    '{start(t){if(this.allowed){n.Game.apiPlugin.betHandler.zeroBet()}t.finish()}}',
    '{start(t){this.allowed&&n.Game.apiPlugin.betHandler.zeroBet(),t.finish()}}',
    '{start(t){this.allowed?(this.show(),n.Game.apiPlugin.betHandler.zeroBet()):t.finish()}}',
    '{start(t){this.allowed?this.show(),n.Game.apiPlugin.betHandler.zeroBet():t.finish()}}',
    '{start(t){if(this.blocked)return;n.Game.apiPlugin.betHandler.zeroBet(),t.finish()}}',
    '{start(t){const e=o.gsap.timeline({paused:true});e.add(()=>n.Game.apiPlugin.betHandler.zeroBet())}}',
    '{start(t){const e=o.gsap.timeline();if(this.allowed)e.add(()=>n.Game.apiPlugin.betHandler.zeroBet())}}',
    '{start(t){this.controller=t;if(this.allowed)n.SimplePresentationRunner.run(this.presentations,()=>this.complete())}complete(){n.Game.apiPlugin.betHandler.zeroBet()}}',
])
def test_guards_and_unplayed_callbacks_never_grant_action(body):
    assert client_actions.automatic_command(bound(body),{'game':{'nextMode':'UNSEEN_PHASE'}}) is None

def test_offline_and_live_use_identical_server_declarations():
    from tester_spin.providers.nolimit_city.protocol import analyze_messages
    row=next(r for r in json.loads((Path(__file__).parent/'fixtures/nolimit_reference_five_2.json').read_text()) if r['reference']=='infectious5')
    rows=[{'direction':'sent','message':{'id':'init','type':'init'}},{'direction':'received','message':{**row['init'],'id':'init'}}]
    for n,step in enumerate(row['steps']):
        rows.extend([{'direction':'sent','message':{'id':str(n),'type':'normal','content':step['request']}},{'direction':'received','message':{**step['response'],'id':str(n)}}])
    report=analyze_messages(rows)
    assert report['closed_rounds']==1 and report['pending_round'] is False
    assert not report['ok_certified']

def test_runtime_double_hex_frame_and_browser_single_hex_are_equivalent():
    from tester_spin.providers.nolimit_city.protocol import decode_capture,rc4_hex,websocket_url
    key='fixture-key';url=websocket_url('https://demo.nolimitcity.com/EjsGameWeb/gs',key)
    text=json.dumps({'id':'1','type':'normal','content':{'type':'zeroBet','bet':'0.00'}})
    raw=rc4_hex(key,text.encode('latin1').hex()).encode('latin1').hex()
    double=rc4_hex(key,text.encode('latin1').hex().encode('latin1').hex()).encode('latin1').hex()
    decoded=[]
    for payload in (raw,double):
        doc={'log':{'entries':[{'request':{'method':'POST','url':'https://demo.nolimitcity.com/EjsFrontWeb/fs'},'response':{'content':{'text':json.dumps({'key':key,'url':'https://demo.nolimitcity.com/EjsGameWeb/gs'})}}}], '_warpWebSockets':[{'url':url,'direction':'sent','payload':payload,'encoding':'utf8'}]}}
        decoded.append(decode_capture(doc)[0]['message'])
    assert decoded[0]==decoded[1]==json.loads(text)


def test_registered_controller_normalizes_multiple_phase_predicate_and_wrapped_event():
    source='class o extends s.ZeroBetController{calculateIsTriggered(e){return this._nextMode=e.nextMode,e.nextMode==n.Mode.UNSEEN_ONE||e.nextMode===n.Mode.UNSEEN_TWO}}t.Auto=o};this.ZERO_BETS=[()=>new l.Auto];initGameEvents(){o.EventHandler.addEventListener(this,n.BalanceEvent.ZERO_BET,(e=>this.onZeroBet(e.params[0])))}onZeroBet(e){this._slotApi.betHandler.zeroBet(),x.counter(e)}'
    for phase in ('UNSEEN_ONE','UNSEEN_TWO'):
        assert client_actions.automatic_command(source,{'game':{'nextMode':phase}})=={'type':'zeroBet','bet':'0.00'}
    assert client_actions.automatic_command(source.replace('return this._nextMode=e.nextMode,','return this.allowed&&'),{'game':{'nextMode':'UNSEEN_ONE'}}) is None


def test_commercial_capabilities_and_phase_categories_have_separate_namespaces():
    from tester_spin.providers.nolimit_city.runtime import declaration,normalized_response
    from tester_spin.providers.nolimit_city.state import feature_observation
    init=json.loads((Path(__file__).parent/'fixtures/nolimit_rows_init.json').read_text())
    modes,_=declaration(init)
    assert set(modes[0]['declared_feature_categories'])=={'BONUS_BUY','BOOSTED_BET'}
    observation=feature_observation({'game':{'mode':'NORMAL','nextMode':'NORMAL'},'features':{'available':['BONUS_BUY','BOOSTED_BET']}},[],[],modes[0]['declared_purchase_options'],[modes[0]['declared_feature_categories']])
    assert observation['kind']=='CATALOG'
    observation=feature_observation({'game':{'mode':'NORMAL','nextMode':'NORMAL'},'features':{'available':['FREESPIN']}},[],[],modes[0]['declared_purchase_options'],[modes[0]['declared_feature_categories']])
    assert observation['kind']=='CATALOG'


@pytest.mark.parametrize('body',[
    '{start(t){if(this.allowed)this.show(),n.Game.apiPlugin.betHandler.zeroBet();t.finish()}}',
    '{start(t){t.finish()}getAnimation(t){n.Game.apiPlugin.betHandler.zeroBet()}}',
])
def test_unbraced_guards_and_inactive_methods_do_not_grant_modern_flow_action(body):
    assert client_actions.automatic_command(bound(body),{'game':{'nextMode':'UNSEEN_PHASE'}}) is None


@pytest.mark.parametrize('mutation',['e.pause();','e.kill();','e=other;'])
def test_cancelled_or_reassigned_timeline_does_not_authorize_its_callback(mutation):
    source=bound('{start(t){const e=o.gsap.timeline();'+mutation+'e.add(()=>n.Game.apiPlugin.betHandler.zeroBet())}}')
    assert client_actions.automatic_command(source,{'game':{'nextMode':'UNSEEN_PHASE'}}) is None


def test_legacy_timeline_shape_cannot_bypass_shared_cancellation_rules():
    source=bound('{constructor(){}start(t){const e=o.gsap.timeline({onComplete:()=>{t.finish()}});e.add(()=>{n.SlotGame.apiPlugin.betHandler.zeroBet()}),e.pause()}}')
    assert client_actions.automatic_command(source,{'game':{'nextMode':'UNSEEN_PHASE'}}) is None


def test_directly_instantiated_idle_binding_uses_the_same_lifecycle_contract():
    source=bound('{start(t){n.Game.apiPlugin.betHandler.zeroBet(),t.finish()}}')
    source=source.replace('IDLE,P','IDLE,new C.Auto')
    assert client_actions.automatic_command(source,{'game':{'nextMode':'UNSEEN_PHASE'}})=={'type':'zeroBet','bet':'0.00'}

@pytest.mark.parametrize('config',[
    'onComplete:()=>this.complete()',
    'onComplete:()=>{this.complete()}',
])
def test_playing_timeline_completion_invokes_its_unconditional_action(config):
    source=bound('{start(t){this.controller=t;n.gsap.timeline({'+config+'})}complete(){n.Game.apiPlugin.betHandler.zeroBet(),this.controller.finish()}}')
    assert client_actions.automatic_command(source,{'game':{'nextMode':'UNSEEN_PHASE'}})=={'type':'zeroBet','bet':'0.00'}
    assert client_actions.automatic_command(source.replace('{'+config+'}', '{paused:true,'+config+'}'),{'game':{'nextMode':'UNSEEN_PHASE'}}) is None


def test_static_mode_value_alias_binds_wire_phase_to_client_symbol():
    source=bound('{start(t){n.Game.apiPlugin.betHandler.zeroBet(),t.finish()}}',phase='RESPIN')
    source='class x extends n.GameMode{}e.Mode=x,x.RESPIN="WIRE_PHASE";'+source
    assert client_actions.automatic_command(source,{'game':{'nextMode':'WIRE_PHASE'}})=={'type':'zeroBet','bet':'0.00'}
    assert client_actions.automatic_command(source.replace('extends n.GameMode','extends n.Other'),{'game':{'nextMode':'WIRE_PHASE'}}) is None


def test_comma_constructor_binding_uses_the_last_value_class():
    source=bound('{start(t){n.Game.apiPlugin.betHandler.zeroBet(),t.finish()}}')
    source=source.replace('P=new C.Auto','P=(new C.Unused,new C.Auto)')
    assert client_actions.automatic_command(source,{'game':{'nextMode':'UNSEEN_PHASE'}})=={'type':'zeroBet','bet':'0.00'}
    assert client_actions.automatic_command(source.replace('(new C.Unused,new C.Auto)','(new C.Auto,new C.Unused)'),{'game':{'nextMode':'UNSEEN_PHASE'}}) is None


@pytest.mark.parametrize('callback',['()=>this.complete()','()=>{this.complete()}'])
@pytest.mark.parametrize('property',['paused:true','onStart:()=>this.disable()'])
def test_trailing_timeline_properties_cannot_hide_from_completion_validation(callback,property):
    source=bound('{start(t){this.controller=t;n.gsap.timeline({onComplete:'+callback+','+property+'})}complete(){n.Game.apiPlugin.betHandler.zeroBet(),this.controller.finish()}}')
    assert client_actions.automatic_command(source,{'game':{'nextMode':'UNSEEN_PHASE'}}) is None
