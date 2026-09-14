from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import tester_spin.providers as providers


class ProviderSelectionTests(unittest.TestCase):
    def test_pragmatic_only_environment_selects_only_pragmatic(self) -> None:
        with patch.dict(os.environ, {"TESTER_SPIN_PROVIDER_ONLY": "pragmatic"}, clear=False):
            self.assertEqual(providers.selected_provider_keys(), ("pragmatic",))

    def test_default_environment_keeps_all_registered_providers(self) -> None:
        env = dict(os.environ)
        env.pop("TESTER_SPIN_PROVIDER_ONLY", None)
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(providers.selected_provider_keys(), ())


if __name__ == "__main__":
    unittest.main()
