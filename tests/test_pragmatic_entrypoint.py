from pathlib import Path


def test_standalone_entrypoint_exists():
    assert Path("run_pragmatic.py").is_file()
