"""Offline family evidence must survive identity changes, not invalid receipts."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import socket
import zipfile

import pytest


FIXTURES = Path(__file__).parent / "fixtures"
COMMAND = "com.pt.casino.platform.game.GameCommand"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("FAMILY_AUDIT_MUST_NOT_OPEN_A_CONNECTION")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


def fixture(kind="respins"):
    return json.loads((FIXTURES / f"playtech_family_{kind}_sanitized.json").read_text())


def frames(document):
    return document["log"]["entries"][0]["_webSocketFrames"]


def message(frame):
    return json.loads(frame["payloadData"][4:])


def replace_message(frame, value):
    frame["payloadData"] = "3:::" + json.dumps(value)


def write(tmp_path, document, name="capture.har"):
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def audit(paths):
    return importlib.import_module(
        "tester_spin.providers.playtech.family_audit"
    ).analyze_hars(paths)


def gameplay(document, direction):
    return [f for f in frames(document) if f["direction"] == direction
            and message(f)["data"].get("_type") == COMMAND]


def automatic_commands(document):
    """Synthetic variant without the real fixture's unbound extra-bet flags."""
    for frame in gameplay(document, "sent"):
        value = message(frame)
        value["data"]["gameData"]["parameters"] = []
        replace_message(frame, value)
    return document


def test_real_fragmented_respins_close_but_unbound_parameters_stay_partial(tmp_path):
    document = fixture()
    mid = len(frames(document)) // 2
    beginning, ending = deepcopy(document), deepcopy(document)
    beginning["log"]["entries"][0]["_webSocketFrames"] = frames(document)[:mid]
    ending["log"]["entries"][0]["_webSocketFrames"] = frames(document)[mid:]
    report = audit([write(tmp_path, ending, "later.har"),
                    write(tmp_path, beginning, "earlier.har")])
    summary = report["summary"]
    assert summary["games"] == 1
    assert summary["paired_operations"] == 13
    assert summary["rounds"] == summary["closed_and_settled_rounds"] == 1
    assert summary["open_round_prefixes"] == summary["invalid_rounds"] == 0
    family, = report["families"]
    assert family["command_class"] == "com.pt.gpas.platform.game.OgwCorosinGameCommand"
    assert family["capabilities"]["entry"]["state"] == "PARTIAL"
    assert family["capabilities"]["continuation"]["state"] == "PARTIAL"
    assert family["capabilities"]["settlement"]["verified"] == 1
    assert family["capabilities"]["continuation"]["observed"] == 12
    assert "PARAMETERS_NOT_REPRODUCED" in family["issues"]
    assert family["capabilities"]["recognition"]["state"] == "MISSING_EVIDENCE"
    assert family["contract_source"] == "wire_observation"
    assert family["live_executable"] is None
    assert report["certifies_live_ok"] is False


def test_zip_and_repeated_exports_do_not_inflate_operations(tmp_path):
    document = fixture()
    path = write(tmp_path, document)
    archive = tmp_path / "captures.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("copy.har", json.dumps(document))
    report = audit([archive, path])
    assert report["summary"]["files"] == 2
    assert report["summary"]["paired_operations"] == 13
    assert report["summary"]["duplicate_frames"] == len(frames(document))
    assert report["summary"]["closed_and_settled_rounds"] == 1


def test_raw_payload_wins_over_exporter_annotation_and_cached_decode(tmp_path):
    document = fixture()
    for frame in frames(document):
        frame["decoded"] = {"parsed": {"correlationId": "forged", "data": {
            "_type": COMMAND, "gameRoundClosed": True, "gameData": {"ID": 40021}}}}
    document["log"]["entries"][0]["_webSocketTransactions"] = [
        {"requestFrameId": -1, "responseFrameId": 99999, "kind": "buy-feature"}]
    report = audit([write(tmp_path, document)])
    assert report["summary"]["paired_operations"] == 13
    assert report["summary"]["closed_and_settled_rounds"] == 1


def test_missing_correlations_never_pair_via_none_or_nearest_response(tmp_path):
    document = fixture()
    for frame in gameplay(document, "sent") + gameplay(document, "received"):
        value = message(frame)
        value.pop("correlationId")
        replace_message(frame, value)
    report = audit([write(tmp_path, document)])
    assert report["summary"]["paired_operations"] == 0
    assert report["summary"]["unpaired_requests"] == 13
    assert report["summary"]["unpaired_responses"] == 13
    assert report["summary"]["closed_and_settled_rounds"] == 0
    assert "CORRELATION_MISSING" in report["issues"]


def test_reused_correlation_with_distinct_requests_is_ambiguous(tmp_path):
    document = fixture()
    duplicate = deepcopy(gameplay(document, "sent")[0])
    duplicate["timestamp"] += 0.25
    frames(document).append(duplicate)
    report = audit([write(tmp_path, document)])
    assert report["summary"]["paired_operations"] == 12
    assert report["summary"]["unpaired_requests"] == 2
    assert "CORRELATION_AMBIGUOUS" in report["issues"]
    assert report["summary"]["closed_and_settled_rounds"] == 0


def test_same_correlation_on_different_connections_does_not_pair(tmp_path):
    document = fixture()
    other = deepcopy(document["log"]["entries"][0])
    other["request"]["url"] = "wss://example.invalid/another-connection"
    other["_webSocketFrames"] = gameplay(document, "received")
    received = {id(f) for f in gameplay(document, "received")}
    document["log"]["entries"][0]["_webSocketFrames"] = [
        f for f in frames(document) if id(f) not in received]
    document["log"]["entries"].append(other)
    report = audit([write(tmp_path, document)])
    assert report["summary"]["paired_operations"] == 0
    assert report["summary"]["closed_and_settled_rounds"] == 0


def test_balance_notification_sharing_correlation_is_not_a_game_response(tmp_path):
    document = fixture()
    victim = gameplay(document, "received")[-1]
    value = message(victim)
    value["data"] = {"_type": "com.pt.casino.platform.balance.BalanceNotification",
                     "balance": [{"_type": "com.pt.casino.platform.balance.MonetaryBalanceData", "amount": 100}]}
    replace_message(victim, value)
    report = audit([write(tmp_path, document)])
    assert report["summary"]["paired_operations"] == 12
    assert report["summary"]["unpaired_requests"] == 1
    assert report["summary"]["closed_and_settled_rounds"] == 0


def test_broken_balance_does_not_turn_a_terminal_round_into_verified_settlement(tmp_path):
    document = fixture()
    end = gameplay(document, "received")[-1]["timestamp"]
    after = next(f for f in frames(document) if f["timestamp"] > end
                 and message(f)["data"].get("_type", "").endswith("BalanceNotification"))
    value = message(after)
    value["data"]["balance"][0]["amount"] += 1
    replace_message(after, value)
    report = audit([write(tmp_path, document)])
    assert report["summary"]["closed_and_settled_rounds"] == 0
    assert report["summary"]["invalid_rounds"] == 1
    assert "BALANCE_NOT_RECONCILED" in report["families"][0]["issues"]


def test_terminal_flag_must_agree_with_phase(tmp_path):
    document = fixture()
    first = gameplay(document, "received")[0]
    value = message(first)
    value["data"]["gameRoundClosed"] = True
    replace_message(first, value)
    report = audit([write(tmp_path, document)])
    assert report["summary"]["closed_and_settled_rounds"] == 0
    assert report["summary"]["invalid_rounds"] == 1
    assert "ROUND_TERMINAL_STATE_CONTRADICTION" in report["families"][0]["issues"]


def test_open_prefix_is_missing_closure_evidence_not_a_broken_round(tmp_path):
    document = fixture()
    end = gameplay(document, "received")[-2]["timestamp"]
    document["log"]["entries"][0]["_webSocketFrames"] = [
        f for f in frames(document) if f["timestamp"] <= end]
    report = audit([write(tmp_path, document)])
    assert report["summary"]["paired_operations"] == 12
    assert report["summary"]["open_round_prefixes"] == 1
    assert report["summary"]["invalid_rounds"] == 0
    assert report["summary"]["closed_and_settled_rounds"] == 0
    assert "ROUND_END_NOT_CAPTURED" in report["families"][0]["missing_evidence"]


def test_broken_turn_chain_cannot_certify_a_closed_round(tmp_path):
    document = fixture()
    second = gameplay(document, "received")[1]
    value = message(second)
    value["data"]["debug"]["context"]["gamecycle"]["previousTurn"] = "missing-turn"
    replace_message(second, value)
    report = audit([write(tmp_path, document)])
    assert report["summary"]["closed_and_settled_rounds"] == 0
    assert "ROUND_CHAIN_BROKEN" in report["families"][0]["issues"]


def test_renaming_games_and_costs_does_not_change_family_or_capability_results(tmp_path):
    document = fixture()
    renamed = json.loads(json.dumps(document).replace("gpas_fixture_alpha", "gpas_unseen_title")
                         .replace("cost-", "new-cost-").replace("cycle-", "new-cycle-")
                         .replace("turn-", "new-turn-"))
    first = audit([write(tmp_path, document, "one.har")])["families"][0]
    second = audit([write(tmp_path, renamed, "two.har")])["families"][0]
    assert first["family_id"] == second["family_id"]
    assert first["capabilities"] == second["capabilities"]
    assert first["issues"] == second["issues"]


def test_public_report_does_not_export_sessions_ids_or_payloads(tmp_path):
    document = fixture()
    document["log"]["entries"][0]["request"]["url"] += "?token=private-session-token"
    first = frames(document)[0]
    value = message(first)
    value["data"]["token"] = "private-body-token"
    replace_message(first, value)
    report = audit([write(tmp_path, document)])
    text = json.dumps(report)
    for value in ("example.invalid", "private-session-token", "private-body-token",
                  "payloadData", "correlationId", "cost-1", "turn-1", "cycle-1"):
        assert value not in text
    assert report["scope"] == "historical_capture"


def test_two_command_classes_produce_two_families_not_two_game_allowlists(tmp_path):
    report = audit([write(tmp_path, fixture(), "respins.har"),
                    write(tmp_path, fixture("quickspin"), "quickspin.har")])
    assert report["summary"]["games"] == 2
    assert report["summary"]["paired_operations"] == 26
    assert report["summary"]["closed_and_settled_rounds"] == 2
    assert len(report["families"]) == 2
    assert {f["command_class"] for f in report["families"]} == {
        "com.pt.gpas.platform.game.OgwCorosinGameCommand", "quickspin.game.playMoney"}


def test_modern_receipt_and_declared_unit_cost_can_determine_factor(tmp_path):
    document = fixture()
    for frame in gameplay(document, "received"):
        value = message(frame)
        value["data"]["gameData"].pop("baseCostMultiplier", None)
        replace_message(frame, value)
    report = audit([write(tmp_path, document)])
    scope = report["families"][0]["capabilities"]["configuration_scope"]
    assert scope["verified"] == 1
    assert scope["issues"] == []


def test_scope_cannot_accept_a_multiplier_excluded_by_current_context(tmp_path):
    document = fixture()
    for frame in frames(document):
        value = message(frame)
        if value["data"].get("_type") == "com.pt.gpas.config.GetGameConfigurationResponse":
            value["data"]["data"].append({"scope": {"betType": "default", "featureType": "BF_RGB"},
                                             "content": {"game": {"baseCostMultipliers": [1],
                                                                   "defaultBaseCostMultiplier": 1}}})
            replace_message(frame, value)
    report = audit([write(tmp_path, document)])
    scope = report["families"][0]["capabilities"]["configuration_scope"]
    assert scope["verified"] == 0
    assert "ENTRY_MULTIPLIER_OUTSIDE_SCOPE" in scope["issues"]
    assert report["summary"]["closed_and_settled_rounds"] == 1


def test_game_limit_and_general_limit_are_intersected(tmp_path):
    document = fixture()
    for frame in frames(document):
        value = message(frame)
        if value["data"].get("_type") == "com.pt.gpas.config.GetGameConfigurationResponse":
            value["data"]["data"].append({"scope": {"betType": "default", "featureType": "BF_RGB"},
                                             "content": {"limits": {"maxBet": 1000}}})
            replace_message(frame, value)
    report = audit([write(tmp_path, document)])
    scope = report["families"][0]["capabilities"]["configuration_scope"]
    assert scope["verified"] == 0
    assert "ENTRY_COST_OUTSIDE_SCOPE" in scope["issues"]


@pytest.mark.parametrize("location", ["command", "gameData"])
def test_unreproduced_extra_command_fields_cannot_be_ignored(tmp_path, location):
    document = automatic_commands(fixture())
    baseline = audit([write(tmp_path, document, "baseline.har")])
    assert baseline["families"][0]["capabilities"]["entry"]["verified"] == 1
    entry = gameplay(document, "sent")[0]
    value = message(entry)
    target = value["data"] if location == "command" else value["data"]["gameData"]
    target["additionalWagerAction"] = "not-built-by-the-primitive"
    replace_message(entry, value)
    report = audit([write(tmp_path, document)])
    assert report["families"][0]["capabilities"]["entry"]["verified"] == 0
    assert "UNREPRODUCED_COMMAND_FIELDS" in report["families"][0]["issues"]


@pytest.mark.parametrize("malformed", [[], 42, "not-an-object"])
def test_non_object_request_game_data_has_a_safe_diagnostic(tmp_path, malformed):
    document = fixture()
    entry = gameplay(document, "sent")[0]
    value = message(entry)
    value["data"]["gameData"] = malformed
    replace_message(entry, value)
    with pytest.raises(ValueError, match="GAME_COMMAND_DATA_INVALID"):
        audit([write(tmp_path, document)])


def test_unknown_command_class_is_observed_without_claiming_builder_support(tmp_path):
    document = automatic_commands(fixture())
    for frame in gameplay(document, "sent"):
        value = message(frame)
        value["data"]["gameData"]["_type"] = "vendor.UnknownGameCommand"
        replace_message(frame, value)
    report = audit([write(tmp_path, document)])
    family, = report["families"]
    assert family["capabilities"]["entry"]["verified"] == 0
    assert family["capabilities"]["continuation"]["verified"] == 0
    assert "COMMAND_CONTRACT_UNSUPPORTED" in family["issues"]
    assert report["summary"]["closed_and_settled_rounds"] == 1


def test_continuation_cannot_be_verified_using_a_response_from_the_future(tmp_path):
    document = automatic_commands(fixture())
    request = gameplay(document, "sent")[1]
    preceding = gameplay(document, "received")[0]
    request["timestamp"] = preceding["timestamp"] - 0.1
    report = audit([write(tmp_path, document)])
    family, = report["families"]
    assert "CONTINUATION_PRECEDES_STATE" in family["issues"]
    assert family["capabilities"]["continuation"]["verified"] == 11
    assert report["summary"]["closed_and_settled_rounds"] == 0


def test_unknown_dialect_never_reports_supported_construction(tmp_path):
    document = automatic_commands(fixture())
    entry = gameplay(document, "sent")[0]
    value = message(entry)
    value["data"].pop("betCost")
    value["data"].pop("featureType")
    replace_message(entry, value)
    report = audit([write(tmp_path, document)])
    family, = report["families"]
    assert family["dialect"] == "unknown"
    assert family["capabilities"]["entry"]["verified"] == 0
    assert family["capabilities"]["continuation"]["verified"] == 0
    assert "COMMAND_CONTRACT_UNSUPPORTED" in family["issues"]


def test_changed_contract_in_one_round_does_not_invalidate_a_later_round(tmp_path):
    document = automatic_commands(fixture())
    following = json.loads(json.dumps(document).replace("correlation-", "later-correlation-")
                           .replace("cycle-", "later-cycle-").replace("turn-", "later-turn-"))
    for frame in frames(following):
        frame["timestamp"] += 200
    tail = [f for f in frames(following) if message(f)["data"].get("_type") != "InitGameSession"]
    changed = gameplay(document, "sent")[1]
    value = message(changed)
    value["data"]["gameData"]["_type"] = "vendor.OtherCommand"
    replace_message(changed, value)
    frames(document).extend(tail)
    report = audit([write(tmp_path, document)])
    assert report["summary"]["rounds"] == 2
    assert report["summary"]["closed_and_settled_rounds"] == 1
    assert report["rounds"][1]["issues"] == []


@pytest.mark.parametrize(("override", "issue"), [
    ({"baseCostMultipliers": [1, 25, True]}, "MODE_SCOPE_MULTIPLIER_DOMAIN_INVALID"),
    ({"maxBet": None}, "MODE_SCOPE_MAX_BET_INVALID"),
    ({"defaultBaseCostMultiplier": None}, "MODE_SCOPE_DEFAULT_FACTOR_INVALID"),
])
def test_invalid_economic_declarations_cannot_be_verified_offline(tmp_path, override, issue):
    document = fixture("quickspin")
    for frame in frames(document):
        value = message(frame)
        if value["data"].get("_type") == "com.pt.gpas.config.GetGameConfigurationResponse":
            value["data"]["data"].append({"scope": {"betType": "default", "featureType": "buyFeature3"},
                                             "content": {"game": override}})
            replace_message(frame, value)
    report = audit([write(tmp_path, document)])
    scope = report["families"][0]["capabilities"]["configuration_scope"]
    assert scope["verified"] == 0
    assert issue in scope["issues"]


@pytest.mark.parametrize("malformed", [[], 42, "not-a-game-configuration"])
def test_non_object_game_configuration_is_diagnosed_without_crashing(tmp_path, malformed):
    document = fixture("quickspin")
    for frame in frames(document):
        value = message(frame)
        if value["data"].get("_type") == "com.pt.gpas.config.GetGameConfigurationResponse":
            value["data"]["data"].append({"scope": {"betType": "default", "featureType": "buyFeature3"},
                                             "content": {"game": malformed}})
            replace_message(frame, value)
    report = audit([write(tmp_path, document)])
    scope = report["families"][0]["capabilities"]["configuration_scope"]
    assert scope["verified"] == 0
    assert "MODE_SCOPE_GAME_MISSING" in scope["issues"]


def test_absent_stake_identity_cannot_be_verified_by_none_matching_none(tmp_path):
    document = fixture("quickspin")
    for frame in gameplay(document, "received"):
        value = message(frame)
        value["data"]["gameData"].pop("stakeCostUuid", None)
        replace_message(frame, value)
    report = audit([write(tmp_path, document)])
    assert report["summary"]["closed_and_settled_rounds"] == 0
    assert report["summary"]["open_round_prefixes"] == 0
    assert report["summary"]["invalid_rounds"] == 0
    assert "STAKE_IDENTITY_NOT_CAPTURED" in report["rounds"][0]["missing_evidence"]


def test_continuation_with_broken_turn_link_is_not_primitive_proof(tmp_path):
    document = fixture("quickspin")
    second = gameplay(document, "received")[1]
    value = message(second)
    value["data"]["debug"]["context"]["gamecycle"]["previousTurn"] = "missing-turn"
    replace_message(second, value)
    report = audit([write(tmp_path, document)])
    continuation = report["families"][0]["capabilities"]["continuation"]
    assert continuation["verified"] == 11
    assert "ROUND_CHAIN_BROKEN" in continuation["issues"]


def test_legacy_requested_stake_identity_must_match_the_receipt(tmp_path):
    document = automatic_commands(fixture("quickspin"))
    for frame in gameplay(document, "sent"):
        value = message(frame)
        data = value["data"]
        data["gameData"]["_type"] = "com.pt.gpas.platform.game.OgwCorosinGameCommand"
        if data["gameData"]["ID"] == 40021:
            data["gameData"].update(bet=data.pop("betCost"), baseCostMultiplier=25,
                                     stakeCostUuid="different-requested-cost")
            data.pop("featureType")
        replace_message(frame, value)
    report = audit([write(tmp_path, document)])
    assert report["summary"]["closed_and_settled_rounds"] == 0
    assert "STAKE_UUID_MISMATCH" in report["rounds"][0]["issues"]


@pytest.mark.parametrize("keep_entry_copy", [False, True])
def test_native_runtime_socket_frames_share_parser_and_deduplication(tmp_path, keep_entry_copy):
    document = fixture("quickspin")
    entry = document["log"]["entries"][0]
    count = len(frames(document))
    document["log"]["_warpWebSockets"] = [
        {"url": entry["request"]["url"], "connectionId": "private-native-connection",
         "direction": frame["direction"], "timestamp": frame["timestamp"],
         "payload": frame["payloadData"], "opcode": frame["opcode"]}
        for frame in frames(document)]
    if not keep_entry_copy:
        document["log"]["entries"] = []
    report = audit([write(tmp_path, document)])
    assert report["summary"]["paired_operations"] == 13
    assert report["summary"]["closed_and_settled_rounds"] == 1
    assert report["summary"]["duplicate_frames"] == (count if keep_entry_copy else 0)
    assert "private-native-connection" not in json.dumps(report)


def test_final_balance_without_timestamp_is_missing_evidence(tmp_path):
    document = fixture("quickspin")
    final = gameplay(document, "received")[-1]["timestamp"]
    after = next(frame for frame in frames(document) if frame["timestamp"] > final
                 and message(frame)["data"].get("_type", "").endswith("BalanceNotification"))
    after.pop("timestamp")
    report = audit([write(tmp_path, document)])
    assert report["summary"]["closed_and_settled_rounds"] == 0
    assert "ROUND_BALANCE_NOT_CAPTURED" in report["rounds"][0]["missing_evidence"]


def native_document(document, *, direction=None, identity="native-socket", include_url=True):
    entry = document["log"]["entries"][0]
    native = []
    for frame in frames(document):
        if direction is not None and frame["direction"] != direction:
            continue
        row = {"direction": frame["direction"], "timestamp": frame["timestamp"],
               "payload": frame["payloadData"], "opcode": frame["opcode"], "connectionId": identity}
        if include_url:
            row["url"] = entry["request"]["url"]
        native.append(row)
    return {"log": {"entries": [], "_warpWebSockets": native}}


def test_distinct_native_connections_in_separate_files_never_pair_by_url(tmp_path):
    document = fixture("quickspin")
    sent = native_document(document, direction="sent", identity="first-socket")
    received = native_document(document, direction="received", identity="different-socket")
    report = audit([write(tmp_path, sent, "sent.har"), write(tmp_path, received, "received.har")])
    assert report["summary"]["connections"] == 2
    assert report["summary"]["paired_operations"] == 0
    assert report["summary"]["closed_and_settled_rounds"] == 0


def test_same_explicit_native_connection_joins_across_fragments(tmp_path):
    document = fixture("quickspin")
    sent = native_document(document, direction="sent")
    received = native_document(document, direction="received")
    report = audit([write(tmp_path, sent, "sent.har"), write(tmp_path, received, "received.har")])
    assert report["summary"]["connections"] == 1
    assert report["summary"]["paired_operations"] == 13
    assert report["summary"]["closed_and_settled_rounds"] == 1


def test_distinct_native_ids_stay_separate_without_urls(tmp_path):
    document = fixture("quickspin")
    native = native_document(document, include_url=False)
    for frame in native["log"]["_warpWebSockets"]:
        frame["connectionId"] = "sent-socket" if frame["direction"] == "sent" else "received-socket"
    report = audit([write(tmp_path, native)])
    assert report["summary"]["connections"] == 2
    assert report["summary"]["paired_operations"] == 0
    assert report["summary"]["closed_and_settled_rounds"] == 0


@pytest.mark.parametrize("second_explicit_identity", [False, True])
def test_anonymous_entry_cannot_guess_an_explicit_connection_without_overlap(tmp_path, second_explicit_identity):
    document = fixture("quickspin")
    received = native_document(document, direction="received", identity="known-socket")
    entry = deepcopy(document)
    entry["log"]["entries"][0]["_webSocketFrames"] = [
        frame for frame in frames(entry) if frame["direction"] == "sent"]
    paths = [write(tmp_path, entry, "entry.har"), write(tmp_path, received, "native.har")]
    if second_explicit_identity:
        other = {"log": {"entries": [], "_warpWebSockets": [{
            "url": document["log"]["entries"][0]["request"]["url"],
            "connectionId": "other-socket", "direction": "received", "timestamp": 1000,
            "payload": "2::", "opcode": 1}]}}
        paths.append(write(tmp_path, other, "other.har"))
    report = audit(paths)
    assert report["summary"]["paired_operations"] == 0
    assert report["summary"]["closed_and_settled_rounds"] == 0
