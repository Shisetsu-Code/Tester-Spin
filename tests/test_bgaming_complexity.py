from __future__ import annotations

from tester_spin.models import GameTestResult, SpinAttempt
from tester_spin.providers.bgaming.complexity import (
    AUTO_COMPLETE,
    INDETERMINATE,
    REVIEW_REQUIRED,
    SIMPLE_PENDING,
    classify_result,
)


def _result(*, status: str = "OK") -> GameTestResult:
    return GameTestResult(
        provider="bgaming",
        slug="sample",
        game_name="Sample",
        game_url="https://example.invalid",
        requested_spins=1,
        successful_spins=1 if status == "OK" else 0,
        failed_spins=0 if status == "OK" else 1,
        status=status,
    )


def test_terminal_known_game_is_auto_complete() -> None:
    result = _result()
    result.discovered_modes = [
        {"id": "SPIN", "kind": "SPIN", "observed": True, "wire_command": "spin"}
    ]
    result.attempts = [
        SpinAttempt(number=1, ok=True, mode_id="SPIN", status_code=200, terminal=True, na="closed")
    ]
    payload = classify_result(result)
    assert payload["classification"] == AUTO_COMPLETE
    assert payload["requires_review"] is False
    assert payload["reasons"] == []


def test_unknown_feature_action_requires_review() -> None:
    result = _result(status="PARCIAL")
    result.discovered_modes = [
        {
            "id": "PLAY_BONUS_GAME",
            "kind": "FEATURE",
            "observed": False,
            "wire_command": "play_bonus_game",
        }
    ]
    payload = classify_result(result)
    assert payload["classification"] == REVIEW_REQUIRED
    assert payload["requires_review"] is True
    assert any(row["kind"] == "UNKNOWN_ACTION" for row in payload["reasons"])


def test_nonterminal_server_state_requires_review() -> None:
    result = _result(status="PARCIAL")
    result.attempts = [
        SpinAttempt(
            number=1,
            ok=False,
            mode_id="PURCHASE_BONUS_BUY",
            status_code=200,
            terminal=False,
            na="select_bonus",
            warning="estado final BGaming no terminal",
        )
    ]
    payload = classify_result(result)
    assert payload["classification"] == REVIEW_REQUIRED
    assert any(row["kind"] == "NON_TERMINAL_STATE" and row["value"] == "select_bonus" for row in payload["reasons"])


def test_unlearned_purchase_contract_is_simple_pending_not_manual_review() -> None:
    result = _result(status="PARCIAL")
    result.discovered_modes = [
        {
            "id": "PURCHASE_BONUS_BUY",
            "kind": "PURCHASE",
            "observed": True,
            "executable": False,
            "discovery_state": "ADVERTISED_ONLY",
            "wire_command": "spin",
        }
    ]
    payload = classify_result(result)
    assert payload["classification"] == SIMPLE_PENDING
    assert payload["requires_review"] is False
    assert payload["reasons"] == []
    assert any(row["kind"] == "UNKNOWN_PURCHASE_CONTRACT" for row in payload["capability_gaps"])


def test_standard_purchase_422_is_simple_pending_when_round_did_not_enter_branch() -> None:
    result = _result(status="PARCIAL")
    result.discovered_modes = [
        {
            "id": "PURCHASE_BONUS_BUY",
            "kind": "PURCHASE",
            "observed": True,
            "executable": True,
            "wire_command": "spin",
        }
    ]
    result.attempts = [
        SpinAttempt(
            number=1,
            ok=False,
            mode_id="PURCHASE_BONUS_BUY",
            status_code=422,
            terminal=False,
            na="",
            warning="HTTP 422 invalid options",
        )
    ]
    payload = classify_result(result)
    assert payload["classification"] == SIMPLE_PENDING
    assert payload["requires_review"] is False
    assert any(row["kind"] == "UNRESOLVED_STANDARD_WIRE" for row in payload["capability_gaps"])


def test_continuation_422_still_requires_review() -> None:
    result = _result(status="PARCIAL")
    result.discovered_modes = [
        {
            "id": "PLAY_BONUS_GAME",
            "kind": "CONTINUATION",
            "observed": True,
            "wire_command": "play_bonus_game",
        }
    ]
    result.attempts = [
        SpinAttempt(
            number=1,
            ok=False,
            mode_id="PLAY_BONUS_GAME",
            status_code=422,
            terminal=False,
            na="select_bonus",
            warning="continuación BGaming respondió HTTP 422; wire-shape no resuelto",
        )
    ]
    payload = classify_result(result)
    assert payload["classification"] == REVIEW_REQUIRED
    assert payload["requires_review"] is True


def test_transport_error_without_complex_branch_is_indeterminate() -> None:
    result = _result(status="ERROR")
    result.error = "ReadTimeout: gateway did not answer"
    result.attempts = [
        SpinAttempt(number=1, ok=False, mode_id="SPIN", terminal=False, error=result.error)
    ]
    payload = classify_result(result)
    assert payload["classification"] == INDETERMINATE
    assert payload["requires_review"] is False
