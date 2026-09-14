from __future__ import annotations

import os
from pathlib import Path


def _configure() -> None:
    raw = os.environ.get("LOCALAPPDATA")
    root = (Path(raw) / "Shisetsu" / "Testers") if raw else (Path.home() / ".shisetsu-testers")
    home = (root / "applications" / "pragmatic").resolve()
    os.environ["TESTER_SPIN_PROVIDER_ONLY"] = "pragmatic"
    os.environ["TESTER_SPIN_LAUNCHER_NAME"] = "Pragmatic Tester"
    os.environ["TESTER_SPIN_LAUNCH_ENTRYPOINT"] = "run_pragmatic.py"
    os.environ["TESTER_SPIN_LAUNCH_HOME"] = str(home)
    os.environ["TESTER_SPIN_LAUNCH_DATA_DIR"] = str(home / "data")


def main() -> int:
    _configure()
    from launcher import main as launcher_main

    return launcher_main()


if __name__ == "__main__":
    raise SystemExit(main())
