from __future__ import annotations

import os
from importlib import import_module
from typing import Any

from tester_spin.providers.base import ProviderAdapter, ProviderRegistry

_PROVIDER_EXPORTS: dict[str, tuple[str, str, str]] = {
    "PragmaticProvider": ("pragmatic", "tester_spin.providers.pragmatic_exhaustive", "PragmaticProvider"),
    "OneSpin4WinProvider": ("one_spin4win", "tester_spin.providers.one_spin4win_exhaustive", "OneSpin4WinProvider"),
    "BelatraProvider": ("belatra", "tester_spin.providers.belatra_exhaustive", "BelatraProvider"),
    "BGamingProvider": ("bgaming", "tester_spin.providers.bgaming_exhaustive", "BGamingProvider"),
    "RubyPlayProvider": ("rubyplay", "tester_spin.providers.rubyplay.exhaustive", "RubyPlayProvider"),
    "RedTigerProvider": ("redtiger", "tester_spin.providers.redtiger", "RedTigerProvider"),
}


def selected_provider_keys() -> tuple[str, ...]:
    raw = str(os.environ.get("TESTER_SPIN_PROVIDER_ONLY") or "").strip().lower()
    if not raw:
        return ()
    keys: list[str] = []
    for part in raw.split(","):
        key = part.strip()
        if key and key not in keys:
            keys.append(key)
    return tuple(keys)


class _DisabledProvider:
    _provider_disabled = True

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass


def __getattr__(name: str) -> Any:
    target = _PROVIDER_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    provider_key, module_name, attribute = target
    selected = selected_provider_keys()
    if selected and provider_key not in selected:
        return _DisabledProvider
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


__all__ = [
    "ProviderAdapter",
    "ProviderRegistry",
    "selected_provider_keys",
    "PragmaticProvider",
    "OneSpin4WinProvider",
    "BelatraProvider",
    "BGamingProvider",
    "RubyPlayProvider",
    "RedTigerProvider",
]
