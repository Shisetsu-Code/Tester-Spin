from __future__ import annotations

from tester_spin.providers.bgaming.assisted_resolution import capture_matches_target


def test_assisted_wildcard_target_captures_non_init_command() -> None:
    targets = [{"command": "*", "fields": []}]
    assert capture_matches_target(
        {"command": "play_bonus_game", "options": {"index": 1}},
        targets,
    )
    assert not capture_matches_target(
        {"command": "init", "options": {}},
        targets,
    )


def test_assisted_command_target_can_capture_full_option_shape() -> None:
    targets = [{"command": "play_bonus_game", "fields": []}]
    assert capture_matches_target(
        {"command": "play_bonus_game", "options": {"mode": "pick", "index": 2}},
        targets,
    )
    assert not capture_matches_target(
        {"command": "spin", "options": {"bet": 20}},
        targets,
    )
