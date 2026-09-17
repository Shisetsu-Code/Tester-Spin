"""Offline regressions for the captured HyperHive wager and settlement shapes."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from tester_spin.models import Game
from tester_spin.providers.bgaming import hyperhive
from tester_spin.providers.bgaming.hyperhive_har import set_thread_har_path, clear_thread_har_path
from tester_spin.providers.bgaming.runtime import BGamingRuntime
from tester_spin.return_to_base import audit_scope


class CapturedAccountingTests(unittest.TestCase):
    def run_capture(self, base, purchase, settlement, debit, win):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            rows = []
            for req in [base, purchase]:
                rows.append({"request": {"method": "POST", "postData": {"text": json.dumps({
                    "id": 0, "method": "play", "params": {"token": "old", "state_lock": "old", "req": req}
                })}}, "response": {"status": 200, "content": {"text": json.dumps({"result": {"final": True}})}}})
            har = folder / "capture.har"
            har.write_text(json.dumps({"log": {"entries": rows}}), encoding="utf-8")
            set_thread_har_path(har)
            session = requests.Session()
            runtime = BGamingRuntime(session=session, launch_url="https://offline.example/game", api_url="https://offline.example/api", identifier="Captured", csrf_header_name="X-CSRF", csrf_header_value="unused", options={"play_token": "fresh"}, round_series_id=1)
            game = Game(provider="bgaming", slug="captured", name="Captured", url=runtime.launch_url, symbol="Captured")
            sent = []
            balance = 100000
            def post(url, *, json, **kwargs):
                nonlocal balance
                if json["method"] == "init":
                    result = {"config": {"default_bet": 100}, "balance": balance, "state_lock": "lock-0"}
                else:
                    req = json["params"]["req"]
                    sent.append(json)
                    index = len(sent)
                    self.assertEqual(json["params"]["token"], "fresh")
                    self.assertEqual(json["params"]["state_lock"], f"lock-{index-1}")
                    if index == 1:
                        self.assertEqual(req, base)
                        balance -= int(base["bet"])
                        result = {"balance": balance, "final": True, "resp": {}}
                    elif index == 2:
                        self.assertEqual(req, purchase)
                        balance -= debit
                        result = {"balance": balance, "final": False, "resp": {"outcome": {"cost": debit, "winnings": 0}}}
                    else:
                        self.assertEqual(req, base)
                        if index == 14:
                            balance += win
                        result = {"balance": balance, "final": index == 14, "resp": settlement if index == 14 else {}}
                    result["state_lock"] = f"lock-{index}"
                response = requests.Response()
                response.status_code = 200
                response._content = __import__("json").dumps({"result": result}).encode()
                response.url = url
                return response
            try:
                with patch.object(session, "post", side_effect=post), patch.object(session, "get", side_effect=AssertionError("Network forbidden")), patch.object(hyperhive, "_download_bundle", return_value=""), patch.object(hyperhive, "_download_engine_contract", return_value=""):
                    result = hyperhive.run_hyperhive_test(game=game, runtime=runtime, spins=1, timeout_s=1, stop_event=threading.Event(), progress=lambda _: None, run_dir=folder / "run", started_iso="2026-09-15", started_monotonic=time.monotonic())
                self.assertEqual(result.status, "OK", [(a.error, a.warning) for a in result.attempts])
                self.assertEqual(len(sent), 14)
                base_proof = json.loads((folder / "run/SPIN/attempt-001/remote-proof.json").read_text())
                self.assertEqual(base_proof["observed_debit"], int(base["bet"]))
                proof = json.loads((folder / "run/PURCHASE_BUY_BONUS/attempt-001/remote-proof.json").read_text())
                self.assertEqual(proof["observed_debit"], debit)
                self.assertEqual(proof["total_win"], win)
            finally:
                clear_thread_har_path()
                session.close()

    def test_big_bucks_actual_wager_not_init_default(self):
        self.run_capture({"bet": 40}, {"bet": 40, "purchased_feature": "buy_bonus"}, {"round": {"win": "1060"}}, 4800, 1060)

    def test_yommi_string_wager_and_accumulated_free_spin_settlement(self):
        base = {"bet": "200", "bet_type": "bet", "modelRev": 0, "minExponent": 2}
        self.run_capture(base, {**base, "purchased_feature": "buy_bonus"}, {"outcome": {"cost": 0, "winnings": 0}, "state": {"freeSpinsTotalWinnings": 13210}}, 20000, 13210)

    def test_base_outcome_winnings_are_available_without_free_spin_state(self):
        summary = hyperhive._result_summary({"result": {"final": True, "resp": {"outcome": {"cost": 600, "winnings": 350}}}})
        self.assertEqual(summary["total_win"], 350)
        self.assertEqual(summary["cost"], 600)

    def test_pending_state_free_spins_prevent_base_return_confirmation(self):
        for count, expected in [(12, False), (0, True)]:
            with self.subTest(count=count):
                summary = hyperhive._result_summary({"result": {"final": True, "resp": {"state": {"freeSpins": count}}}})
                self.assertEqual(hyperhive.is_base_return(summary), expected)

    def test_paid_base_win_is_not_hidden_by_zero_free_spin_accumulator(self):
        summary = hyperhive._result_summary({"result": {"final": True, "resp": {"state": {"freeSpins": 0, "freeSpinsTotalWinnings": 0}, "outcome": {"cost": 200, "winnings": 350}}}})
        self.assertEqual(summary["total_win"], 350)

    def test_return_probe_drains_natural_event_before_two_base_results(self):
        with tempfile.TemporaryDirectory() as temp, requests.Session() as session:
            runtime = BGamingRuntime(session=session, launch_url="https://offline.example/game", api_url="https://offline.example/api", identifier="Captured", csrf_header_name="X-CSRF", csrf_header_value="unused", options={"play_token": "fresh"}, round_series_id=1)
            game = Game(provider="bgaming", slug="captured", name="Captured", url=runtime.launch_url, symbol="Captured")
            calls = []
            results = iter([
                {"config": {"default_bet": 100}, "balance": 10000, "state_lock": "lock-0"},
                {"final": True, "balance": 9900, "state_lock": "lock-1", "resp": {"totalWin": 0}},
                {"final": False, "balance": 9800, "state_lock": "lock-2", "resp": {"nextAction": "freespin"}},
                {"final": True, "balance": 10000, "state_lock": "lock-3", "resp": {"totalWin": 200}},
                {"final": True, "balance": 9900, "state_lock": "lock-4", "resp": {"totalWin": 0}},
                {"final": True, "balance": 9800, "state_lock": "lock-5", "resp": {"totalWin": 0}},
            ])
            def rpc(runtime, method, *, params, **kwargs):
                calls.append((method, params))
                return type("Response", (), {"status_code": 200})(), {"method": method, "params": params}, {"result": next(results)}
            modes = [{"id": "SPIN", "kind": "SPIN", "request": {"action": "spin"}, "executable": True, "source": "fixture", "expected_multiplier": 1}]
            with audit_scope(), patch.object(hyperhive, "_rpc", side_effect=rpc), patch.object(hyperhive, "_download_bundle", return_value=""), patch.object(hyperhive, "_download_engine_contract", return_value=""), patch.object(hyperhive, "discover_modes_from_bundle", return_value=modes), patch.object(hyperhive, "discover_action_vocabulary", return_value={"spin", "freespin"}):
                result = hyperhive.run_hyperhive_test(game=game, runtime=runtime, spins=1, timeout_s=1, stop_event=threading.Event(), progress=lambda _: None, run_dir=Path(temp), started_iso="2026-09-15", started_monotonic=time.monotonic())
            self.assertEqual(result.status, "OK", [a.warning for a in result.attempts])
            self.assertEqual(len(calls), 6)
            self.assertEqual(calls[3][1]["req"]["action"], "freespin")
            self.assertEqual(calls[3][1]["state_lock"], "lock-2")
            proof = json.loads((Path(temp)/"SPIN/attempt-001/return-to-base.json").read_text())
            self.assertEqual(proof["status"], "CONFIRMED")
            self.assertEqual(len(proof["probes"]), 3)
            self.assertEqual(len(proof["probes"][0]["captures"]), 2)
