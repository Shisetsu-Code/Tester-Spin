from __future__ import annotations

from tester_spin.providers.bgaming.ui_first_canvas_patch import install


def main() -> int:
    install()
    from run import main as base_main

    return int(base_main())


if __name__ == "__main__":
    raise SystemExit(main())
