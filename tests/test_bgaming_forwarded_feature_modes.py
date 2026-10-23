"""Request/price relationships minimized from a current two-argument client.

The source fixture follows the same store -> modifier -> identity play wrapper
as the public client; it contains no launch/session credentials.
"""
import json
from unittest.mock import patch

import pytest
import requests

from tester_spin.providers.bgaming import hyperhive
from tester_spin.providers.bgaming.runtime import BGamingRuntime


SOURCE = '''const rpc=async(method,params)=>{const response=await http.post("/api",{id:crypto.randomUUID(),jsonrpc:"2.0",method:method,params:params});if(response.data?.error)throw response.data.error;return response.data},play=async(req,lock)=>(await rpc("play",{token:token(),state_lock:lock,req:req})).result;
const store=createStore(),chancePrice=1.5,prices={buy_bonus:60,buy_super_bonus:90,buy_ultra_bonus:120},cost=req=>"freebet"===req.bet_type?0:req.purchased_feature?req.bet*((feature,level)=>{if("buy_chance"===feature)return chancePrice;if("buy_bonus"===feature){if(!level)throw new Error("feature_id required for buy_bonus");return prices[level]}return 1})(req.purchased_feature,req.feature_id):req.bet;
const build=()=>{const state=store.getState(),free=state.freebets;return{bet:free?limits[0]:state.bet,bet_type:free?"freebet":"bet"}},decorate=(request,selection)=>("bet"===request.bet_type&&(request.purchased_feature=selection.purchased_feature,request.feature_id=selection.feature_id),request);
async function resume(){const request=build(),response=await play(request,current.lock);return response}
async function spin(){const state=store.getState(),request=decorate(build(),{purchased_feature:state.boost?"buy_chance":state.purchased_feature,feature_id:state.feature_id}),response=await play(request,current.lock);return response}
function charge(){const state=store.getState(),request=decorate(build(),{purchased_feature:state.boost?"buy_chance":state.purchased_feature,feature_id:state.feature_id}),debit=cost(request),balance=state.balance-debit;store.setState({balance:balance})}
const choices=[{featureId:"buy_bonus",icon:"standard"},{featureId:"buy_super_bonus",icon:"super"},{featureId:"buy_ultra_bonus",icon:"ultra"}];
choices.forEach((item,index)=>{const button=makeButton(item);button.onPress.connect(()=>{store.setState({purchased_feature:"buy_bonus",feature_id:item.featureId,boost:!1}),events.emit("SPIN")})});
boostButton.onPress.connect(()=>{store.setState({boost:!0,feature_id:void 0}),hide()});
'''


def discover(source):
    runtime = BGamingRuntime(session=requests.Session(),
        launch_url="https://fixture.demo.bgaming-network.com/hyperhive",
        api_url="https://fixture.demo.bgaming-network.com/api", identifier="fixture",
        csrf_header_name="", csrf_header_value="", options={}, round_series_id=1)
    try:
        with patch.object(hyperhive, "_download_bundle", return_value=source):
            return hyperhive.discover_modes_from_bundle(runtime, timeout_s=1,
                bundle_text=source, engine_contract=source)
    finally:
        runtime.session.close()


def purchases(source):
    return [m for m in discover(source) if m["kind"] == "PURCHASE" and m.get("executable")]


def test_forwarded_state_modifier_expands_menu_and_uses_declared_prices():
    modes = purchases(SOURCE)
    assert {m["id"]: (m["request"], m["expected_multiplier"]) for m in modes} == {
        "PURCHASE_BUY_CHANCE": ({"bet_type": "bet", "purchased_feature": "buy_chance"}, 1.5),
        "PURCHASE_BUY_BONUS_FEATURE_ID_BUY_BONUS": ({"bet_type": "bet", "purchased_feature": "buy_bonus", "feature_id": "buy_bonus"}, 60),
        "PURCHASE_BUY_BONUS_FEATURE_ID_BUY_SUPER_BONUS": ({"bet_type": "bet", "purchased_feature": "buy_bonus", "feature_id": "buy_super_bonus"}, 90),
        "PURCHASE_BUY_BONUS_FEATURE_ID_BUY_ULTRA_BONUS": ({"bet_type": "bet", "purchased_feature": "buy_bonus", "feature_id": "buy_ultra_bonus"}, 120),
    }


@pytest.mark.parametrize("before,after", [
    ('req:req}', 'req:other}'),
    ('jsonrpc:"2.0"', 'protocol:"other"'),
    ('play(request,current.lock)', 'other(request,current.lock)'),
    ('request=decorate(build()', 'request=other(build()'),
    ('request.feature_id=selection.feature_id', 'request.feature_id=selection.other'),
    ('request.purchased_feature=selection.purchased_feature', 'request.purchased_feature=selection.other'),
    ('feature_id:state.feature_id', 'feature_id:other.feature_id'),
    ('store.setState({purchased_feature:', 'other.setState({purchased_feature:'),
    ('feature_id:item.featureId', 'feature_id:other.featureId'),
    ('return prices[level]', 'return other[level]'),
    ('req.purchased_feature,req.feature_id', 'req.purchased_feature,req.other'),
    ('buy_ultra_bonus:120', 'buy_ultra_bonus:unknown'),
    ('buy_ultra_bonus:120', 'buy_ultra_bonus:-1'),
    ('featureId:"buy_ultra_bonus"', 'featureId:"unpriced"'),
    ('debit=cost(request)', 'debit=unrelated(request)'),
    ('balance=state.balance-debit', 'balance=state.balance'),
    ('boost:!0,feature_id:void 0', 'boost:!1,feature_id:void 0'),
    ('button.onPress.connect(()=>{store.setState', 'button.onPress.connect(()=>{if(false)store.setState'),
    ('button.onPress.connect', 'if(false)button.onPress.connect'),
])
def test_broken_feature_data_flow_cannot_authorize_purchase(before, after):
    assert not purchases(SOURCE.replace(before, after))


@pytest.mark.parametrize("suffix", [
    'decorate=(request,selection)=>request;',
    'prices={buy_bonus:1};',
    'prices.buy_ultra_bonus=1;',
    'choices.push({featureId:"unpriced"});',
    'function other(play){return play(request,current.lock)}',
    'function other(decorate){return decorate(request,selection)}',
    'function other(prices){return prices[level]}',
    'const p=prices;p.buy_ultra_bonus=1;',
    'choices[0].featureId="other";',
    'chancePrice++;',
    'choices.forEach(item=>item.featureId="other");',
])
def test_ambiguous_binding_or_mutable_domain_is_not_executable(suffix):
    assert not purchases(SOURCE + suffix)


def test_non_code_and_duplicate_collectors_preserve_proof_boundaries():
    assert not purchases("/*" + SOURCE + "*/")
    assert not purchases("const documentation=" + json.dumps(SOURCE) + ";")
    assert len(purchases(SOURCE + "\n" + SOURCE)) == 4


def test_base_spin_does_not_acquire_purchase_fields():
    base = next(mode for mode in discover(SOURCE) if mode["kind"] == "SPIN")
    assert base["executable"] is True
    assert base["request"] == {"bet_type": "bet"}
