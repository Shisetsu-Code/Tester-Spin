from pathlib import Path

from tester_spin.updater import Updater


def test_updater_honors_standalone_home_and_data_overrides(tmp_path: Path, monkeypatch):
    home = tmp_path / "provider-home"
    data = tmp_path / "provider-data"
    monkeypatch.setenv("TESTER_SPIN_APP_HOME_OVERRIDE", str(home))
    monkeypatch.setenv("TESTER_SPIN_DATA_ROOT_OVERRIDE", str(data))

    updater = Updater()

    assert updater.home == home.resolve()
    assert updater.data_dir == data.resolve()
