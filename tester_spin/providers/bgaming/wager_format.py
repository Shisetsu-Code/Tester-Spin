from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from tester_spin.models import Game, utc_now_iso
from tester_spin.providers.base import Progress
from tester_spin.providers.bgaming.har_select import select_best_har
from tester_spin.providers.bgaming.request_syntax import scan_request_syntax
from tester_spin.providers.bgaming.runtime import (
    bootstrap_game,
    is_demo_url,
    post_command,
    resolve_fresh_demo_url,
    sanitize_session_url,
)
from tester_spin.providers.bgaming.server_guided import _load_client_bundle
from tester_spin.structure.normalization import sanitize
from tester_spin.structure.persistence import atomic_write

SCHEMA = "tester-spin/bgaming-wager-format/v1"
_MAX_DOMAIN_ITEMS = 96
_MAX_DOMAIN_DEPTH = 6
_MAX_EMBEDDED_SOURCE_BYTES = 48 * 1024 * 1024

_OUTCOME_NAMES = {
    "outcome", "screen", "screens", "storage", "seed", "paytable", "paylines",
    "wins", "win", "payouts", "symbols", "reels", "coins_screen", "new_values",
    "prizes", "result",
}


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
    seen: set[str] = set()
    for value in values:
        if not _is_scalar(value):
            continue
        marker = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
        if len(result) >= _MAX_DOMAIN_ITEMS:
            break
    return result


def _path_has_outcome(path: str) -> bool:
    normalized = path.replace("[", ".").replace("]", ".")
    return any(part.casefold() in _OUTCOME_NAMES for part in normalized.split(".") if part)


def extract_finite_domains(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Census finite input/config domains already exposed by init."""
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
        rows.append({
            "path": path,
            "name": path.rsplit(".", 1)[-1].casefold(),
            "kind": kind,
            "values": sanitize(bounded),
            "size": len(bounded),
            "authority": "server-init-observed",
        })

    def walk(value: Any, path: str, depth: int) -> None:
        if depth > _MAX_DOMAIN_DEPTH or _path_has_outcome(path):
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
            add(path, "mapping-keys", [str(key) for key in value])
            if all(_is_scalar(item) for item in value.values()):
                add(path, "mapping-values", list(value.values()))
        for key, item in list(value.items())[:_MAX_DOMAIN_ITEMS]:
            if isinstance(item, (dict, list)):
                walk(item, f"{path}.{key}", depth + 1)

    for root in ("options", "features", "game", "bet_to_batch_state"):
        value = data.get(root)
        if isinstance(value, (dict, list)):
            walk(value, f"$.{root}", 0)
    rows.sort(key=lambda item: (str(item["path"]), str(item["kind"])))
    return rows


def canonical_wager_domains(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    options = data.get("options")
    options = options if isinstance(options, dict) else {}

    bets = options.get("available_bets")
    if isinstance(bets, list) and bets:
        result["bet"] = {
            "values": sanitize(_bounded_unique(list(bets))),
            "source": "$.options.available_bets",
            "authority": "server-init-observed",
        }

    feature_options = options.get("feature_options")
    feature_options = feature_options if isinstance(feature_options, dict) else {}
    multipliers = feature_options.get("feature_multipliers")
    multipliers = multipliers if isinstance(multipliers, dict) else {}
    names: list[str] = []
    levels: list[str] = []
    by_feature: dict[str, list[str]] = {}
    prices: dict[str, Any] = {}
    for raw_name, value in multipliers.items():
        name = str(raw_name)
        if name == "base_bet":
            continue
        names.append(name)
        if isinstance(value, dict):
            current = [str(key) for key in value.keys()][:_MAX_DOMAIN_ITEMS]
            by_feature[name] = current
            levels.extend(current)
            prices[name] = sanitize(value)
        elif _is_scalar(value):
            prices[name] = sanitize(value)

    if names:
        result["purchased_feature"] = {
            "values": _bounded_unique(names),
            "source": "$.options.feature_options.feature_multipliers.keys",
            "authority": "server-init-observed",
        }
    if levels:
        result["purchased_feature_level"] = {
            "values": _bounded_unique(levels),
            "source": "$.options.feature_options.feature_multipliers.<feature>.keys",
            "authority": "server-init-observed",
            "by_feature": by_feature,
        }
    if prices:
        result["purchase_prices"] = {
            "values": prices,
            "source": "$.options.feature_options.feature_multipliers",
            "authority": "server-init-observed",
        }

    coins = feature_options.get("coin_values")
    if isinstance(coins, list) and coins:
        result["coin_values"] = {
            "values": sanitize(_bounded_unique(list(coins))),
            "source": "$.options.feature_options.coin_values",
            "authority": "server-init-observed-config",
        }
    return result


def _unique_dicts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        marker = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            result.append(row)
    return result


def _domain_candidates(
    field: str,
    literal_values: list[Any],
    canonical: dict[str, dict[str, Any]],
    census: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if literal_values:
        rows.append({
            "values": sanitize(_bounded_unique(literal_values)),
            "source": "client-literal-callsites",
            "authority": "client-proven",
        })
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
        aliases.update({needle[:-5] + "_types", needle[:-5] + "_prices"})
    if needle.endswith("_level"):
        aliases.add(needle[:-6] + "_levels")

    for domain in census:
        name = str(domain.get("name") or "").casefold()
        path = str(domain.get("path") or "").casefold()
        if name in aliases or any(f".{alias}" in path for alias in aliases):
            rows.append({
                "values": domain.get("values"),
                "source": domain.get("path"),
                "authority": "server-init-candidate",
                "kind": domain.get("kind"),
            })
    return _unique_dicts(rows)[:12]


def _merge_syntax_sources(*sources: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source in sources:
        for command, raw in source.items():
            if not isinstance(raw, dict):
                continue
            row = merged.setdefault(command, {
                "hits": 0,
                "option_fields": [],
                "literal_variants": [],
                "unresolved_variants": [],
                "wrappers": [],
            })
            row["hits"] = int(row["hits"]) + int(raw.get("hits") or 0)
            for field in raw.get("option_fields") or []:
                text = str(field)
                if text and text not in row["option_fields"]:
                    row["option_fields"].append(text)
            row["literal_variants"].extend(
                item for item in raw.get("literal_variants") or [] if isinstance(item, dict)
            )
            row["unresolved_variants"].extend(
                item for item in raw.get("unresolved_variants") or [] if isinstance(item, dict)
            )
            for wrapper in raw.get("wrappers") or []:
                text = str(wrapper)
                if text and text not in row["wrappers"]:
                    row["wrappers"].append(text)
    for row in merged.values():
        row["literal_variants"] = _unique_dicts(list(row["literal_variants"]))
        row["unresolved_variants"] = _unique_dicts(list(row["unresolved_variants"]))
    return merged


def discover_command_formats(
    bundle: str,
    init_data: dict[str, Any],
    *,
    census: list[dict[str, Any]] | None = None,
    canonical: dict[str, dict[str, Any]] | None = None,
    extra_syntax: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    census = list(census or extract_finite_domains(init_data))
    canonical = dict(canonical or canonical_wager_domains(init_data))
    syntax = _merge_syntax_sources(scan_request_syntax(bundle), extra_syntax or {})
    flow = init_data.get("flow")
    flow = flow if isinstance(flow, dict) else {}
    advertised = {str(value) for value in flow.get("available_actions") or []}

    rows: list[dict[str, Any]] = []
    for command, raw in sorted(syntax.items()):
        fields = [str(value) for value in raw.get("option_fields") or []]
        literal_variants = [dict(value) for value in raw.get("literal_variants") or [] if isinstance(value, dict)]
        unresolved_variants = [dict(value) for value in raw.get("unresolved_variants") or [] if isinstance(value, dict)]
        unresolved_fields = {
            str(field)
            for variant in unresolved_variants
            for field in variant.get("unresolved_fields") or []
        }
        field_rows: dict[str, Any] = {}
        for field in fields:
            values: list[Any] = []
            for variant in literal_variants:
                options = variant.get("options")
                if isinstance(options, dict) and field in options:
                    values.append(options[field])
            for variant in unresolved_variants:
                options = variant.get("literal_options")
                if isinstance(options, dict) and field in options:
                    values.append(options[field])
            field_rows[field] = {
                "resolved_by_literal": bool(values),
                "unresolved_in_client": field in unresolved_fields,
                "domain_candidates": _domain_candidates(field, values, canonical, census),
            }
        parameterless = any(
            isinstance(variant.get("options"), dict) and not variant.get("options")
            for variant in literal_variants
        )
        rows.append({
            "command": command,
            "initially_advertised": command in advertised,
            "client_command_literal_hits": int(raw.get("hits") or 0),
            "serializer_shape_proven": True,
            "parameterless": parameterless,
            "option_fields": fields,
            "fields": field_rows,
            "literal_variants": literal_variants,
            "unresolved_variants": unresolved_variants,
            "client_wrappers": [str(value) for value in raw.get("wrappers") or []],
            "forwarded_options_parameters": [],
        })
    return rows


def _parse_post_payload(entry: dict[str, Any]) -> dict[str, Any] | None:
    request = entry.get("request")
    request = request if isinstance(request, dict) else {}
    post = request.get("postData")
    post = post if isinstance(post, dict) else {}
    text = str(post.get("text") or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except Exception:
        form = parse_qs(text, keep_blank_values=True)
        payload = {key: values[-1] if values else "" for key, values in form.items()}
        nested = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(nested, str) and nested.startswith("{"):
            try:
                decoded = json.loads(nested)
                if isinstance(decoded, dict):
                    payload = decoded
            except Exception:
                pass
    return payload if isinstance(payload, dict) else None


def _response_source(entry: dict[str, Any]) -> str:
    request = entry.get("request")
    request = request if isinstance(request, dict) else {}
    response = entry.get("response")
    response = response if isinstance(response, dict) else {}
    content = response.get("content")
    content = content if isinstance(content, dict) else {}
    url = str(request.get("url") or "").casefold()
    mime = str(content.get("mimeType") or "").casefold()
    if "javascript" not in mime and ".js" not in url:
        return ""
    text = content.get("text")
    if not isinstance(text, str) or not text:
        return ""
    if str(content.get("encoding") or "").casefold() == "base64":
        try:
            return base64.b64decode(text).decode("utf-8", errors="replace")
        except Exception:
            return ""
    return text


def scan_har_request_syntax(path: Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path or ""),
        "syntax": {},
        "wire_commands": {},
        "embedded_sources": 0,
        "source_text": "",
    }
    if path is None or not path.is_file():
        return result
    try:
        har = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return result
    log = har.get("log") if isinstance(har, dict) else None
    entries = log.get("entries") if isinstance(log, dict) else None
    if not isinstance(entries, list):
        return result

    source_parts: list[str] = []
    source_bytes = 0
    wire_commands: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        payload = _parse_post_payload(entry)
        if isinstance(payload, dict):
            command = str(payload.get("command") or "").strip()
            if command:
                options = payload.get("options")
                options = options if isinstance(options, dict) else {}
                row = wire_commands.setdefault(command, {"samples": 0, "option_fields": [], "variants": []})
                row["samples"] = int(row["samples"]) + 1
                for field in options:
                    text = str(field)
                    if text not in row["option_fields"]:
                        row["option_fields"].append(text)
                row["variants"].append({"options": sanitize(options), "source": "har-wire-observed"})
        source = _response_source(entry)
        if source:
            size = len(source.encode("utf-8", errors="replace"))
            if source_bytes + size <= _MAX_EMBEDDED_SOURCE_BYTES:
                source_parts.append(source)
                source_bytes += size

    embedded = "\n;\n".join(source_parts)
    syntax = scan_request_syntax(embedded)
    for command, wire in wire_commands.items():
        row = syntax.setdefault(command, {
            "hits": 0,
            "option_fields": [],
            "literal_variants": [],
            "unresolved_variants": [],
            "wrappers": [],
        })
        for field in wire.get("option_fields") or []:
            text = str(field)
            if text not in row["option_fields"]:
                row["option_fields"].append(text)
        row["literal_variants"].extend(
            dict(value) for value in wire.get("variants") or [] if isinstance(value, dict)
        )
        row["literal_variants"] = _unique_dicts(list(row["literal_variants"]))

    result["syntax"] = syntax
    result["wire_commands"] = wire_commands
    result["embedded_sources"] = len(source_parts)
    result["source_text"] = embedded
    return result


def build_wager_format(
    init_data: dict[str, Any],
    bundle: str,
    *,
    source: str = "",
    extra_syntax: dict[str, dict[str, Any]] | None = None,
    har_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    census = extract_finite_domains(init_data)
    canonical = canonical_wager_domains(init_data)
    commands = discover_command_formats(
        bundle,
        init_data,
        census=census,
        canonical=canonical,
        extra_syntax=extra_syntax,
    )
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
        "method": "har+init+client-request-syntax",
        "network_policy": "analysis only; no browser UI and no gameplay commands",
        "har": sanitize(har_meta or {}),
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
    candidates: list[str] = [str(game.url)] if game.url else []
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
    analysis_dir = provider.game_dir(game) / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    artifact = analysis_dir / "wager-format.json"

    selected_har = select_best_har(provider.game_dir(game))
    har = scan_har_request_syntax(selected_har)
    syntax = har.get("syntax")
    syntax = syntax if isinstance(syntax, dict) else {}
    progress(
        f"[{game.name}] FORMATO: HAR commands={len(syntax)}, embedded_sources={int(har.get('embedded_sources') or 0)}; sin UI."
    )

    session, launch_url = _resolve_launch(provider, game, timeout_s)
    if session is None or not launch_url:
        if syntax:
            payload = build_wager_format(
                {},
                str(har.get("source_text") or ""),
                source="har-embedded-client",
                extra_syntax=syntax,
                har_meta={
                    "path": str(selected_har or ""),
                    "embedded_sources": int(har.get("embedded_sources") or 0),
                    "wire_commands": sorted(str(key) for key in (har.get("wire_commands") or {})),
                },
            )
            atomic_write(artifact, payload)
            coverage = payload.get("coverage") or {}
            return WagerFormatResult(
                "PARCIAL",
                game.slug,
                artifact=str(artifact),
                commands=int(coverage.get("commands") or 0),
                domains=int(coverage.get("finite_domains") or 0),
                unresolved=int(coverage.get("unresolved_fields_without_domain") or 0),
                error="Sin demo fresco; gramática extraída del HAR",
            )
        return WagerFormatResult("SIN_DEMO", game.slug, artifact=str(artifact), error="No se pudo resolver demo fresco")

    try:
        runtime = bootstrap_game(session, launch_url, timeout_s=timeout_s)
        _response, _payload, init_data = post_command(runtime, "init", timeout_s=timeout_s, options={})
        bundle, source = _load_client_bundle(runtime, timeout_s=timeout_s)
        combined = "\n;\n".join(part for part in (bundle, str(har.get("source_text") or "")) if part)
        payload = build_wager_format(
            init_data,
            combined,
            source=source or "har-embedded-client",
            extra_syntax=syntax,
            har_meta={
                "path": str(selected_har or ""),
                "embedded_sources": int(har.get("embedded_sources") or 0),
                "wire_commands": sorted(str(key) for key in (har.get("wire_commands") or {})),
            },
        )
        atomic_write(artifact, payload)
        coverage = payload.get("coverage") or {}
        result = WagerFormatResult(
            "OK" if int(coverage.get("commands") or 0) else "PARCIAL",
            game.slug,
            artifact=str(artifact),
            commands=int(coverage.get("commands") or 0),
            domains=int(coverage.get("finite_domains") or 0),
            unresolved=int(coverage.get("unresolved_fields_without_domain") or 0),
            error="" if int(coverage.get("commands") or 0) else "No se detectó gramática command/options",
        )
        progress(
            f"[{game.name}] FORMATO {result.status}: commands={result.commands}, domains={result.domains}, unresolved={result.unresolved}."
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
    "scan_har_request_syntax",
]
