"""Read-only GPAS family checks against historical HAR messages.

The observed wire contract is sufficient to exercise pure builders, but never
authorizes live dispatch. This module neither constructs a provider nor writes
game results. Identifiers used for joins remain private to this call.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import zipfile

from . import primitives
from .gpas_continuation import ContinuationPlanner
from .operation_scopes import validate_stake_domain
from .protocol import money, resolve_configuration


SCHEMA = "tester-spin/playtech-family-audit/v1"
COMMAND = "com.pt.casino.platform.game.GameCommand"
_MAX_FILE_BYTES = 256 * 1024 * 1024
_MAX_TOTAL_BYTES = 1024 * 1024 * 1024
_MAX_FILES = 4096
_SYMBOL = re.compile(r"[A-Za-z_$][A-Za-z0-9_.$-]{0,159}\Z")


def _symbol(value, default="UNKNOWN"):
    return value if isinstance(value, str) and _SYMBOL.fullmatch(value) else default


def _code(error):
    value = str(error)
    return value if re.fullmatch(r"[A-Z][A-Z0-9_]{1,100}", value) else "PRIMITIVE_REJECTED_EVIDENCE"


def _documents(paths):
    total = 0
    count = 0
    for raw_path in paths:
        path = Path(raw_path)
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                members = sorted((m for m in archive.infolist()
                                  if not m.is_dir() and m.filename.lower().endswith(".har")),
                                 key=lambda m: m.filename)
                if not members:
                    raise ValueError("ZIP_HAS_NO_HAR")
                for member in members:
                    count += 1
                    total += member.file_size
                    if member.file_size > _MAX_FILE_BYTES or total > _MAX_TOTAL_BYTES or count > _MAX_FILES:
                        raise ValueError("CAPTURE_SIZE_LIMIT")
                    yield archive.read(member)
        else:
            size = path.stat().st_size
            total += size
            count += 1
            if size > _MAX_FILE_BYTES or total > _MAX_TOTAL_BYTES or count > _MAX_FILES:
                raise ValueError("CAPTURE_SIZE_LIMIT")
            yield path.read_bytes()


def _message(frame):
    # A cached exporter decode must not override the actual wire payload.
    payload = frame.get("payloadData", frame.get("data", frame.get("payload")))
    if isinstance(payload, str):
        text = payload[4:] if payload.startswith("3:::") else payload
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            return None, payload, False
        return parsed if isinstance(parsed, dict) else None, payload, False
    decoded = frame.get("decoded")
    parsed = decoded.get("parsed") if isinstance(decoded, dict) else None
    if isinstance(parsed, dict):
        return parsed, json.dumps(parsed, sort_keys=True, separators=(",", ":")), True
    return None, "", False


def _timestamp(frame):
    value = frame.get("timestamp", frame.get("time"))
    return value if type(value) in (int, float) and math.isfinite(value) else None


def _capture_frames(document):
    """Normalize exporter entries and Tester-Spin's native socket recorder.

    Identity arbitration happens across the complete input set in _read, never
    independently per document. Both representations use the same decoder.
    """
    for entry_index, entry in enumerate(document["log"]["entries"]):
        if not isinstance(entry, dict):
            continue
        frames = entry.get("_webSocketFrames", entry.get("_webSocketMessages"))
        if not isinstance(frames, list):
            continue
        request = entry.get("request") or {}
        url = request.get("url") if isinstance(request, dict) else None
        for frame_index, frame in enumerate(frames):
            identity = frame.get("connectionId", entry.get("connectionId")) if isinstance(frame, dict) else None
            yield url, identity, {"entry": entry_index, "frame": frame_index}, frame
    native = document["log"].get("_warpWebSockets", [])
    if not isinstance(native, list):
        raise ValueError("INVALID_NATIVE_SOCKET_CAPTURE")
    for frame_index, frame in enumerate(native):
        if not isinstance(frame, dict):
            continue
        yield frame.get("url"), frame.get("connectionId"), {
            "entry": None, "frame": frame_index, "format": "_warpWebSockets"}, frame


def _read(paths):
    connections = {}
    files = []
    seen = set()
    issues = set()
    counts = {"frames": 0, "duplicate_frames": 0, "decoded_only_frames": 0}
    captured = []
    explicit_ids = defaultdict(set)
    identified_witnesses = defaultdict(set)
    anonymous_witnesses = defaultdict(set)
    order = 0
    for raw in _documents(paths):
        try:
            document = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ValueError("INVALID_HAR_JSON") from None
        if not isinstance(document, dict) or not isinstance(document.get("log"), dict):
            raise ValueError("INVALID_HAR_DOCUMENT")
        entries = document["log"].get("entries")
        if not isinstance(entries, list):
            raise ValueError("INVALID_HAR_ENTRIES")
        file_id = "har-" + str(len(files) + 1).zfill(4)
        files.append({"file": file_id, "sha256": sha256(raw).hexdigest()})
        for url, identity, location, frame in _capture_frames(document):
            if not isinstance(frame, dict):
                continue
            order += 1
            counts["frames"] += 1
            parsed, payload, decoded_only = _message(frame)
            direction = frame.get("direction", frame.get("type"))
            direction = {"send": "sent", "receive": "received"}.get(direction, direction)
            stamp = _timestamp(frame)
            url_key = sha256(url.encode()).hexdigest() if isinstance(url, str) and url else None
            explicit = _correlation(identity)
            explicit = sha256(json.dumps(explicit).encode()).hexdigest() if explicit is not None else None
            group = (file_id, location.get("format", "entry"), location["entry"], url_key)
            signature = (stamp, direction, frame.get("opcode"), sha256(payload.encode()).hexdigest())
            data = parsed.get("data") if isinstance(parsed, dict) else None
            # Anonymous entries can be associated with an explicit connection
            # only through an identical, timed gameplay frame, not a common
            # heartbeat or URL. A second explicit ID anywhere makes the URL
            # ambiguous for all anonymous fragments.
            witness = (stamp is not None and isinstance(data, dict)
                       and data.get("_type") == COMMAND
                       and _correlation(parsed.get("correlationId")) is not None)
            if url_key is not None and explicit is not None:
                explicit_ids[url_key].add(explicit)
                if witness:
                    identified_witnesses[(url_key, explicit)].add(signature)
            elif witness and url_key is not None:
                anonymous_witnesses[group].add(signature)
            captured.append({"url": url_key, "explicit": explicit, "group": group,
                             "file": file_id, "location": location, "signature": signature,
                             "parsed": parsed, "direction": direction, "stamp": stamp,
                             "order": order, "decoded_only": decoded_only})
    aliases = {}
    for group, witnesses in anonymous_witnesses.items():
        url_key = group[-1]
        identities = explicit_ids[url_key]
        if len(identities) == 1:
            explicit = next(iter(identities))
            if witnesses & identified_witnesses[(url_key, explicit)]:
                aliases[group] = explicit
    for capture in captured:
            url_key, explicit = capture["url"], capture["explicit"]
            file_id, location = capture["file"], capture["location"]
            problem = None
            if explicit is not None:
                # Missing URLs do not collapse distinct native IDs. IDs alone
                # are local to a capture and cannot join unrelated files.
                connection = ("identified", url_key, explicit) if url_key is not None else (
                    "local-identified", file_id, explicit)
            elif url_key is not None and not explicit_ids[url_key]:
                connection = ("url", url_key)
            elif url_key is not None and capture["group"] in aliases:
                connection = ("identified", url_key, aliases[capture["group"]])
            elif url_key is not None:
                connection = ("anonymous", capture["group"])
                problem = ("CONNECTION_IDENTITY_AMBIGUOUS" if len(explicit_ids[url_key]) > 1
                           else "CONNECTION_IDENTITY_NOT_RECONCILED")
            else:
                connection = ("unidentified", capture["group"],
                              location["frame"] if location.get("format") == "_warpWebSockets" else None)
                problem = "CONNECTION_IDENTITY_MISSING"
            if problem:
                issues.add(problem)
            if url_key is None:
                issues.add("CONNECTION_URL_MISSING")
            events = connections.setdefault(connection, [])
            stamp, direction, parsed = capture["stamp"], capture["direction"], capture["parsed"]
            # Missing times cannot distinguish a retransmission from a new
            # identical message. Retain both instead of silently deduping.
            key = (connection, capture["signature"],
                   None if stamp is not None else (file_id, json.dumps(location)))
            if key in seen:
                counts["duplicate_frames"] += 1
                continue
            seen.add(key)
            if not isinstance(parsed, dict) or direction not in ("sent", "received"):
                continue
            data = parsed.get("data")
            if not isinstance(data, dict):
                continue
            if stamp is None:
                issues.add("FRAME_TIMESTAMP_MISSING")
            counts["decoded_only_frames"] += capture["decoded_only"]
            events.append({"data": data, "correlation": parsed.get("correlationId"),
                           "direction": direction, "stamp": stamp,
                           "sort": (stamp if stamp is not None else math.inf, capture["order"]),
                           "identity_issue": problem,
                           "ref": {"file": file_id, **location}})
    for events in connections.values():
        events.sort(key=lambda event: event["sort"])
    return connections, files, counts, issues


def _correlation(value):
    if type(value) not in (str, int) or value == "":
        return None
    return type(value).__name__, value


def _dialect(data):
    game = data.get("gameData")
    if not isinstance(game, dict):
        return "unknown"
    if "betCost" in data and "featureType" in data:
        return "modern"
    if all(key in game for key in ("bet", "stakeCostUuid", "baseCostMultiplier")):
        return "legacy"
    return "unknown"


def _capability():
    return {"observed": 0, "verified": 0, "issues": set(), "missing_evidence": set()}


def _family(families, command_class, dialect):
    signature = {"envelope": COMMAND, "command_class": _symbol(command_class), "dialect": dialect}
    key = sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()[:20]
    if key not in families:
        families[key] = {
            "family_id": "gpas-" + key, **signature, "contract_source": "wire_observation",
            "live_executable": None, "game_codes": set(), "operations": 0,
            "requests": 0, "responses": 0, "rounds": 0,
            "capabilities": {name: _capability() for name in (
                "recognition", "entry", "configuration_scope", "continuation", "settlement")},
            "issues": set(), "missing_evidence": {"CURRENT_CLIENT_CONTRACT_REQUIRED"},
            "phases": {}, "evidence_refs": [],
        }
    return families[key]


def _contract(family):
    command_class = family["command_class"]
    dialect = family["dialect"]
    command_family = ("quickspin-modern" if command_class == "quickspin.game.playMoney" and dialect == "modern"
                      else "corosin-" + dialect if command_class == primitives.GAME_CLASS else "unknown")
    return {"class": command_class, "dialect": dialect, "entry_id": 40021,
            "continuation_id": 48775, "pick_bound": False,
            "command_family": command_family, "command_binding_validated": False,
            "binding_source": "wire_observation"}


def _known_contract(contract):
    return ((contract["class"] == primitives.GAME_CLASS
             and contract["dialect"] in ("modern", "legacy"))
            or (contract["class"] == "quickspin.game.playMoney"
                and contract["dialect"] == "modern"))


def _semantics(command):
    game = command.get("gameData") or {}
    # An omitted empty list carries no semantic parameters. Explicit null is
    # retained: Quickspin's wire serializer is a separate contract.
    parameters = game.get("parameters", [])
    return {"envelope": command.get("_type"), "autoplay": command.get("autoplay", False),
            **{key: command.get(key) for key in ("betType", "featureType", "betCost")},
            "game": {**{key: game.get(key) for key in (
                "_type", "ID", "bet", "stakeCostUuid", "baseCostMultiplier")}, "parameters": parameters}}


def _compare_command(actual, captured):
    command_keys = {"_type", "autoplay", "betType", "featureType", "betCost", "gameData"}
    game_keys = {"_type", "ID", "bet", "stakeCostUuid", "baseCostMultiplier", "parameters"}
    # Transport metadata lives outside data/GameCommand. An unfamiliar field
    # inside the action is not safe to discard merely because our builder does
    # not know it. Both generated and observed extra fields require a binding.
    for command in (actual, captured):
        game = command.get("gameData")
        if (set(command) - command_keys or not isinstance(game, dict)
                or set(game) - game_keys):
            return "UNREPRODUCED_COMMAND_FIELDS"
    left, right = _semantics(actual), _semantics(captured)
    if left["game"]["parameters"] != right["game"]["parameters"]:
        return "PARAMETERS_NOT_REPRODUCED"
    return "COMMAND_NOT_REPRODUCED" if left != right else None


def _entry_probe(pair, configurations, contract):
    if not _known_contract(contract):
        return False, False, "COMMAND_CONTRACT_UNSUPPORTED", None
    request, response = pair
    sent = request["data"]
    received = primitives.decode_game_data(response["data"].get("gameData"))
    configurations = [event for event in configurations if event["sort"] < request["sort"]]
    if not configurations:
        return False, False, None, "MODE_CONFIGURATION_NOT_CAPTURED"
    context = {"betType": sent.get("betType", "default")}
    selector = sent.get("featureType")
    if isinstance(selector, str):
        context["featureType"] = selector
    config = resolve_configuration(configurations[-1]["data"].get("data"), context)
    domain = validate_stake_domain(config)
    game = config["game"]
    costs = game.get("costConfiguration")
    if not isinstance(costs, list):
        return False, False, None, "COST_DECLARATION_NOT_CAPTURED"
    identity = received.get("stakeCostUuid")
    rows = [row for row in costs if isinstance(row, dict) and row.get("uuid") == identity]
    if len(rows) != 1 or not money(rows[0].get("cost")) or rows[0]["cost"] == 0:
        return False, False, "COST_ROW_NOT_RESOLVED", None
    factor = received.get("baseCostMultiplier")
    if factor is None:
        factor = sent.get("gameData", {}).get("baseCostMultiplier")
    if factor is None:
        # Modern commands can expose only the total amount. The independent
        # receipt and declared unit cost determine a factor exactly; this is
        # an offline arithmetic observation, never a new live wager choice.
        charged = response["data"].get("stakeAmount")
        if money(charged) and charged > 0 and charged % rows[0]["cost"] == 0:
            factor = charged // rows[0]["cost"]
        else:
            return False, False, None, "STAKE_MULTIPLIER_NOT_CAPTURED"
    if not money(factor) or factor == 0 or factor not in domain["factors"]:
        return False, False, "ENTRY_MULTIPLIER_OUTSIDE_SCOPE", None
    price = rows[0]["cost"] * factor
    if (price < domain["min_bet"]
            or domain["max_bet"] is not None and price > domain["max_bet"]):
        return False, False, "ENTRY_COST_OUTSIDE_SCOPE", None
    mode = {"id": identity, "name": rows[0].get("name"), "kind": "OBSERVED_ENTRY",
            "cost": rows[0]["cost"], "multiplier": factor, "selector": selector,
            "bet_type": sent.get("betType", "default")}
    actual = primitives.entry_command(mode, contract)
    issue = _compare_command(actual, sent)
    return issue is None, True, issue, None


def _gamecycle(response):
    debug = response.get("debug")
    context = debug.get("context") if isinstance(debug, dict) else None
    cycle = context.get("gamecycle") if isinstance(context, dict) else None
    return cycle if isinstance(cycle, dict) else {}


def _balance(event):
    if (event["stamp"] is None or event["direction"] != "received"
            or not str(event["data"].get("_type", "")).endswith("BalanceNotification")):
        return None
    balances = event["data"].get("balance")
    if not isinstance(balances, list):
        return None
    amounts = [item.get("amount") for item in balances if isinstance(item, dict)
               and str(item.get("_type", "")).endswith("MonetaryBalanceData")]
    return amounts[0] if len(amounts) == 1 and money(amounts[0]) else None


def _truth(value):
    return value is True or value == "true"


def _round(pairs, family, events, configurations, alias, connection_issues):
    pairs.sort(key=lambda pair: pair[0]["sort"])
    family["rounds"] += 1
    settlement = family["capabilities"]["settlement"]
    settlement["observed"] += 1
    problems = set(connection_issues)
    missing = set()
    first, last = pairs[0][0], pairs[-1][1]
    first_data = first["data"].get("gameData") or {}
    responses = [pair[1]["data"] for pair in pairs]
    cycles = [_gamecycle(data) for data in responses]
    if first_data.get("ID") != 40021 or not _truth(cycles[0].get("firstTurn")):
        missing.add("ROUND_START_NOT_CAPTURED")
    if any(not cycle.get("id") or not cycle.get("turn") for cycle in cycles):
        missing.add("ROUND_LINK_EVIDENCE_MISSING")
    for before, after in zip(cycles, cycles[1:]):
        if before.get("turn") and after.get("previousTurn") != before.get("turn"):
            problems.add("ROUND_CHAIN_BROKEN")
    for previous, current in zip(pairs, pairs[1:]):
        if current[0]["sort"] <= previous[1]["sort"]:
            problems.add("CONTINUATION_PRECEDES_STATE")
    if any(pair[0]["stamp"] is None or pair[1]["stamp"] is None for pair in pairs):
        missing.add("FRAME_TIMESTAMP_MISSING")
    before = [(event, _balance(event)) for event in events if event["sort"] < first["sort"]]
    before = [(event, amount) for event, amount in before if amount is not None]
    next_request = next((event["sort"] for event in events if event["sort"] > last["sort"]
                         and event["direction"] == "sent" and event["data"].get("_type") == COMMAND), None)
    after = [(event, _balance(event)) for event in events if event["sort"] > last["sort"]
             and (next_request is None or event["sort"] < next_request)]
    after = [(event, amount) for event, amount in after if amount is not None]
    before_amount = before[-1][1] if before else None
    after_amount = after[0][1] if after else None
    charge = first["data"].get("betCost", first_data.get("bet"))
    ledger = None
    states = []
    try:
        initial = primitives.decode_game_data(responses[0].get("gameData"))
        if not money(charge):
            raise ValueError("ENTRY_CHARGE_NOT_CAPTURED")
        identity = initial.get("stakeCostUuid")
        if not isinstance(identity, str) or not identity.strip():
            missing.add("STAKE_IDENTITY_NOT_CAPTURED")
        else:
            if "stakeCostUuid" in first_data:
                requested = first_data["stakeCostUuid"]
                if not isinstance(requested, str) or not requested.strip():
                    missing.add("STAKE_IDENTITY_NOT_CAPTURED")
                elif requested != identity:
                    problems.add("STAKE_UUID_MISMATCH")
            ledger = primitives.RoundLedger(before_amount, identity, charge)
            for index, response in enumerate(responses):
                if ledger.closed:
                    raise ValueError("RESPONSE_AFTER_ROUND_CLOSED")
                if index and pairs[index][0]["data"].get("gameData", {}).get("ID") != 48775:
                    raise ValueError("UNEXPECTED_ENTRY_IN_ROUND")
                if type(response.get("gameRoundClosed")) is not bool:
                    raise ValueError("ROUND_TERMINAL_STATUS_MISSING")
                states.append(ledger.accept(response))
    except (ValueError, TypeError, KeyError) as exc:
        problems.add(_code(exc))
    closed = bool(ledger and ledger.closed and len(states) == len(responses))
    if closed and not _truth(cycles[-1].get("lastTurn")):
        problems.add("ROUND_LAST_TURN_CONTRADICTION")
    if not closed and not problems and len(states) == len(responses):
        missing.add("ROUND_END_NOT_CAPTURED")
    if closed:
        if before_amount is None or after_amount is None:
            missing.add("ROUND_BALANCE_NOT_CAPTURED")
        elif not ledger.verify(after_amount):
            problems.add("BALANCE_NOT_RECONCILED")
    verified = bool(closed and not problems and not missing and ledger.verify(after_amount))
    settlement["verified"] += verified
    settlement["issues"].update(problems)
    settlement["missing_evidence"].update(missing)
    contract = _contract(family)
    for pair in pairs:
        if pair[0]["data"].get("gameData", {}).get("ID") != 40021:
            continue
        entry = family["capabilities"]["entry"]
        scope = family["capabilities"]["configuration_scope"]
        try:
            ok, scoped, issue, absent = _entry_probe(pair, configurations, contract)
        except (ValueError, TypeError, KeyError) as exc:
            ok, scoped, issue, absent = False, False, _code(exc), None
        entry["verified"] += ok
        scope["verified"] += scoped
        if issue:
            entry["issues"].add(issue)
            if not scoped:
                scope["issues"].add(issue)
        if absent:
            entry["missing_evidence"].add(absent)
            scope["missing_evidence"].add(absent)
    planner, picks = ContinuationPlanner(), primitives.PickState()
    continuation = family["capabilities"]["continuation"]
    for index, pair in enumerate(pairs[1:], 1):
        if pair[0]["data"].get("gameData", {}).get("ID") != 48775:
            continue
        phase = "UNKNOWN"
        issue = None
        try:
            state = primitives.decode_game_data(responses[index - 1].get("gameData"))
            phase = _symbol(state.get("nextRound"))
            if pair[0]["sort"] <= pairs[index - 1][1]["sort"]:
                raise ValueError("CONTINUATION_PRECEDES_STATE")
            if cycles[index - 1].get("turn") and cycles[index].get("previousTurn") != cycles[index - 1]["turn"]:
                raise ValueError("ROUND_CHAIN_BROKEN")
            if not _known_contract(contract):
                raise ValueError("COMMAND_CONTRACT_UNSUPPORTED")
            parameters = planner.parameters(state, contract, picks)
            actual = primitives.continuation_command(parameters, contract)
            issue = _compare_command(actual, pair[0]["data"])
        except (ValueError, TypeError, KeyError) as exc:
            issue = _code(exc)
        phase_row = family["phases"].setdefault(phase, _capability())
        phase_row["observed"] += 1
        continuation["verified"] += issue is None
        phase_row["verified"] += issue is None
        if issue:
            continuation["issues"].add(issue)
            phase_row["issues"].add(issue)
    family["issues"].update(problems)
    family["missing_evidence"].update(missing)
    if len(family["evidence_refs"]) < 6:
        family["evidence_refs"].append({"round": alias, "start": first["ref"], "end": last["ref"]})
    return {"round": alias, "family_id": family["family_id"], "operations": len(pairs),
            "closed": closed, "settlement_verified": verified,
            "open_prefix": bool(ledger and not closed and not problems and len(states) == len(responses)
                                and responses[-1].get("gameRoundClosed") is False
                                and "ROUND_START_NOT_CAPTURED" not in missing),
            "issues": sorted(problems), "missing_evidence": sorted(missing),
            "start": first["ref"], "end": last["ref"]}


def _finish_capability(capability, *, settlement=False):
    observed, verified = capability["observed"], capability["verified"]
    if capability["issues"]:
        state = "INCONSISTENT" if settlement else "PARTIAL"
    elif observed and verified == observed:
        state = "VERIFIED_OFFLINE"
    elif verified:
        state = "PARTIAL"
    else:
        state = "OBSERVED" if observed else "MISSING_EVIDENCE"
    return {"state": state, "observed": observed, "verified": verified,
            "issues": sorted(capability["issues"]),
            "missing_evidence": sorted(capability["missing_evidence"])}


def analyze_hars(paths: list[Path]) -> dict:
    """Inspect local HAR/ZIP files without contacting hosts or persisting state.

    Counts describe unique messages, operations and rounds separately. An open
    prefix says only that its ending was not captured; it is not a server fault.
    """
    if not isinstance(paths, (list, tuple)) or not paths:
        raise ValueError("CAPTURE_PATHS_REQUIRED")
    connections, files, counts, issues = _read(paths)
    families = {}
    rounds = []
    games = set()
    total_requests = total_responses = total_pairs = 0
    unpaired_requests = unpaired_responses = 0
    for events in connections.values():
        inits = [event for event in events if event["direction"] == "sent"
                 and event["data"].get("_type") == "InitGameSession"]
        codes = {_symbol(event["data"].get("gameCode")) for event in inits}
        codes.discard("UNKNOWN")
        games.update(codes)
        connection_issues = {event["identity_issue"] for event in events if event.get("identity_issue")}
        if len(codes) > 1 or len(inits) > 1:
            connection_issues.add("CONNECTION_INITIALIZATION_AMBIGUOUS")
        requests = [event for event in events if event["direction"] == "sent"
                    and event["data"].get("_type") == COMMAND]
        responses = [event for event in events if event["direction"] == "received"
                     and event["data"].get("_type") == COMMAND]
        total_requests += len(requests)
        total_responses += len(responses)
        dialects = defaultdict(set)
        for request in requests:
            game_data = request["data"].get("gameData")
            if not isinstance(game_data, dict):
                raise ValueError("GAME_COMMAND_DATA_INVALID")
            if game_data.get("ID") == 40021:
                dialects[_symbol(game_data.get("_type"))].add(_dialect(request["data"]))
        for request in requests:
            game_data = request["data"].get("gameData")
            game_data = game_data if isinstance(game_data, dict) else {}
            command_class = _symbol(game_data.get("_type"))
            found = dialects.get(command_class, set())
            dialect = next(iter(found)) if len(found) == 1 else _dialect(request["data"])
            family = _family(families, command_class, dialect)
            request["family"] = family
            family["game_codes"].update(codes if len(codes) == 1 else ())
            family["requests"] += 1
            action = game_data.get("ID")
            if action == 40021:
                family["capabilities"]["entry"]["observed"] += 1
                family["capabilities"]["configuration_scope"]["observed"] += 1
            elif action == 48775:
                family["capabilities"]["continuation"]["observed"] += 1
            else:
                family["issues"].add("COMMAND_ID_UNSUPPORTED")
            if not inits:
                family["missing_evidence"].add("GAME_INITIALIZATION_NOT_CAPTURED")
        req_by_id, res_by_id = defaultdict(list), defaultdict(list)
        for collection, destination in ((requests, req_by_id), (responses, res_by_id)):
            for event in collection:
                identity = _correlation(event["correlation"])
                if identity is None:
                    issues.add("CORRELATION_MISSING")
                else:
                    destination[identity].append(event)
        paired_req, paired_res = set(), set()
        cycles = defaultdict(list)
        configurations = [event for event in events if event["direction"] == "received"
                          and event["data"].get("_type") == "com.pt.gpas.config.GetGameConfigurationResponse"]
        for identity in req_by_id.keys() | res_by_id.keys():
            sent, received = req_by_id[identity], res_by_id[identity]
            if len(sent) != 1 or len(received) != 1:
                if len(sent) > 1 or len(received) > 1:
                    issues.add("CORRELATION_AMBIGUOUS")
                continue
            request, response = sent[0], received[0]
            if response["sort"] <= request["sort"]:
                issues.add("RESPONSE_PRECEDES_REQUEST")
                continue
            paired_req.add(id(request))
            paired_res.add(id(response))
            total_pairs += 1
            request["family"]["operations"] += 1
            request["family"]["responses"] += 1
            cycle = _gamecycle(response["data"]).get("id")
            if type(cycle) not in (str, int) or cycle == "":
                cycle = ("missing", id(request))
            else:
                cycle = (type(cycle).__name__, cycle)
            cycles[cycle].append((request, response))
        for request in requests:
            if id(request) not in paired_req:
                family = request["family"]
                family["missing_evidence"].add("GAME_RESPONSE_NOT_PAIRED")
                action = request["data"].get("gameData", {}).get("ID")
                name = "continuation" if action == 48775 else "entry"
                family["capabilities"][name]["missing_evidence"].add("GAME_RESPONSE_NOT_PAIRED")
        unpaired_requests += len(requests) - len(paired_req)
        unpaired_responses += len(responses) - len(paired_res)
        for pairs in sorted(cycles.values(), key=lambda group: min(pair[0]["sort"] for pair in group)):
            family = min(pairs, key=lambda pair: pair[0]["sort"])[0]["family"]
            round_issues = set(connection_issues)
            if any(pair[0]["family"] is not family for pair in pairs):
                round_issues.add("ROUND_COMMAND_CONTRACT_CHANGED")
            rounds.append(_round(pairs, family, events, configurations,
                                 "round-" + str(len(rounds) + 1).zfill(4), round_issues))
    public_families = []
    for family in sorted(families.values(), key=lambda value: value["family_id"]):
        for capability in family["capabilities"].values():
            family["issues"].update(capability["issues"])
            family["missing_evidence"].update(capability["missing_evidence"])
        family["capabilities"] = {
            key: _finish_capability(value, settlement=key == "settlement")
            for key, value in family["capabilities"].items()}
        family["capabilities"]["recognition"].update(
            state="MISSING_EVIDENCE", missing_evidence=["CURRENT_CLIENT_CONTRACT_REQUIRED"])
        family["capabilities"]["continuation"]["phases"] = [
            {"phase": phase, **_finish_capability(value)}
            for phase, value in sorted(family.pop("phases").items())]
        family["games"] = len(family["game_codes"])
        family["game_codes"] = sorted(family["game_codes"])
        family["issues"] = sorted(family["issues"])
        family["missing_evidence"] = sorted(family["missing_evidence"])
        issues.update(family["issues"])
        public_families.append(family)
    if unpaired_requests or unpaired_responses:
        issues.add("UNPAIRED_GAME_COMMAND")
    return {"schema": SCHEMA, "scope": "historical_capture", "certifies_live_ok": False,
            "summary": {"files": len(files), "connections": len(connections), "games": len(games),
                        **counts, "unique_frames": counts["frames"] - counts["duplicate_frames"],
                        "gameplay_requests": total_requests, "gameplay_responses": total_responses,
                        "paired_operations": total_pairs, "unpaired_requests": unpaired_requests,
                        "unpaired_responses": unpaired_responses, "rounds": len(rounds),
                        "closed_and_settled_rounds": sum(row["settlement_verified"] for row in rounds),
                        "open_round_prefixes": sum(row["open_prefix"] for row in rounds),
                        "invalid_rounds": sum(bool(row["issues"]) for row in rounds)},
            "families": public_families, "rounds": rounds, "files": files, "issues": sorted(issues),
            "limits": ["Offline checks cover observed operations, not unobserved modes or live readiness.",
                       "A missing round ending is a capture limit, not proof that the server failed.",
                       "Current client bindings, current declarations and a fresh execution remain required for live OK."]}
