from tester_spin.models import GameTestResult
from tester_spin.providers import bgaming_paths_v2 as paths


def result(modes):
    return GameTestResult(provider="bgaming",slug="fixture",game_name="Fixture",game_url="https://example.invalid",requested_spins=1,successful_spins=1,failed_spins=0,status="OK",discovered_modes=modes)


def test_incomplete_required_purchase_prevents_ok_without_inventing_wire():
    r=result([{"id":"PURCHASE_BUY_BONUS","kind":"PURCHASE","executable":False,"coverage_required":False,"discovery_state":"DISCOVERED_LITERAL_ONLY","observed":True}])
    paths._enforce_required_mode_evidence(r)
    assert r.status == "PARCIAL"
    assert "PURCHASE_BUY_BONUS" in r.error
    assert not r.discovered_modes[0]["executable"]


def test_optional_server_metadata_does_not_create_purchase_obligation():
    r=result([{"id":"PURCHASE_GENERIC","kind":"DISCOVERED_ONLY","executable":False,"observed":True}])
    paths._enforce_required_mode_evidence(r)
    assert r.status == "OK"
