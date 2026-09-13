from __future__ import annotations

from typing import Any

from tester_spin.providers.bgaming import ui_first as base
from tester_spin.providers.bgaming.canvas_behavior import (
    filter_canvas_dom_candidates,
    probe_grid_points,
)

_ORIGINAL_DOM = base._dom_candidates
_ORIGINAL_CANVAS = base._canvas_candidates
_ORIGINAL_SCAN = base.scan_ui_candidates
_ORIGINAL_DISCOVER = base.discover_game_ui_first
_INSTALLED = False


def _dom_candidates(page: Any) -> list[dict[str, Any]]:
    # The HTML canvas itself is only the transport surface for Pixi/custom-engine
    # input. Treating it as one DOM button hides the actual controls underneath.
    return filter_canvas_dom_candidates(_ORIGINAL_DOM(page))


def _opaque_canvas_probes(page: Any) -> list[dict[str, Any]]:
    """Create behavior probes for every canvas that exists in the live frame tree.

    Candidate creation deliberately does not require is_visible()/bounding_box().
    Some BGaming/Pixi builds expose the canvas while Playwright still reports
    transient/odd geometry. Geometry is validated later when the candidate is
    actually replayed, producing an explicit diagnostic instead of silently
    suppressing the whole frontier.
    """
    result: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(list(page.frames)[:12]):
        try:
            canvases = frame.locator("canvas")
            count = min(int(canvases.count()), 4)
        except Exception:
            continue
        for canvas_index in range(count):
            for point in probe_grid_points():
                result.append({
                    "kind": "canvas-probe",
                    "frame": frame_index,
                    "canvas_index": canvas_index,
                    "signature": (
                        f"canvas-probe:{frame_index}:{canvas_index}:"
                        f"{point[0]:.4f}:{point[1]:.4f}"
                    ),
                    "label": "canvas behavior probe",
                    "role": "canvas-probe",
                    "point": point,
                })
    return result


def _fallback_canvas_candidates(page: Any) -> list[dict[str, Any]]:
    rows = _ORIGINAL_CANVAS(page)
    if rows:
        return rows
    return _opaque_canvas_probes(page)


def _scan_ui_candidates(page: Any) -> list[dict[str, Any]]:
    rows = _ORIGINAL_SCAN(page)
    if rows:
        return rows
    # Last-resort guard: even if the original scan filtered everything for some
    # engine-specific reason, an existing canvas must yield a behavioral frontier.
    return _opaque_canvas_probes(page)[:96]


def _discover_game_ui_first(*args: Any, **kwargs: Any):
    progress = kwargs.get("progress")
    game = args[1] if len(args) > 1 else kwargs.get("game")
    if callable(progress):
        name = getattr(game, "name", "BGaming")
        progress(
            f"[{name}] UI FIRST canvas-fallback=ACTIVE: "
            "canvas DOM excluido; grilla conductual 7x4 habilitada."
        )
    return _ORIGINAL_DISCOVER(*args, **kwargs)


def install() -> None:
    """Install the BGaming-only opaque-canvas fallback for UI First."""
    global _INSTALLED
    if _INSTALLED:
        return
    base._dom_candidates = _dom_candidates
    base._canvas_candidates = _fallback_canvas_candidates
    base.scan_ui_candidates = _scan_ui_candidates
    base.discover_game_ui_first = _discover_game_ui_first
    _INSTALLED = True


__all__ = ["install"]
