from __future__ import annotations

import os
from typing import Any

SUPPORTED_PROVIDERS: dict[str, tuple[str, str]] = {
    "pragmatic": ("PragmaticProvider", "Pragmatic Play"),
    "belatra": ("BelatraProvider", "Belatra"),
    "one_spin4win": ("OneSpin4WinProvider", "1spin4win"),
    "rubyplay": ("RubyPlayProvider", "RubyPlay"),
    "redtiger": ("RedTigerProvider", "Red Tiger"),
}


class _StandaloneDisabledProvider:
    _provider_disabled = True

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass


def provider_export_name(provider_key: str) -> str:
    try:
        return SUPPORTED_PROVIDERS[provider_key][0]
    except KeyError as exc:
        raise KeyError(f"provider standalone no soportado: {provider_key}") from exc


def _install_provider(provider_key: str) -> str:
    export_name, display_name = SUPPORTED_PROVIDERS[provider_key]

    # The common GUI registry respects this selector without patching classes.
    os.environ['TESTER_SPIN_PROVIDER_ONLY'] = provider_key
    return display_name


def main() -> int:
    provider_key = str(os.environ.get("TESTER_SPIN_PROVIDER_ONLY") or "").strip().lower()
    if provider_key not in SUPPORTED_PROVIDERS:
        raise RuntimeError(f"TESTER_SPIN_PROVIDER_ONLY inválido para standalone: {provider_key!r}")

    display_name = _install_provider(provider_key)

    from tester_spin.app_current import CurrentTesterSpinApp

    app = CurrentTesterSpinApp()
    app.title(f"{display_name} Tester")
    if hasattr(app, "provider_combo"):
        app.provider_combo.configure(state="disabled")
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
