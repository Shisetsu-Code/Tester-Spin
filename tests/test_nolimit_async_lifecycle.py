from tester_spin.providers.nolimit_city.client_actions import _block
from tester_spin.providers.nolimit_city import async_lifecycle


HELPER = 'var h=this&&this.__awaiter||function(t,e,i,n){return new(i||(i=Promise))(function(o,s){function a(t){try{l(n.next(t))}catch(t){s(t)}}function r(t){try{l(n.throw(t))}catch(t){s(t)}}function l(t){var e;t.done?o(t.value):(e=t.value,e instanceof i?e:new i(function(t){t(e)})).then(a,r)}l((n=n.apply(t,e||[])).next())})};'


def bundle(*,generator=None,on_game=None):
    generator=generator or 'g.Game.model.isRestore&&(yield never()),g.Game.apiPlugin.betHandler.zeroBet(),t.finish()'
    on_game=on_game or 'this.parsedGameData=new p.Parsed(t),this.isRestore=!1,super.onGame(t)'
    return ('({1(t,e,i){const a=i(2);use(new a.Action)},2(t,e,i){'+HELPER+'const g=i(3);e.Action=class{start(t){return h(this,void 0,void 0,function*(){'+generator+'})}}},'
    '3(t,e,i){const m=i(4);class G{static init(){G.model=new m.Model(G.apiPlugin)}}e.Game=G},'
    '4(t,e,i){const b=i(5),p=i(7);class M extends b.Base{constructor(t){super(t),this.isRestore=!1}onGame(t){'+on_game+'}}e.Model=M},'
    '5(t,e,i){const a=i(6);e.Base=class{constructor(t){t.events.on(a.Events.GAME,t=>this.onGame(t))}onGame(t){this.gameData=t,this.data=t}}},'
    '6(t,e){var n;e.Events=void 0,(n=e.Events||(e.Events={})).GAME="game"},'
    '7(t,e){e.Parsed=class{constructor(t){this.isRestoreState=!1}}}})')


def prove(source,**context):
    return async_lifecycle.proves_async_zero_bet(source,source.index('use('),'a.Action',{'game':{'mode':'NORMAL','nextMode':'RESPIN'}},_block,**context)


def test_source_proven_nonrestore_generator_reaches_zero_bet():
    assert prove(bundle())


def test_generator_timeline_callback_uses_normal_lifecycle_proof():
    source=bundle(generator='const e=g.Game.model,i=new a.TimelineLite;g.Game.model.isRestore&&(yield never()),i.add(()=>{g.Game.apiPlugin.betHandler.zeroBet()})')
    assert prove(source)


def test_unknown_awaiter_helper_is_not_executed_or_assumed():
    assert not prove(bundle().replace(HELPER,'var h=unknown;'))


def test_mutated_awaiter_rejected():
    assert not prove(bundle().replace('const g=i(3);','h=unknown;const g=i(3);'))


def test_unknown_restore_flag_leaves_yield_unproven():
    assert not prove(bundle().replace('g.Game.model.isRestore&&','g.Game.model.otherFlag&&'))


def test_missing_model_restore_reset_is_not_false_by_absence():
    assert not prove(bundle().replace('this.isRestore=!1,super.onGame(t)','super.onGame(t)'))


def test_unknown_game_event_binding_does_not_prove_model_state():
    assert not prove(bundle().replace('.GAME="game"','.GAME="other"'))


def test_action_spins_guard_needs_explicit_trusted_false_context():
    source=bundle(on_game='if(g.Game.isActionSpinsActive)return unknown();this.parsedGameData=new p.Parsed(t),this.isRestore=!1,super.onGame(t)').replace('const b=i(5),p=i(7);','const b=i(5),p=i(7),g=i(3);')
    assert not prove(source)
    assert not prove(source,action_spins_active=True)
    assert prove(source,action_spins_active=False)


def test_unknown_action_flag_cannot_use_action_spins_context():
    source=bundle(on_game='if(g.Game.unknownFlag)return unknown();this.parsedGameData=new p.Parsed(t),this.isRestore=!1,super.onGame(t)').replace('const b=i(5),p=i(7);','const b=i(5),p=i(7),g=i(3);')
    assert not prove(source,action_spins_active=False)


def test_mutated_generator_callback_is_not_inline_proof():
    source=bundle().replace('return h(this,void 0,void 0,function*(){','let callback=function*(){').replace('t.finish()})','t.finish()};mutate(callback);return h(this,void 0,void 0,callback)')
    assert not prove(source)


def test_unconditional_yield_is_not_assumed_to_resolve():
    assert not prove(bundle(generator='yield never();g.Game.apiPlugin.betHandler.zeroBet()'))


def test_conditional_send_remains_conditional():
    assert not prove(bundle(generator='g.Game.model.isRestore&&(yield never());unknown.flag&&g.Game.apiPlugin.betHandler.zeroBet()'))


def test_restore_ternary_selects_only_proven_nonrestore_arm():
    assert prove(bundle(generator='let x;g.Game.model.isRestore?(x=1,yield never()):x=2;g.Game.apiPlugin.betHandler.zeroBet()'))


def test_restore_reset_followed_by_unknown_reassignment_is_rejected():
    assert not prove(bundle().replace('this.isRestore=!1,super.onGame(t)','this.isRestore=!1,this.isRestore=unknown,super.onGame(t)'))


import os
from pathlib import Path
import re
import pytest
from tester_spin.providers.nolimit_city.client_actions import _mode_reference


_CACHE=Path(os.environ.get('NLC_CLIENT_CACHE','data/providers/nolimit_city/_clients'))


@pytest.mark.skipif(not _CACHE.is_dir(),reason='Exact public client cache not supplied')
@pytest.mark.parametrize('game,version,phase,expected_class,default',[
    ('Disturbed','1.2.10','RESPIN_FREESPIN','DisturbedRespinIdlePresentation',True),
    ('WalkOfShame','1.2.6','SUPER_FREESPIN_RESPIN','WalkOfShameZeroBetIdlePresentation',True),
    ('Tanked3','1.1.178','NORMAL_AVALANCHE','Tanked3AvalancheIdlePresentation',False),
    ('Serial','1.3.17','FREESPIN_RESPIN','SerialRespinIdlePresentation',False),
])
def test_exact_public_bundle_active_idle_binding(game,version,phase,expected_class,default):
    source=(_CACHE/game/(version+'.js')).read_text(encoding='utf-8')
    pattern=(r'addGameModeFlowStatePresentationMap\('+_mode_reference(source,phase)
        +r',new Map\(\[\[\w+\.FlowState\.IDLE,(\w+)')
    matches=list(re.finditer(pattern,source));assert len(matches)==1
    binding=matches[0];prefix=source[max(0,binding.start()-16000):binding.start()]
    assignment=list(re.finditer(r'\b'+re.escape(binding[1])+r'=new ([\w$]+\.[\w$]+)',prefix))[-1]
    assert assignment[1].split('.')[1]==expected_class
    answer={'game':{'mode':'NORMAL','nextMode':phase}}
    assert async_lifecycle.proves_async_zero_bet(source,binding.start(),assignment[1],answer,_block) is default
    assert async_lifecycle.proves_async_zero_bet(source,binding.start(),assignment[1],answer,_block,action_spins_active=False)


def test_competing_game_model_object_alias_write_invalidates_proof():
    source=bundle().replace('e.Game=G}', 'e.Game=G;const alias=G;alias.model=unknown}')
    assert not prove(source)


def test_conditional_game_registration_is_not_proven():
    source=bundle().replace('t.events.on(a.Events.GAME','unknown.flag&&t.events.on(a.Events.GAME')
    assert not prove(source)


def test_model_constructor_callback_reassignment_invalidates_game_provenance():
    source=bundle().replace('super(t),this.isRestore=!1','super(t),this.isRestore=!1,this.onGame=unknown')
    assert not prove(source)


def test_exported_game_event_constant_mutation_invalidates_binding():
    source=bundle().replace('.GAME="game"}', '.GAME="game",e.Events.GAME="other"}')
    assert not prove(source)


def test_async_helper_with_changed_generator_driver_is_not_canonical():
    assert not prove(bundle().replace('n.next(t)','n.return(t)'))


def test_restore_state_getter_cannot_use_unrelated_parsed_object():
    source=bundle(generator='const data=g.Game.getParsedData();data.isRestoreState&&(yield never()),g.Game.apiPlugin.betHandler.zeroBet()')
    source=source.replace('static init(){','static getParsedData(){return unknown}static init(){')
    assert not prove(source)


@pytest.mark.parametrize('replacement',[
    'e.Game=G;G["model"]=unknown}',
    'e.Game=G;e.Game["model"]=unknown}',
    'e.Game=G;const alias=G;alias["model"]=unknown}',
])
def test_competing_bracket_model_write_invalidates_binding(replacement):
    assert not prove(bundle().replace('e.Game=G}',replacement))


def test_model_restore_reset_cannot_be_overridden_with_bracket_write():
    source=bundle().replace('this.isRestore=!1,super.onGame(t)','this.isRestore=!1,this["isRestore"]=unknown,super.onGame(t)')
    assert not prove(source)


def test_model_restore_reset_cannot_be_overridden_through_this_alias():
    source=bundle().replace('this.isRestore=!1,super.onGame(t)','this.isRestore=!1;const alias=this;alias.isRestore=unknown;super.onGame(t)')
    assert not prove(source)


def test_model_restore_accessor_does_not_establish_false_state():
    source=bundle().replace('onGame(t){this.parsedGameData','get isRestore(){return true}set isRestore(value){}onGame(t){this.parsedGameData')
    assert not prove(source)


def test_model_on_game_callback_cannot_be_replaced_through_brackets():
    source=bundle().replace('super(t),this.isRestore=!1','super(t),this.isRestore=!1,this["onGame"]=unknown')
    assert not prove(source)


def test_raw_answer_flag_does_not_supply_trusted_action_spins_context():
    source=bundle(on_game='if(g.Game.isActionSpinsActive)return unknown();this.parsedGameData=new p.Parsed(t),this.isRestore=!1,super.onGame(t)').replace('const b=i(5),p=i(7);','const b=i(5),p=i(7),g=i(3);')
    answer={'game':{'mode':'NORMAL','nextMode':'RESPIN','action_spins_active':False}}
    assert not async_lifecycle.proves_async_zero_bet(source,source.index('use('),'a.Action',answer,_block)


def test_action_constructor_cannot_mutate_bound_awaiter_before_start():
    assert not prove(bundle().replace('e.Action=class{start(t)', 'e.Action=class{constructor(){h=unknown}start(t)'))


def test_unknown_model_base_ancestor_cannot_hide_restore_accessor():
    source=bundle().replace('e.Base=class{constructor(t)', 'e.Base=class extends unknown.Parent{constructor(t)')
    assert not prove(source)


def test_game_event_expression_must_be_exact_wire_literal():
    assert not prove(bundle().replace('.GAME="game"}', '.GAME="game"+"Suffix"}'))


def test_awaiter_scope_cannot_shadow_promise_constructor_with_resolver():
    altered=re.sub(r'\bo\b','i',HELPER)
    assert not prove(bundle().replace(HELPER,altered))


def test_generator_restore_write_invalidates_prior_model_reset():
    source=bundle(generator='g.Game.model.isRestore=true;g.Game.model.isRestore&&(yield never()),g.Game.apiPlugin.betHandler.zeroBet()')
    assert not prove(source)


def test_parsed_state_alias_reassignment_cannot_use_old_restore_provenance():
    source=bundle(generator='let data=g.Game.getParsedData();data=unknown;data.isRestoreState&&(yield never()),g.Game.apiPlugin.betHandler.zeroBet()')
    source=source.replace('static init(){','static getParsedData(){return G.model.parsedGameData?G.model.parsedGameData:G.model.parsedInitData}static init(){')
    assert not prove(source)


def test_late_module_awaiter_reassignment_changes_actual_start_helper():
    source=bundle().replace('})}}},','})}};h=unknown},',1)
    assert not prove(source)


def test_external_model_prototype_on_game_replacement_invalidates_reset():
    source=bundle().replace('e.Model=M}', 'e.Model=M;M.prototype.onGame=function(t){this.isRestore=true}}')
    assert not prove(source)


def test_model_prototype_alias_on_game_replacement_invalidates_reset():
    source=bundle().replace('e.Model=M}', 'e.Model=M;const proto=M.prototype;proto["onGame"]=unknown}')
    assert not prove(source)


def test_external_base_constructor_replacement_is_not_proven_dispatch():
    source=bundle().replace('this.gameData=t,this.data=t}}}', 'this.gameData=t,this.data=t}};e.Base.prototype.onGame=unknown}')
    assert not prove(source)
