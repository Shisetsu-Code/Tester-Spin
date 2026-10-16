import os
from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.client_actions import _block,automatic_command
from tester_spin.providers.nolimit_city.event_actions import automatic_event_command


DISPATCHER='constructor(){this._listeners={},this._firstListeners={},this._lastListeners={}}hasEventHandler(e,t){return!!this._listeners[t]&&this._listeners[t].some((t,i,n)=>t.source===e)}addEventListener(e,t,i,n){this.hasEventHandler(e,t)||(this._listeners[t]=this._listeners[t]||[],this._listeners[t].push({source:e,type:t,callback:i,params:n}))}dispatchEvent(e){let t=this._firstListeners[e.type];if(t&&t.callback.call(this,e,t.params),this._listeners[e.type])for(let t=this._listeners[e.type].length-1;t>=0;t--){const i=this._listeners[e.type][t];i.callback.call(this,e,i.params)}let i=this._lastListeners[e.type];i&&i.callback.call(this,e,i.params)}'


def bundle():
    return ('({1(t,e,i){const a=i(2);class C{constructor(){this.GAME_ROUND_CONFIG=()=>({AUTO:{idle:[new a.Step]}})}}e.Config=C,C.instance=new C},'
    '2(t,e,i){const b=i(3),v=i(4),z=i(5),g=i(12);e.Step=class{getAnimation(e){const t=new g.TimelineLite;return t.add(()=>{b.Bus.dispatchEvent(new v.Event(z.Balance.ZERO_BET,e.freespinsLeft-1))},.5),t}}},'
    '3(t,e,i){const d=i(9);class S{static get enabled(){return this._enabled}static set enabled(e){this._enabled=e}static dispatchEvent(e){S._enabled&&this._eventDispatcher.dispatchEvent(e)}static addEventListener(e,t,i,...n){this._eventDispatcher.addEventListener(e,t,i,n)}}S._eventDispatcher=new d.Dispatcher,S._enabled=!0,e.Bus=S},'
    '4(t,e){e.Event=class{get type(){return this._type}get params(){return this._params}constructor(e,...t){this._type=e,this._params=t}}},'
    '5(t,e){class E{}E.ZERO_BET="balanceEvent_zeroBet",e.Balance=E},'
    '6(t,e,i){const b=i(3),z=i(5),a=i(7),slot=i(11);class B{constructor(e){this._slotApi=e,this.initSlotApiEvents(),this.initGameEvents()}initSlotApiEvents(){this._slotApi.events.on(a.Events.ACTION_SPINS_IS_ACTIVE,e=>this.onActionSpins(e))}onActionSpins(e){b.Bus.enabled=!e}initGameEvents(){b.Bus.addEventListener(this,z.Balance.ZERO_BET,e=>this.onZeroBet(e.params[0]))}onZeroBet(e){this._slotApi.betHandler.zeroBet(),null==e&&(e=-1),slot.SlotGame.keypad.setZeroBetSpinCounter(e)}}e.Bridge=B},'
    '7(t,e){var n;e.Events=void 0,(n=e.Events||(e.Events={})).ACTION_SPINS_IS_ACTIVE="actionSpinsActive"},'
    '8(t,e,i){const a=i(7);class U{constructor(){}maximize(){this.newView.visible=!0,o.NolimitApplication.addDialog(this.newView,!0),U.IS_MINIMIZED=!1,U.apiPlugIn.events.trigger(a.Events.ACTION_SPINS_IS_ACTIVE,!0),U.apiPlugIn.events.trigger(h.PromoPanelEvents.PROMO_PANEL_MAXIMIZED)}}e.UI=U},'
    '9(t,e){e.Dispatcher=class{'+DISPATCHER+'}},'
    '10(t,e,i){const c=i(1);class G extends a.Base{constructor(){super(c.Config.instance)}}e.Game=G}})')


def run(source,**fields):
    game={'mode':'PREVIOUS','nextMode':'AUTO','freespinsLeft':3};game.update(fields)
    return automatic_event_command(source,{'game':game},_block,direct_demo_transport=True)


def test_bound_phase_timeline_event_becomes_zero_bet_without_payload():
    assert run(bundle())=={'type':'zeroBet','bet':'0.00'}


def test_untrusted_transport_context_does_not_assume_bus_enabled():
    assert automatic_event_command(bundle(),{'game':{'nextMode':'AUTO'}},_block) is None


def test_wrong_wire_phase_does_not_use_neighboring_animation():
    assert run(bundle(),nextMode='OTHER') is None


def test_conditional_dispatch_stays_unresolved():
    source=bundle().replace('b.Bus.dispatchEvent(new v.Event','unknown.flag&&b.Bus.dispatchEvent(new v.Event')
    assert run(source) is None


def test_paused_timeline_does_not_prove_dispatch():
    assert run(bundle().replace('return t.add','t.pause();return t.add')) is None


def test_bridge_cannot_forward_event_counter_as_bet_payload():
    assert run(bundle().replace('this._slotApi.betHandler.zeroBet()','this._slotApi.betHandler.zeroBet(e)')) is None


def test_unrelated_enum_and_bus_names_are_not_equivalent():
    assert run(bundle().replace('ZERO_BET="balanceEvent_zeroBet"','ZERO_BET="other"')) is None


def test_initially_disabled_bus_is_not_assumed_enabled():
    assert run(bundle().replace('S._enabled=!0','S._enabled=!1')) is None


def test_competing_bus_disable_rejected():
    assert run(bundle().replace('e.Bus=S}', 'e.Bus=S;S.enabled=!1}')) is None


def test_unknown_action_spins_producer_rejected():
    assert run(bundle().replace('e.UI=U}', 'e.UI=U;boot.events.trigger(a.Events.ACTION_SPINS_IS_ACTIVE,!0)}')) is None


def test_unproven_prior_animation_blocks_later_event_action():
    source=bundle().replace('idle:[new a.Step]','idle:[new a.Unknown,new a.Step]')
    assert run(source) is None


def test_paid_quote_never_uses_automatic_event_action():
    assert run(bundle(),extraSpinCost='2.00') is None


def test_unknown_dispatcher_does_not_deliver_proven_listener():
    assert run(bundle().replace('i.callback.call(this,e,i.params)','unknown(i)')) is None


def test_nonround_config_is_not_active_phase_registration():
    assert run(bundle().replace('this.GAME_ROUND_CONFIG=','this.UNUSED_CONFIG=')) is None


_CACHE=Path(os.environ.get('NLC_CLIENT_CACHE','data/providers/nolimit_city/_clients'))


@pytest.mark.skipif(not _CACHE.is_dir(),reason='Exact public client cache not supplied')
@pytest.mark.parametrize('game,version,mode,next_mode,left',[
    ('BuffaloHunter','1.4.5','FREESPIN_PICK','FREESPIN_TRANSFORM',10),
    ('MilkyWays','1.3.5','FREESPIN','FREESPIN_WIN_RESPIN',1),
])
def test_exact_client_post_choice_and_respin_wire_phases(game,version,mode,next_mode,left):
    source=(_CACHE/game/(version+'.js')).read_text(encoding='utf-8')
    answer={'game':{'mode':mode,'nextMode':next_mode,'freespinsLeft':left}}
    assert automatic_event_command(source,answer,_block,direct_demo_transport=True)=={'type':'zeroBet','bet':'0.00'}
    assert automatic_event_command(source,answer,_block) is None
    assert automatic_command(source,answer,direct_demo_transport=True)=={'type':'zeroBet','bet':'0.00'}


def test_conditional_bridge_registration_is_not_a_listener():
    assert run(bundle().replace('b.Bus.addEventListener(this,','unknown.flag&&b.Bus.addEventListener(this,')) is None


def test_bridge_constructor_cannot_replace_zero_bet_callback():
    assert run(bundle().replace('this._slotApi=e,this.initSlotApiEvents()','this._slotApi=e,this.onZeroBet=unknown,this.initSlotApiEvents()')) is None


def test_late_bridge_prototype_replacement_is_rejected():
    assert run(bundle().replace('e.Bridge=B}', 'e.Bridge=B;B.prototype.onZeroBet=unknown}')) is None


def test_late_bridge_api_reassignment_is_rejected():
    assert run(bundle().replace('this._slotApi=e,this.initSlotApiEvents()','this._slotApi=e,this._slotApi=unknown,this.initSlotApiEvents()')) is None


def test_conditional_initial_bus_enable_is_not_initial_state():
    assert run(bundle().replace('S._enabled=!0','unknown.flag&&(S._enabled=!0)')) is None


def test_static_bus_method_cannot_mutate_enabled_later():
    source=bundle().replace('static dispatchEvent(e){','static disable(){this._enabled=!1}static dispatchEvent(e){')
    assert run(source) is None


def test_dispatcher_listener_registration_cannot_always_skip():
    source=bundle().replace('return!!this._listeners[t]&&this._listeners[t].some((t,i,n)=>t.source===e)','return true')
    assert run(source) is None


def test_constructor_animation_override_is_not_the_bound_method():
    source=bundle().replace('e.Step=class{getAnimation(e)', 'e.Step=class{constructor(){this.getAnimation=unknown}getAnimation(e)')
    assert run(source) is None


def test_dormant_unconsumed_round_config_is_not_a_binding():
    assert run(bundle().replace('super(c.Config.instance)','super(unknown)')) is None


def test_late_config_factory_replacement_invalidates_phase_map():
    assert run(bundle().replace('C.instance=new C}', 'C.instance=new C;C.instance.GAME_ROUND_CONFIG=unknown}')) is None


def test_late_bus_dispatcher_property_replacement_rejected():
    assert run(bundle().replace('e.Bus=S}', 'e.Bus=S;S._eventDispatcher.dispatchEvent=unknown}')) is None


def test_source_phase_proof_cached_but_each_answer_guard_rechecked():
    from tester_spin.providers.nolimit_city.event_actions import _event_action_proven
    _event_action_proven.cache_clear()
    source=bundle()
    assert run(source)=={'type':'zeroBet','bet':'0.00'}
    assert run(source)=={'type':'zeroBet','bet':'0.00'}
    assert _event_action_proven.cache_info().hits==1
    for fields in ({'isExtraSpin':True},{'wasExtraSpin':True},{'extraSpinCost':1}):
        assert run(source,**fields) is None
    assert automatic_event_command(source,{'game':{'nextMode':'AUTO'}},_block) is None
    assert _event_action_proven.cache_info().hits==1


def test_cached_proof_returns_fresh_commands_and_source_phase_invalidates():
    from tester_spin.providers.nolimit_city.event_actions import _event_action_proven
    _event_action_proven.cache_clear()
    source=bundle()
    first=run(source)
    first['bet']='999.00'
    assert run(source)=={'type':'zeroBet','bet':'0.00'}
    assert run(source.replace('S._enabled=!0','S._enabled=!1')) is None
    assert run(source,nextMode='UNKNOWN') is None
    assert _event_action_proven.cache_info().misses==3
