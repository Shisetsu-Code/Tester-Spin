from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tester_spin.models import GameTestResult, SpinAttempt
from tester_spin.providers.sampling_plan import build_sampling_plan, write_sampling_plan


class SamplingPlanTests(unittest.TestCase):
    def test_ready_path_is_separate_from_unresolved_branch(self) -> None:
        result = GameTestResult(
            provider="synthetic",
            slug="slot",
            game_name="Slot",
            game_url="https://example.invalid",
            requested_spins=2,
            successful_spins=1,
            failed_spins=1,
            status="PARCIAL",
            discovered_modes=[
                {
                    "id": "SPIN",
                    "kind": "SPIN",
                    "executable": True,
                },
                {
                    "id": "CHOICE",
                    "kind": "CHOICE_BRANCH",
                    "executable": True,
                    "coverage_required": True,
                    "branch_signature": "choice:root",
                    "required_options": ["A", "B"],
                    "covered_options": ["A"],
                },
            ],
            attempts=[
                SpinAttempt(
                    number=1,
                    ok=True,
                    mode_id="SPIN",
                    mode_kind="SPIN",
                    terminal=True,
                    wire_steps=1,
                    na="closed",
                ),
            ],
        )
        plan = build_sampling_plan(result)
        by_id = {item["mode_id"]: item for item in plan["paths"]}
        self.assertTrue(by_id["SPIN"]["sampling_ready"])
        self.assertFalse(by_id["CHOICE"]["sampling_ready"])
        self.assertEqual(by_id["CHOICE"]["missing_options"], ["B"])
        self.assertIsNone(plan["semantics"]["repetitions_per_path"])
        self.assertIn("never RNG probabilities", plan["semantics"]["outcome_policy"])

    def test_suffixed_branch_attempts_are_attributed_to_base_mode(self) -> None:
        result = GameTestResult(
            provider="synthetic",
            slug="slot",
            game_name="Slot",
            game_url="https://example.invalid",
            requested_spins=1,
            successful_spins=1,
            failed_spins=0,
            status="OK",
            discovered_modes=[
                {
                    "id": "PURCHASE_BONUS",
                    "kind": "PURCHASE",
                    "executable": True,
                }
            ],
            attempts=[
                SpinAttempt(
                    number=1,
                    ok=True,
                    mode_id="PURCHASE_BONUS__FLOW_PICK_A",
                    mode_kind="PURCHASE_CHOICE_VARIANT",
                    terminal=True,
                    wire_steps=4,
                )
            ],
        )
        path = build_sampling_plan(result)["paths"][0]
        self.assertEqual(path["observed_attempts"], 1)
        self.assertEqual(path["terminal_successes"], 1)
        self.assertEqual(path["wire_steps_observed"], 4)
        self.assertTrue(path["sampling_ready"])

    def test_writer_is_best_effort_artifact_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = GameTestResult(
                provider="synthetic",
                slug="slot",
                game_name="Slot",
                game_url="https://example.invalid",
                requested_spins=0,
                successful_spins=0,
                failed_spins=0,
                status="PARCIAL",
                run_dir=temp,
            )
            path = write_sampling_plan(result)
            self.assertEqual(path, Path(temp) / "sampling-plan.json")
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
