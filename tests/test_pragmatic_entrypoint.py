from pathlib import Path
import unittest


class PragmaticEntrypointTests(unittest.TestCase):
    def test_standalone_entrypoint_exists(self) -> None:
        self.assertTrue(Path("run_pragmatic.py").is_file())
        self.assertTrue(Path("pragmatic_launcher.py").is_file())


if __name__ == "__main__":
    unittest.main()
