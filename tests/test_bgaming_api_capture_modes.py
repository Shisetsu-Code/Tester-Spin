import json
import unittest
import tempfile
from pathlib import Path
from tester_spin.providers.bgaming.api_capture import load_api_capture, expand_api_modes

def entry(command, options, balance, *, bet=120, win=0, mode="2", status=200, game="Example"):
    return {"request": {"method": "POST", "url": f"https://demo.bgaming-network.com/api/{game}/1/session", "postData": {"text": json.dumps({"command": command, "options": options})}}, "response": {"status": status, "content": {"text": json.dumps({"api_version": "2", "flow": {"command": command, "round_id": 1}, "balance": balance, "outcome": {"bet": bet, "win": win, "storage": {"mode": mode}}})}}}

class CaptureTests(unittest.TestCase):
 def test_captured_modes_and_purchase_cost_use_prior_total_balance(self):
    with tempfile.TemporaryDirectory() as directory:
      self.check_capture(Path(directory))

 def test_error_and_unreadable_pairs_do_not_supply_modes_or_bridge_costs(self):
    for broken_kind in ("singular_error", "unreadable"):
      with self.subTest(broken_kind=broken_kind), tempfile.TemporaryDirectory() as directory:
        first = entry("init", {}, {"wallet": 100000, "game": 0})
        broken = entry("spin", {"bet": 40, "mode": "9"}, {"wallet": 90000, "game": 0})
        if broken_kind == "singular_error":
          body = json.loads(broken["response"]["content"]["text"])
          body["error"] = {"code": "rejected"}
          broken["response"]["content"]["text"] = json.dumps(body)
        else:
          broken["response"]["content"]["text"] = "not JSON"
        buy = entry("spin", {"bet": 40, "mode": "2", "purchased_feature": "bonus_buy"}, {"wallet": 82800, "game": 0})
        path = Path(directory)/"capture.har"
        path.write_text(json.dumps({"log": {"entries": [first, broken, buy]}}), encoding="utf-8")
        capture = load_api_capture(path, "Example")
        self.assertNotIn("9", capture["mode_multipliers"])
        self.assertEqual(capture["purchase_costs"], {})

 def check_capture(self, tmp_path):
    entries = [entry("init", {}, {"wallet": 100000, "game": 1000})]
    entries += [entry("spin", {"bet": 40, "mode": "2", "purchased_feature": "bonus_buy"}, {"wallet": 93800, "game": 7800}, win=7800)]
    entries += [entry("respin", {"bet": 40}, {"wallet": 93800, "game": 8000}, win=8000)]
    entries += [entry("spin", {"bet": 40, "mode": str(i)}, {"wallet": 90000, "game": 0}, bet=40*(i+1), mode=str(i)) for i in range(5)]
    entries += [entry("spin", {"bet": 40, "mode": "99"}, {"wallet": 1}, status=500), entry("spin", {"bet": 40, "mode": "88"}, {"wallet": 1}, game="Other")]
    path = tmp_path / "capture.har"
    path.write_text(json.dumps({"log": {"entries": entries}}))
    capture = load_api_capture(path, "Example")
    assert capture["mode_multipliers"] == {str(i): float(i+1) for i in range(5)}
    assert capture["purchase_costs"]["bonus_buy"]["2"] == 180.0
    assert capture["command_options"] == {"respin": {"bet": "$base_bet"}}
    specs = expand_api_modes([{"id": "SPIN", "kind": "SPIN", "purchase": None}, {"id": "PURCHASE_BONUS_BUY", "kind": "PURCHASE", "purchase": {"name": "bonus_buy", "cost_multiplier": 60}}], capture)
    assert len(specs) == 10
    buys = [m for m in specs if m["kind"] == "PURCHASE"]
    assert [m["options"]["mode"] for m in buys] == [str(i) for i in range(5)]
    assert buys[2]["captured_cost_per_base_bet"] == 180.0
    assert buys[0]["captured_cost_per_base_bet"] is None
    assert buys[0]["discovery_state"] == "CAPTURE_SERIALIZER_CANDIDATE"
    assert buys[2]["discovery_state"] == "CAPTURE_OBSERVED"
    assert buys[0]["purchase"] is not buys[1]["purchase"]


class ExecutionCaptureTests(unittest.TestCase):
 def test_capture_modes_reach_wire_and_base_audits_keep_origin(self):
    self.run_capture()

 def test_purchase_without_cost_evidence_remains_pending(self):
    self.run_capture(missing_purchase_balance=True)

 def test_purchase_with_zero_inferred_cost_remains_pending(self):
    self.run_capture(zero_purchase_cost=True)

 def run_capture(self, missing_purchase_balance=False, zero_purchase_cost=False):
    import threading
    from unittest.mock import patch
    import requests
    from tester_spin.models import Game
    from tester_spin.providers.bgaming.adapter import BGamingProvider
    from tester_spin.providers.bgaming.runtime import BGamingRuntime
    from tester_spin.return_to_base import audit_scope
    with tempfile.TemporaryDirectory() as directory:
      provider = BGamingProvider(Path(directory))
      game = Game(provider="bgaming", slug="example", name="Example", url="https://demo.bgaming-network.com/games/Example/FUN", symbol="Example")
      analysis = provider.game_dir(game) / "analysis"
      analysis.mkdir(parents=True)
      entries = [entry("spin", {"bet": 40, "mode": str(i)}, {"wallet": 90000, "game": 0}, bet=40*(i+1), mode=str(i)) for i in range(5)]
      entries = [entry("init", {}, {"wallet": 100000, "game": 1000}), entry("spin", {"bet": 40, "mode": "2", "purchased_feature": "bonus_buy"}, {"wallet": 93800, "game": 7800}, win=7800)] + entries
      entries += [entry("respin", {"bet": 40}, {"wallet": 90000, "game": 0})]
      (analysis / "capture.har").write_text(json.dumps({"log": {"entries": entries}}))
      session = requests.Session()
      runtime = BGamingRuntime(session=session, launch_url=game.url, api_url="https://demo.bgaming-network.com/api/Example/1/session", identifier="Example", csrf_header_name="X-CSRF", csrf_header_value="secret", options={}, round_series_id=1)
      calls = []
      wallet = 100000
      action = 0
      mode = "0"
      round_id = 0
      def post(runtime, command, **kwargs):
        nonlocal wallet, action, mode, round_id
        options = kwargs.get("options") or {}
        calls.append((command, dict(options)))
        if command == "init":
          wallet = 100000
          return type("Response", (), {"status_code": 200})(), {"command": command}, {"api_version": "2", "options": {"default_bet": 40, "available_bets": [40], "feature_options": {"feature_multipliers": {"bonus_buy": 60, "base_bet": 1}}}, "balance": {"wallet": wallet, "game": 0}, "flow": {"state": "ready", "command": "init", "available_actions": ["spin"]}}
        if command == "spin":
          round_id += 1
          mode = options.get("mode", "0")
          if not (zero_purchase_cost and options.get("purchased_feature")):
            wallet -= 40*(int(mode)+1)*(60 if options.get("purchased_feature") else 1)
        action += 1
        # First base probe enters a respin; audits must serialize bet as well.
        respin = command == "spin" and action % 4 == 2
        data = {"api_version": "2", "outcome": {"bet": 40*(int(mode)+1), "win": 0, "storage": {"seed": action, "mode": mode}}, "balance": {"wallet": wallet, "game": 0}, "flow": {"command": command, "round_id": round_id, "last_action_id": str(action), "state": "respin" if respin else "closed", "available_actions": ["respin"] if respin else ["spin"]}}
        if options.get("purchased_feature"):
          data["flow"]["purchased_feature"] = {"name": options["purchased_feature"]}
          if missing_purchase_balance:
            data.pop("balance")
        return type("Response", (), {"status_code": 200})(), {"command": command, "options": options}, data
      with patch.object(provider, "_new_session", return_value=session), patch("tester_spin.providers.bgaming.execution.bootstrap_game", return_value=runtime), patch("tester_spin.providers.bgaming.execution.discover_api_v2_wire_profile", return_value={}), patch("tester_spin.providers.bgaming.execution.post_command", side_effect=post), audit_scope():
        result = provider.test_game(game, spins=1, timeout_s=5, stop_event=threading.Event(), progress=lambda _: None)
      self.assertEqual({o.get("mode") for c,o in calls if c == "spin"}, {str(i) for i in range(5)})
      if missing_purchase_balance or zero_purchase_cost:
        self.assertNotEqual(result.status, "OK")
        self.assertFalse(next(a for a in result.attempts if a.mode_kind == "PURCHASE").ok)
        return
      with patch("tester_spin.providers.bgaming.adapter.queue_result_publish"):
        result = provider.finalize_test_result(result, progress=lambda _: None)
      from tester_spin.run_diagnostics import write_run_diagnostics
      diagnostics = write_run_diagnostics(result)
      self.assertEqual(diagnostics["unknown_actions"], [])
      self.assertTrue(all(m["validated"] for m in diagnostics["modes"] if m["kind"] in {"SPIN", "PURCHASE"}))
      self.assertEqual(len(result.attempts), 10)
      self.assertFalse({"SPIN", "PURCHASE_BONUS_BUY"} & {m["id"] for m in result.discovered_modes})
      self.assertEqual(result.status, "OK", result.error)
      self.assertTrue(all(m.get("observed") for m in result.discovered_modes if m["kind"] in {"SPIN", "PURCHASE"}))
      self.assertTrue(all(m.get("validated") for m in result.discovered_modes if m["kind"] in {"SPIN", "PURCHASE"}))
      self.assertTrue(all(o == {"bet": 40} for c,o in calls if c == "respin"))
      for attempt in result.attempts:
        self.assertTrue(attempt.ok, attempt.warning)
        proof = json.loads((Path(attempt.artifact_dir)/"return-to-base.json").read_text())
        self.assertEqual(proof["status"], "CONFIRMED")
        self.assertTrue(all(probe["captures"][0]["request"]["options"]["mode"] == attempt.mode_id.rsplit("_", 1)[1] for probe in proof["probes"]))
