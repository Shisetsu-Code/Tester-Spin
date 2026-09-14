from __future__ import annotations

import unittest
from pathlib import Path

from provider_launcher import ProviderLaunchConfig, config_for_executable
from run_standalone import SUPPORTED_PROVIDERS, provider_export_name


class StandaloneProviderConfigurationTests(unittest.TestCase):
    def test_each_supported_provider_has_exact_export(self) -> None:
        cases = {
            "pragmatic": "PragmaticProvider",
            "belatra": "BelatraProvider",
            "one_spin4win": "OneSpin4WinProvider",
            "rubyplay": "RubyPlayProvider",
            "redtiger": "RedTigerProvider",
        }
        self.assertEqual(set(SUPPORTED_PROVIDERS), set(cases))
        for key, export in cases.items():
            with self.subTest(provider=key):
                self.assertEqual(provider_export_name(key), export)

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

    def test_bgaming_has_no_standalone_executable_or_runtime_entry(self) -> None:
        self.assertNotIn("bgaming", SUPPORTED_PROVIDERS)
        with self.assertRaises(ValueError):
            config_for_executable(Path("BGaming.exe"))
        with self.assertRaises(KeyError):
            provider_export_name("bgaming")


if __name__ == "__main__":
    unittest.main()
