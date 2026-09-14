from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tester_spin.models import GameTestResult, utc_now_iso
from tester_spin.structure.persistence import atomic_write

SCHEMA = "tester-spin/bgaming-complexity/v1"
AUTO_COMPLETE = "AUTO_COMPLETO"
SIMPLE_PENDING = "SIMPLE_PENDIENTE"
REVIEW_REQUIRED = "REQUIERE_REVISION"
INDETERMINATE = "INDETERMINADO"
MANUAL_RESOLVED = "RESUELTO_MANUALMENTE"

_STANDARD_MODE_PREFIXES = (
    "PURCHASE_",
    "SPIN",
    "ANTE",
    "BONUS_CHANCE",
)


def _coverage_mode_ids(value: str) -> list[str]:
    """Extract uppercase mode identifiers from a coverage diagnostic.

    Coverage messages often contain Python-list formatting, e.g.
    ``PURCHASE_X -> ['PURCHASE_X']``.  Parsing with whitespace splitting leaves
    quotes/brackets attached and can accidentally classify a standard purchase as
    complex gameplay.  Regex extraction keeps the classifier independent from
    presentation formatting.
    """
    return list(dict.fromkeys(re.findall(r"\b[A-Z][A-Z0-9_]*\b", str(value or ""))))


def _standard_coverage_only(value: str) -> bool:
    mode_ids = _coverage_mode_ids(value)
    return bool(mode_ids) and all(
        mode_id.startswith(_STANDARD_MODE_PREFIXES)
        for mode_id in mode_ids
    )


def classify_result(result: GameTestResult) -> dict[str, Any]:
    """Classify gameplay complexity independently from technical completeness.

    A missing standard spin variant (ante/bonus chance/purchase) is not, by
    itself, complex gameplay.  Manual review is reserved for runtime-observed
    branching: unknown actions, non-terminal states, or unresolved continuation
    wire shapes.  This keeps the review queue focused on genuinely interactive
    games instead of every mode the executor has not learned yet.
    """
    reasons: list[dict[str, str]] = []
    capability_gaps: list[dict[str, str]] = []
    seen_reasons: set[tuple[str, str]] = set()
    seen_gaps: set[tuple[str, str]] = set()
    review_targets: list[str] = []

    def add_reason(kind: str, value: str, target: str = "") -> None:
        marker = (kind, value)
        if marker not in seen_reasons:
            seen_reasons.add(marker)
            reasons.append({"kind": kind, "value": value})
        target = str(target or "").strip()
        if target and target not in review_targets:
            review_targets.append(target)

    def add_gap(kind: str, value: str) -> None:
        marker = (kind, value)
        if marker not in seen_gaps:
            seen_gaps.add(marker)
            capability_gaps.append({"kind": kind, "value": value})

    mode_kind_by_id: dict[str, str] = {}
    for mode in result.discovered_modes or []:
        if not isinstance(mode, dict):
            continue
        mode_id = str(mode.get("id") or "")
        kind = str(mode.get("kind") or "").upper()
        command = str(mode.get("wire_command") or mode_id)
        if mode_id:
            mode_kind_by_id[mode_id] = kind

        if kind == "FEATURE" and mode.get("observed") is False:
            add_reason("UNKNOWN_ACTION", command, command)
            continue

        if kind == "PURCHASE" and mode.get("executable") is False:
            add_gap("UNKNOWN_PURCHASE_CONTRACT", mode_id)

        discovery_state = str(mode.get("discovery_state") or "").upper()
        if discovery_state == "ADVERTISED_ONLY":
            if kind == "FEATURE":
                add_reason("ADVERTISED_ONLY_ACTION", command, command)
            else:
                add_gap("ADVERTISED_ONLY_MODE", mode_id or command)

    for attempt in result.attempts or []:
        text = (str(attempt.warning or "") + " " + str(attempt.error or "")).casefold()
        state = str(attempt.na or "").strip()
        mode_id = str(attempt.mode_id or "")
        mode_kind = mode_kind_by_id.get(mode_id, "")
        wire_unresolved = (
            attempt.status_code == 422
            or "http 422" in text
            or "wire-shape" in text
        )
        if wire_unresolved:
            if (
                "continuación" in text
                or "continuation" in text
                or mode_kind in {"FEATURE", "CONTINUATION"}
            ):
                add_reason("UNRESOLVED_CONTINUATION_WIRE", mode_id or state or "unknown", mode_id)
            else:
                add_gap("UNRESOLVED_STANDARD_WIRE", mode_id or "spin")

        if (
            attempt.status_code is not None
            and not attempt.terminal
            and state
            and state.casefold() != "closed"
        ):
            add_reason("NON_TERMINAL_STATE", state)

    error = str(result.error or "")
    folded = error.casefold()
    if "cobertura requerida pendiente:" in folded:
        value = error.split("Cobertura requerida pendiente:", 1)[-1][:500]
        if _standard_coverage_only(value):
            add_gap("STANDARD_COVERAGE_GAP", value)
        else:
            add_reason("COVERAGE_GAP", value)

    if "acciones opcionales/no clasificadas:" in folded:
        value = error.split("Acciones opcionales/no clasificadas:", 1)[-1][:500]
        add_reason("UNKNOWN_ACTION", value, value)

    if reasons:
        classification = REVIEW_REQUIRED
        requires_review = True
    elif str(result.status or "").upper() == "OK":
        classification = AUTO_COMPLETE
        requires_review = False
    elif capability_gaps:
        classification = SIMPLE_PENDING
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
        "capability_gaps": capability_gaps,
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


__all__ = [
    "AUTO_COMPLETE",
    "SIMPLE_PENDING",
    "REVIEW_REQUIRED",
    "INDETERMINATE",
    "MANUAL_RESOLVED",
    "classify_result",
    "load_complexity",
    "mark_manual_resolution",
    "persist_result_complexity",
]
