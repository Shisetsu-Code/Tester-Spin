from __future__ import annotations

import json
import threading
from typing import Any

from tester_spin.models import utc_now_iso
from tester_spin.providers.base import Progress
from tester_spin.providers.bgaming.har_capture import _is_bgaming_state_post
from tester_spin.structure.normalization import sanitize


def _capture_key(command: str, options: dict[str, Any]) -> str:
    return json.dumps(
        {"command": command, "options": sanitize(options)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def run_assisted_browser(
    *,
    game_name: str,
    launch_url: str,
    targets: list[dict[str, Any]],
    timeout_s: float,
    stop_event: threading.Event,
    progress: Progress,
    capture_matches: Any,
) -> tuple[list[dict[str, Any]], bool, str]:
    from playwright.sync_api import sync_playwright

    target_map = {
        str(item.get("command") or ""): [str(value) for value in item.get("fields") or []]
        for item in targets
    }
    captures: list[dict[str, Any]] = []
    markers: set[str] = set()
    browser_error = ""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.set_default_timeout(int(max(5.0, min(timeout_s, 30.0)) * 1000))

        def on_request(request: Any) -> None:
            try:
                if not _is_bgaming_state_post(request):
                    return
                try:
                    payload = request.post_data_json
                except Exception:
                    payload = None
                if not isinstance(payload, dict) or not capture_matches(payload, targets):
                    return
                command = str(payload.get("command") or "")
                options = payload.get("options")
                if not isinstance(options, dict):
                    return
                marker = _capture_key(command, options)
                if marker in markers:
                    return
                markers.add(marker)
                clean_options = sanitize(options)
                captures.append(
                    {
                        "at": utc_now_iso(),
                        "command": command,
                        "options": clean_options,
                        "target_fields": list(target_map.get(command) or []),
                    }
                )
                progress(
                    f"[{game_name}] ASISTIDO CAPTURA #{len(captures)}: "
                    f"{command} options={clean_options!r}."
                )
            except Exception:
                return

        page.on("request", on_request)
        try:
            page.goto(
                launch_url,
                wait_until="domcontentloaded",
                timeout=int(max(8.0, min(timeout_s, 30.0)) * 1000),
            )
            progress(
                f"[{game_name}] ASISTIDO: navegador listo. Probá todas las opciones visibles. "
                "Cuando termines, cerrá la ventana del juego. DETENER cancela la promoción."
            )
            while not stop_event.is_set() and not page.is_closed():
                page.wait_for_timeout(250)
        except Exception as exc:
            browser_error = f"{type(exc).__name__}: {exc}"
            progress(f"[{game_name}] ASISTIDO navegador ERROR: {browser_error}")
        finally:
            try:
                context.close()
            finally:
                browser.close()

    completed = bool(captures) and not browser_error and not stop_event.is_set()
    return captures, completed, browser_error


__all__ = ["run_assisted_browser"]
