from unittest.mock import Mock, patch
import pytest
from tester_spin.providers.rubyplay import bootstrap_fallback as fallback
from tester_spin.providers.rubyplay.runtime import RubyPlayClientProfile


def test_missing_static_math_uses_observed_official_init_contract():
    profile = RubyPlayClientProfile()
    session = Mock()
    session.get.return_value.text = "public page"
    session.get.return_value.url = "https://rubyplay.com/games/example/"
    launcher = Mock(launcher_url="https://provider.example/launcher")
    sentinel = object()
    with patch.object(fallback, "_ORIGINAL_BOOTSTRAP", side_effect=[ValueError("RubyPlay: no se pudo descubrir v_math desde el cliente."), sentinel]), patch.object(fallback._runtime, "extract_launcher_url", return_value=launcher.launcher_url), patch.object(fallback._runtime, "parse_launcher_url", return_value=launcher), patch.object(fallback, "_discover_profile_for_launcher", return_value=profile), patch.object(fallback, "capture_init_contract_browser", return_value={"v_protocol": 3, "v_math": 98765}):
        result = fallback.bootstrap_game(session, "https://rubyplay.com/games/example/", timeout_s=5)
    assert result is sentinel
    assert profile.math_version == 98765
    assert profile.protocol_version == 3
    assert "browser.official-init.v_math" in profile.evidence


def test_unrelated_bootstrap_error_does_not_launch_browser():
    with patch.object(fallback, "_ORIGINAL_BOOTSTRAP", side_effect=ValueError("ambiguous launcher")), patch.object(fallback, "capture_init_contract_browser") as browser:
        with pytest.raises(ValueError, match="ambiguous launcher"):
            fallback.bootstrap_game(Mock(), "https://rubyplay.com/games/example/", timeout_s=5)
    browser.assert_not_called()
