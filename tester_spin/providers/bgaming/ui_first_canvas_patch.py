from __future__ import annotations

from typing import Any

from tester_spin.providers.bgaming import ui_first as base
from tester_spin.providers.bgaming.canvas_behavior import (
    filter_canvas_dom_candidates,
    probe_grid_points,
)

_ORIGINAL_DOM = base._dom_candidates
_ORIGINAL_CANVAS = base._canvas_candidates


def _dom_candidates(page: Any) -> list[dict[str, Any]]:
    return filter_canvas_dom_candidates(_ORIGINAL_DOM(page))


def _fallback_canvas_candidates(page: Any) -> list[dict[str, Any]]:
    rows = _ORIGINAL_CANVAS(page)
    if rows:
        return rows

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
            except Exception:
                continue
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


def install() -> None:
    """Install the BGaming-only opaque-canvas fallback for UI First."""
    base._dom_candidates = _dom_candidates
    base._canvas_candidates = _fallback_canvas_candidates


__all__ = ["install"]
