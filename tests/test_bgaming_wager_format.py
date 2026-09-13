from __future__ import annotations

from tester_spin.providers.bgaming.wager_format import (
    build_wager_format,
    canonical_wager_domains,
    discover_command_formats,
    extract_finite_domains,
)


def _adventures_init() -> dict:
    return {
        "flow": {
            "state": "ready",
            "command": "init",
            "available_actions": ["init", "spin"],
        },
        "options": {
            "available_bets": [10, 20, 40, 100],
            "default_bet": 100,
            "feature_options": {
                "feature_multipliers": {
                    "base_bet": 10,
                    "bonus_buy": {"0": 750, "1": 1000, "2": 1500},
                },
                "coin_values": [1, 2, 3, 5, 10],
            },
        },
        "bet_to_batch_state": {
            "10": {"boss_id": "base_cash", "number_in_set": 0},
            "20": {"boss_id": "base_box", "number_in_set": 1},
            "40": {"boss_id": "respin_bonus", "number_in_set": 2},
        },
        "outcome": {
            "screen": [[1, 2, 3], [4, 5, 6]],
            "win": 123,
        },
    }


def _bundle() -> str:
    return (
        'requestSpin=async e=>api.request({command:"spin",options:e});'
        'onSpin=()=>requestSpin({bet:100});'
        'onBuy=(e,t)=>requestSpin({bet:100,purchased_feature:"bonus_buy",purchased_feature_level:t});'
        'requestRespin=()=>api.request({command:"respin",options:{}});'
        'requestBonus=async e=>api.request({command:"play_bonus_game",options:e});'
        'chooseBonus=e=>requestBonus({mode:"pick",index:e});'
    )


def test_canonical_domains_reconstruct_purchase_grammar_from_init() -> None:
    domains = canonical_wager_domains(_adventures_init())
    assert domains["bet"]["values"] == [10, 20, 40, 100]
    assert domains["purchased_feature"]["values"] == ["bonus_buy"]
    assert domains["purchased_feature_level"]["values"] == ["0", "1", "2"]
    assert domains["purchased_feature_level"]["by_feature"] == {
        "bonus_buy": ["0", "1", "2"]
    }
    assert domains["purchase_prices"]["values"]["bonus_buy"] == {
        "0": 750,
        "1": 1000,
        "2": 1500,
    }


def test_finite_census_keeps_config_and_excludes_outcome_rng_arrays() -> None:
    rows = extract_finite_domains(_adventures_init())
    paths = {row["path"] for row in rows}
    assert "$.options.available_bets" in paths
    assert "$.options.feature_options.coin_values" in paths
    assert "$.options.feature_options.feature_multipliers.bonus_buy" in paths
    assert "$.bet_to_batch_state" in paths
    assert not any("outcome" in path for path in paths)
    assert not any("screen" in path for path in paths)


def test_command_inventory_links_known_wager_fields_without_ui() -> None:
    commands = discover_command_formats(_bundle(), _adventures_init())
    spin = next(row for row in commands if row["command"] == "spin")
    assert spin["serializer_shape_proven"] is True
    assert set(spin["option_fields"]) == {
        "bet",
        "purchased_feature",
        "purchased_feature_level",
    }
    assert spin["fields"]["bet"]["domain_candidates"]
    assert spin["fields"]["purchased_feature"]["domain_candidates"]
    assert spin["fields"]["purchased_feature_level"]["domain_candidates"]

    respin = next(row for row in commands if row["command"] == "respin")
    assert respin["parameterless"] is True

    bonus = next(row for row in commands if row["command"] == "play_bonus_game")
    assert bonus["option_fields"] == ["mode", "index"]
    assert bonus["fields"]["mode"]["resolved_by_literal"] is True
    assert bonus["fields"]["index"]["unresolved_in_client"] is True


def test_artifact_is_static_analysis_and_reports_remaining_unknowns() -> None:
    payload = build_wager_format(_adventures_init(), _bundle(), source="https://cdn.invalid/game/bundle.js")
    assert payload["method"] == "bootstrap+init+official-client-static-analysis"
    assert "no spin" in payload["network_policy"]
    assert payload["coverage"]["commands"] >= 3
    assert payload["canonical_wager_domains"]["bet"]["values"] == [10, 20, 40, 100]
    bonus = next(row for row in payload["commands"] if row["command"] == "play_bonus_game")
    assert bonus["fields"]["index"]["domain_candidates"] == []
