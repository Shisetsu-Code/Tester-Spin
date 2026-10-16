from tester_spin.providers.bgaming.runtime import discover_effective_bet_multipliers, effective_bet_for_options

SOURCE = """var scales={20:1,40:2,60:3,80:4,100:5};class Client{init(){this.additionalSpinOptions.mode=this.linesCount}restore(response){var stake=this.getBet();if(response.outcome.bet!==stake*scales[this.linesCount])stake=Math.round(response.outcome.bet/scales[this.linesCount])}}"""

def test_selected_lines_scale_is_proven_by_client_bet_conversion():
    mapping=discover_effective_bet_multipliers(SOURCE)
    assert mapping == {"20":1.0,"40":2.0,"60":3.0,"80":4.0,"100":5.0}
    assert effective_bet_for_options(20,selector_field="mode",multipliers=mapping,options={"mode":"60"}) == 60


def test_unbound_table_or_unrelated_multiplier_is_not_evidence():
    for source in [SOURCE.replace('stake*scales[this.linesCount]','stake*other[this.linesCount]'), SOURCE.replace('this.additionalSpinOptions.mode=this.linesCount','this.other=this.linesCount'), SOURCE.replace('this.getBet()','this.getWin()'), '/*'+SOURCE+'*/']:
        assert discover_effective_bet_multipliers(source) == {}


def test_proven_selector_reaches_profile_without_inventing_choice_domain():
    import requests
    from tester_spin.providers.bgaming.runtime import BGamingRuntime
    from tester_spin.providers.bgaming.profile import discover_profile
    runtime=BGamingRuntime(session=requests.Session(),launch_url="https://demo.example/",api_url="https://demo.example/api",identifier="fixture",csrf_header_name="",csrf_header_value="",options={},round_series_id=1)
    try:
        profile=discover_profile(runtime,{"api_version":"2","options":{"default_bet":20}},timeout_s=1,wire_profile={"spin_options":{"mode":"60"},"effective_bet_selector":"mode","effective_bet_multipliers":discover_effective_bet_multipliers(SOURCE)})
        assert profile.effective_bet_selector == "mode"
        assert profile.spin_option_choices == {}
        assert effective_bet_for_options(20,selector_field=profile.effective_bet_selector,multipliers=profile.effective_bet_multipliers,options=profile.spin_options) == 60
    finally:
        runtime.session.close()
