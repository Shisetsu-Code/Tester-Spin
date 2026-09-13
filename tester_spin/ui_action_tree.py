from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from tester_spin.models import utc_now_iso
from tester_spin.structure.contracts import merge_schema, observe_schema
from tester_spin.structure.normalization import bounded_add, identity, sanitize
from tester_spin.structure.persistence import atomic_write

SCHEMA = "tester-spin/ui-action-tree/v1"


class UIActionTree:
    """Cumulative UI-first control graph.

    This artifact records what the real client exposed and what each interaction
    actually caused.  It never authorizes a request by itself; the farming layer
    must still bind fresh runtime/session fields and validate current server state.
    """

    def __init__(self, provider: str, game: str, protocol_family: str = "") -> None:
        self.scope = (provider, game, protocol_family)
        self.data: dict[str, Any] = {
            "schema": SCHEMA,
            "metadata": {
                "provider": provider,
                "game_identifier": game,
                "protocol_family": protocol_family,
                "generated_at": utc_now_iso(),
                "runs_merged": [],
            },
            "states": {},
            "candidates": {},
            "edges": {},
            "noise": {},
            "provider_chrome": {},
            "unresolved": {},
            "coverage": {},
        }

    @classmethod
    def load(cls, payload: dict[str, Any]) -> "UIActionTree":
        if payload.get("schema") != SCHEMA:
            raise ValueError("Unsupported UI action tree schema")
        meta = payload.get("metadata") or {}
        result = cls(str(meta.get("provider") or ""), str(meta.get("game_identifier") or ""), str(meta.get("protocol_family") or ""))
        for key in ("states", "candidates", "edges", "noise", "provider_chrome", "unresolved", "coverage"):
            if not isinstance(payload.get(key), dict):
                raise ValueError("Malformed UI action tree: " + key)
        result.data = deepcopy(payload)
        result.scope = (
            str(meta.get("provider") or ""),
            str(meta.get("game_identifier") or ""),
            str(meta.get("protocol_family") or ""),
        )
        return result

    def key(self, kind: str, *parts: Any) -> str:
        return identity(kind, self.scope, *parts)

    def state(self, server_state: str, available_actions: list[str] | tuple[str, ...] = (), *, local_fingerprint: str = "") -> str:
        key = self.key("ui-state", server_state, local_fingerprint)
        row = self.data["states"].setdefault(key, {
            "id": key,
            "server_state": sanitize(server_state),
            "local_fingerprint": sanitize(local_fingerprint),
            "available_actions": [],
            "observations": 0,
            "candidates": [],
            "outgoing_edges": [],
            "incoming_edges": [],
        })
        row["observations"] += 1
        for action in available_actions:
            bounded_add(row["available_actions"], sanitize(action), 256)
        return key

    def candidate(self, state_id: str, descriptor: dict[str, Any]) -> str:
        stable = {
            "kind": descriptor.get("kind"),
            "frame": descriptor.get("frame"),
            "signature": descriptor.get("signature"),
            "label": descriptor.get("label"),
            "role": descriptor.get("role"),
            "point": descriptor.get("point"),
        }
        key = self.key("ui-candidate", state_id, stable)
        row = self.data["candidates"].setdefault(key, {
            "id": key,
            "state_id": state_id,
            "descriptor": sanitize(stable),
            "observations": 0,
            "attempts": 0,
            "wire_transitions": 0,
            "local_transitions": 0,
            "classification": "untried",
        })
        row["observations"] += 1
        bounded_add(self.data["states"][state_id]["candidates"], key, 4096)
        return key

    def mark_provider_chrome(self, candidate_id: str, reason: str) -> None:
        row = self.data["candidates"].get(candidate_id)
        if row is not None:
            row["classification"] = "provider_chrome"
        self.data["provider_chrome"][candidate_id] = {
            "id": candidate_id,
            "reason": sanitize(reason),
        }

    def mark_noise(self, candidate_id: str, reason: str) -> None:
        row = self.data["candidates"].get(candidate_id)
        if row is not None:
            row["classification"] = "no_effect"
        self.data["noise"][candidate_id] = {
            "id": candidate_id,
            "reason": sanitize(reason),
        }

    def unresolved(self, entity: str, reason: str) -> None:
        key = self.key("ui-unresolved", entity, reason)
        self.data["unresolved"][key] = {
            "id": key,
            "entity": sanitize(entity),
            "reason": sanitize(reason),
        }

    def edge(
        self,
        from_state: str,
        candidate_id: str | None,
        *,
        request: dict[str, Any] | None,
        response: dict[str, Any] | None,
        to_state: str,
        evidence: str,
        automatic: bool = False,
    ) -> str:
        clean_request = sanitize(request or {})
        command = str((request or {}).get("command") or (request or {}).get("method") or "")
        key = self.key("ui-edge", from_state, candidate_id or "automatic", command, clean_request, to_state, evidence)
        row = self.data["edges"].setdefault(key, {
            "id": key,
            "from_state": from_state,
            "candidate": candidate_id,
            "command": sanitize(command),
            "request": clean_request,
            "response_schema": {},
            "response_examples": [],
            "to_state": to_state,
            "evidence": evidence,
            "automatic": bool(automatic),
            "observations": 0,
        })
        row["observations"] += 1
        if isinstance(response, dict):
            observe_schema(row["response_schema"], response)
            clean_response = sanitize(response)
            try:
                import json
                if len(json.dumps(clean_response, ensure_ascii=False, sort_keys=True)) <= 16384:
                    bounded_add(row["response_examples"], clean_response, 2)
            except Exception:
                pass
        bounded_add(self.data["states"][from_state]["outgoing_edges"], key, 4096)
        bounded_add(self.data["states"][to_state]["incoming_edges"], key, 4096)
        if candidate_id and candidate_id in self.data["candidates"]:
            candidate = self.data["candidates"][candidate_id]
            candidate["attempts"] += 1
            if evidence == "WIRE_OBSERVED":
                candidate["wire_transitions"] += 1
                candidate["classification"] = "action"
            elif evidence == "UI_LOCAL_OBSERVED":
                candidate["local_transitions"] += 1
                candidate["classification"] = "local_action"
        return key

    def merge(self, other: "UIActionTree") -> None:
        if self.scope != other.scope:
            raise ValueError("Incompatible UI action tree scope")
        for table in ("states", "candidates", "edges", "noise", "provider_chrome", "unresolved"):
            target = self.data[table]
            for key, incoming in other.data[table].items():
                if key not in target:
                    target[key] = deepcopy(incoming)
                    continue
                row = target[key]
                for counter in ("observations", "attempts", "wire_transitions", "local_transitions"):
                    if counter in incoming:
                        row[counter] = int(row.get(counter, 0)) + int(incoming.get(counter, 0))
                for field in ("available_actions", "candidates", "outgoing_edges", "incoming_edges", "response_examples"):
                    for value in incoming.get(field, []):
                        bounded_add(row.setdefault(field, []), deepcopy(value), 4096 if field != "response_examples" else 2)
                if table == "edges" and incoming.get("response_schema"):
                    merge_schema(row.setdefault("response_schema", {}), incoming["response_schema"])
                if table == "candidates" and row.get("classification") == "untried":
                    row["classification"] = incoming.get("classification", "untried")
        for run in other.data.get("metadata", {}).get("runs_merged", []):
            bounded_add(self.data["metadata"].setdefault("runs_merged", []), run, 10000)
        self.data["metadata"]["generated_at"] = utc_now_iso()

    def finalize(self, *, frontier_exhausted: bool) -> dict[str, Any]:
        unresolved_actions: list[dict[str, Any]] = []
        for state_id, state in self.data["states"].items():
            observed_commands = {
                str(self.data["edges"][edge].get("command") or "")
                for edge in state.get("outgoing_edges", [])
                if edge in self.data["edges"] and self.data["edges"][edge].get("evidence") == "WIRE_OBSERVED"
            }
            for action in state.get("available_actions", []):
                action_text = str(action)
                if action_text == "init":
                    continue
                if action_text not in observed_commands:
                    unresolved_actions.append({"state": state_id, "action": action_text})
        for item in unresolved_actions:
            self.unresolved(item["state"] + ":" + item["action"], "Server-advertised action has no UI-observed wire edge")
        candidates = list(self.data["candidates"].values())
        actionable = [c for c in candidates if c.get("classification") not in {"provider_chrome", "no_effect"}]
        untried = [c for c in actionable if c.get("classification") == "untried"]
        self.data["coverage"] = {
            "states": len(self.data["states"]),
            "candidates": len(candidates),
            "actions": sum(c.get("classification") == "action" for c in candidates),
            "local_actions": sum(c.get("classification") == "local_action" for c in candidates),
            "provider_chrome": len(self.data["provider_chrome"]),
            "no_effect": len(self.data["noise"]),
            "untried": len(untried),
            "unresolved_server_actions": len(unresolved_actions),
            "frontier_exhausted": bool(frontier_exhausted),
            "ready_for_farming": bool(frontier_exhausted and not untried and not unresolved_actions),
        }
        return deepcopy(self.data)


def persist_ui_action_tree(path: Path, incoming: UIActionTree, *, run_key: str, frontier_exhausted: bool) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = incoming
    if path.exists():
        import json
        previous = UIActionTree.load(json.loads(path.read_text(encoding="utf-8")))
        previous.merge(incoming)
        result = previous
    bounded_add(result.data["metadata"].setdefault("runs_merged", []), run_key, 10000)
    payload = result.finalize(frontier_exhausted=frontier_exhausted)
    atomic_write(path, payload)
    return payload
