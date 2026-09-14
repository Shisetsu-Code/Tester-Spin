from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

import launcher


class LauncherConfigurationTests(unittest.TestCase):
    def test_launcher_environment_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "standalone-home"
            with patch.dict(
                os.environ,
                {
                    "TESTER_SPIN_LAUNCHER_NAME": "Pragmatic Tester",
                    "TESTER_SPIN_LAUNCH_ENTRYPOINT": "run_pragmatic.py",
                    "TESTER_SPIN_LAUNCH_HOME": str(home),
                },
                clear=False,
            ):
                self.assertEqual(launcher._launcher_name(), "Pragmatic Tester")
                self.assertEqual(launcher._entrypoint_name(), "run_pragmatic.py")
                self.assertEqual(launcher._home_override(), home.resolve())

    def test_launcher_rejects_nested_entrypoint(self) -> None:
        with patch.dict(os.environ, {"TESTER_SPIN_LAUNCH_ENTRYPOINT": "../bad.py"}, clear=False):
            self.assertEqual(launcher._entrypoint_name(), "run.py")


if __name__ == "__main__":
    unittest.main()
