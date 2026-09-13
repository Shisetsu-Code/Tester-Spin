from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tester_spin.models import GameTestResult, SpinAttempt


SCHEMA = "tester-spin/path-sampling-plan/v1"


def _values(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    out: list[str] = []
    for item in value:
        text = str(item)
        if text and text not in out:
            out.append(text)
    return out


def _mode_attempts(result: GameTestResult, mode_id: str) -> list[SpinAttempt]:
    if not mode_id:
        return []
    return [
        attempt
        for attempt in result.attempts
        if str(attempt.mode_id or "") == mode_id
        or str(attempt.mode_id or "").startswith(mode_id + "__")
    ]


def _path_entry(result: GameTestResult, mode: dict[str, Any]) -> dict[str, Any]:
    mode_id = str(mode.get("id") or "")
    branch_signature = str(mode.get("branch_signature") or "")
    required = _values(mode.get("required_options"))
    covered = _values(mode.get("covered_options"))
    missing = [value for value in required if value not in covered]
    attempts = _mode_attempts(result, mode_id)
    terminal_successes = sum(1 for item in attempts if item.ok and item.terminal)
    executable = mode.get("executable") is not False
    unresolved = bool(mode.get("coverage_required")) and bool(missing)

    return {
        "path_id": branch_signature or mode_id,
        "mode_id": mode_id,
        "kind": str(mode.get("kind") or ""),
        "branch_signature": branch_signature,
        "wire_command": str(mode.get("wire_command") or ""),
        "executable": executable,
        "coverage_required": bool(mode.get("coverage_required")),
        "required_options": required,
        "covered_options": covered,
        "missing_options": missing,
        "sampling_ready": bool(executable and not unresolved and terminal_successes > 0),
        "observed_attempts": len(attempts),
        "terminal_successes": terminal_successes,
        "failed_attempts": sum(1 for item in attempts if not item.ok),
        "wire_steps_observed": sum(int(item.wire_steps or 0) for item in attempts),
        "observed_terminal_markers": sorted(
            {
                str(item.na)
                for item in attempts
                if item.terminal and str(item.na or "")
            }
        ),
        "evidence": [
            str(item.artifact_dir)
            for item in attempts
            if str(item.artifact_dir or "")
        ],
    }


def build_sampling_plan(result: GameTestResult) -> dict[str, Any]:
    paths = [
        _path_entry(result, mode)
        for mode in result.discovered_modes
        if isinstance(mode, dict) and str(mode.get("id") or "")
    ]

    # A provider can have a valid base attempt before it emits rich mode
    # metadata. Preserve that execution path rather than losing evidence.
    known_mode_ids = {entry["mode_id"] for entry in paths}
    for attempt in result.attempts:
        mode_id = str(attempt.mode_id or "SPIN")
        base_mode = mode_id.split("__", 1)[0]
        if base_mode in known_mode_ids:
            continue
        synthetic = {
            "id": base_mode,
            "kind": str(attempt.mode_kind or ""),
            "executable": True,
            "coverage_required": False,
        }
        paths.append(_path_entry(result, synthetic))
        known_mode_ids.add(base_mode)

    return {
        "schema": SCHEMA,
        "provider": result.provider,
        "game": {
            "slug": result.slug,
            "name": result.game_name,
            "symbol": result.symbol,
        },
        "source_status": result.status,
        "phase": "coverage",
        "semantics": {
            "coverage_goal": (
                "Traverse every provider/client-demonstrated executable path, "
                "using fresh sessions whenever the protocol consumes state."
            ),
            "sampling_unit": (
                "One normalized path/branch. Future high-volume runs repeat each "
                "sampling-ready path independently instead of multiplying unrelated selectors."
            ),
            "outcome_policy": (
                "Provider-specific request/response evidence classifies observed "
                "outcome families. Observed counts are samples and are never RNG probabilities."
            ),
            "repetitions_per_path": None,
        },
        "summary": {
            "paths": len(paths),
            "sampling_ready": sum(1 for item in paths if item["sampling_ready"]),
            "unresolved": sum(
                1
                for item in paths
                if item["coverage_required"] and item["missing_options"]
            ),
        },
        "paths": paths,
    }


def write_sampling_plan(result: GameTestResult) -> Path | None:
    root = Path(str(result.run_dir or ""))
    if not root.is_dir():
        return None
    path = root / "sampling-plan.json"
    path.write_text(
        json.dumps(build_sampling_plan(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


__all__ = ["SCHEMA", "build_sampling_plan", "write_sampling_plan"]
