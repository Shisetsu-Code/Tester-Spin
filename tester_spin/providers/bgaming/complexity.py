from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tester_spin.models import GameTestResult, utc_now_iso
from tester_spin.structure.persistence import atomic_write

SCHEMA = "tester-spin/bgaming-complexity/v1"
AUTO_COMPLETE = "AUTO_COMPLETO"
REVIEW_REQUIRED = "REQUIERE_REVISION"
INDETERMINATE = "INDETERMINADO"
MANUAL_RESOLVED = "RESUELTO_MANUALMENTE"


def classify_result(result: GameTestResult) -> dict[str, Any]:
    reasons: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    review_targets: list[str] = []

    def add(kind: str, value: str, target: str = "") -> None:
        marker = (kind, value)
        if marker not in seen:
            seen.add(marker)
            reasons.append({"kind": kind, "value": value})
        target = str(target or "").strip()
        if target and target not in review_targets:
            review_targets.append(target)

    for mode in result.discovered_modes or []:
        if not isinstance(mode, dict):
            continue
        mode_id = str(mode.get("id") or "")
        kind = str(mode.get("kind") or "").upper()
        command = str(mode.get("wire_command") or mode_id)
        if kind == "FEATURE" and mode.get("observed") is False:
            add("UNKNOWN_ACTION", command, command)
        if kind == "PURCHASE" and mode.get("executable") is False:
            add("UNKNOWN_PURCHASE_CONTRACT", mode_id, "spin")
        if str(mode.get("discovery_state") or "").upper() == "ADVERTISED_ONLY":
            add("ADVERTISED_ONLY", command, command)

    for attempt in result.attempts or []:
        text = (str(attempt.warning or "") + " " + str(attempt.error or "")).casefold()
        state = str(attempt.na or "").strip()
        if attempt.status_code == 422 or "http 422" in text or "wire-shape" in text:
            add("UNRESOLVED_WIRE_SHAPE", attempt.mode_id or "unknown")
        if attempt.status_code is not None and not attempt.terminal and state and state.casefold() != "closed":
            add("NON_TERMINAL_STATE", state)

    error = str(result.error or "")
    folded = error.casefold()
    if "cobertura requerida pendiente:" in folded:
        add("COVERAGE_GAP", error.split("Cobertura requerida pendiente:", 1)[-1][:500])
    if "acciones opcionales/no clasificadas:" in folded:
        add("UNKNOWN_ACTION", error.split("Acciones opcionales/no clasificadas:", 1)[-1][:500])

    if reasons:
        classification = REVIEW_REQUIRED
        requires_review = True
    elif str(result.status or "").upper() == "OK":
        classification = AUTO_COMPLETE
        requires_review = False
    else:
        classification = INDETERMINATE
        requires_review = False

    return {
        "schema": SCHEMA,
        "classification": classification,
        "requires_review": requires_review,
        "technical_status": str(result.status or ""),
        "reasons": reasons,
        "review_targets": review_targets,
        "classified_at": utc_now_iso(),
        "source": "normal-runner",
    }


def complexity_path(game_dir: Path) -> Path:
    return Path(game_dir) / "analysis" / "complexity.json"


def persist_result_complexity(game_dir: Path, result: GameTestResult) -> dict[str, Any]:
    payload = classify_result(result)
    path = complexity_path(game_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, payload)
    result.structural_map = dict(result.structural_map or {})
    result.structural_map["complexity"] = payload
    return payload


def load_complexity(game_dir: Path) -> dict[str, Any]:
    try:
        value = json.loads(complexity_path(game_dir).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def mark_manual_resolution(game_dir: Path, *, completed: bool, remaining_fields: int, captures: int) -> dict[str, Any]:
    payload = load_complexity(game_dir)
    resolved = bool(completed and remaining_fields == 0 and captures > 0)
    payload.update({
        "schema": SCHEMA,
        "classification": MANUAL_RESOLVED if resolved else REVIEW_REQUIRED,
        "requires_review": not resolved,
        "manual_resolution": {
            "completed": bool(completed),
            "remaining_fields": int(remaining_fields),
            "captures": int(captures),
            "at": utc_now_iso(),
        },
    })
    path = complexity_path(game_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, payload)
    return payload


__all__ = ["AUTO_COMPLETE", "REVIEW_REQUIRED", "INDETERMINATE", "MANUAL_RESOLVED", "classify_result", "load_complexity", "mark_manual_resolution", "persist_result_complexity"]
