import pytest

from tester_spin.models import GameTestResult, SpinAttempt
from tester_spin.providers.bgaming_paths_v2 import _annotate_mode_evidence
from tester_spin.providers.path_coverage import _declared_feature_points


def result(*, ok=True, terminal=True):
    return GameTestResult(provider="bgaming", slug="fixture", game_name="Fixture",
        game_url="https://example.invalid", requested_spins=2,
        successful_spins=int(ok), failed_spins=int(not ok), status="PARCIAL",
        feature_domains={
            "purchase": {"complete": True, "source": "init.feature_multipliers", "options": ["bonus_buy:0", "bonus_buy:1"]},
            "ante": {"complete": True, "source": "init.feature_multipliers", "options": ["bonus_chance"]},
        },
        discovered_modes=[
            {"id": "PURCHASE_BONUS_BUY_LEVEL_0", "kind": "PURCHASE", "purchased_feature": "bonus_buy", "purchased_feature_level": "0", "source": "init.feature_multipliers+client"},
            {"id": "PURCHASE_BONUS_BUY_LEVEL_1", "kind": "PURCHASE", "purchased_feature": "bonus_buy", "purchased_feature_level": "1", "source": "init.feature_multipliers+client"},
            {"id": "PURCHASE_BONUS_CHANCE", "kind": "PURCHASE", "purchased_feature": "bonus_chance", "purchased_feature_level": None, "source": "init.feature_multipliers+client"},
        ], attempts=[
            SpinAttempt(number=1, mode_id="PURCHASE_BONUS_BUY_LEVEL_0", mode_kind="PURCHASE", ok=ok, terminal=terminal),
            SpinAttempt(number=1, mode_id="PURCHASE_BONUS_CHANCE", mode_kind="PURCHASE", ok=ok, terminal=terminal),
        ])


def test_verified_bgaming_feature_names_and_levels_match_the_declared_domains():
    evidence = result()
    _annotate_mode_evidence(evidence, lambda _: None)
    points = {point["mode_id"]: point for point in _declared_feature_points(evidence)}
    assert points["PURCHASE_DECLARATION"]["required"] == ["bonus_buy:0", "bonus_buy:1"]
    assert points["PURCHASE_DECLARATION"]["covered"] == ["bonus_buy:0"]
    assert points["ANTE_DECLARATION"]["covered"] == ["bonus_chance"]


@pytest.mark.parametrize("ok,terminal", [(False, False), (True, False), (False, True)])
def test_unvalidated_feature_contract_does_not_close_a_declared_obligation(ok, terminal):
    evidence = result(ok=ok, terminal=terminal)
    _annotate_mode_evidence(evidence, lambda _: None)
    assert all(not point["covered"] for point in _declared_feature_points(evidence))
