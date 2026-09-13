from __future__ import annotations

import json
import unittest

from tester_spin.providers.bgaming.ui_first import _trace_safe


class UIFirstDiagnosticsTests(unittest.TestCase):
    def test_trace_sanitizes_runtime_secrets(self):
        payload = _trace_safe({
            "token": "private-token",
            "session_id": "private-session",
            "round_series_id": 123456,
            "nested": {"authorization": "Bearer secret"},
        })
        raw = json.dumps(payload)
        self.assertNotIn("private-token", raw)
        self.assertNotIn("private-session", raw)
        self.assertNotIn("123456", raw)
        self.assertNotIn("Bearer secret", raw)
        self.assertIn("runtime", raw)


if __name__ == "__main__":
    unittest.main()
