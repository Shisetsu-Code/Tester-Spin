from __future__ import annotations

import os


def main() -> int:
    os.environ["TESTER_SPIN_PROVIDER_ONLY"] = "pragmatic"
    from tester_spin.app_current import CurrentTesterSpinApp

    app = CurrentTesterSpinApp()
    app.title("Pragmatic Tester")
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
