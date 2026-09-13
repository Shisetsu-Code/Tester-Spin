from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from tester_spin.models import Game, utc_now_iso
from tester_spin.providers.base import Progress
from tester_spin.providers.bgaming.runtime import (
    bootstrap_game,
    is_demo_url,
    post_command,
    resolve_fresh_demo_url,
    sanitize_session_url,
)
from tester_spin.providers.bgaming.server_guided import (
    _load_client_bundle,
    _serializer_details,
)
from tester_spin.structure.normalization import sanitize
from tester_spin.structure.persistence import atomic_write

SCHEMA = "tester-spin/bgaming-wager-format/v1"
_MAX_COMMANDS = 96
_MAX_DOMAIN_ITEMS = 96
_MAX_DOMAIN_DEPTH = 6

_COMMAND_LITERAL = re.compile(
    r"(?:[\"']?command[\"']?)\s*:\s*[\"']([A-Za-z_][A-Za-z0-9_.:-]{0,95})[\"']"
)

# These paths describe outcomes/rendering/RNG observations rather than inputs a
# player can select. They are deliberately excluded from the finite-input census.
_OUTCOME_PATH = re.compile(
    r"(?:^|\.)(?:outcome|screen|screens|storage|seed|paytable|paylines?|wins?|payouts?|"
    r"symbols?|reels?|coins_screen|new_values|prizes?|result)(?:\.|$)",
    re.I,
)


@dataclass(slots=True)
class WagerFormatResult:
    status: str
    game: str
    artifact: str = ""
    commands: int = 0
    domains: int = 0
    unresolved: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "game": self.game,
            "artifact": self.artifact,
            "commands": self.commands,
            "domains": self.domains,
            "unresolved": self.unresolved,
            "error": self.error,
        }


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _bounded_unique(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    markers: set[str] = set()
    for value in values:
        if not _is_scalar(value):
            continue
        marker = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if marker in markers:
            continue
        markers.add(marker)
        result.append(value)
        if len(result) >= _MAX_DOMAIN_ITEMS:
            break
    return result


def _path_name(path: str) -> str:
    return path.rsplit(".", 1)[-1].casefold() if path else ""


def extract_finite_domains(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract bounded input/config domains already present in authoritative init.

    This is a census, not execution authority. It intentionally records where a
    finite set came from so later command-field correlation can stay fail-closed.
    """
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(path: str, kind: str, values: list[Any]) -> None:
        bounded = _bounded_unique(values)
        if not bounded:
            return
        marker = (path, kind)
        if marker in seen:
            return
        seen.add(marker)
        rows.append(
            {
                "path": path,
                "name": _path_name(path),
                "kind": kind,
                "values": sanitize(bounded),
                "size": len(bounded),
                "authority": "server-init-observed",
            }
        )

    def walk(value: Any, path: str, depth: int) -> None:
        if depth > _MAX_DOMAIN_DEPTH or _OUTCOME_PATH.search(path):
            return
        if isinstance(value, list):
            if 0 < len(value) <= _MAX_DOMAIN_ITEMS and all(_is_scalar(item) for item in value):
                add(path, "scalar-list", list(value))
                return
            for index, item in enumerate(value[:_MAX_DOMAIN_ITEMS]):
                if isinstance(item, (dict, list)):
                    walk(item, f"{path}[{index}]", depth + 1)
            return
        if not isinstance(value, dict):
            return

        if 0 < len(value) <= _MAX_DOMAIN_ITEMS:
            keys = [str(key) for key in value]
            add(path, "mapping-keys", keys)
            if all(_is_scalar(item) for item in value.values()):
                add(path, "mapping-values", list(value.values()))

        for raw_key, item in list(value.items())[:_MAX_DOMAIN_ITEMS]:
            child = f"{path}.{raw_key}" if path else str(raw_key)
            if isinstance(item, (dict, list)):
                walk(item, child, depth + 1)

    for root in ("options", "features", "game", "bet_to_batch_state"):
        value = data.get(root)
        if isinstance(value, (dict, list)):
            walk(value, f"$.{root}", 0)

    rows.sort(key=lambda item: (str(item["path"]), str(item["kind"])))
    return rows


def canonical_wager_domains(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Resolve the common BGaming wager fields directly from init structure."""
    result: dict[str, dict[str, Any]] = {}
    options = data.get("options")
    options = options if isinstance(options, dict) else {}

    bets = options.get("available_bets")
    if isinstance(bets, list) and bets and all(_is_scalar(item) for item in bets):
        result["bet"] = {
            "values": sanitize(_bounded_unique(list(bets))),
            "source": "$.options.available_bets",
            "authority": "server-init-observed",
        }

    feature_options = options.get("feature_options")
    feature_options = feature_options if isinstance(feature_options, dict) else {}
    multipliers = feature_options.get("feature_multipliers")
    multipliers = multipliers if isinstance(multipliers, dict) else {}
    feature_names: list[str] = []
    levels: list[str] = []
    feature_levels: dict[str, list[str]] = {}
    feature_prices: dict[str, Any] = {}
    for raw_name, raw_value in multipliers.items():
        name = str(raw_name)
        if name == "base_bet":
            continue
        feature_names.append(name)
        if isinstance(raw_value, dict):
            current_levels = [str(key) for key in raw_value.keys()][:_MAX_DOMAIN_ITEMS]
            feature_levels[name] = current_levels
            levels.extend(current_levels)
            feature_prices[name] = sanitize(raw_value)
        elif _is_scalar(raw_value):
            feature_prices[name] = sanitize(raw_value)

    if feature_names:
        result["purchased_feature"] = {
            "values": _bounded_unique(feature_names),
            "source": "$.options.feature_options.feature_multipliers.keys",
            "authority": "server-init-observed",
        }
    if levels:
        result["purchased_feature_level"] = {
            "values": _bounded_unique(levels),
            "source": "$.options.feature_options.feature_multipliers.<feature>.keys",
            "authority": "server-init-observed",
            "by_feature": feature_levels,
        }
    if feature_prices:
        result["purchase_prices"] = {
            "values": feature_prices,
            "source": "$.options.feature_options.feature_multipliers",
            "authority": "server-init-observed",
        }

    coins = feature_options.get("coin_values")
    if isinstance(coins, list) and coins and all(_is_scalar(item) for item in coins):
        result["coin_values"] = {
            "values": sanitize(_bounded_unique(list(coins))),
            "source": "$.options.feature_options.coin_values",
            "authority": "server-init-observed-config",
        }

    return result


def _all_command_occurrences(bundle: str) -> dict[str, list[Any]]:
    result: dict[str, list[Any]] = {}
    for match in _COMMAND_LITERAL.finditer(bundle or ""):
        command = str(match.group(1))
        if command not in result and len(result) >= _MAX_COMMANDS:
            continue
        result.setdefault(command, []).append(match)
        if len(result[command]) > 32:
            result[command] = result[command][:32]
    return result


def _merge_unique(target: list[dict[str, Any]], item: dict[str, Any]) -> None:
    marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
    if marker not in {json.dumps(row, ensure_ascii=False, sort_keys=True) for row in target}:
        target.append(dict(item))


def _field_domain_candidates(
    field: str,
    *,
    literal_values: list[Any],
    canonical: dict[str, dict[str, Any]],
    census: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if literal_values:
        rows.append(
            {
                "values": sanitize(_bounded_unique(literal_values)),
                "source": "client-literal-callsites",
                "authority": "client-proven",
            }
        )
    if field in canonical:
        rows.append(dict(canonical[field]))

    needle = field.casefold()
    aliases = {
        needle,
        needle + "s",
        needle + "_values",
        needle + "_options",
        needle + "_types",
        needle + "_prices",
    }
    if needle.endswith("_type"):
        aliases.add(needle[:-5] + "_types")
        aliases.add(needle[:-5] + "_prices")
    if needle.endswith("_level"):
        aliases.add(needle[:-6] + "_levels")

    for domain in census:
        name = str(domain.get("name") or "").casefold()
        path = str(domain.get("path") or "").casefold()
        if name not in aliases and not any(f".{alias}" in path for alias in aliases):
            continue
        rows.append(
            {
                "values": domain.get("values"),
                "source": domain.get("path"),
                "authority": "server-init-candidate",
                "kind": domain.get("kind"),
            }
        )

    unique: list[dict[str, Any]] = []
    for row in rows:
        _merge_unique(unique, row)
    return unique[:12]


def discover_command_formats(
    bundle: str,
    init_data: dict[str, Any],
    *,
    census: list[dict[str, Any]] | None = None,
    canonical: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    census = list(census or extract_finite_domains(init_data))
    canonical = dict(canonical or canonical_wager_domains(init_data))
    flow = init_data.get("flow")
    flow = flow if isinstance(flow, dict) else {}
    advertised = {str(value) for value in flow.get("available_actions") or []}

    rows: list[dict[str, Any]] = []
    for command, occurrences in sorted(_all_command_occurrences(bundle).items()):
        option_fields: list[str] = []
        option_variants: list[dict[str, Any]] = []
        unresolved_variants: list[dict[str, Any]] = []
        wrappers: list[str] = []
        forwarded: list[str] = []
        parameterless = False
        shape_proven = False

        for occurrence in occurrences:
            details = _serializer_details(bundle, occurrence)
            shape_proven = shape_proven or bool(details.get("shape_proven"))
            parameterless = parameterless or bool(details.get("parameterless"))
            for field in details.get("option_fields") or []:
                text = str(field)
                if text and text not in option_fields:
                    option_fields.append(text)
            for variant in details.get("option_variants") or []:
                if isinstance(variant, dict):
                    _merge_unique(option_variants, variant)
            for variant in details.get("unresolved_option_variants") or []:
                if isinstance(variant, dict):
                    _merge_unique(unresolved_variants, variant)
            wrapper = str(details.get("client_wrapper") or "")
            if wrapper and wrapper not in wrappers:
                wrappers.append(wrapper)
            parameter = str(details.get("forwarded_options_parameter") or "")
            if parameter and parameter not in forwarded:
                forwarded.append(parameter)

        field_rows: dict[str, Any] = {}
        unresolved_fields: set[str] = set()
        for variant in unresolved_variants:
            for field in variant.get("unresolved_fields") or []:
                unresolved_fields.add(str(field))

        for field in option_fields:
            literal_values: list[Any] = []
            for variant in option_variants:
                options = variant.get("options")
                if isinstance(options, dict) and field in options:
                    literal_values.append(options[field])
            for variant in unresolved_variants:
                options = variant.get("literal_options")
                if isinstance(options, dict) and field in options:
                    literal_values.append(options[field])
            candidates = _field_domain_candidates(
                field,
                literal_values=literal_values,
                canonical=canonical,
                census=census,
            )
            field_rows[field] = {
                "resolved_by_literal": bool(literal_values),
                "unresolved_in_client": field in unresolved_fields,
                "domain_candidates": candidates,
            }

        rows.append(
            {
                "command": command,
                "initially_advertised": command in advertised,
                "client_command_literal_hits": len(occurrences),
                "serializer_shape_proven": shape_proven,
                "parameterless": parameterless,
                "option_fields": option_fields,
                "fields": field_rows,
                "literal_variants": option_variants,
                "unresolved_variants": unresolved_variants,
                "client_wrappers": wrappers,
                "forwarded_options_parameters": forwarded,
            }
        )
    return rows


def build_wager_format(init_data: dict[str, Any], bundle: str, *, source: str = "") -> dict[str, Any]:
    census = extract_finite_domains(init_data)
    canonical = canonical_wager_domains(init_data)
    commands = discover_command_formats(bundle, init_data, census=census, canonical=canonical)
    unresolved = sum(
        1
        for command in commands
        for field in (command.get("fields") or {}).values()
        if isinstance(field, dict)
        and field.get("unresolved_in_client")
        and not field.get("domain_candidates")
    )
    flow = init_data.get("flow")
    flow = flow if isinstance(flow, dict) else {}
    options = init_data.get("options")
    options = options if isinstance(options, dict) else {}
    return {
        "schema": SCHEMA,
        "generated_at": utc_now_iso(),
        "method": "bootstrap+init+official-client-static-analysis",
        "network_policy": "init-only; no spin, purchase, continuation or browser UI",
        "client": {
            "source": sanitize_session_url(source) if source else "",
            "bundle_sha256": hashlib.sha256((bundle or "").encode("utf-8", errors="replace")).hexdigest() if bundle else "",
        },
        "init": {
            "identifier": str(options.get("identifier") or init_data.get("identifier") or ""),
            "state": str(flow.get("state") or ""),
            "available_actions": [str(value) for value in flow.get("available_actions") or []],
        },
        "canonical_wager_domains": canonical,
        "finite_domains": census,
        "commands": commands,
        "coverage": {
            "commands": len(commands),
            "finite_domains": len(census),
            "canonical_fields": len(canonical),
            "unresolved_fields_without_domain": unresolved,
        },
    }


def _resolve_launch(provider: Any, game: Game, timeout_s: float) -> tuple[Any, str]:
    session = provider._new_session()
    candidates: list[str] = []
    if game.url:
        candidates.append(str(game.url))
    metadata = provider.game_dir(game) / "game.json"
    if metadata.is_file():
        try:
            raw = json.loads(metadata.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        if isinstance(raw, dict):
            for key in ("public_url", "demo_url"):
                value = str(raw.get(key) or "").strip()
                if value and value not in candidates:
                    candidates.append(value)
    for candidate in candidates:
        if is_demo_url(candidate):
            return session, candidate
        try:
            resolved = resolve_fresh_demo_url(session, candidate, timeout_s=timeout_s)
        except Exception:
            continue
        if resolved:
            return session, resolved
    session.close()
    return None, ""


def analyze_game_wager_format(
    provider: Any,
    game: Game,
    *,
    timeout_s: float,
    progress: Progress,
) -> WagerFormatResult:
    """Analyze BGaming wager/request grammar without spins or browser UI."""
    analysis_dir = provider.game_dir(game) / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    artifact = analysis_dir / "wager-format.json"
    progress(f"[{game.name}] FORMATO: resolviendo bootstrap; sin Chromium ni tiradas...")
    session, launch_url = _resolve_launch(provider, game, timeout_s)
    if session is None or not launch_url:
        return WagerFormatResult("SIN_DEMO", game.slug, artifact=str(artifact), error="No se pudo resolver demo fresco")
    try:
        runtime = bootstrap_game(session, launch_url, timeout_s=timeout_s)
        _response, _payload, init_data = post_command(runtime, "init", timeout_s=timeout_s, options={})
        progress(
            f"[{game.name}] FORMATO: init OK; state={((init_data.get('flow') or {}).get('state') if isinstance(init_data.get('flow'), dict) else '')!r}."
        )
        bundle, source = _load_client_bundle(runtime, timeout_s=timeout_s)
        payload = build_wager_format(init_data, bundle, source=source)
        atomic_write(artifact, payload)
        coverage = payload.get("coverage") or {}
        result = WagerFormatResult(
            "OK" if bundle else "PARCIAL",
            game.slug,
            artifact=str(artifact),
            commands=int(coverage.get("commands") or 0),
            domains=int(coverage.get("finite_domains") or 0),
            unresolved=int(coverage.get("unresolved_fields_without_domain") or 0),
            error="" if bundle else "Bundle oficial no disponible",
        )
        progress(
            f"[{game.name}] FORMATO {result.status}: commands={result.commands}, domains={result.domains}, "
            f"unresolved={result.unresolved}; {artifact}"
        )
        return result
    finally:
        session.close()


__all__ = [
    "SCHEMA",
    "WagerFormatResult",
    "analyze_game_wager_format",
    "build_wager_format",
    "canonical_wager_domains",
    "discover_command_formats",
    "extract_finite_domains",
]
