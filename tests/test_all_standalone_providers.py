from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from provider_launcher import ProviderLaunchConfig, config_for_executable
from tester_spin.app import configured_provider_exports


class StandaloneProviderConfigurationTests(unittest.TestCase):
    def test_each_supported_provider_selects_only_its_export(self) -> None:
        cases = {
            "pragmatic": "PragmaticProvider",
            "belatra": "BelatraProvider",
            "one_spin4win": "OneSpin4WinProvider",
            "rubyplay": "RubyPlayProvider",
            "redtiger": "RedTigerProvider",
        }
        for key, export in cases.items():
            with self.subTest(provider=key):
                with patch.dict(os.environ, {"TESTER_SPIN_PROVIDER_ONLY": key}, clear=False):
                    self.assertEqual(configured_provider_exports(), (export,))

    def test_default_mode_preserves_original_core_registry(self) -> None:
        env = dict(os.environ)
        env.pop("TESTER_SPIN_PROVIDER_ONLY", None)
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                configured_provider_exports(),
                (
                    "PragmaticProvider",
                    "OneSpin4WinProvider",
                    "BelatraProvider",
                    "BGamingProvider",
                ),
            )

    def test_executable_names_map_to_isolated_provider_configs(self) -> None:
        cases = {
            "Pragmatic.exe": ProviderLaunchConfig("pragmatic", "Pragmatic Play"),
            "Belatra.exe": ProviderLaunchConfig("belatra", "Belatra"),
            "OneSpin4Win.exe": ProviderLaunchConfig("one_spin4win", "1spin4win"),
            "RubyPlay.exe": ProviderLaunchConfig("rubyplay", "RubyPlay"),
            "RedTiger.exe": ProviderLaunchConfig("redtiger", "Red Tiger"),
        }
        for executable, expected in cases.items():
            with self.subTest(executable=executable):
                self.assertEqual(config_for_executable(Path(executable)), expected)

    def test_bgaming_has_no_standalone_executable(self) -> None:
        with self.assertRaises(ValueError):
            config_for_executable(Path("BGaming.exe"))


if __name__ == "__main__":
    unittest.main()
