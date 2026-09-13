from __future__ import annotations

from tester_spin.providers.bgaming.assisted_resolution import (
    _restore_assisted_history,
    capture_matches_target,
    merge_assisted_captures,
    unresolved_targets,
)


def _payload() -> dict:
    return {
        "commands": [
            {
                "command": "play_bonus_game",
                "fields": {
                    "mode": {
                        "unresolved_in_client": False,
                        "domain_candidates": [{"values": ["pick"]}],
                    },
                    "index": {
                        "unresolved_in_client": True,
                        "domain_candidates": [],
                    },
                },
            },
            {
                "command": "spin",
                "fields": {
                    "bet": {
                        "unresolved_in_client": False,
                        "domain_candidates": [{"values": [20]}],
                    }
                },
            },
        ],
        "coverage": {"unresolved_fields_without_domain": 1},
    }


def test_unresolved_targets_only_returns_fields_without_domain() -> None:
    assert unresolved_targets(_payload()) == [
        {"command": "play_bonus_game", "fields": ["index"]}
    ]


def test_capture_requires_command_and_target_field() -> None:
    targets = unresolved_targets(_payload())
    assert capture_matches_target(
        {"command": "play_bonus_game", "options": {"mode": "pick", "index": 2}},
        targets,
    )
    assert not capture_matches_target(
        {"command": "play_bonus_game", "options": {"mode": "pick"}},
        targets,
    )
    assert not capture_matches_target(
        {"command": "spin", "options": {"index": 2}},
        targets,
    )


def test_partial_capture_is_preserved_but_not_promoted() -> None:
    merged, resolved = merge_assisted_captures(
        _payload(),
        [{"command": "play_bonus_game", "options": {"mode": "pick", "index": 1}}],
        completed=False,
        session_id="s1",
    )
    assert resolved == 0
    assert unresolved_targets(merged) == [
        {"command": "play_bonus_game", "fields": ["index"]}
    ]
    command = merged["commands"][0]
    assert command["assisted_variants"][0]["options"]["index"] == 1


def test_completed_capture_promotes_reviewed_domain_and_preserves_tuples() -> None:
    merged, resolved = merge_assisted_captures(
        _payload(),
        [
            {"command": "play_bonus_game", "options": {"mode": "pick", "index": 0}},
            {"command": "play_bonus_game", "options": {"mode": "pick", "index": 1}},
            {"command": "play_bonus_game", "options": {"mode": "pick", "index": 2}},
        ],
        completed=True,
        session_id="s2",
    )
    assert resolved == 1
    assert unresolved_targets(merged) == []
    command = merged["commands"][0]
    assert [row["options"]["index"] for row in command["assisted_variants"]] == [0, 1, 2]
    candidate = command["fields"]["index"]["domain_candidates"][0]
    assert candidate["values"] == [0, 1, 2]
    assert candidate["authority"] == "assisted-user-reviewed"
    assert candidate["complete"] is True
    assert merged["coverage"]["unresolved_fields_without_domain"] == 0
    assert merged["coverage"]["assisted_user_reviewed_fields"] == 1


def test_static_refresh_can_restore_prior_assisted_session() -> None:
    previous, _ = merge_assisted_captures(
        _payload(),
        [
            {"command": "play_bonus_game", "options": {"mode": "pick", "index": 0}},
            {"command": "play_bonus_game", "options": {"mode": "pick", "index": 1}},
        ],
        completed=True,
        session_id="reviewed",
    )
    fresh = _payload()
    assert unresolved_targets(fresh)
    restored = _restore_assisted_history(fresh, previous)
    assert unresolved_targets(restored) == []
    candidate = restored["commands"][0]["fields"]["index"]["domain_candidates"][0]
    assert candidate["values"] == [0, 1]
