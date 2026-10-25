"""Sanitized modern API-v2 identity chain, minimized from official demos."""
from unittest.mock import patch

import pytest
import requests

from tester_spin.providers.bgaming import runtime as module
from tester_spin.providers.bgaming.runtime import BGamingRuntime


SOURCE = '''const WireHolder=class Wire{
spinRequest(done){return task(this,arguments,function*(callback,options={}){!options.bonus&&!context.data.isNextSpinFree&&(options.bet=context.data.bet/Config.currentConfig.base_bet*variants[0].base_bet),context.data.isNextSpinFree||(options.mode=Config.currentVariantId.toString()),Config.currentConfig.requestOptions&&(delete options.mode,context.data.isNextSpinFree||Object.assign(options,Config.currentConfig.requestOptions));let command="spin";context.data.isNextSpinFree&&(command=context.data.spinData.flow.available_actions.find(action=>action==="freespin"||action==="respin")),this.requestCommand(command,response=>task(this,null,function*(){callback(response)}),options)})}
requestCommand(command,callback,options,quiet=!1){this.request(window.__OPTIONS__.api,{command:command,options:options},void 0,void 0,quiet).then(callback)}
request(endpoint,payload,attempt=1,headers,quiet=!1){let request;return payload&&(headers=headers||{},headers["Content-Type"]="application/json",request={body:JSON.stringify(payload),method:"POST",headers:headers}),http.fetch(context.currentContainer,endpoint,"json",request,attempt,!0)}
};let Api=WireHolder;
class Game{
init(){this.api=new Api}
spin(options){this.schedule("spin request",()=>{this.spinRequest(options)})}
spinRequest(options={}){let response;const send=()=>{if(context.data.purchased_feature=options.purchased_feature,options.purchased_feature&&Config.allOptions[0].buy_features)for(const entry of Config.allOptions[0].buy_features.features)entry.name===options.purchased_feature&&entry.level==options.purchased_feature_level&&entry.requestName&&(options.purchased_feature=entry.requestName);this.api.spinRequest(reply=>{response=reply,this.spinRequestFlow.unlockFlow("wait for spin response")},options)};send()}
}
class Menu{buy(entry){context.data.game.spin({purchased_feature:entry.name,purchased_feature_level:entry.level})}}
'''


def profile(source, extra_module=""):
    runtime = BGamingRuntime(session=requests.Session(),
        launch_url="https://demo.bgaming-network.com/fixture",
        api_url="https://demo.bgaming-network.com/api/fixture", identifier="fixture",
        csrf_header_name="", csrf_header_value="", options={}, round_series_id=1)
    try:
        with patch.object(module, "_runtime_bundle_candidates", return_value=[]), patch.object(
                module, "_collect_provider_script_contracts", return_value=[(30, "https://cdn.bgaming-network.com/fixture.js", source)] + ([(20, "https://cdn.bgaming-network.com/other.js", extra_module)] if extra_module else [])):
            return module.discover_api_v2_wire_profile(runtime, timeout_s=1)
    finally:
        runtime.session.close()


def test_modern_identity_chain_supports_advertised_purchase_levels():
    evidence = profile(SOURCE)
    assert evidence["purchase_feature_level_supported"] is True
    assert evidence["dynamic_purchased_feature"] is True


@pytest.mark.parametrize("before,after", [
    ('purchased_feature_level:entry.level', 'purchased_feature_level:other.level'),
    ('this.spinRequest(options)', 'this.spinRequest({})'),
    ('this.api.spinRequest(reply=>', 'this.other.spinRequest(reply=>'),
    ('},options)};send()', '},{})};send()'),
    ('this.api=new Api', 'this.api=new Other'),
    ('let Api=WireHolder', 'let Api=Other'),
    ('}),options)})', '}),other)})'),
    ('{command:command,options:options}', '{command:command,options:other}'),
    ('JSON.stringify(payload)', 'JSON.stringify(other)'),
    ('method:"POST"', 'method:"GET"'),
    ('this.requestCommand(command,', 'this.otherCommand(command,'),
    ('let command="spin";', 'let command="other";'),
    ('let command="spin";', 'options.purchased_feature_level="3";let command="spin";'),
    ('let command="spin";', 'mutate(options);let command="spin";'),
    ('spin(options){', 'spin(options){options.purchased_feature_level="3";'),
    ('spin(options){', 'spin(options){options["purchased_feature_level"]="3";'),
    ('spin(options){', 'spin(options){const alias=options;alias.purchased_feature_level="3";'),
    ('spin(options){', 'spin(options){Object.assign(options,{purchased_feature_level:"3"});'),
    ('init(){this.api=new Api}', 'init(){this.api=new Api;this.api=other}'),
    ('let request;return', 'payload.options={};let request;return'),
    ('http.fetch(context.currentContainer', '(request.body="{}",http.fetch)(context.currentContainer'),
    ('}),http.fetch(', '}),request.body="{}",http.fetch('),
    ('}),http.fetch(', '}),Object.assign(request,{body:"{}"}),http.fetch('),
    ('spin(options){', 'spin(options){rewrite(options);'),
    ('spin(options){', 'spin(options){Reflect.set(options,"purchased_feature_level","3");'),
])
def test_broken_or_modified_level_chain_does_not_enable_it(before, after):
    assert before in SOURCE
    assert not profile(SOURCE.replace(before, after))["purchase_feature_level_supported"]


def test_comments_and_ambiguous_api_rebinding_are_not_contracts():
    assert not profile('/*'+SOURCE+'*/')["purchase_feature_level_supported"]
    assert not profile(SOURCE+'Api=Other;')["purchase_feature_level_supported"]


def test_identical_script_collection_duplicates_preserve_the_contract():
    assert profile(SOURCE+'\n'+SOURCE)["purchase_feature_level_supported"]


def test_independent_modules_do_not_share_minified_lexical_bindings():
    assert profile(SOURCE, 'const Api=Other;')["purchase_feature_level_supported"]


@pytest.mark.parametrize("use", [
    'Object.assign(payload.options,{purchased_feature_level:"999"});',
    'const alias=payload.options;alias.purchased_feature_level="999";',
    'rewrite(payload);',
    'rewrite(payload.options);',
    'Reflect.set(payload.options,"purchased_feature_level","999");',
    'delete payload.options.purchased_feature_level;',
])
def test_payload_and_nested_options_cannot_escape_before_serialization(use):
    source = SOURCE.replace('let request;return', use+'let request;return')
    assert profile(source)["purchase_feature_level_supported"] is False


def replay_reader_source(body):
    replay = ('const ReplayHolder=class Replay{getReplayData(payload){'+body+'}};'
              'let ReplayAlias=ReplayHolder;'
              'var define=Object.defineProperty,'
              'put=(object,key,value)=>key in object?define(object,key,{enumerable:!0,configurable:!0,writable:!0,value:value}):object[key]=value,'
              'field=(object,key,value)=>put(object,typeof key!="symbol"?key+"":key,value);')
    return replay + SOURCE.replace('class Wire{', 'class Wire{constructor(){field(this,"replays",new ReplayAlias)}').replace(
        'let request;return', 'const response=this.replays.getReplayData(payload);let request;return')


def test_bound_replay_reader_only_inspects_payload_primitives():
    source = replay_reader_source('if(this.replayData&&payload){if(payload.options){}if(payload.command==="init")return this.replayData[0]}')
    assert profile(source)["purchase_feature_level_supported"] is True


@pytest.mark.parametrize("body", [
    'Object.assign(payload.options,{purchased_feature_level:"999"});',
    'rewrite(payload);',
    'const alias=payload.options;alias.purchased_feature_level="999";',
    'if(delete payload.command==="init")return this.replayData[0];',
])
def test_replay_reader_must_preserve_payload_before_serialization(body):
    assert profile(replay_reader_source(body))["purchase_feature_level_supported"] is False


def test_unbound_replay_reader_does_not_authorize_payload_escape():
    source = SOURCE.replace('let request;return', 'this.replays.getReplayData(payload);let request;return')
    assert profile(source)["purchase_feature_level_supported"] is False


NOTIFICATION_SOURCE = 'const WILL_REQUEST="EVENT_WILL_REQUEST";' + SOURCE.replace(
    'class Game{', 'class Game{onWillRequest(callback,context){this.on(WILL_REQUEST,callback,context)}'
    'offWillRequest(callback,context){this.off(WILL_REQUEST,callback,context)}').replace(
    'const send=()=>{', 'const send=()=>{this.emit(WILL_REQUEST,options);')


@pytest.mark.parametrize('handler', ['', 'delete options.bet;options.bonus=true;'])
def test_notification_with_no_selector_mutation_preserves_level(handler):
    listener = ('class Listener{init(){context.data.game.onWillRequest(this.onRequest)}'
                'onRequest(options){'+handler+'}}')
    assert profile(NOTIFICATION_SOURCE, listener)["purchase_feature_level_supported"]


def test_bound_notification_handler_preserves_the_same_method():
    listener = ('class Listener{constructor(){this.onRequest=this.onRequest.bind(this)}'
                'init(){context.data.game.onWillRequest(this.onRequest)}onRequest(options){delete options.bet;options.bonus=true}}')
    assert profile(NOTIFICATION_SOURCE, listener)["purchase_feature_level_supported"]
    assert not profile(NOTIFICATION_SOURCE, listener.replace('this.onRequest.bind(this)', 'rewrite'))["purchase_feature_level_supported"]


@pytest.mark.parametrize('listener', [
    'context.data.game.onWillRequest(other);',
    'const register=context.data.game.onWillRequest;',
    'class Listener{init(){context.data.game.onWillRequest(this.onRequest)}onRequest(options){options.purchased_feature_level="3"}}',
    'class Listener{init(){context.data.game.onWillRequest(this.onRequest)}onRequest(options){rewrite(options)}}',
    'bus.on("EVENT_WILL_REQUEST",rewrite);',
])
def test_unknown_or_mutating_notification_consumer_remains_unresolved(listener):
    assert not profile(NOTIFICATION_SOURCE, listener)["purchase_feature_level_supported"]


@pytest.mark.parametrize("generation", [2, 3])
def test_cached_generation_cannot_hide_a_newly_proven_level_contract(generation):
    from tester_spin.providers.bgaming.profile import API_V2, BGamingProfile, discover_profile
    runtime = BGamingRuntime(session=requests.Session(), launch_url="https://demo.bgaming-network.com/fixture",
        api_url="https://demo.bgaming-network.com/api/fixture", identifier="fixture",
        csrf_header_name="", csrf_header_value="", options={}, round_series_id=1)
    old = BGamingProfile(capability_version=generation, family=API_V2, validated=True,
        purchase_features=["freespin_buy"], purchase_feature_level_supported=False)
    init = {"api_version": "2", "options": {"default_bet": 20,
        "feature_options": {"feature_multipliers": {"base_bet": 20, "freespin_buy": {"0": 2000}}}}}
    try:
        fresh = discover_profile(runtime, init, timeout_s=1, persisted=old, wire_profile=profile(SOURCE))
        assert fresh.purchase_feature_level_supported is True
        assert fresh.purchase_features == ["freespin_buy"]
    finally:
        runtime.session.close()
