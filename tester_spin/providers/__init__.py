from __future__ import annotations

from importlib import import_module
from typing import Any

from tester_spin.providers.base import ProviderAdapter, ProviderRegistry

_PROVIDER_EXPORTS: dict[str, tuple[str, str]] = {
    "PragmaticProvider": ("tester_spin.providers.pragmatic_exhaustive", "PragmaticProvider"),
    "OneSpin4WinProvider": ("tester_spin.providers.one_spin4win_exhaustive", "OneSpin4WinProvider"),
    "BelatraProvider": ("tester_spin.providers.belatra_exhaustive", "BelatraProvider"),
    "BGamingProvider": ("tester_spin.providers.bgaming_exhaustive", "BGamingProvider"),
    "RubyPlayProvider": ("tester_spin.providers.rubyplay.exhaustive", "RubyPlayProvider"),
    "RedTigerProvider": ("tester_spin.providers.redtiger", "RedTigerProvider"),
}


def __getattr__(name: str) -> Any:
    target = _PROVIDER_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


__all__ = [
    "ProviderAdapter",
    "ProviderRegistry",
    "PragmaticProvider",
    "OneSpin4WinProvider",
    "BelatraProvider",
    "BGamingProvider",
    "RubyPlayProvider",
    "RedTigerProvider",
]
