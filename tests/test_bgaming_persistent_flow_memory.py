from __future__ import annotations

import json
from pathlib import Path

from tester_spin.providers.bgaming import flow_choices
from tester_spin.providers.bgaming import persistent_flow_memory as memory
from tester_spin.providers.bgaming import server_guided


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _flow(*, state: str, feature: str = "bonus_buy", level: str = "1") -> dict:
    return {
        "state": state,
        "command": "spin",
        "available_actions": ["init", "spin"],
        "purchased_feature": {"name": feature, "level": level},
    }


def test_purchase_scope_is_runtime_driven() -> None:
    assert memory.purchase_scope(_flow(state="super_spin")) == "PURCHASE_BONUS_BUY_LEVEL_1"
    assert memory.purchase_scope({"state": "closed"}) == ""


def test_assisted_internal_spin_requires_open_purchased_feature() -> None:
    capture = {
        "command": "spin",
        "options": {"mode": "continue"},
        "from_flow": {
            **_flow(state="super_spin"),
            "purchase_scope": "PURCHASE_BONUS_BUY_LEVEL_1",
        },
    }
    evidence = memory._evidence_from_assisted_capture(
        capture,
        bundle_sha256="abc123",
    )
    assert evidence is not None
    assert evidence["client"]["bundle_sha256"] == "abc123"
    assert evidence["flow"]["state"] == "super_spin"
    assert evidence["actions"][0]["action"] == "spin"
    assert evidence["actions"][0]["option_variants"][0]["options"] == {"mode": "continue"}

    base_capture = {
        "command": "spin",
        "options": {"bet": 20},
        "from_flow": {"state": "closed", "available_actions": ["spin"]},
    }
    assert memory._evidence_from_assisted_capture(
        base_capture,
        bundle_sha256="abc123",
    ) is None


def test_persisted_evidence_is_filtered_by_current_bundle_fingerprint(tmp_path: Path) -> None:
    good = {
        "flow": {"state": "select_bonus", "available_actions": ["pick_chest"]},
        "client": {"bundle_sha256": "current"},
        "actions": [],
    }
    stale = {
        "flow": {"state": "select_bonus", "available_actions": ["pick_chest"]},
        "client": {"bundle_sha256": "old"},
        "actions": [],
    }
    _write_json(
        tmp_path / "tests" / "a" / "server-guided-discovery.json",
        {"states": [good, stale]},
    )
    _write_json(
        tmp_path / "analysis" / "assisted-resolution" / "s1" / "session.json",
        {
            "completed_by_user": True,
            "client_bundle_sha256": "current",
            "captures": [
                {
                    "command": "pick_chest",
                    "options": {"index": 1},
                    "from_flow": {
                        "state": "select_bonus",
                        "available_actions": ["pick_chest"],
                        "purchased_feature": {"name": "bonus_buy"},
                        "purchase_scope": "PURCHASE_BONUS_BUY",
                    },
                }
            ],
        },
    )
    _write_json(
        tmp_path / "analysis" / "assisted-resolution" / "s2" / "session.json",
        {
            "completed_by_user": True,
            "client_bundle_sha256": "old",
            "captures": [
                {
                    "command": "pick_chest",
                    "options": {"index": 99},
                    "from_flow": {
                        "state": "select_bonus",
                        "available_actions": ["pick_chest"],
                        "purchased_feature": {"name": "bonus_buy"},
                        "purchase_scope": "PURCHASE_BONUS_BUY",
                    },
                }
            ],
        },
    )

    rows = memory._persisted_evidence(tmp_path, bundle_sha256="current")
    assert rows
    assert all(row.get("client", {}).get("bundle_sha256") == "current" for row in rows)
    assisted = [
        row for row in rows
        if row.get("client", {}).get("source") == "assisted-runtime-observation"
    ]
    assert len(assisted) == 1
    assert assisted[0]["actions"][0]["option_variants"][0]["options"] == {"index": 1}


def test_internal_spin_becomes_choice_only_inside_matching_purchase_scope() -> None:
    server_guided.begin_dynamic_contract_run()
    try:
        evidence = {
            "flow": {
                "state": "super_spin",
                "available_actions": ["spin"],
                "purchase_scope": "PURCHASE_BONUS_BUY",
                "purchased_feature": {"name": "bonus_buy"},
            },
            "client": {"source": "fixture", "bundle_sha256": "fixture"},
            "actions": [
                {
                    "action": "spin",
                    "replay_eligible": True,
                    "option_fields": ["mode"],
                    "option_variants": [
                        {
                            "label": 'mode="continue"',
                            "options": {"mode": "continue"},
                        }
                    ],
                }
            ],
        }
        memory._remember_with_context(evidence)

        matching = {"flow": _flow(state="super_spin", feature="bonus_buy", level="")}
        prompts = flow_choices._candidate_prompts(matching)
        assert any(prompt.command == "spin" for prompt in prompts)

        other = {"flow": _flow(state="super_spin", feature="other_buy", level="")}
        prompts = flow_choices._candidate_prompts(other)
        assert not any(prompt.command == "spin" for prompt in prompts)
    finally:
        server_guided.end_dynamic_contract_run()
