from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import threading
import time
from typing import Any

from tester_spin.models import Game, utc_now_iso
from tester_spin.providers.base import Progress
from tester_spin.providers.bgaming.assisted_browser import run_assisted_browser
from tester_spin.providers.bgaming.wager_format import (
    _resolve_launch,
    analyze_game_wager_format,
)
from tester_spin.structure.normalization import sanitize
from tester_spin.structure.persistence import atomic_write

SCHEMA = "tester-spin/bgaming-assisted-resolution/v1"


@dataclass(slots=True)
class AssistedResolutionResult:
    status: str
    game: str
    artifact: str = ""
    targets: int = 0
    captures: int = 0
    resolved_fields: int = 0
    completed: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "game": self.game,
            "artifact": self.artifact,
            "targets": self.targets,
            "captures": self.captures,
            "resolved_fields": self.resolved_fields,
            "completed": self.completed,
            "error": self.error,
        }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def unresolved_targets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for command in payload.get("commands") or []:
        if not isinstance(command, dict):
            continue
        command_name = str(command.get("command") or "").strip()
        fields = command.get("fields")
        if not command_name or not isinstance(fields, dict):
            continue
        unresolved: list[str] = []
        for field_name, raw in fields.items():
            if not isinstance(raw, dict):
                continue
            if bool(raw.get("unresolved_in_client")) and not list(raw.get("domain_candidates") or []):
                unresolved.append(str(field_name))
        if unresolved:
            result.append({"command": command_name, "fields": unresolved})
    return result


def capture_matches_target(payload: dict[str, Any], targets: list[dict[str, Any]]) -> bool:
    command = str(payload.get("command") or "")
    options = payload.get("options")
    if not command or not isinstance(options, dict):
        return False
    for target in targets:
        if str(target.get("command") or "") != command:
            continue
        if any(str(field) in options for field in target.get("fields") or []):
            return True
    return False


def _unique_json_values(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        marker = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def merge_assisted_captures(
    payload: dict[str, Any],
    captures: list[dict[str, Any]],
    *,
    completed: bool,
    session_id: str,
) -> tuple[dict[str, Any], int]:
    merged = json.loads(json.dumps(payload, ensure_ascii=False)) if payload else {}
    commands = merged.get("commands")
    commands = commands if isinstance(commands, list) else []
    captures = [sanitize(value) for value in captures if isinstance(value, dict)]
    resolved_fields = 0

    for row in commands:
        if not isinstance(row, dict):
            continue
        command_name = str(row.get("command") or "")
        relevant = [value for value in captures if str(value.get("command") or "") == command_name]
        if not relevant:
            continue

        assisted_variants = row.setdefault("assisted_variants", [])
        if not isinstance(assisted_variants, list):
            assisted_variants = []
            row["assisted_variants"] = assisted_variants
        seen = {
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for value in assisted_variants
            if isinstance(value, dict)
        }
        for capture in relevant:
            options = capture.get("options")
            if not isinstance(options, dict):
                continue
            variant = {
                "options": sanitize(options),
                "source": "assisted-runtime-observation",
                "evidence": "USER_ASSISTED_RUNTIME",
            }
            marker = json.dumps(variant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if marker not in seen:
                seen.add(marker)
                assisted_variants.append(variant)

        if not completed:
            continue

        fields = row.get("fields")
        if not isinstance(fields, dict):
            continue
        for field_name, field_row in fields.items():
            if not isinstance(field_row, dict) or not bool(field_row.get("unresolved_in_client")):
                continue
            values: list[Any] = []
            for capture in relevant:
                options = capture.get("options")
                if not isinstance(options, dict) or field_name not in options:
                    continue
                value = options[field_name]
                if value is None or isinstance(value, (str, int, float, bool)):
                    values.append(value)
            values = _unique_json_values(values)
            if not values:
                continue

            candidates = field_row.setdefault("domain_candidates", [])
            if not isinstance(candidates, list):
                candidates = []
                field_row["domain_candidates"] = candidates
            candidate = {
                "values": sanitize(values),
                "source": "assisted-runtime-observation",
                "authority": "assisted-user-reviewed",
                "complete": True,
            }
            marker = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            existing = {
                json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                for value in candidates
                if isinstance(value, dict)
            }
            if marker not in existing:
                candidates.append(candidate)
            field_row["assisted_user_reviewed"] = True
            resolved_fields += 1

    assisted = merged.setdefault("assisted_resolution", {})
    if not isinstance(assisted, dict):
        assisted = {}
        merged["assisted_resolution"] = assisted
    sessions = assisted.setdefault("sessions", [])
    if not isinstance(sessions, list):
        sessions = []
        assisted["sessions"] = sessions
    sessions.append(
        {
            "schema": SCHEMA,
            "session_id": session_id,
            "finished_at": utc_now_iso(),
            "completed_by_user": bool(completed),
            "captures": captures,
        }
    )
    assisted["last_session_id"] = session_id
    assisted["last_completed_by_user"] = bool(completed)

    coverage = merged.setdefault("coverage", {})
    if not isinstance(coverage, dict):
        coverage = {}
        merged["coverage"] = coverage
    unresolved = 0
    reviewed = 0
    for row in commands:
        fields = row.get("fields") if isinstance(row, dict) else None
        if not isinstance(fields, dict):
            continue
        for field_row in fields.values():
            if not isinstance(field_row, dict):
                continue
            if field_row.get("assisted_user_reviewed"):
                reviewed += 1
            if bool(field_row.get("unresolved_in_client")) and not list(field_row.get("domain_candidates") or []):
                unresolved += 1
    coverage["unresolved_fields_without_domain"] = unresolved
    coverage["assisted_user_reviewed_fields"] = reviewed
    return merged, resolved_fields


def _restore_assisted_history(
    fresh: dict[str, Any],
    previous: dict[str, Any],
) -> dict[str, Any]:
    assisted = previous.get("assisted_resolution")
    if not isinstance(assisted, dict):
        return fresh
    sessions = assisted.get("sessions")
    if not isinstance(sessions, list):
        return fresh

    restored = fresh
    for index, session in enumerate(sessions):
        if not isinstance(session, dict):
            continue
        captures = session.get("captures")
        if not isinstance(captures, list):
            continue
        session_id = str(session.get("session_id") or f"restored-{index}")
        completed = bool(session.get("completed_by_user"))
        restored, _ = merge_assisted_captures(
            restored,
            [value for value in captures if isinstance(value, dict)],
            completed=completed,
            session_id=session_id,
        )
    return restored


def resolve_game_assisted(
    provider: Any,
    game: Game,
    *,
    timeout_s: float,
    stop_event: threading.Event,
    progress: Progress,
) -> AssistedResolutionResult:
    analysis_dir = provider.game_dir(game) / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    artifact = analysis_dir / "wager-format.json"

    previous_payload = _read_json(artifact) if artifact.is_file() else {}
    analyze_game_wager_format(provider, game, timeout_s=timeout_s, progress=progress)
    payload = _restore_assisted_history(_read_json(artifact), previous_payload)
    atomic_write(artifact, payload)

    targets = unresolved_targets(payload)
    if not targets:
        progress(f"[{game.name}] ASISTIDO: no quedan campos unresolved; no se abre Chromium.")
        return AssistedResolutionResult(
            "READY",
            game.slug,
            artifact=str(artifact),
            targets=0,
            completed=True,
        )

    target_text = "; ".join(
        f"{str(item.get('command') or '')}({', '.join(str(value) for value in item.get('fields') or [])})"
        for item in targets
    )
    progress(f"[{game.name}] ASISTIDO: pendientes={target_text}.")

    session, launch_url = _resolve_launch(provider, game, timeout_s)
    if session is None or not launch_url:
        return AssistedResolutionResult(
            "SIN_DEMO",
            game.slug,
            artifact=str(artifact),
            targets=len(targets),
            error="No se pudo resolver demo fresco",
        )
    session.close()

    captures, completed, browser_error = run_assisted_browser(
        game_name=game.name,
        launch_url=launch_url,
        targets=targets,
        timeout_s=timeout_s,
        stop_event=stop_event,
        progress=progress,
        capture_matches=capture_matches_target,
    )

    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = analysis_dir / "assisted-resolution" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    session_artifact = run_dir / "session.json"
    atomic_write(
        session_artifact,
        {
            "schema": SCHEMA,
            "game": game.slug,
            "targets": targets,
            "captures": captures,
            "completed_by_user": completed,
            "browser_error": browser_error,
            "finished_at": utc_now_iso(),
        },
    )

    merged, resolved_fields = merge_assisted_captures(
        payload,
        captures,
        completed=completed,
        session_id=stamp,
    )
    atomic_write(artifact, merged)
    remaining = unresolved_targets(merged)

    if completed and not remaining:
        status = "READY"
    elif captures:
        status = "PARCIAL"
    else:
        status = "CANCELADO"

    progress(
        f"[{game.name}] ASISTIDO {status}: capturas={len(captures)}, "
        f"campos_resueltos={resolved_fields}, "
        f"pendientes={sum(len(item.get('fields') or []) for item in remaining)}; "
        f"artifact={session_artifact}"
    )
    return AssistedResolutionResult(
        status,
        game.slug,
        artifact=str(artifact),
        targets=len(targets),
        captures=len(captures),
        resolved_fields=resolved_fields,
        completed=completed,
        error=browser_error,
    )


__all__ = [
    "SCHEMA",
    "AssistedResolutionResult",
    "capture_matches_target",
    "merge_assisted_captures",
    "resolve_game_assisted",
    "unresolved_targets",
]
