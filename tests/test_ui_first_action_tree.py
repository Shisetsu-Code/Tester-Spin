from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tester_spin.providers.bgaming.ui_first import _cluster_pointer_cells, is_provider_chrome_candidate
from tester_spin.ui_action_tree import UIActionTree, persist_ui_action_tree


class UIActionTreeTests(unittest.TestCase):
    def test_provider_chrome_filter_does_not_hide_gameplay(self):
        self.assertTrue(is_provider_chrome_candidate({"kind": "dom", "text": "Sound settings"}))
        self.assertTrue(is_provider_chrome_candidate({"kind": "dom", "aria": "Paytable"}))
        self.assertFalse(is_provider_chrome_candidate({"kind": "dom", "text": "Spin"}))
        self.assertFalse(is_provider_chrome_candidate({"kind": "dom", "text": "5 Free Spins"}))
        self.assertFalse(is_provider_chrome_candidate({"kind": "canvas", "label": "unknown"}))

    def test_pointer_cells_are_clustered_into_independent_controls(self):
        groups = _cluster_pointer_cells({(0, 0), (1, 0), (5, 3), (5, 4)}, 8, 6)
        self.assertEqual(sorted(len(group) for group in groups), [2, 2])

    def test_wire_observed_choice_resolves_advertised_action(self):
        tree = UIActionTree("bgaming", "fixture", "bgaming-live-ui")
        source = tree.state("closed", ["init", "spin"])
        candidate = tree.candidate(source, {
            "kind": "dom", "frame": 0, "signature": "spin", "label": "Spin", "role": "button"
        })
        target = tree.state("closed", ["init", "spin"])
        tree.edge(source, candidate, request={"command": "spin", "options": {"bet": 10}},
                  response={"flow": {"state": "closed", "available_actions": ["spin"]}},
                  to_state=target, evidence="WIRE_OBSERVED")
        data = tree.finalize(frontier_exhausted=True)
        self.assertEqual(data["coverage"]["actions"], 1)
        self.assertEqual(data["coverage"]["unresolved_server_actions"], 0)
        self.assertTrue(data["coverage"]["ready_for_farming"])

    def test_discovered_select_bonus_stays_partial_until_wire_edge_exists(self):
        tree = UIActionTree("bgaming", "adventures", "bgaming-live-ui")
        state = tree.state("select_bonus", ["init", "play_bonus_game"])
        tree.candidate(state, {
            "kind": "canvas", "frame": 0, "signature": "choice-a", "label": "canvas interactive zone",
            "role": "canvas-zone", "point": [0.4, 0.5],
        })
        data = tree.finalize(frontier_exhausted=True)
        self.assertFalse(data["coverage"]["ready_for_farming"])
        self.assertEqual(data["coverage"]["unresolved_server_actions"], 1)
        self.assertTrue(data["unresolved"])

    def test_local_ui_choice_can_precede_confirming_wire_action(self):
        tree = UIActionTree("bgaming", "compound", "bgaming-live-ui")
        before = tree.state("select_bonus", ["play_bonus_game"], local_fingerprint="a")
        choice = tree.candidate(before, {
            "kind": "dom", "frame": 0, "signature": "x5", "label": "x5", "role": "button"
        })
        selected = tree.state("select_bonus", ["play_bonus_game"], local_fingerprint="b")
        tree.edge(before, choice, request=None, response=None, to_state=selected, evidence="UI_LOCAL_OBSERVED")
        confirm = tree.candidate(selected, {
            "kind": "dom", "frame": 0, "signature": "confirm", "label": "Confirm", "role": "button"
        })
        after = tree.state("freespins", ["freespin"])
        tree.edge(selected, confirm, request={"command": "play_bonus_game", "options": {"multiplier": 5}},
                  response={"flow": {"state": "freespins", "available_actions": ["freespin"]}},
                  to_state=after, evidence="WIRE_OBSERVED")
        data = tree.finalize(frontier_exhausted=True)
        self.assertEqual(data["coverage"]["local_actions"], 1)
        self.assertEqual(data["coverage"]["actions"], 1)

    def test_multiple_runs_merge_mutually_exclusive_choices(self):
        a = UIActionTree("bgaming", "fixture", "bgaming-live-ui")
        b = UIActionTree("bgaming", "fixture", "bgaming-live-ui")
        for tree, label, multiplier in ((a, "x2", 2), (b, "x5", 5)):
            state = tree.state("choose_multiplier", ["select_multiplier"])
            candidate = tree.candidate(state, {
                "kind": "dom", "frame": 0, "signature": label, "label": label, "role": "button"
            })
            after = tree.state("freespins", [])
            tree.edge(state, candidate,
                      request={"command": "select_multiplier", "options": {"multiplier": multiplier}},
                      response={"flow": {"state": "freespins"}}, to_state=after,
                      evidence="WIRE_OBSERVED")
        a.merge(b)
        self.assertEqual(len(a.data["candidates"]), 2)
        self.assertEqual(len(a.data["edges"]), 2)

    def test_persistence_sanitizes_runtime_secrets(self):
        tree = UIActionTree("bgaming", "fixture", "bgaming-live-ui")
        state = tree.state("closed", ["spin"])
        candidate = tree.candidate(state, {
            "kind": "dom", "frame": 0, "signature": "spin", "label": "Spin", "role": "button"
        })
        tree.edge(state, candidate,
                  request={"command": "spin", "session_id": "private-session", "round_series_id": 12345},
                  response={"flow": {"state": "closed"}, "token": "private-token"},
                  to_state=state, evidence="WIRE_OBSERVED")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "action-tree.json"
            data = persist_ui_action_tree(path, tree, run_key="run-a", frontier_exhausted=True)
            raw = json.dumps(data)
            self.assertNotIn("private-session", raw)
            self.assertNotIn("private-token", raw)
            self.assertNotIn("12345", raw)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
