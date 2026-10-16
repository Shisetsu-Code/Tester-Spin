from tester_spin.providers.nolimit_city.client_actions import automatic_command


def bundle(wrapper=None, action=None, other=""):
    wrapper = wrapper or "static createFlow(t){return{start:e=>n.SimplePresentationRunner.run(t,()=>e.finish(),t=>e.setSkipCallback(t))}}"
    action = action or "shouldRun(){return!0}start(t){x.apiPlugin.betHandler.zeroBet(),t.finish()}"
    return ('({1(t,e,i){const w=i(2),a=i(3);g.addGameModeFlowStatePresentationMap("NORMAL_RESPIN",new Map([[f.FlowState.IDLE,w.FlowWrapper.createFlow([new a.Step])]]))},'
            + "2(t,e,i){const n=i(4);e.FlowWrapper=class{" + wrapper + "}},"
            + "3(t,e,i){e.Step=class{" + action + "}}" + other + "})")


def run(source):
    return automatic_command(source, {"game":{"nextMode":"NORMAL_RESPIN"}})


def test_exact_bound_flow_wrapper_dispatches_zero_bet():
    assert run(bundle()) == {"type":"zeroBet","bet":"0.00"}


def test_wrapper_must_really_run_presentations():
    assert run(bundle(wrapper="static createFlow(t){return{start:e=>e.finish()}}")) is None


def test_conditional_presentation_is_not_automatic():
    assert run(bundle(action="shouldRun(){return model.flag}start(t){x.apiPlugin.betHandler.zeroBet()}")) is None


def test_same_export_name_in_unrelated_module_is_not_proof():
    assert run(bundle(action="start(t){t.finish()}",other=",9(t,e,i){e.Step=class{start(t){x.apiPlugin.betHandler.zeroBet()}}}")) is None


def test_unknown_preceding_presentation_blocks_wrapper():
    assert run(bundle().replace("[new a.Step]","[new a.Unknown,new a.Step]")) is None


def test_reassigned_import_is_not_proof():
    assert run(bundle().replace('g.addGameMode', 'a=unknown;g.addGameMode')) is None


def test_dollar_identifiers_resolve_without_global_export_guessing():
    assert run(bundle().replace('a=i(3)', '$a=i(3)').replace('new a.Step', 'new $a.Step')) == {"type":"zeroBet","bet":"0.00"}


def test_bounded_nested_runner_timeline_method_chain():
    from tester_spin.providers.nolimit_city.client_actions import _block
    from tester_spin.providers.nolimit_city.lifecycle import proves_zero_bet
    body='{start(t){r.SimplePresentationRunner.run(this.items,()=>this.complete(),e=>t.setSkipCallback(e))}complete(){const e=g.gsap.timeline();e.to({},{duration:.001}),e.add(()=>{this.endPresentation()})}endPresentation(){a.apiPlugin.betHandler.zeroBet()}}'
    assert proves_zero_bet(body,_block)


def test_recursive_method_chain_never_proves_effect():
    from tester_spin.providers.nolimit_city.client_actions import _block
    from tester_spin.providers.nolimit_city.lifecycle import proves_zero_bet
    assert not proves_zero_bet('{start(t){this.complete()}complete(){this.complete()}}',_block)


def test_inherited_export_resolution_keeps_override_active():
    from tester_spin.providers.nolimit_city import static_bindings
    from tester_spin.providers.nolimit_city.client_actions import _block
    source='({1(t,e,i){const a=i(2);use(new a.Child)},2(t,e,i){const b=i(3);class $C extends b.Base{finish(){return false}}e.Child=$C},3(t,e,i){e.Base=class{start(t){this.finish()}finish(){x.apiPlugin.betHandler.zeroBet()}}}})'
    resolved=static_bindings.inherited_methods(source,source.index('use('),'a.Child',_block)
    assert resolved['start'][:2]==('t','this.finish()')
    assert resolved['finish'][:2]==('','return false')


def test_inherited_unknown_base_stays_unresolved():
    from tester_spin.providers.nolimit_city import static_bindings
    from tester_spin.providers.nolimit_city.client_actions import _block
    source='({1(t,e,i){const a=i(2);use(new a.Child)},2(t,e,i){const b=i(99);class C extends b.Base{start(t){x.apiPlugin.betHandler.zeroBet()}}e.Child=C}})'
    assert static_bindings.inherited_methods(source,source.index('use('),'a.Child',_block) is None


def inherited_flow_source(override=''):
    return ('({1(t,e,i){const a=i(2);g.addGameModeFlowStatePresentationMap("NORMAL_RESPIN",new Map([[f.FlowState.IDLE,new a.Flow]]))},'
    '2(t,e,i){const b=i(3),n=i(4);class Z extends b.Base{constructor(){super("z",false)}buildTimeline(){const t=this.tl;t.add(()=>{x.apiPlugin.betHandler.zeroBet()})}'+override+'}class Intro extends b.Base{shouldRun(){return x.Game.model.mode.toString().includes("NORMAL")&&x.Game.model.nextMode.toString().includes("FREESPIN")}buildTimeline(){unknown()}}e.Flow=class{constructor(){this.presentations=[new Intro,new Z]}start(t){n.SimplePresentationRunner.run(this.presentations,()=>t.finish(),e=>t.setSkipCallback(e))}}},'
    '3(t,e,i){e.Base=class{constructor(t,e){this.name=t,this.createSkipCallback=e}shouldRun(){return!0}skip(){this.tl.progress(1)}start(t){this.controller=t,this.tl=n.gsap.timeline({onComplete:()=>{t.setSkipCallback(),t.finish()}}),this.createSkipCallback&&this.tl.add(()=>{this.controller.setSkipCallback(()=>{this.skip()})},.1),this.buildTimeline()}}}})')


def test_constructor_runner_resolves_local_inherited_timeline_and_false_intro():
    assert automatic_command(inherited_flow_source(),{'game':{'mode':'NORMAL','nextMode':'NORMAL_RESPIN'}})=={"type":"zeroBet","bet":"0.00"}


def test_inherited_should_run_override_remains_conditional():
    assert automatic_command(inherited_flow_source('shouldRun(){return unknown.flag}'),{'game':{'mode':'NORMAL','nextMode':'NORMAL_RESPIN'}}) is None


def test_active_intro_without_proven_completion_blocks_later_action():
    source=inherited_flow_source().replace('includes("FREESPIN")','includes("NORMAL")')
    assert automatic_command(source,{'game':{'mode':'NORMAL','nextMode':'NORMAL_RESPIN'}}) is None


def test_inherited_start_with_unrelated_getter_uses_active_finish_override():
    source='({1(t,e,i){const a=i(2);g.addGameModeFlowStatePresentationMap("NORMAL_AVALANCHE",new Map([[f.FlowState.IDLE,new a.Child]]))},2(t,e,i){const b=i(3);class C extends b.Base{finishPresentation(){x.apiPlugin.betHandler.zeroBet()}}e.Child=C},3(t,e,i){e.Base=class{get gameMode(){return "NORMAL"}start(t){r.SimplePresentationRunner.run(this.items,()=>this.finishPresentation(),e=>t.setSkipCallback(e))}finishPresentation(){this.controller.finish()}}}})'
    assert automatic_command(source,{'game':{'nextMode':'NORMAL_AVALANCHE'}})=={"type":"zeroBet","bet":"0.00"}


def test_accessor_override_blocks_inherited_callable():
    source='({1(t,e,i){const a=i(2);g.addGameModeFlowStatePresentationMap("NORMAL_AVALANCHE",new Map([[f.FlowState.IDLE,new a.Child]]))},2(t,e,i){const b=i(3);class C extends b.Base{get start(){return unknown}}e.Child=C},3(t,e,i){e.Base=class{start(t){x.apiPlugin.betHandler.zeroBet()}}}})'
    assert automatic_command(source,{'game':{'nextMode':'NORMAL_AVALANCHE'}}) is None


def test_bound_custom_recursive_runner_completion_reaches_active_finish():
    source='({1(t,e,i){const a=i(2);g.addGameModeFlowStatePresentationMap("NORMAL_AVALANCHE",new Map([[f.FlowState.IDLE,new a.Child]]))},2(t,e,i){const r=i(3);e.Child=class{start(t){r.Custom.run(this.items,()=>this.done(),e=>t.setSkipCallback(e))}done(){x.apiPlugin.betHandler.zeroBet()}}},3(t,e,i){class R{static run(e,t,n){const s=e.concat(),o=s.shift();null==o?t():o.shouldRun()?o.start({finish:()=>R.run(s,t,n),setSkipCallback:n}):R.run(s,t,n)}}e.Custom=R}})'
    assert automatic_command(source,{'game':{'nextMode':'NORMAL_AVALANCHE'}})=={"type":"zeroBet","bet":"0.00"}
    assert automatic_command(source.replace('null==o?t():','null==o?unknown():'),{'game':{'nextMode':'NORMAL_AVALANCHE'}}) is None


def test_imported_module_without_require_parameter_resolves():
    assert run(bundle().replace('3(t,e,i){','3(t,e){')) == {"type":"zeroBet","bet":"0.00"}


def test_false_guard_uses_bound_inherited_enum_literal():
    from tester_spin.providers.nolimit_city.static_bindings import inactive_guard
    from tester_spin.providers.nolimit_city.client_actions import _block
    source='({1(t,e,i){const a=i(2);use()},2(t,e,i){const b=i(3);class M extends b.Base{}e.Modes=M},3(t,e){class M{}e.Base=M,M.NORMAL="NORMAL",M.FS="FREESPIN"}})'
    body='return g.Game.model.data.mode.includes(a.Modes.NORMAL)&&a.Modes.FS===g.Game.model.data.nextMode&&!g.Game.model.data.brokeTheBank'
    assert inactive_guard(body,{'mode':'NORMAL','nextMode':'NORMAL_RESPIN'},source,source.index('use()'),_block)
    assert not inactive_guard(body,{'mode':'NORMAL','nextMode':'FREESPIN'},source,source.index('use()'),_block)


def test_constructor_presentation_mutation_invalidates_list_proof():
    source=inherited_flow_source().replace('this.presentations=[new Intro,new Z]','this.presentations=[new Intro,new Z],this.presentations.unshift(unknown)')
    assert automatic_command(source,{'game':{'mode':'NORMAL','nextMode':'NORMAL_RESPIN'}}) is None


def test_accessor_should_run_override_is_not_an_unconditional_guard():
    source=inherited_flow_source('get shouldRun(){return unknown}')
    assert automatic_command(source,{'game':{'mode':'NORMAL','nextMode':'NORMAL_RESPIN'}}) is None


def test_inherited_timeline_property_pause_invalidates_alias_proof():
    source=inherited_flow_source().replace('t.add(()=>{x.apiPlugin.betHandler.zeroBet()})','this.tl.pause(),t.add(()=>{x.apiPlugin.betHandler.zeroBet()})')
    assert automatic_command(source,{'game':{'mode':'NORMAL','nextMode':'NORMAL_RESPIN'}}) is None


def test_constructor_callable_reassignment_blocks_inherited_method():
    source=inherited_flow_source().replace('super("z",false)','super("z",false),this.buildTimeline=unknown')
    assert automatic_command(source,{'game':{'mode':'NORMAL','nextMode':'NORMAL_RESPIN'}}) is None


def test_export_reassignment_blocks_wrapper_class_proof():
    source=bundle().replace('x.apiPlugin.betHandler.zeroBet(),t.finish()}}','x.apiPlugin.betHandler.zeroBet(),t.finish()}};e.Step=unknown')
    assert run(source) is None


def replay_bundle(fake_type='FAKE_BET',extra=''):
    source='({1(t,e,i){const a=i(2);g.addGameModeFlowStatePresentationMap("NORMAL_RESPIN",new Map([[f.FlowState.IDLE,new a.Action]]))},2(t,e,i){const g=i(3);e.Action=class{start(t){g.Game.localReplay.isPlaying?g.Game.localReplay.sendFakeBet():g.Game.apiPlugin.betHandler.zeroBet(),t.finish()}}},3(t,e,i){const r=i(4);class G{static init(){G.localReplay=new r.LocalReplay(G.apiPlugin)}}e.Game=G},4(t,e){class R extends PIXI.Container{get isPlaying(){return this.replaying}sendFakeBet(){s.NolimitApplication.apiPlugin.events.trigger("bet",{type:"FAKE_BET",bet:"0.00",isFakeBet:!0,replayAndFeatureBuy:!0,requestNextResponse:!0})}constructor(t){super(),this.replaying=!1,this.startReplayButton.addClickCallback(()=>this.startPlayback())}startPlayback(){this.recordedResponses.length<=0||(this.replaying=!0,this.sendInitialBet())}sendInitialBet(){this.apiPlugin.events.trigger("game",this.recordedResponses[this.currentResponseIndex++])}}e.LocalReplay=R}})'
    return source.replace('type:"FAKE_BET"','type:"'+fake_type+'"').replace('sendInitialBet(){','sendInitialBet(){'+extra)


def test_trusted_direct_demo_context_selects_only_verified_local_replay_else():
    source=replay_bundle()
    assert automatic_command(source,{'game':{'nextMode':'NORMAL_RESPIN'}},direct_demo_transport=True)=={"type":"zeroBet","bet":"0.00"}
    assert run(source) is None


def test_demo_context_cannot_authorize_arbitrary_is_playing_flag():
    assert automatic_command(replay_bundle(fake_type='normalBet'),{'game':{'nextMode':'NORMAL_RESPIN'}},direct_demo_transport=True) is None


def test_unknown_local_replay_activation_path_blocks_context_assumption():
    assert automatic_command(replay_bundle(extra='this.replaying=!0,'),{'game':{'nextMode':'NORMAL_RESPIN'}},direct_demo_transport=True) is None


def test_chained_export_void_initialization_is_not_a_reassignment():
    from tester_spin.providers.nolimit_city.static_bindings import class_record
    from tester_spin.providers.nolimit_city.client_actions import _block
    source=bundle().replace('3(t,e,i){','3(t,e,i){e.Step=e.Other=void 0;')
    assert run(source)=={"type":"zeroBet","bet":"0.00"}
    assert class_record(source,source.index('g.addGameMode'),'a.Step',_block) is not None


def test_numeric_webpack_module_ids_accept_scientific_notation():
    assert run(bundle().replace('3(t,e,i){','3e0(t,e,i){'))=={"type":"zeroBet","bet":"0.00"}


def test_arrow_webpack_module_factories_resolve_imports():
    source=bundle().replace('1(t,e,i){','1:(t,e,i)=>{').replace('2(t,e,i){','2:(t,e,i)=>{').replace('3(t,e,i){','3:(t,e,i)=>{')
    assert run(source)=={"type":"zeroBet","bet":"0.00"}


def test_function_webpack_module_factory_resolves_imports():
    assert run(bundle().replace('3(t,e,i){','3:function(t,e,i){'))=={"type":"zeroBet","bet":"0.00"}


def test_if_condition_root_timeline_effect_is_unconditional():
    from tester_spin.providers.nolimit_city.client_actions import _block
    from tester_spin.providers.nolimit_city.lifecycle import proves_zero_bet
    body='{start(t){const tl=g.gsap.timeline();if(tl.add(()=>{a.apiPlugin.betHandler.zeroBet()}),unknown.flag){ui.show()}}}'
    assert proves_zero_bet(body,_block)
    assert not proves_zero_bet(body.replace('if(tl.add','if(unknown.guard&&tl.add'),_block)
    assert not proves_zero_bet(body.replace('ui.show()','tl.pause()'),_block)


def test_demo_context_rejects_competing_static_local_replay_write():
    source=replay_bundle().replace('e.Game=G}', 'e.Game=G,G.localReplay=unknown}')
    assert automatic_command(source,{'game':{'nextMode':'NORMAL_RESPIN'}},direct_demo_transport=True) is None


def test_demo_context_rejects_export_alias_local_replay_write():
    source=replay_bundle().replace('e.Game=G}', 'e.Game=G,e.Game.localReplay=unknown}')
    assert automatic_command(source,{'game':{'nextMode':'NORMAL_RESPIN'}},direct_demo_transport=True) is None


def test_demo_context_rejects_local_alias_local_replay_write():
    source=replay_bundle().replace('e.Game=G}', 'e.Game=G;const alias=G;alias.localReplay=unknown}')
    assert automatic_command(source,{'game':{'nextMode':'NORMAL_RESPIN'}},direct_demo_transport=True) is None
