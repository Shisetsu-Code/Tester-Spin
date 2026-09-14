from __future__ import annotations

import importlib


def test_pragmatic_only_environment_selects_only_pragmatic(monkeypatch):
    monkeypatch.setenv("TESTER_SPIN_PROVIDER_ONLY", "pragmatic")
    import tester_spin.providers as providers

    providers = importlib.reload(providers)
    assert providers.selected_provider_keys() == ("pragmatic",)


def test_default_environment_keeps_all_registered_providers(monkeypatch):
    monkeypatch.delenv("TESTER_SPIN_PROVIDER_ONLY", raising=False)
    import tester_spin.providers as providers

    providers = importlib.reload(providers)
    assert providers.selected_provider_keys() == ()
