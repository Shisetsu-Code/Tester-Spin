from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from tester_spin.models import Game
from tester_spin.providers.bgaming.adapter import BGamingProvider
from tester_spin.providers.bgaming.profile import (
    API_V2,
    BGamingProfile,
    discover_profile,
    load_profile,
    save_profile,
)
from tester_spin.providers.bgaming.runtime import BGamingRuntime


class BGamingProfileCacheCurrentContractTests(unittest.TestCase):
    def setUp(self) -> None:
        session = requests.Session()
        self.addCleanup(session.close)
        self.runtime = BGamingRuntime(
            session=session,
            launch_url="https://demo.bgaming-network.com/games/Test/FUN",
            api_url="https://demo.bgaming-network.com/api/Test/1/session",
            identifier="Test",
            csrf_header_name="X-CSRF",
            csrf_header_value="test",
            options={},
            round_series_id=1,
        )
        self.init = {
            "api_version": "2",
            "options": {"default_bet": 10, "layout": {"reels": 5, "rows": 3}},
        }

    @staticmethod
    def persisted() -> BGamingProfile:
        return BGamingProfile(
            capability_version=3,
            family=API_V2,
            confidence=1.0,
            spin_options={"mode": "4"},
            command_options={"freespin": {"mode": "4", "rows": 7}},
            request_extra_data={"old_contract_flag": True},
            spin_option_choices={"mode": ["0", "4"]},
            effective_bet_selector="mode",
            effective_bet_multipliers={"0": 1.0, "4": 4.0},
            purchase_features=["bonus_buy"],
            rows_required=True,
            allowed_continuations=["freespin"],
            source="https://cdn.bgaming-network.com/game/bundle.js",
            bundle_sha256="old",
            validated=True,
        )

    @staticmethod
    def empty_wire() -> dict:
        return {
            "spin_options": {},
            "command_options": {},
            "request_extra_data": {},
            "required_option_fields": [],
            "spin_option_choices": {},
            "effective_bet_selector": "",
            "effective_bet_multipliers": {},
            "dynamic_purchased_feature": False,
            "purchase_feature_level_supported": False,
            "purchase_features": [],
            "source": "https://cdn.bgaming-network.com/game/bundle.js",
            "bundle_sha256": "new",
            "diagnostics": [],
        }

    def test_changed_bundle_does_not_fall_back_to_cached_wire_fields(self) -> None:
        self.runtime.request_extra_data = {"api_version": 2}
        profile = discover_profile(
            self.runtime,
            self.init,
            timeout_s=1,
            persisted=self.persisted(),
            wire_profile=self.empty_wire(),
        )

        self.assertEqual(profile.spin_options, {})
        self.assertEqual(profile.command_options, {})
        self.assertEqual(profile.spin_option_choices, {})
        self.assertEqual(profile.effective_bet_selector, "")
        self.assertEqual(profile.effective_bet_multipliers, {})
        self.assertFalse(profile.rows_required)
        self.assertEqual(profile.purchase_features, [])
        self.assertEqual(profile.request_extra_data, {"api_version": 2})
        self.assertFalse(profile.validated)
        self.assertEqual(profile.bundle_sha256, "new")

    def test_changed_bundle_selects_required_option_from_current_domain(self) -> None:
        persisted = self.persisted()
        persisted.command_options = {}
        persisted.request_extra_data = {}
        persisted.purchase_features = []
        persisted.rows_required = False
        wire = self.empty_wire()
        wire.update(
            required_option_fields=["mode", "rows"],
            spin_option_choices={"mode": ["1", "2"]},
            effective_bet_selector="mode",
            effective_bet_multipliers={"1": 1.0, "2": 2.0},
        )
        profile = discover_profile(
            self.runtime,
            self.init,
            timeout_s=1,
            persisted=persisted,
            wire_profile=wire,
        )

        self.assertEqual(profile.spin_options, {"mode": "1", "rows": 3})
        self.assertEqual(profile.spin_option_choices, {"mode": ["1", "2"]})
        self.assertEqual(profile.effective_bet_selector, "mode")
        self.assertEqual(profile.effective_bet_multipliers, {"1": 1.0, "2": 2.0})
        self.assertEqual(profile.command_options, {})
        self.assertFalse(profile.rows_required)
        self.assertFalse(profile.validated)

    def test_same_bundle_with_rejected_selector_does_not_reuse_cached_domain(self) -> None:
        wire = self.empty_wire()
        wire["bundle_sha256"] = "old"
        profile = discover_profile(
            self.runtime, self.init, timeout_s=1,
            persisted=self.persisted(), wire_profile=wire,
        )

        self.assertEqual(profile.spin_options, {})
        self.assertEqual(profile.effective_bet_selector, "")
        self.assertFalse(profile.validated)

    def test_unavailable_current_source_leaves_cached_capabilities_unverified(self) -> None:
        persisted = self.persisted()
        profile = discover_profile(
            self.runtime, self.init, timeout_s=1,
            persisted=persisted, wire_profile={},
        )

        self.assertEqual(profile.spin_options, {})
        self.assertEqual(profile.effective_bet_selector, "")
        self.assertEqual(profile.request_extra_data, {})
        self.assertFalse(profile.validated)
        self.assertEqual(persisted.spin_options, {"mode": "4"})

    def test_cached_profile_without_supplied_wire_requires_current_discovery(self) -> None:
        with patch("tester_spin.providers.bgaming.profile.discover_api_v2_wire_profile", return_value={}):
            profile = discover_profile(
                self.runtime, self.init, timeout_s=1, persisted=self.persisted(),
            )

        self.assertEqual(profile.spin_options, {})
        self.assertFalse(profile.validated)

    def test_different_source_does_not_inherit_validation_from_equal_hash(self) -> None:
        persisted = self.persisted()
        wire = self.empty_wire()
        wire.update(
            source="https://cdn.bgaming-network.com/other/bundle.js",
            bundle_sha256="old",
            spin_options={"mode": "0"},
            spin_option_choices={"mode": ["0", "4"]},
            effective_bet_selector="mode",
            effective_bet_multipliers={"0": 1.0, "4": 4.0},
        )
        profile = discover_profile(
            self.runtime, self.init, timeout_s=1,
            persisted=persisted, wire_profile=wire,
        )

        self.assertEqual(profile.spin_options, {"mode": "0"})
        self.assertEqual(profile.source, "https://cdn.bgaming-network.com/other/bundle.js")
        self.assertFalse(profile.validated)

    def test_other_refresh_reasons_do_not_keep_cached_options(self) -> None:
        for reason in ("third-party-source", "purchase-contract-missing", "capability-changed"):
            with self.subTest(reason=reason):
                persisted = self.persisted()
                wire = self.empty_wire()
                wire["bundle_sha256"] = "old"
                init = dict(self.init)
                if reason == "third-party-source":
                    persisted.source = "https://analytics.example/tracker.js"
                elif reason == "purchase-contract-missing":
                    persisted.purchase_features = []
                    init["options"] = {
                        **self.init["options"],
                        "feature_options": {
                            "feature_multipliers": {"base_bet": 10, "bonus_buy": 1000},
                            "disabled_features": [],
                        },
                    }
                else:
                    persisted.dynamic_purchased_feature = True

                profile = discover_profile(
                    self.runtime,
                    init,
                    timeout_s=1,
                    persisted=persisted,
                    wire_profile=wire,
                )

                self.assertEqual(profile.spin_options, {})
                self.assertEqual(profile.command_options, {})
                self.assertEqual(profile.effective_bet_selector, "")
                self.assertEqual(profile.request_extra_data, {})
                self.assertFalse(profile.rows_required)
                self.assertFalse(profile.validated)

    def test_matching_validated_cache_keeps_its_proven_contract(self) -> None:
        wire = self.empty_wire()
        wire.update(
            bundle_sha256="old",
            spin_options={"mode": "0"},
            request_extra_data={"old_contract_flag": True},
            spin_option_choices={"mode": ["0", "4"]},
            effective_bet_selector="mode",
            effective_bet_multipliers={"0": 1.0, "4": 4.0},
            purchase_features=["bonus_buy"],
        )
        profile = discover_profile(
            self.runtime,
            self.init,
            timeout_s=1,
            persisted=self.persisted(),
            wire_profile=wire,
        )

        self.assertEqual(profile.spin_options, {"mode": "4"})
        self.assertEqual(profile.command_options, {"freespin": {"mode": "4", "rows": 7}})
        self.assertEqual(profile.request_extra_data, {"old_contract_flag": True})
        self.assertEqual(profile.spin_option_choices, {"mode": ["0", "4"]})
        self.assertEqual(profile.effective_bet_selector, "mode")
        self.assertEqual(profile.effective_bet_multipliers, {"0": 1.0, "4": 4.0})
        self.assertTrue(profile.rows_required)
        self.assertEqual(profile.purchase_features, ["bonus_buy"])
        self.assertTrue(profile.validated)
        self.assertEqual(profile.bundle_sha256, "old")

    def run_api_session(self, wire: dict, *, cached_dynamic_feature: bool = False,
                        cached_selector: bool = False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        provider = BGamingProvider(Path(temporary.name))
        self.addCleanup(provider.http.close)
        game = Game(
            provider="bgaming", slug="test", name="Test", url=self.runtime.launch_url,
        )
        game_json = provider.game_dir(game) / "game.json"
        save_profile(game_json, BGamingProfile(
            family=API_V2,
            source="https://cdn.bgaming-network.com/game/bundle.js",
            bundle_sha256="old",
            validated=True,
            dynamic_purchased_feature=cached_dynamic_feature,
            spin_options={"mode": "4"} if cached_selector else {},
            spin_option_choices={"mode": ["0", "4"]} if cached_selector else {},
            effective_bet_selector="mode" if cached_selector else "",
            effective_bet_multipliers={"0": 1.0, "4": 1.0} if cached_selector else {},
            request_extra_data={"cached_field": "old-contract", "api_version": 1},
        ))
        self.runtime.request_extra_data = {"bootstrap_field": "current"}
        sent = []

        def respond(url, **kwargs):
            self.assertEqual(url, self.runtime.api_url)
            payload = kwargs["json"]
            sent.append(payload)
            if payload["command"] == "init":
                data = {
                    **self.init,
                    "balance": {"wallet": 1000, "game": 0},
                    "flow": {"command": "init", "state": "ready", "available_actions": ["spin"]},
                }
            else:
                self.assertEqual(payload["command"], "spin")
                data = {
                    "api_version": "2",
                    "outcome": {"bet": 10, "win": 0, "screen": [["1", "2", "3"]] * 5},
                    "balance": {"wallet": 990, "game": 0},
                    "flow": {"command": "spin", "state": "closed", "available_actions": ["spin"],
                             "round_id": 1, "last_action_id": "1_1"},
                }
            response = requests.Response()
            response.status_code = 200
            response.url = url
            response._content = json.dumps(data).encode()
            return response

        with (
            patch.object(provider, "_new_session", return_value=self.runtime.session),
            patch("tester_spin.providers.bgaming.execution.bootstrap_game", return_value=self.runtime),
            patch("tester_spin.providers.bgaming.execution.discover_api_v2_wire_profile", return_value=wire),
            patch.object(self.runtime.session, "post", side_effect=respond),
        ):
            result = provider.test_game(
                game, spins=1, timeout_s=1,
                stop_event=threading.Event(), progress=lambda _message: None,
            )

        self.assertTrue(sent, result.error)
        current = json.loads((Path(result.run_dir) / "profile.json").read_text())
        return sent, load_profile(game_json), current, result

    def test_execution_changed_bundle_excludes_cached_extra_data(self) -> None:
        wire = self.empty_wire()
        wire["request_extra_data"] = {"api_version": 2}
        sent, saved, current, result = self.run_api_session(wire)

        self.assertEqual(sent[0]["extra_data"], {
            "round_series_id": 1, "bootstrap_field": "current", "api_version": 2,
        })
        self.assertEqual([payload["command"] for payload in sent], ["init"])
        self.assertNotEqual(result.status, "OK")
        self.assertIn("request_extra_data.cached_field", current["unverified_cached_capabilities"])
        self.assertEqual(current["request_extra_data"], {"bootstrap_field": "current", "api_version": 2})
        self.assertFalse(saved.validated)
        self.assertEqual(saved.request_extra_data, {"cached_field": "old-contract", "api_version": 1})

    def test_execution_changed_capability_excludes_cached_extra_data(self) -> None:
        wire = self.empty_wire()
        wire["bundle_sha256"] = "old"
        sent, saved, current, result = self.run_api_session(wire, cached_dynamic_feature=True)

        self.assertEqual(sent[0]["extra_data"], {"round_series_id": 1, "bootstrap_field": "current"})
        self.assertEqual([payload["command"] for payload in sent], ["init"])
        self.assertNotEqual(result.status, "OK")
        self.assertFalse(saved.validated)
        self.assertIn("dynamic_purchased_feature", current["unverified_cached_capabilities"])

    def test_execution_matching_cache_preserves_cached_extra_data(self) -> None:
        wire = self.empty_wire()
        wire["bundle_sha256"] = "old"
        wire["request_extra_data"] = {"cached_field": "current-contract", "api_version": 2}
        sent, saved, current, result = self.run_api_session(wire)

        self.assertEqual(sent[0]["extra_data"], {
            "round_series_id": 1, "bootstrap_field": "current", "cached_field": "current-contract", "api_version": 2,
        })
        self.assertEqual(saved.request_extra_data, {
            "bootstrap_field": "current", "cached_field": "current-contract", "api_version": 2,
        })
        self.assertEqual(result.status, "OK", result.error)
        self.assertEqual([payload["command"] for payload in sent], ["init", "spin"])
        self.assertEqual(current["unverified_cached_capabilities"], [])

    def test_execution_unavailable_contract_keeps_pending_cache_without_spinning(self) -> None:
        sent, saved, current, result = self.run_api_session({}, cached_selector=True)

        self.assertEqual(sent[0]["extra_data"], {"round_series_id": 1, "bootstrap_field": "current"})
        self.assertEqual([payload["command"] for payload in sent], ["init"])
        self.assertNotEqual(result.status, "OK")
        self.assertFalse(current["validated"])
        self.assertEqual(current["spin_options"], {})
        self.assertIn("current-client-source", current["unverified_cached_capabilities"])
        self.assertEqual(saved.spin_options, {"mode": "4"})
        self.assertFalse(saved.validated)

    def test_execution_rejected_same_hash_selector_blocks_spin(self) -> None:
        wire = self.empty_wire()
        wire["bundle_sha256"] = "old"
        wire["request_extra_data"] = {"cached_field": "current-contract", "api_version": 2}
        sent, saved, current, result = self.run_api_session(wire, cached_selector=True)

        self.assertEqual([payload["command"] for payload in sent], ["init"])
        self.assertNotEqual(result.status, "OK")
        self.assertEqual(current["spin_options"], {})
        self.assertFalse(current["validated"])
        self.assertIn("spin_options.mode", current["unverified_cached_capabilities"])
        self.assertEqual(saved.spin_options, {"mode": "4"})
        self.assertFalse(saved.validated)


if __name__ == "__main__":
    unittest.main()
