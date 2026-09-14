from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProviderLaunchConfig:
    key: str
    display_name: str


_BY_EXECUTABLE = {
    "pragmatic": ProviderLaunchConfig("pragmatic", "Pragmatic Play"),
    "belatra": ProviderLaunchConfig("belatra", "Belatra"),
    "onespin4win": ProviderLaunchConfig("one_spin4win", "1spin4win"),
    "rubyplay": ProviderLaunchConfig("rubyplay", "RubyPlay"),
    "redtiger": ProviderLaunchConfig("redtiger", "Red Tiger"),
}


def config_for_executable(executable: Path) -> ProviderLaunchConfig:
    key = Path(executable).stem.strip().lower()
    try:
        return _BY_EXECUTABLE[key]
    except KeyError as exc:
        raise ValueError(f"ejecutable standalone no soportado: {Path(executable).name}") from exc


def _suite_root() -> Path:
    raw = os.environ.get("LOCALAPPDATA")
    if raw:
        return (Path(raw) / "Shisetsu" / "Testers").resolve()
    return (Path.home() / ".shisetsu-testers").resolve()


def configure_environment(config: ProviderLaunchConfig) -> Path:
    home = (_suite_root() / "applications" / config.key).resolve()
    os.environ["TESTER_SPIN_PROVIDER_ONLY"] = config.key
    os.environ["TESTER_SPIN_LAUNCHER_NAME"] = f"{config.display_name} Tester"
    os.environ["TESTER_SPIN_LAUNCH_ENTRYPOINT"] = "run_standalone.py"
    os.environ["TESTER_SPIN_LAUNCH_HOME"] = str(home)
    os.environ["TESTER_SPIN_LAUNCH_DATA_DIR"] = str(home / "data")
    return home


def main() -> int:
    executable = Path(sys.executable if getattr(sys, "frozen", False) else sys.argv[0])
    config = config_for_executable(executable)
    configure_environment(config)
    from launcher import main as launcher_main

    return launcher_main()


if __name__ == "__main__":
    raise SystemExit(main())
