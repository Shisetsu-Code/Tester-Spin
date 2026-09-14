from pathlib import Path

import launcher


def test_launcher_environment_overrides(monkeypatch, tmp_path: Path):
    home = tmp_path / "standalone-home"
    monkeypatch.setenv("TESTER_SPIN_LAUNCHER_NAME", "Pragmatic Tester")
    monkeypatch.setenv("TESTER_SPIN_LAUNCH_ENTRYPOINT", "run_pragmatic.py")
    monkeypatch.setenv("TESTER_SPIN_LAUNCH_HOME", str(home))

    assert launcher._launcher_name() == "Pragmatic Tester"
    assert launcher._entrypoint_name() == "run_pragmatic.py"
    assert launcher._home_override() == home.resolve()


def test_launcher_rejects_nested_entrypoint(monkeypatch):
    monkeypatch.setenv("TESTER_SPIN_LAUNCH_ENTRYPOINT", "../bad.py")
    assert launcher._entrypoint_name() == "run.py"
