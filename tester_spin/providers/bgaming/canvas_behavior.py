from __future__ import annotations

from typing import Any


def probe_grid_points(cols: int = 7, rows: int = 4) -> list[list[float]]:
    """Return stable normalized probe points for an opaque game canvas."""
    cols = max(1, int(cols))
    rows = max(1, int(rows))
    return [
        [round((x + 0.5) / cols, 4), round((y + 0.5) / rows, 4)]
        for y in range(rows)
        for x in range(cols)
    ]


def filter_canvas_dom_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A canvas is an interaction surface, not a semantic DOM button."""
    return [
        candidate
        for candidate in candidates
        if str(candidate.get("tag") or "").lower() != "canvas"
    ]


def visual_delta(before: list[list[int]], after: list[list[int]]) -> float:
    """Normalized mean absolute delta between coarse canvas signatures."""
    if not before or not after or len(before) != len(after):
        return 0.0
    total = 0
    amount = 0
    for left, right in zip(before, after):
        if not left or len(left) != len(right):
            continue
        total += sum(abs(int(a) - int(b)) for a, b in zip(left, right))
        amount += len(left)
    return float(total) / float(amount * 255) if amount else 0.0


def material_visual_change(baseline: float, effect: float) -> bool:
    """Reject ordinary idle animation while retaining large local UI changes."""
    return float(effect) >= max(0.035, float(baseline) * 2.5 + 0.010)


__all__ = [
    "probe_grid_points",
    "filter_canvas_dom_candidates",
    "visual_delta",
    "material_visual_change",
]
