from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any

import requests

from tester_spin.models import Game, utc_now_iso
from tester_spin.providers.base import Progress
from tester_spin.providers.bgaming.har_capture import _is_bgaming_state_post
from tester_spin.providers.bgaming.runtime import is_demo_url, resolve_fresh_demo_url
from tester_spin.structure.persistence import atomic_write
from tester_spin.ui_action_tree import UIActionTree, persist_ui_action_tree

_DOM_SELECTOR = (
    "button,[role='button'],a[href],[onclick],[tabindex],input[type='button'],"
    "input[type='submit'],[data-tester-spin-interactive]"
)
_ENTRY = re.compile(r"^(play|play demo|start|continue|ok|accept|enter|tap to play)$", re.I)
# Stable provider chrome. Named game controls (spin, buy, multiplier, cards, etc.)
# are intentionally NOT listed here.
_CHROME = re.compile(
    r"(?:sound|mute|volume|settings?|paytable|rules?|info|history|fullscreen|full screen|"
    r"language|help|home|menu|responsible|privacy|terms|turbo|autoplay|auto play)",
    re.I,
)
_POINTER_CURSORS = {"pointer", "hand"}


@dataclass(slots=True)
class DiscoveryResult:
    status: str
    game: str
    artifact: str = ""
    states: int = 0
    actions: int = 0
    unresolved: int = 0
    ready_for_farming: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "game": self.game,
            "artifact": self.artifact,
            "states": self.states,
            "actions": self.actions,
            "unresolved": self.unresolved,
            "ready_for_farming": self.ready_for_farming,
            "error": self.error,
        }


def _flow(response: Any) -> tuple[str, list[str]]:
    if not isinstance(response, dict):
        return "<ui-only>", []
    flow = response.get("flow")
    if not isinstance(flow, dict):
        return "<ui-only>", []
    state = str(flow.get("state") or "<ui-only>")
    raw = flow.get("available_actions")
    actions = [str(value) for value in raw] if isinstance(raw, list) else []
    return state, actions


def _label(value: dict[str, Any]) -> str:
    return " ".join(
        str(value.get(name) or "").strip()
        for name in ("text", "aria", "title", "label", "name", "role", "id", "class_name", "type")
        if str(value.get(name) or "").strip()
    )[:500]


def is_provider_chrome_candidate(candidate: dict[str, Any]) -> bool:
    # DOM and scene-graph nodes often expose stable semantic names. Canvas probes
    # intentionally stay unknown until an interaction proves what they do.
    if candidate.get("kind") not in {"dom", "scene"}:
        return False
    label = _label(candidate)
    return bool(label and _CHROME.search(label))


def _candidate_fingerprint(candidates: list[dict[str, Any]]) -> str:
    signatures = sorted(str(value.get("signature") or "") for value in candidates)
    raw = json.dumps(signatures, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _dom_candidates(page: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(list(page.frames)[:12]):
        try:
            locator = frame.locator(_DOM_SELECTOR)
            count = min(int(locator.count()), 120)
        except Exception:
            continue
        for index in range(count):
            item = locator.nth(index)
            try:
                if not item.is_visible(timeout=120):
                    continue
                raw = item.evaluate(
                    """el => ({
                      tag: (el.tagName || '').toLowerCase(),
                      text: (el.innerText || el.textContent || '').trim().replace(/\\s+/g,' ').slice(0,160),
                      aria: (el.getAttribute('aria-label') || '').trim().slice(0,160),
                      title: (el.getAttribute('title') || '').trim().slice(0,160),
                      role: (el.getAttribute('role') || '').trim().slice(0,80),
                      id: (el.id || '').slice(0,120),
                      class_name: typeof el.className === 'string' ? el.className.slice(0,180) : '',
                      disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true'
                    })"""
                )
                if not isinstance(raw, dict) or raw.get("disabled"):
                    continue
                semantic = {
                    "tag": raw.get("tag"), "text": raw.get("text"), "aria": raw.get("aria"),
                    "title": raw.get("title"), "role": raw.get("role"), "id": raw.get("id"),
                    "class_name": raw.get("class_name"),
                }
                signature = "dom:" + hashlib.sha256(
                    json.dumps([frame_index, semantic], ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest()[:20]
                rows.append({
                    "kind": "dom", "frame": frame_index, "dom_index": index,
                    "signature": signature, "label": _label(semantic),
                    "role": str(raw.get("role") or raw.get("tag") or ""), **semantic,
                })
            except Exception:
                continue
    return rows


def _scene_candidates(page: Any) -> list[dict[str, Any]]:
    """Best-effort live scene-graph introspection.

    BGaming titles commonly render controls inside Pixi/custom display trees, where
    there is no DOM button at all. We inspect only object graphs already reachable
    from window and only retain nodes that advertise interaction. Nothing found
    here is execution authority until a real click produces a real wire edge.
    """
    rows: list[dict[str, Any]] = []
    script = r"""() => {
      const out = [];
      const seen = new WeakSet();
      const queue = [];
      const push = (value, path, depth) => {
        if (!value || (typeof value !== 'object' && typeof value !== 'function') || depth > 8) return;
        if (seen.has(value)) return;
        seen.add(value);
        queue.push([value, path, depth]);
      };
      for (const name of Object.getOwnPropertyNames(window).slice(0, 700)) {
        try {
          const d = Object.getOwnPropertyDescriptor(window, name);
          if (!d || !('value' in d)) continue;
          const v = d.value;
          if (!v || (typeof v !== 'object' && typeof v !== 'function')) continue;
          if (Array.isArray(v.children) || v.stage || v.scene || v.root || v.app || v.application) {
            push(v, 'window.' + name, 0);
          }
        } catch (_) {}
      }
      const canvas = document.querySelector('canvas');
      const clientW = canvas ? (canvas.clientWidth || 0) : 0;
      const clientH = canvas ? (canvas.clientHeight || 0) : 0;
      const pixelW = canvas ? (canvas.width || clientW) : 0;
      const pixelH = canvas ? (canvas.height || clientH) : 0;
      let visited = 0;
      while (queue.length && visited++ < 5000 && out.length < 160) {
        const [obj, path, depth] = queue.shift();
        try {
          const eventMode = String(obj.eventMode || '');
          const cursor = String(obj.cursor || obj.buttonMode && 'pointer' || '');
          const ev = obj._events && typeof obj._events === 'object' ? Object.keys(obj._events) : [];
          const interactive = obj.interactive === true || obj.buttonMode === true ||
            eventMode === 'static' || eventMode === 'dynamic' || cursor === 'pointer' ||
            ev.some(k => /click|tap|pointerdown|pointerup|pointertap/i.test(k));
          const visible = obj.visible !== false && obj.renderable !== false && Number(obj.alpha ?? 1) > 0;
          if (interactive && visible) {
            let bounds = null;
            try { if (typeof obj.getBounds === 'function') bounds = obj.getBounds(); } catch (_) {}
            let point = null;
            if (bounds && Number.isFinite(bounds.x) && Number.isFinite(bounds.y) &&
                Number.isFinite(bounds.width) && Number.isFinite(bounds.height) &&
                bounds.width > 2 && bounds.height > 2) {
              const cx = bounds.x + bounds.width / 2;
              const cy = bounds.y + bounds.height / 2;
              let w = clientW, h = clientH;
              if (!(cx >= 0 && cy >= 0 && cx <= clientW * 1.25 && cy <= clientH * 1.25)) {
                w = pixelW; h = pixelH;
              }
              if (w > 0 && h > 0) {
                const nx = cx / w, ny = cy / h;
                if (nx >= 0 && nx <= 1 && ny >= 0 && ny <= 1) point = [nx, ny];
              }
            }
            const textValue = typeof obj.text === 'string' ? obj.text : '';
            out.push({
              path,
              name: String(obj.name || '').slice(0,120),
              label: String(obj.label || obj.accessibleTitle || '').slice(0,160),
              text: textValue.slice(0,160),
              type: String(obj.constructor && obj.constructor.name || '').slice(0,80),
              eventMode: eventMode.slice(0,40),
              cursor: cursor.slice(0,40),
              point,
            });
          }
          const children = Array.isArray(obj.children) ? obj.children : [];
          for (let i = 0; i < Math.min(children.length, 300); i++) {
            const child = children[i];
            const childName = child && (child.name || child.label || child.constructor && child.constructor.name) || i;
            push(child, path + '.children[' + i + ']<' + String(childName).slice(0,60) + '>', depth + 1);
          }
          for (const key of ['stage','scene','root','app','application']) {
            try {
              const child = obj[key];
              if (child && child !== obj) push(child, path + '.' + key, depth + 1);
            } catch (_) {}
          }
        } catch (_) {}
      }
      return out;
    }"""
    for frame_index, frame in enumerate(list(page.frames)[:12]):
        try:
            found = frame.evaluate(script)
        except Exception:
            continue
        if not isinstance(found, list):
            continue
        for raw in found:
            if not isinstance(raw, dict):
                continue
            point = raw.get("point")
            if not (isinstance(point, list) and len(point) == 2):
                continue
            semantic = {
                "name": str(raw.get("name") or ""),
                "label": str(raw.get("label") or ""),
                "text": str(raw.get("text") or ""),
                "type": str(raw.get("type") or ""),
                "path": str(raw.get("path") or "")[:500],
            }
            signature = "scene:" + hashlib.sha256(
                json.dumps([frame_index, semantic], ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()[:20]
            rows.append({
                "kind": "scene", "frame": frame_index, "canvas_index": 0,
                "signature": signature, "label": _label(semantic), "role": "scene-node",
                "point": [round(float(point[0]), 4), round(float(point[1]), 4)], **semantic,
            })
    return rows


def _cluster_pointer_cells(cells: set[tuple[int, int]], cols: int, rows: int) -> list[set[tuple[int, int]]]:
    pending = set(cells)
    groups: list[set[tuple[int, int]]] = []
    while pending:
        start = pending.pop()
        group = {start}
        stack = [start]
        while stack:
            x, y = stack.pop()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) in pending:
                    pending.remove((nx, ny))
                    group.add((nx, ny))
                    stack.append((nx, ny))
        groups.append(group)
    return groups


def _pointer_probe_points(cells: set[tuple[int, int]], cols: int, rows: int) -> tuple[list[list[float]], bool]:
    """Turn cursor evidence into candidate points.

    A single huge pointer cluster is not one button; many canvas engines simply set
    pointer on the whole surface. In that case emit a bounded probing lattice and
    let real UI/wire effects classify the points.
    """
    if not cells:
        return [], False
    groups = _cluster_pointer_cells(cells, cols, rows)
    largest = max((len(group) for group in groups), default=0)
    non_informative = len(groups) == 1 and largest >= max(8, int(cols * rows * 0.35))
    if non_informative:
        result: list[list[float]] = []
        probe_cols, probe_rows = 7, 4
        for py in range(probe_rows):
            for px in range(probe_cols):
                nx = (px + 0.5) / probe_cols
                ny = (py + 0.5) / probe_rows
                gx = min(cols - 1, max(0, int(nx * cols)))
                gy = min(rows - 1, max(0, int(ny * rows)))
                if (gx, gy) in cells:
                    result.append([round(nx, 4), round(ny, 4)])
        return result[:28], True
    result = []
    for group in groups:
        nx = sum((gx + 0.5) / cols for gx, _ in group) / len(group)
        ny = sum((gy + 0.5) / rows for _, gy in group) / len(group)
        result.append([round(nx, 4), round(ny, 4)])
    return result, False


def _canvas_candidates(page: Any, *, cols: int = 14, rows: int = 9) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(list(page.frames)[:12]):
        try:
            canvases = frame.locator("canvas")
            count = min(int(canvases.count()), 4)
        except Exception:
            continue
        for canvas_index in range(count):
            canvas = canvases.nth(canvas_index)
            try:
                if not canvas.is_visible(timeout=150):
                    continue
                box = canvas.bounding_box(timeout=300)
                if not box or box["width"] < 80 or box["height"] < 80:
                    continue
                active: set[tuple[int, int]] = set()
                for gy in range(rows):
                    for gx in range(cols):
                        x = box["x"] + (gx + 0.5) * box["width"] / cols
                        y = box["y"] + (gy + 0.5) * box["height"] / rows
                        page.mouse.move(x, y)
                        page.wait_for_timeout(4)
                        cursor = str(canvas.evaluate("el => getComputedStyle(el).cursor || el.style.cursor || ''") or "").lower()
                        if cursor in _POINTER_CURSORS:
                            active.add((gx, gy))
                points, probing = _pointer_probe_points(active, cols, rows)
                for point in points:
                    role = "canvas-probe" if probing else "canvas-zone"
                    signature = f"{role}:{frame_index}:{canvas_index}:{point[0]:.4f}:{point[1]:.4f}"
                    result.append({
                        "kind": role, "frame": frame_index, "canvas_index": canvas_index,
                        "signature": signature,
                        "label": "canvas behavior probe" if probing else "canvas interactive zone",
                        "role": role, "point": point,
                    })
            except Exception:
                continue
    return result


def scan_ui_candidates(page: Any) -> list[dict[str, Any]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    semantic = [*_dom_candidates(page), *_scene_candidates(page)]
    for candidate in semantic:
        signature = str(candidate.get("signature") or "")
        if signature and signature not in seen:
            seen.add(signature)
            rows.append(candidate)
    # Cursor probing is fallback evidence. Avoid duplicating a scene-graph hit at
    # approximately the same location.
    for candidate in _canvas_candidates(page):
        point = candidate.get("point")
        duplicate = False
        if isinstance(point, list) and len(point) == 2:
            for prior in rows:
                p = prior.get("point")
                if prior.get("frame") == candidate.get("frame") and isinstance(p, list) and len(p) == 2:
                    if abs(float(p[0]) - float(point[0])) <= 0.035 and abs(float(p[1]) - float(point[1])) <= 0.035:
                        duplicate = True
                        break
        if duplicate:
            continue
        signature = str(candidate.get("signature") or "")
        if signature and signature not in seen:
            seen.add(signature)
            rows.append(candidate)
    # Keep semantic candidates first; probes fill the remaining budget.
    return rows[:96]


def _install_dom_probe(context: Any) -> None:
    context.add_init_script(
        """(() => {
          const original = EventTarget.prototype.addEventListener;
          EventTarget.prototype.addEventListener = function(type, listener, options) {
            try {
              if (this instanceof Element && ['click','pointerdown','pointerup','touchstart'].includes(String(type))) {
                this.setAttribute('data-tester-spin-interactive', '1');
              }
            } catch (_) {}
            return original.call(this, type, listener, options);
          };
        })();"""
    )


def _dismiss_entry(page: Any) -> None:
    for frame in list(page.frames)[:12]:
        try:
            locator = frame.locator("button,[role='button'],a")
            for index in range(min(int(locator.count()), 20)):
                item = locator.nth(index)
                try:
                    if not item.is_visible(timeout=100):
                        continue
                    text = str(item.inner_text(timeout=100) or "").strip()
                    aria = str(item.get_attribute("aria-label") or "").strip()
                    if _ENTRY.match(text or aria):
                        item.click(timeout=500, force=True)
                        page.wait_for_timeout(600)
                except Exception:
                    continue
        except Exception:
            continue


def _click_candidate(page: Any, candidate: dict[str, Any]) -> None:
    frame_index = int(candidate.get("frame") or 0)
    frames = list(page.frames)
    if frame_index >= len(frames):
        raise RuntimeError("UI frame disappeared during replay")
    frame = frames[frame_index]
    if candidate.get("kind") == "dom":
        locator = frame.locator(_DOM_SELECTOR).nth(int(candidate.get("dom_index") or 0))
        locator.click(timeout=1200, force=True)
        return
    if candidate.get("kind") in {"canvas-zone", "canvas-probe", "scene"}:
        canvas = frame.locator("canvas").nth(int(candidate.get("canvas_index") or 0))
        box = canvas.bounding_box(timeout=500)
        if not box:
            raise RuntimeError("Canvas disappeared during replay")
        point = candidate.get("point") or [0.5, 0.5]
        page.mouse.click(box["x"] + float(point[0]) * box["width"], box["y"] + float(point[1]) * box["height"])
        return
    raise RuntimeError("Unsupported UI candidate kind")


def _session_launch_url(game: Game, timeout_s: float) -> str:
    session = requests.Session()
    try:
        if is_demo_url(game.url):
            return game.url
        return str(resolve_fresh_demo_url(session, game.url, timeout_s=timeout_s) or "")
    finally:
        session.close()


def _run_path(
    game: Game,
    path: tuple[dict[str, Any], ...],
    *,
    timeout_s: float,
    headless: bool,
    stop_event: threading.Event,
) -> tuple[UIActionTree, str | None, list[dict[str, Any]], bool]:
    from playwright.sync_api import sync_playwright

    tree = UIActionTree("bgaming", game.slug, "bgaming-live-ui")
    launch_url = _session_launch_url(game, timeout_s)
    if not launch_url:
        tree.unresolved("launch", "No fresh demo launch could be resolved for this session")
        return tree, None, [], False

    events: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless, args=["--autoplay-policy=no-user-gesture-required"])
        context = browser.new_context(viewport={"width": 1440, "height": 900}, service_workers="block")
        _install_dom_probe(context)
        page = context.new_page()
        page.set_default_timeout(int(max(5.0, min(timeout_s, 30.0)) * 1000))

        def on_response(response: Any) -> None:
            try:
                request = response.request
                if not _is_bgaming_state_post(request):
                    return
                try:
                    payload = request.post_data_json
                except Exception:
                    payload = {}
                try:
                    data = response.json()
                except Exception:
                    data = None
                if isinstance(payload, dict) and isinstance(data, dict):
                    events.append({"request": payload, "response": data})
            except Exception:
                return

        page.on("response", on_response)
        try:
            page.goto(launch_url, wait_until="domcontentloaded", timeout=int(max(8.0, min(timeout_s, 30.0)) * 1000))
            page.wait_for_timeout(2600)
            _dismiss_entry(page)
            page.wait_for_timeout(1200)
            if stop_event.is_set():
                return tree, None, [], False

            last_response = events[-1]["response"] if events else None
            server_state, available = _flow(last_response)
            current_candidates = scan_ui_candidates(page)
            local_fp = "" if events else _candidate_fingerprint(current_candidates)
            state_id = tree.state(server_state, available, local_fingerprint=local_fp)

            for wanted in path:
                if stop_event.is_set():
                    return tree, state_id, [], False
                candidates = scan_ui_candidates(page)
                found = next((value for value in candidates if value.get("signature") == wanted.get("signature")), None)
                if found is None:
                    tree.unresolved(str(wanted.get("signature")), "UI candidate could not be replayed in fresh session")
                    return tree, state_id, candidates, False
                candidate_id = tree.candidate(state_id, found)
                before_event_count = len(events)
                before_fp = _candidate_fingerprint(candidates)
                _click_candidate(page, found)
                page.wait_for_timeout(2200)
                new_events = events[before_event_count:]
                if new_events:
                    for offset, event in enumerate(new_events):
                        response_state, response_actions = _flow(event["response"])
                        next_state = tree.state(response_state, response_actions)
                        tree.edge(
                            state_id,
                            candidate_id if offset == 0 else None,
                            request=event["request"], response=event["response"], to_state=next_state,
                            evidence="WIRE_OBSERVED", automatic=offset > 0,
                        )
                        state_id = next_state
                        candidate_id = None
                    continue
                after_candidates = scan_ui_candidates(page)
                after_fp = _candidate_fingerprint(after_candidates)
                if after_fp != before_fp:
                    next_state = tree.state(server_state, available, local_fingerprint=after_fp)
                    tree.edge(state_id, candidate_id, request=None, response=None, to_state=next_state,
                              evidence="UI_LOCAL_OBSERVED", automatic=False)
                    state_id = next_state
                else:
                    tree.mark_noise(candidate_id, "Interaction produced neither provider wire traffic nor a changed control surface")
                    return tree, state_id, after_candidates, False

            final_candidates = scan_ui_candidates(page)
            return tree, state_id, final_candidates, True
        finally:
            context.close()
            browser.close()


def _candidate_summary(candidates: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    labels: list[str] = []
    for value in candidates:
        kind = str(value.get("kind") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
        label = str(value.get("label") or "").strip()
        if label and label not in labels and label not in {"canvas behavior probe", "canvas interactive zone"}:
            labels.append(label[:60])
    kinds = ",".join(f"{key}={counts[key]}" for key in sorted(counts)) or "none"
    return kinds + ("; labels=" + " | ".join(labels[:5]) if labels else "")


def discover_game_ui_first(
    provider: Any,
    game: Game,
    *,
    timeout_s: float,
    stop_event: threading.Event,
    progress: Progress,
    max_paths: int = 64,
    max_depth: int = 10,
    max_sessions: int = 3,
) -> DiscoveryResult:
    """Explore one BGaming game through independent real-client sessions.

    UI First stays completely separate from HTTP/exhaustive farming. Mutually
    exclusive branches are replayed from independent browser contexts/processes and
    their evidence is merged only after each worker returns, so cookies/session ids
    and round state are never shared between branches.
    """
    game_dir = provider.game_dir(game)
    artifact_dir = game_dir / "analysis" / "ui-first"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = artifact_dir / "runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "result.json"
    tree = UIActionTree("bgaming", game.slug, "bgaming-live-ui")

    # Fail fast before spawning several browsers if no demo is resolvable at all.
    progress(f"[{game.name}] UI FIRST: resolviendo demo fresco...")
    initial_launch = _session_launch_url(game, timeout_s)
    if not initial_launch:
        result = DiscoveryResult("SIN_DEMO", game.slug, error="No se pudo resolver un launch demo fresco.")
        atomic_write(summary_path, result.to_dict())
        return result

    headless = os.environ.get("TESTER_SPIN_UI_FIRST_HEADLESS", "1").strip().lower() not in {"0", "false", "no"}
    max_sessions = max(1, min(int(max_sessions), 8))
    queue: deque[tuple[dict[str, Any], ...]] = deque([tuple()])
    queued = {tuple()}
    submitted = 0
    completed = 0
    frontier_exhausted = True

    progress(
        f"[{game.name}] UI FIRST: explorando cliente real; max_paths={max_paths}, max_depth={max_depth}, "
        f"sessions={max_sessions}, headless={headless}."
    )
    with ThreadPoolExecutor(max_workers=max_sessions, thread_name_prefix="bgaming-ui-first") as pool:
        while queue and not stop_event.is_set():
            if submitted >= max_paths:
                frontier_exhausted = False
                tree.unresolved("frontier", f"Exploration stopped at max_paths={max_paths}")
                break

            batch: list[tuple[int, tuple[dict[str, Any], ...]]] = []
            while queue and len(batch) < max_sessions and submitted < max_paths:
                path = queue.popleft()
                submitted += 1
                batch.append((submitted, path))

            futures = {
                pool.submit(
                    _run_path, game, path, timeout_s=timeout_s, headless=headless, stop_event=stop_event
                ): (sequence, path)
                for sequence, path in batch
            }
            for future in as_completed(futures):
                sequence, path = futures[future]
                completed += 1
                try:
                    fragment, state_id, candidates, replay_ok = future.result()
                    tree.merge(fragment)
                except Exception as exc:
                    tree.unresolved(
                        "path:" + "/".join(str(item.get("signature")) for item in path),
                        "Browser replay failed: " + type(exc).__name__,
                    )
                    progress(f"[{game.name}] UI FIRST path {sequence}: {type(exc).__name__}")
                    continue
                if state_id is None:
                    progress(f"[{game.name}] UI FIRST path {sequence}: no state; fresh launch unresolved")
                    continue
                state_row = tree.data["states"].get(state_id, {})
                progress(
                    f"[{game.name}] UI FIRST path {sequence}: depth={len(path)}, candidates={len(candidates)}, "
                    f"state={state_row.get('server_state')}, actions={state_row.get('available_actions')}, "
                    f"{_candidate_summary(candidates)}"
                )
                if len(path) >= max_depth:
                    if candidates:
                        frontier_exhausted = False
                        tree.unresolved(state_id, f"UI depth guard reached ({max_depth})")
                    continue
                for candidate in candidates:
                    cid = tree.candidate(state_id, candidate)
                    if is_provider_chrome_candidate(candidate):
                        tree.mark_provider_chrome(cid, "Known BGaming chrome/control unrelated to game-state wagering")
                        continue
                    row = tree.data["candidates"][cid]
                    if row.get("classification") in {"action", "local_action", "provider_chrome", "no_effect"}:
                        continue
                    next_path = (*path, candidate)
                    signature_path = tuple(str(item.get("signature")) for item in next_path)
                    if signature_path in queued:
                        continue
                    queued.add(signature_path)
                    queue.append(next_path)

    if stop_event.is_set():
        frontier_exhausted = False
        tree.unresolved("frontier", "Discovery stopped by user")
    if queue:
        frontier_exhausted = False

    payload = persist_ui_action_tree(
        artifact_dir / "action-tree.json", tree, run_key=stamp,
        frontier_exhausted=frontier_exhausted and not queue,
    )
    atomic_write(run_dir / "action-tree.json", payload)
    coverage = payload.get("coverage") or {}
    active_unresolved = int(coverage.get("unresolved_server_actions") or 0) + int(coverage.get("untried") or 0)
    if not coverage.get("frontier_exhausted"):
        active_unresolved += 1
    result = DiscoveryResult(
        "READY" if coverage.get("ready_for_farming") else "PARCIAL",
        game.slug,
        artifact=str(artifact_dir / "action-tree.json"),
        states=int(coverage.get("states") or 0),
        actions=int(coverage.get("actions") or 0),
        unresolved=active_unresolved,
        ready_for_farming=bool(coverage.get("ready_for_farming")),
    )
    atomic_write(summary_path, {
        **result.to_dict(), "finished_at": utc_now_iso(),
        "submitted_paths": submitted, "completed_paths": completed, "max_sessions": max_sessions,
    })
    progress(
        f"[{game.name}] UI FIRST {result.status}: states={result.states}, actions={result.actions}, "
        f"unresolved={result.unresolved}, ready_for_farming={result.ready_for_farming}."
    )
    return result


__all__ = [
    "DiscoveryResult", "discover_game_ui_first", "is_provider_chrome_candidate",
    "scan_ui_candidates", "_cluster_pointer_cells", "_pointer_probe_points",
]
