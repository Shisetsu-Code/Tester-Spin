from __future__ import annotations

import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
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
  const state = {seq: 0, last: performance.now()};
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


# Unlike the visible-card collector, this intentionally ignores CSS visibility.
# The HAR shows Load More can reveal cards already present client-side and only then
# lazy-load their images. If those cards already exist in the DOM, reading them now
# eliminates most or all Load More clicks.
ALL_CARD_SNAPSHOT_JS = r"""
() => {
  const attrMap = (el) => {
    const out = {};
    if (!el || !el.attributes) return out;
    for (const a of Array.from(el.attributes)) {
      if (a && a.name && a.value) out[a.name] = a.value;
    }
    return out;
  };

  const sourceCandidates = (img) => [
    img.getAttribute('data-src') || '',
    img.getAttribute('data-lazy-src') || '',
    img.getAttribute('data-original') || '',
    img.getAttribute('src') || '',
    img.currentSrc || '',
    img.getAttribute('data-srcset') || '',
    img.getAttribute('srcset') || '',
  ].filter(Boolean);

  const sourceFor = (img) => {
    const values = sourceCandidates(img);
    return values.find(v => /(?:339x180|338x180|340x180|300x160|600x320)/i.test(v)) ||
           values.find(v => /\/wp-content\/uploads\//i.test(v)) ||
           values[0] || '';
  };

  const gameishImage = (img) => {
    const values = sourceCandidates(img);
    const joined = values.join(' ');
    const alt = (img.alt || img.title || '').trim();
    if (/(?:339x180|338x180|340x180|300x160|600x320)/i.test(joined)) return true;
    if (/\/wp-content\/uploads\//i.test(joined) && alt.length >= 2) return true;
    return false;
  };

  const chooseCard = (img) => {
    let node = img;
    let best = img.parentElement || img;
    for (let i = 0; i < 9 && node && node.parentElement; i++) {
      node = node.parentElement;
      const controls = node.querySelectorAll(
        'a,button,[role="button"],[data-href],[data-url],[data-game],[data-slug],[onclick]'
      );
      const gameImgs = Array.from(node.querySelectorAll('img')).filter(gameishImage);
      const text = (node.innerText || node.textContent || '').trim();
      if (gameImgs.length >= 1 && gameImgs.length <= 4 && (controls.length >= 1 || text.length > 0)) {
        best = node;
        if (gameImgs.length === 1) break;
      }
    }
    return best;
  };

  const cards = [];
  const seen = new Set();
  for (const img of Array.from(document.querySelectorAll('img')).filter(gameishImage)) {
    const card = chooseCard(img);
    const src = sourceFor(img);
    const key = src + '|' + (img.alt || '') + '|' + (card.textContent || '').slice(0, 160);
    if (seen.has(key)) continue;
    seen.add(key);

    const links = [];
    for (const el of Array.from(card.querySelectorAll(
      'a,button,[role="button"],[data-href],[data-url],[data-game],[data-slug],[onclick]'
    ))) {
      links.push({
        tag: el.tagName,
        text: (el.innerText || el.textContent || el.value || '').trim().slice(0, 300),
        href: el.href || el.getAttribute('href') || '',
        attrs: attrMap(el),
      });
    }

    const cardAttrs = [];
    let p = card;
    for (let depth = 0; depth < 5 && p; depth++, p = p.parentElement) {
      cardAttrs.push({tag: p.tagName, attrs: attrMap(p)});
    }

    cards.push({
      text: (card.innerText || card.textContent || '').trim().slice(0, 1200),
      image: {
        src,
        raw_src: img.getAttribute('src') || '',
        alt: img.alt || '',
        title: img.title || '',
        width: Number(img.getAttribute('width') || 0),
        height: Number(img.getAttribute('height') || 0),
        attrs: attrMap(img),
      },
      links,
      card_attrs: cardAttrs,
    });
  }
  return cards;
}
"""


def _all_snapshot(page) -> list[dict[str, Any]]:
    try:
        value = page.evaluate(ALL_CARD_SNAPSHOT_JS)
        return value if isinstance(value, list) else []
    except Exception:
        return []


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
    """Fast catalog crawler for Pragmatic's preloaded/lazy-visible game grid.

    First enumerate game-like cards regardless of CSS visibility. A single Load More
    click is then enough to tell whether the site is merely revealing already-known
    cards or structurally appending new cards. Structural additions are followed
    until they stop; visibility-only pagination terminates immediately because all
    hidden cards have already been captured.
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
            if on_game is not None:
                on_game(game)
            progress(f"  + [{source}] {game.name} — {game.url}")
        return new_count

    progress(f"Catálogo Pragmatic FAST-DOM — {provider.catalog_url}")
    progress("Modo rápido: enumera tarjetas ocultas/preloaded; Load More queda como verificación/fallback.")

    from playwright.sync_api import sync_playwright

    loads_done = 0
    final_snapshot: list[dict[str, Any]] = []
    preloaded_complete = False

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="en-US")
        page = context.new_page()
        try:
            page.goto(provider.catalog_url, wait_until="domcontentloaded", timeout=60_000)
            for label in ("Accept All", "Accept all", "Allow all", "I agree"):
                try:
                    control = page.get_by_role("button", name=re.compile(re.escape(label), re.I))
                    if control.count() and control.first.is_visible():
                        control.first.click(timeout=1_000)
                        break
                except Exception:
                    pass

            _install_mutation_observer(page)
            page.wait_for_timeout(150)

            visible_initial = _snapshot(page)
            current = _all_snapshot(page)
            if not current:
                current = visible_initial
            current_keys = _snapshot_keys(current, provider.catalog_url)

            provider._write_json(diag_root / "all-cards-0000.json", current)
            ingest(current, "preloaded-dom:0")
            progress(
                f"DOM inicial: visibles={len(visible_initial)}, todas={len(current)}, "
                f"juegos={len(by_slug)}"
            )

            while loads_done < max_loads and not stop_event.is_set():
                control = _find_load_more(page)
                if control is None:
                    progress("Load More Games ya no está visible: catálogo agotado.")
                    break

                before_keys = current_keys
                before_seq = _mutation_seq(page)
                loads_done += 1

                try:
                    strategy = _click_load_more(page, control)
                except Exception as exc:
                    progress(f"No se pudo activar Load More: {type(exc).__name__}: {exc}")
                    break

                _wait_for_dom_update(page, before_seq)
                after = _all_snapshot(page)
                if not after:
                    after = _snapshot(page)
                after_keys = _snapshot_keys(after, provider.catalog_url)
                structural_delta = _delta_snapshots(after, before_keys, provider.catalog_url)

                if not structural_delta:
                    # One short frame/lazy-load retry. If still no new structural card,
                    # this click only changed visibility of cards already captured.
                    page.wait_for_timeout(180)
                    after = _all_snapshot(page) or _snapshot(page)
                    after_keys = _snapshot_keys(after, provider.catalog_url)
                    structural_delta = _delta_snapshots(after, before_keys, provider.catalog_url)

                new_count = ingest(structural_delta, f"appended-dom:{loads_done}")
                current = after
                current_keys = after_keys

                if structural_delta:
                    provider._write_json(
                        diag_root / f"delta-cards-{loads_done:04d}.json",
                        structural_delta,
                    )
                    progress(
                        f"Load More #{loads_done}: click={strategy}, "
                        f"+estructurales={len(structural_delta)}, +juegos={new_count}, total={len(by_slug)}"
                    )
                    continue

                preloaded_complete = True
                progress(
                    f"Load More #{loads_done}: click={strategy}, sin tarjetas estructurales nuevas. "
                    f"Las tarjetas restantes ya estaban precargadas; total={len(by_slug)}."
                )
                break

            final_snapshot = current
        except Exception:
            try:
                provider._write_json(diag_root / "all-cards-error.json", _all_snapshot(page))
                (diag_root / "dom-error.html").write_text(page.content(), encoding="utf-8")
            except Exception:
                pass
            raise
        finally:
            context.close()
            browser.close()

    provider._write_json(diag_root / "all-cards-final.json", final_snapshot)

    games = sorted(by_slug.values(), key=lambda item: item.name.casefold())
    provider._write_catalog_index(games)

    # The GUI receives games immediately during enumeration. Native thumbnail and
    # game.json persistence is intentionally deferred so it cannot block Load More.
    if games and not stop_event.is_set():
        workers = min(10, max(4, len(games) // 25 + 1))
        progress(f"Enumeración terminada: {len(games)} juegos. Miniaturas en paralelo ({workers} workers)...")
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
                if on_game is not None:
                    on_game(game)
                if completed % 25 == 0 or completed == len(games):
                    progress(f"Miniaturas/metadata: {completed}/{len(games)}; errores={errors}")

    provider._write_catalog_index(games)
    provider._write_json(
        diag_root / "summary.json",
        {
            "schema": "tester-spin/pragmatic-fast-dom-catalog/v2",
            "updated_at": utc_now_iso(),
            "count": len(games),
            "loads_done": loads_done,
            "preloaded_complete": preloaded_complete,
            "strategy": "hidden/preloaded DOM enumeration + structural Load More verification + parallel persistence",
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
