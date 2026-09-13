from __future__ import annotations

import unittest

from tester_spin.providers.bgaming.canvas_behavior import (
    filter_canvas_dom_candidates,
    material_visual_change,
    probe_grid_points,
    visual_delta,
)


class BGamingCanvasBehaviorTests(unittest.TestCase):
    def test_probe_grid_is_stable_and_normalized(self):
        points = probe_grid_points(7, 4)
        self.assertEqual(len(points), 28)
        self.assertEqual(len({tuple(point) for point in points}), 28)
        self.assertTrue(all(0.0 < point[0] < 1.0 and 0.0 < point[1] < 1.0 for point in points))

    def test_canvas_is_not_a_semantic_dom_button(self):
        rows = filter_canvas_dom_candidates([
            {"tag": "canvas", "signature": "surface"},
            {"tag": "button", "signature": "spin"},
        ])
        self.assertEqual(rows, [{"tag": "button", "signature": "spin"}])

    def test_visual_delta_detects_material_change(self):
        before = [[10, 10, 10, 10]]
        idle = [[11, 10, 10, 10]]
        changed = [[100, 100, 100, 100]]
        baseline = visual_delta(before, idle)
        effect = visual_delta(idle, changed)
        self.assertFalse(material_visual_change(baseline, baseline))
        self.assertTrue(material_visual_change(baseline, effect))


if __name__ == "__main__":
    unittest.main()
