from __future__ import annotations

import argparse
import json
from pathlib import Path
import threading

from tester_spin.models import Game
from tester_spin.providers import BGamingProvider
from tester_spin.providers.bgaming.assisted_resolution import resolve_game_assisted


def _game_from_row(row: dict) -> Game:
    return Game(
        provider="bgaming",
        slug=str(row.get("slug") or ""),
        name=str(row.get("name") or row.get("slug") or ""),
        url=str(row.get("url") or row.get("public_url") or row.get("demo_url") or ""),
        thumbnail_url=str(row.get("thumbnail_url") or ""),
        thumbnail_path=str(row.get("thumbnail_path") or ""),
        symbol=str(row.get("identifier") or ""),
    )


def _load_game(provider: BGamingProvider, query: str) -> Game:
    catalog = provider.provider_root / "catalog.json"
    if not catalog.is_file():
        raise RuntimeError("No existe data/providers/bgaming/catalog.json; cargá el catálogo desde la GUI primero.")
    raw = json.loads(catalog.read_text(encoding="utf-8"))
    rows = [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []
    needle = query.strip().casefold()
    exact = [
        row for row in rows
        if str(row.get("slug") or "").casefold() == needle
        or str(row.get("name") or "").casefold() == needle
    ]
    matches = exact or [
        row for row in rows
        if needle in str(row.get("slug") or "").casefold()
        or needle in str(row.get("name") or "").casefold()
    ]
    if not matches:
        raise RuntimeError(f"No encontré BGaming {query!r} en el catálogo local.")
    if len(matches) > 1:
        names = ", ".join(str(row.get("name") or row.get("slug") or "") for row in matches[:12])
        raise RuntimeError(f"La búsqueda es ambigua; coincidencias: {names}")
    game = _game_from_row(matches[0])
    if not game.url:
        raise RuntimeError("El juego seleccionado no tiene URL pública/demo utilizable.")
    return game


def main() -> int:
    parser = argparse.ArgumentParser(description="BGaming human-assisted wager-format resolution")
    parser.add_argument("game", help="nombre o slug del juego, por ejemplo: Adventures")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    data_root = Path.cwd() / "data"
    provider = BGamingProvider(data_root)
    game = _load_game(provider, args.game)
    stop_event = threading.Event()

    print(f"=== RESOLUCIÓN ASISTIDA: {game.name} ===", flush=True)
    print("Probá todas las opciones visibles que correspondan a la elección pendiente y cerrá Chromium cuando termines.", flush=True)
    try:
        result = resolve_game_assisted(
            provider,
            game,
            timeout_s=max(8.0, float(args.timeout)),
            stop_event=stop_event,
            progress=lambda message: print(message, flush=True),
        )
    except KeyboardInterrupt:
        stop_event.set()
        print("Cancelado por usuario.", flush=True)
        return 130

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), flush=True)
    return 0 if result.status in {"READY", "PARCIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
