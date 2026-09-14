from __future__ import annotations

import os


def test_pragmatic_only_environment_selects_only_pragmatic(monkeypatch):
    monkeypatch.setenv("TESTER_SPIN_PROVIDER_ONLY", "pragmatic")
    import importlib
    import tester_spin.app as app

    app = importlib.reload(app)
    assert app._selected_provider_keys() == ("pragmatic",)


def test_default_environment_keeps_all_registered_providers(monkeypatch):
    monkeypatch.delenv("TESTER_SPIN_PROVIDER_ONLY", raising=False)
    import importlib
    import tester_spin.app as app

    app = importlib.reload(app)
    assert app._selected_provider_keys() == (
        "pragmatic",
        "one_spin4win",
        "belatra",
        "bgaming",
    )
