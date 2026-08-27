from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from tester_spin.models import Game, utc_now_iso
from tester_spin.providers.base import GameCallback, Progress
from tester_spin.providers.pragmatic import _human_from_slug
from tester_spin.providers.pragmatic_catalog_dom import (
    _click_load_more,
    _find_load_more,
    _snapshot,
    snapshot_to_game,
)


MUTATION_OBSERVER_JS = r"""
() => {
  if (window.__testerSpinCatalogMutation) return;
  const state = {
    seq: 0,
    last: performance.now(),
  };
  const observer = new MutationObserver((records) => {
    state.seq += Math.max(1, records.length);
    state.last = performance.now();
  });
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: [
      'class', 'style', 'hidden', 'aria-hidden',
      'src', 'srcset', 'data-src', 'data-lazy-src', 'data-srcset'
    ],
  });
  window.__testerSpinCatalogMutation = state;
}
"""


def _snapshot_key(snapshot: dict[str, Any], base_url: str) -> str:
    game = snapshot_to_game(snapshot, base_url)
    if game is not None and game.slug:
        return game.slug
    image = snapshot.get("image") or {}
    return str(image.get("src") or image.get("raw_src") or "").strip()


def _snapshot_keys(snapshots: list[dict[str, Any]], base_url: str) -> set[str]:
    return {key for item in snapshots if (key := _snapshot_key(item, base_url))}


def _delta_snapshots(
    snapshots: list[dict[str, Any]],
    previous_keys: set[str],
    base_url: str,
) -> list[dict[str, Any]]:
    return [item for item in snapshots if (key := _snapshot_key(item, base_url)) and key not in previous_keys]


def _install_mutation_observer(page) -> None:
    try:
        page.evaluate(MUTATION_OBSERVER_JS)
    except Exception:
        pass


def _mutation_seq(page) -> int:
    try:
        value = page.evaluate(
            "() => Number((window.__testerSpinCatalogMutation || {}).seq || 0)"
        )
        return int(value or 0)
    except Exception:
        return 0


def _wait_for_dom_update(page, before_seq: int) -> None:
    """Wait for actual DOM activity, not an arbitrary multi-second sleep.

    Load More in the observed Pragmatic catalog changes visibility/classes and starts
    lazy image loading. MutationObserver lets us react as soon as that happens. A
    short fallback covers animation/frame scheduling without turning every click
    into the previous 15-second polling loop.
    """
    try:
        page.wait_for_function(
            "before => Number((window.__testerSpinCatalogMutation || {}).seq || 0) > before",
            arg=before_seq,
            timeout=900,
        )
    except Exception:
        page.wait_for_timeout(80)

    try:
        page.wait_for_function(
            "quiet => performance.now() - Number((window.__testerSpinCatalogMutation || {}).last || 0) >= quiet",
            arg=90,
            timeout=650,
        )
    except Exception:
        pass


def _persist_one(provider, game: Game, source: str) -> tuple[Game, str]:
    try:
        provider._persist_catalog_artifacts(game, source)
        return game, ""
    except Exception as exc:
        return game, f"{type(exc).__name__}: {exc}"


def crawl_pragmatic_catalog_fast(
    provider,
    *,
    stop_event: threading.Event,
    progress: Progress,
    max_pages: int,
    on_game: GameCallback | None = None,
) -> list[Game]:
    """Fast Load More crawler for Pragmatic's preloaded/lazy-visible catalog.

    Performance properties:
    - one full DOM snapshot per successful click instead of repeated 250 ms rescans;
    - MutationObserver-driven settling, normally hundreds of ms rather than 15 s;
    - no full-page HTML write on successful clicks;
    - new games are emitted immediately, before thumbnail network I/O;
    - thumbnail/game.json persistence runs concurrently after enumeration.
    """
    by_slug: dict[str, Game] = {}
    persistence_source: dict[str, str] = {}
    max_loads = max(1, int(max_pages))
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    diag_root = provider.provider_root / "catalog-diagnostics" / f"{stamp}-fast-dom"
    diag_root.mkdir(parents=True, exist_ok=True)

    def ingest(snapshots: list[dict[str, Any]], source: str) -> int:
        new_count = 0
        for snap in snapshots:
            game = snapshot_to_game(snap, provider.catalog_url)
            if game is None:
                continue
            current = by_slug.get(game.slug)
            if current is not None:
                if not current.thumbnail_url and game.thumbnail_url:
                    current.thumbnail_url = game.thumbnail_url
                if current.name == _human_from_slug(game.slug) and game.name != current.name:
                    current.name = game.name
                continue

            by_slug[game.slug] = game
            persistence_source[game.slug] = source
            new_count += 1

            # Do not block catalog discovery on thumbnail HTTP and disk writes.
            if on_game is not None:
                on_game(game)
            progress(f"  + [{source}] {game.name} — {game.url}")
        return new_count

    progress(f"Catálogo Pragmatic FAST-DOM — {provider.catalog_url}")
    progress("Modo rápido: MutationObserver + delta DOM; miniaturas diferidas y paralelas.")

    from playwright.sync_api import sync_playwright

    loads_done = 0
    no_growth = 0
    final_snapshot: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="en-US")
        page = context.new_page()
        try:
            page.goto(provider.catalog_url, wait_until="domcontentloaded", timeout=60_000)
            for label in ("Accept All", "Accept all", "Allow all", "I agree"):
                try:
                    import re

                    control = page.get_by_role("button", name=re.compile(re.escape(label), re.I))
                    if control.count() and control.first.is_visible():
                        control.first.click(timeout=1_000)
                        break
                except Exception:
                    pass

            _install_mutation_observer(page)
            page.wait_for_timeout(150)

            current = _snapshot(page)
            current_keys = _snapshot_keys(current, provider.catalog_url)
            provider._write_json(diag_root / "visible-cards-0000.json", current)
            ingest(current, "fast-dom:0")
            progress(f"DOM inicial: tarjetas={len(current)}, juegos={len(by_slug)}")

            while loads_done < max_loads and not stop_event.is_set():
                control = _find_load_more(page)
                if control is None:
                    progress("Load More Games ya no está visible: catálogo agotado.")
                    break

                loads_done += 1
                before_keys = current_keys
                before_count = len(current)
                before_seq = _mutation_seq(page)

                try:
                    strategy = _click_load_more(page, control)
                except Exception as exc:
                    progress(f"No se pudo activar Load More: {type(exc).__name__}: {exc}")
                    break

                _wait_for_dom_update(page, before_seq)
                after = _snapshot(page)
                after_keys = _snapshot_keys(after, provider.catalog_url)
                delta = _delta_snapshots(after, before_keys, provider.catalog_url)

                # One compact retry is enough for a requestAnimationFrame / lazy-load
                # edge case, while avoiding the old 15 s polling loop.
                if not delta and len(after) <= before_count:
                    page.wait_for_timeout(180)
                    after = _snapshot(page)
                    after_keys = _snapshot_keys(after, provider.catalog_url)
                    delta = _delta_snapshots(after, before_keys, provider.catalog_url)

                new_count = ingest(delta, f"fast-dom:{loads_done}")
                current = after
                current_keys = after_keys

                if delta:
                    provider._write_json(diag_root / f"delta-cards-{loads_done:04d}.json", delta)

                progress(
                    f"Load More #{loads_done}: click={strategy}, +tarjetas={len(delta)}, "
                    f"+juegos={new_count}, total={len(by_slug)}"
                )

                if delta or new_count:
                    no_growth = 0
                    continue

                no_growth += 1
                progress(f"Click sin crecimiento ({no_growth}/2); guardando diagnóstico completo.")
                provider._write_json(diag_root / f"visible-cards-stall-{loads_done:04d}.json", after)
                try:
                    (diag_root / f"dom-stall-{loads_done:04d}.html").write_text(
                        page.content(), encoding="utf-8"
                    )
                except Exception:
                    pass
                if no_growth >= 2:
                    break

            final_snapshot = current
        finally:
            context.close()
            browser.close()

    provider._write_json(diag_root / "visible-cards-final.json", final_snapshot)

    games = sorted(by_slug.values(), key=lambda item: item.name.casefold())
    provider._write_catalog_index(games)

    # Thumbnails are useful for the GUI but should not serialize discovery.
    if games and not stop_event.is_set():
        workers = min(12, max(4, len(games) // 20 + 1))
        progress(f"Catálogo enumerado: {len(games)} juegos. Guardando miniaturas con {workers} workers...")
        errors = 0
        completed = 0
        futures: list[Future[tuple[Game, str]]] = []
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="catalog-artifact") as pool:
            for game in games:
                futures.append(
                    pool.submit(
                        _persist_one,
                        provider,
                        game,
                        persistence_source.get(game.slug, provider.catalog_url),
                    )
                )

            for future in as_completed(futures):
                if stop_event.is_set():
                    for pending in futures:
                        pending.cancel()
                    break
                game, error = future.result()
                completed += 1
                if error:
                    errors += 1
                    progress(f"[{game.name}] miniatura/metadata: {error}")
                # Refresh storage/UI now that thumbnail_path may be available.
                if on_game is not None:
                    on_game(game)
                if completed % 25 == 0 or completed == len(games):
                    progress(f"Miniaturas/metadata: {completed}/{len(games)}; errores={errors}")

    provider._write_catalog_index(games)
    provider._write_json(
        diag_root / "summary.json",
        {
            "schema": "tester-spin/pragmatic-fast-dom-catalog/v1",
            "updated_at": utc_now_iso(),
            "count": len(games),
            "loads_done": loads_done,
            "strategy": "mutation-observer + delta snapshots + parallel artifact persistence",
            "games": [
                {
                    "name": game.name,
                    "slug": game.slug,
                    "url": game.url,
                    "thumbnail_url": game.thumbnail_url,
                    "thumbnail_path": game.thumbnail_path,
                }
                for game in games
            ],
        },
    )
    progress(f"Catálogo FAST terminado: {len(games)} juegos; Load More={loads_done}.")
    return games
