from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from tester_spin.providers.bgaming import server_guided as _server_guided


_LOCAL = threading.local()
_INSTALLED = False
_ORIGINAL_BEGIN = _server_guided.begin_dynamic_contract_run
_ORIGINAL_REMEMBER = _server_guided.remember_dynamic_evidence
_ORIGINAL_DYNAMIC_VARIANTS = _server_guided.dynamic_action_variants
_ORIGINAL_DISCOVER = _server_guided.discover_server_guided_client_evidence


def _clean(value: Any) -> str:
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value).strip()
    return ""


def purchase_scope(flow: dict[str, Any] | None) -> str:
    if not isinstance(flow, dict):
        return ""
    purchased = flow.get("purchased_feature")
    if not isinstance(purchased, dict):
        return ""
    name = _clean(purchased.get("name"))
    if not name:
        return ""
    scope = "PURCHASE_" + name.upper()
    level = _clean(purchased.get("level"))
    if level:
        scope += "_LEVEL_" + level.upper()
    return scope


def _variant_label(options: dict[str, Any]) -> str:
    if not options:
        return "__execute__"
    return "|".join(
        f"{key}={json.dumps(options[key], ensure_ascii=False, sort_keys=True)}"
        for key in sorted(options)
    )


def _enrich_evidence(
    evidence: dict[str, Any] | None,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(evidence, dict):
        return evidence
    source_flow = data.get("flow")
    if not isinstance(source_flow, dict):
        return evidence
    flow = evidence.get("flow")
    if not isinstance(flow, dict):
        flow = {}
        evidence["flow"] = flow
    scope = purchase_scope(source_flow)
    if scope:
        flow["purchase_scope"] = scope
    purchased = source_flow.get("purchased_feature")
    if isinstance(purchased, dict):
        flow["purchased_feature"] = {
            key: purchased.get(key)
            for key in ("name", "level")
            if purchased.get(key) not in (None, "")
        }
    return evidence


def _discover_with_context(runtime, data: dict[str, Any], *, timeout_s: float):
    evidence = _ORIGINAL_DISCOVER(runtime, data, timeout_s=timeout_s)
    return _enrich_evidence(evidence, data)


def _remember_with_context(evidence: dict[str, Any]) -> None:
    """Remember client-proven choices and narrowly allow feature-internal spin.

    ``spin`` is deliberately excluded by the legacy dynamic learner because a
    normal spin is a wager.  It becomes replayable here only when all of these
    are true: the server response is non-terminal, the round belongs to an
    explicit purchased feature, the server advertised ``spin``, and the client
    supplied an exact replay-eligible literal payload.  This models provider
    features that require pressing Spin inside an already purchased feature
    without turning arbitrary base spins into continuations.
    """
    if not isinstance(evidence, dict):
        return

    _ORIGINAL_REMEMBER(evidence)

    flow = evidence.get("flow")
    if not isinstance(flow, dict):
        return
    state = _clean(flow.get("state"))
    scope = _clean(flow.get("purchase_scope"))
    actions = flow.get("available_actions")
    advertised = {str(item) for item in actions} if isinstance(actions, list) else set()

    specs = _server_guided._dynamic_specs()

    # Add purchase scope as an additional compatibility guard to every dynamic
    # action learned from this response.  State-only reuse is too broad for
    # provider clients that reuse action names across different buy features.
    if scope:
        for raw in evidence.get("actions") or []:
            if not isinstance(raw, dict) or not raw.get("replay_eligible"):
                continue
            action = _clean(raw.get("action"))
            spec = specs.get(action)
            if isinstance(spec, dict):
                scopes = spec.setdefault("scopes", set())
                if isinstance(scopes, set):
                    scopes.add(scope)

    if not state or state == "closed" or not scope or "spin" not in advertised:
        return

    rows = evidence.get("actions")
    if not isinstance(rows, list):
        return
    for raw in rows:
        if (
            not isinstance(raw, dict)
            or _clean(raw.get("action")) != "spin"
            or not raw.get("replay_eligible")
        ):
            continue
        variants = raw.get("option_variants")
        if not isinstance(variants, list) or not variants:
            continue
        spec = specs.setdefault(
            "spin",
            {
                "states": set(),
                "scopes": set(),
                "variants": {},
                "source": str((evidence.get("client") or {}).get("source") or ""),
                "option_fields": [],
            },
        )
        spec.setdefault("states", set()).add(state)
        spec.setdefault("scopes", set()).add(scope)
        for field in raw.get("option_fields") or []:
            text = _clean(field)
            if text and text not in spec.setdefault("option_fields", []):
                spec["option_fields"].append(text)
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            options = variant.get("options")
            if not isinstance(options, dict):
                continue
            label = _clean(variant.get("label")) or _variant_label(options)
            spec.setdefault("variants", {})[label] = dict(options)


def _dynamic_variants_with_scope(data: dict[str, Any], action: str) -> list[dict[str, Any]]:
    variants = _ORIGINAL_DYNAMIC_VARIANTS(data, action)
    if not variants:
        return []
    spec = _server_guided._dynamic_specs().get(str(action or ""))
    if not isinstance(spec, dict):
        return variants
    scopes = spec.get("scopes")
    if isinstance(scopes, set) and scopes:
        flow = data.get("flow") if isinstance(data, dict) else None
        if purchase_scope(flow if isinstance(flow, dict) else None) not in scopes:
            return []
    return variants


def _evidence_from_assisted_capture(capture: dict[str, Any]) -> dict[str, Any] | None:
    command = _clean(capture.get("command"))
    options = capture.get("options")
    flow = capture.get("from_flow")
    if not command or command == "init" or not isinstance(options, dict) or not isinstance(flow, dict):
        return None
    state = _clean(flow.get("state"))
    scope = _clean(flow.get("purchase_scope")) or purchase_scope(flow)
    if not state:
        return None
    # A persisted internal spin is only safe with an explicit purchase scope.
    if command == "spin" and (state == "closed" or not scope):
        return None
    option_fields = [str(key) for key in options]
    return {
        "schema": "tester-spin/bgaming-server-guided-discovery/v1",
        "flow": {
            "state": state,
            "command": _clean(flow.get("command")),
            "available_actions": [command],
            "purchase_scope": scope,
            "purchased_feature": flow.get("purchased_feature") if isinstance(flow.get("purchased_feature"), dict) else {},
        },
        "client": {
            "source": "assisted-runtime-observation",
            "bundle_sha256": "",
        },
        "actions": [
            {
                "action": command,
                "advertised": True,
                "option_fields": option_fields,
                "parameterless": not options,
                "option_variants": [
                    {
                        "label": _variant_label(options),
                        "options": dict(options),
                        "source": "assisted-runtime-observation",
                    }
                ],
                "unresolved_option_variants": [],
                "serializer_shape_proven": True,
                "replay_eligible": True,
                "execution_authority": "assisted-user-reviewed",
            }
        ],
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _persisted_evidence(game_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    # Historical normal runs already contain bounded server/client correlations.
    # Reuse them instead of rediscovering a known branch on every catalog pass.
    test_files = sorted(
        game_dir.glob("tests/*/server-guided-discovery.json"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )[:24]
    for path in test_files:
        payload = _load_json(path)
        for item in payload.get("states") or []:
            if isinstance(item, dict):
                rows.append(item)

    assisted_files = sorted(
        game_dir.glob("analysis/assisted-resolution/*/session.json"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )[:24]
    for path in assisted_files:
        payload = _load_json(path)
        # Aborted sessions are useful diagnostics but must not become execution
        # authority.  Only a user-completed review can promote captured payloads.
        if not bool(payload.get("completed_by_user")):
            continue
        for capture in payload.get("captures") or []:
            if not isinstance(capture, dict):
                continue
            evidence = _evidence_from_assisted_capture(capture)
            if evidence is not None:
                rows.append(evidence)
    return rows


def _begin_with_persisted_evidence() -> None:
    _ORIGINAL_BEGIN()
    game_dir = getattr(_LOCAL, "game_dir", None)
    if not isinstance(game_dir, Path):
        return
    for evidence in _persisted_evidence(game_dir):
        _remember_with_context(evidence)


def set_current_game_dir(path: Path | None) -> None:
    _LOCAL.game_dir = Path(path) if path is not None else None


def clear_current_game_dir() -> None:
    _LOCAL.game_dir = None


def _install_flow_choice_spin_bridge() -> None:
    # Import only after server_guided has been patched so flow_choices binds the
    # scoped dynamic_action_* helpers rather than their unguarded originals.
    from tester_spin.providers.bgaming import flow_choices

    original_candidates = flow_choices._candidate_prompts

    if getattr(original_candidates, "_tester_spin_internal_spin", False):
        return

    def candidates_with_internal_spin(data: dict[str, Any]):
        prompts = list(original_candidates(data))
        flow = data.get("flow") if isinstance(data, dict) else None
        if not isinstance(flow, dict):
            return prompts
        state = _clean(flow.get("state"))
        actions = flow.get("available_actions")
        action_names = {str(item) for item in actions} if isinstance(actions, list) else set()
        if state == "closed" or "spin" not in action_names or not purchase_scope(flow):
            return prompts
        prompt = flow_choices._dynamic_prompt_for(data, "spin")
        if prompt is not None and not any(existing.command == "spin" for existing in prompts):
            prompts.append(prompt)
        return prompts

    candidates_with_internal_spin._tester_spin_internal_spin = True  # type: ignore[attr-defined]
    flow_choices._candidate_prompts = candidates_with_internal_spin


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _server_guided.discover_server_guided_client_evidence = _discover_with_context
    _server_guided.remember_dynamic_evidence = _remember_with_context
    _server_guided.dynamic_action_variants = _dynamic_variants_with_scope
    _server_guided.begin_dynamic_contract_run = _begin_with_persisted_evidence
    _install_flow_choice_spin_bridge()
    _INSTALLED = True


def wrap_provider(base_cls):
    install()

    class PersistentFlowBGamingProvider(base_cls):
        def test_game(self, game, *, spins, timeout_s, stop_event, progress):
            set_current_game_dir(self.game_dir(game))
            try:
                return super().test_game(
                    game,
                    spins=spins,
                    timeout_s=timeout_s,
                    stop_event=stop_event,
                    progress=progress,
                )
            finally:
                clear_current_game_dir()

    PersistentFlowBGamingProvider.__name__ = "BGamingProvider"
    PersistentFlowBGamingProvider.__qualname__ = "BGamingProvider"
    PersistentFlowBGamingProvider.__module__ = "tester_spin.providers.bgaming"
    return PersistentFlowBGamingProvider


install()


__all__ = [
    "clear_current_game_dir",
    "install",
    "purchase_scope",
    "set_current_game_dir",
    "wrap_provider",
]
