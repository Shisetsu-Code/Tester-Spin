from pathlib import Path
import unittest


class PragmaticStandaloneImportTests(unittest.TestCase):
    def test_pragmatic_entrypoint_does_not_import_other_provider_names(self) -> None:
        text = Path("run_pragmatic.py").read_text(encoding="utf-8").lower()
        for forbidden in ("bgaming", "belatra", "one_spin4win", "rubyplay", "redtiger"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
