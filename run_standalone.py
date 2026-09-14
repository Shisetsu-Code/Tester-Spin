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

    import tester_spin.providers as provider_exports

    provider_class = getattr(provider_exports, export_name)

    # TesterSpinApp's legacy constructor owns four registration slots. For a
    # standalone process we deliberately inject the selected adapter into one
    # slot and make every other slot a no-op. This keeps the proven GUI and
    # scheduler unchanged while ensuring the process instantiates exactly one
    # provider, including RubyPlay and RedTiger which are normally registered
    # by the higher app_har layer.
    import tester_spin.app as base_app

    base_app.PragmaticProvider = provider_class
    base_app.OneSpin4WinProvider = _StandaloneDisabledProvider
    base_app.BelatraProvider = _StandaloneDisabledProvider
    base_app.BGamingProvider = _StandaloneDisabledProvider
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
