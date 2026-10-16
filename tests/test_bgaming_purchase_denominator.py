from tester_spin.providers.bgaming import runtime

SOURCE = """class Client{initBuyFeatures(data){var map=data.options.feature_options.feature_multipliers,base=map.base_bet||100;for(var feature in map){var value=map[feature];if(feature.endsWith("_buy"))for(var level in value)this.baseBonusPrices[feature][level]=value[level]/base;else if(feature.endsWith("_chance"))this.baseChancePrices[feature]=value/base}}}"""

def test_client_denominator_is_scoped_to_feature_multiplier_conversion():
    assert runtime.discover_purchase_base_fallback(SOURCE) == 100


def test_price_conversion_needs_same_map_value_and_denominator():
    for source in [SOURCE.replace('value[level]/base','value[level]/other').replace('value/base','value/other'), SOURCE.replace('value=map[feature]','value=other[feature]'),SOURCE.replace('feature_options.feature_multipliers','unrelated.multipliers'),'/*'+SOURCE+'*/']:
        assert runtime.discover_purchase_base_fallback(source) is None


def test_server_base_overrides_client_fallback_and_no_global_default():
    data={"options":{"feature_options":{"feature_multipliers":{"freespin_buy":{"4":10000},"freespin_chance":{"4":150}}}}}
    assert runtime.discover_purchase_modes(data)[0]["cost_multiplier"] is None
    modes=runtime.discover_purchase_modes(data,client_base_fallback=100)
    assert [m["cost_multiplier"] for m in modes] == [100,1.5]
    data["options"]["feature_options"]["feature_multipliers"]["base_bet"]=20
    assert runtime.discover_purchase_modes(data,client_base_fallback=100)[0]["cost_multiplier"] == 500


def test_zero_server_base_uses_proven_or_default_but_negative_does_not():
    data={"options":{"feature_options":{"feature_multipliers":{"base_bet":0,"bonus_buy":10000}}}}
    assert runtime.discover_purchase_modes(data,client_base_fallback=100)[0]["cost_multiplier"] == 100
    data["options"]["feature_options"]["feature_multipliers"]["base_bet"]=-2
    assert runtime.discover_purchase_modes(data,client_base_fallback=100)[0]["cost_multiplier"] is None


def test_profile_preserves_denominator_for_executor_and_persistence():
    import requests
    from tester_spin.providers.bgaming.profile import discover_profile, BGamingProfile
    session=requests.Session()
    rt=runtime.BGamingRuntime(session=session,launch_url="https://demo.example/",api_url="https://demo.example/api",identifier="fixture",csrf_header_name="",csrf_header_value="",options={},round_series_id=1)
    try:
        profile=discover_profile(rt,{"api_version":"2","options":{"default_bet":10}},timeout_s=1,wire_profile={"purchase_base_fallback":runtime.discover_purchase_base_fallback(SOURCE)})
        assert profile.purchase_base_fallback == 100
        assert BGamingProfile.from_dict(profile.to_dict()).purchase_base_fallback == 100
    finally:
        session.close()


def test_reassigned_denominator_and_conflicting_client_defaults_are_rejected():
    assert runtime.discover_purchase_base_fallback(SOURCE.replace('for(var feature', 'base=50;for(var feature')) is None
    assert runtime.discover_purchase_base_fallback(SOURCE + SOURCE.replace('||100','||200')) is None


def test_path_policy_wrappers_preserve_proven_client_denominator():
    from tester_spin.providers.bgaming_path_policy import _discover_purchase_modes_policy
    from tester_spin.providers.bgaming_paths_v2 import _purchase_modes_guard
    data={"options":{"feature_options":{"feature_multipliers":{"bonus_buy":10000}}}}
    for discover in [_discover_purchase_modes_policy,_purchase_modes_guard]:
        modes=discover(data,client_base_fallback=100)
        assert modes[0]["cost_multiplier"] == 100
        assert discover(data)[0]["cost_multiplier"] is None
