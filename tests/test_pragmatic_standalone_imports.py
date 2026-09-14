from pathlib import Path


def test_pragmatic_entrypoint_does_not_import_other_provider_names():
    text = Path("run_pragmatic.py").read_text(encoding="utf-8").lower()
    for forbidden in ("bgaming", "belatra", "one_spin4win", "rubyplay", "redtiger"):
        assert forbidden not in text
