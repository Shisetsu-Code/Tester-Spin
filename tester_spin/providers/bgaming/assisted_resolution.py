from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from tester_spin.structure.normalization import sanitize

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


def merge_assisted_captures(payload: dict[str, Any], captures: list[dict[str, Any]], *, completed: bool, session_id: str) -> tuple[dict[str, Any], int]:
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
        seen = {json.dumps(value, ensure_ascii=False, sort_keys=True) for value in assisted_variants if isinstance(value, dict)}
        for capture in relevant:
            options = capture.get("options")
            if not isinstance(options, dict):
                continue
            variant = {"options": sanitize(options), "source": "assisted-runtime-observation", "evidence": "USER_ASSISTED_RUNTIME"}
            marker = json.dumps(variant, ensure_ascii=False, sort_keys=True)
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
            values = []
            for capture in relevant:
                options = capture.get("options")
                if isinstance(options, dict) and field_name in options:
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
            candidates.append({"values": sanitize(values), "source": "assisted-runtime-observation", "authority": "assisted-user-reviewed", "complete": True})
            field_row["assisted_user_reviewed"] = True
            resolved_fields += 1

    assisted = merged.setdefault("assisted_resolution", {})
    sessions = assisted.setdefault("sessions", []) if isinstance(assisted, dict) else []
    if isinstance(sessions, list):
        sessions.append({"schema": SCHEMA, "session_id": session_id, "completed_by_user": bool(completed), "captures": captures})

    coverage = merged.setdefault("coverage", {})
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
    if isinstance(coverage, dict):
        coverage["unresolved_fields_without_domain"] = unresolved
        coverage["assisted_user_reviewed_fields"] = reviewed
    return merged, resolved_fields


__all__ = ["SCHEMA", "AssistedResolutionResult", "capture_matches_target", "merge_assisted_captures", "unresolved_targets"]
