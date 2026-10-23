"""Offline-only Games Global AdvancedSlots HAR inspection.

No network access, tokens, session identifiers, personal IDs, or raw payloads
are exported. Captured capabilities are evidence, not permission to replay.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

SCHEMA = "tester-spin/games-global-har-contract/v1"
PLAY_PATH = re.compile(r"/casino/play/public/v1/games/module/(\d+)/client/(\d+)/play\Z")
SAFE_ACTION = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,79}\Z")
MAX_HAR_BYTES = 100 * 1024 * 1024
MAX_ENTRIES = 6000
MAX_PLAY_BODY = 1024 * 1024


def _xml(raw: str) -> ET.Element:
    if not isinstance(raw, str) or len(raw) > MAX_PLAY_BODY or "<!" in raw:
        raise ValueError("UNSAFE_OR_OVERSIZED_XML")
    try:
        doc = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("INVALID_XML_PACKET") from exc
    if doc.tag != "Pkt":
        raise ValueError("UNEXPECTED_PACKET_ROOT")
    return doc


def _money(value: object) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("FINANCIAL_AMOUNT_MISSING")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("INVALID_FINANCIAL_AMOUNT") from exc
    if not number.is_finite() or number.as_tuple().exponent < -4:
        raise ValueError("INVALID_FINANCIAL_AMOUNT")
    return number


def _int(value: str | None) -> int | None:
    if value is None or not re.fullmatch(r"\d{1,12}", value):
        return None
    return int(value)


def _money_str(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _asset_names(entries: list[dict]) -> list[str]:
    names: set[str] = set()
    pattern = re.compile(r"/gameassetsuat/VersionedGames/([^/?#]+)/")
    for e in entries:
        path = urlsplit(str(e.get("request", {}).get("url", ""))).path
        match = pattern.search(path)
        if match:
            # Game/studio/version label, never the query string or credentials.
            names.add(match.group(1)[:160])
    return sorted(names)


def analyze_har(data: dict, *, fingerprint: str = "") -> dict:
    """Inspect captured request/response evidence without executing a request."""
    entries = data.get("log", {}).get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise ValueError("INVALID_HAR_ENTRIES")
    rows: list[dict] = []
    action_counter: Counter[str] = Counter()
    action_declarations: set[str] = set()
    fs_selections: dict[str, set[int]] = {}
    stages_seen: set[str] = set()
    client_ids: set[tuple[str, str]] = set()
    last_balance: Decimal | None = None
    mismatches: list[int] = []
    costs_checked = 0
    returns: list[dict] = []
    natural_sequences: list[dict] = []
    outstanding_bonus: dict | None = None

    for entry in entries:
        request = entry.get("request") if isinstance(entry, dict) else None
        if not isinstance(request, dict):
            continue
        url = urlsplit(str(request.get("url", "")))
        path_match = PLAY_PATH.fullmatch(url.path)
        if not path_match or request.get("method") != "POST":
            continue
        if url.scheme != "https" or not (url.hostname or "").endswith(".gameassists.co.uk"):
            raise ValueError("GAME_PROTOCOL_UNEXPECTED_ORIGIN")
        if not isinstance(request.get("postData"), dict):
            raise ValueError("GAME_REQUEST_BODY_MISSING")
        req_text = request["postData"].get("text")
        response = entry.get("response") if isinstance(entry, dict) else None
        if not isinstance(response, dict) or response.get("status") != 200:
            raise ValueError("GAME_RESPONSE_NOT_SUCCESSFUL")
        response_text = (response.get("content") or {}).get("text")
        if not isinstance(req_text, str) or not isinstance(response_text, str) or any(
            len(s) > MAX_PLAY_BODY for s in (req_text, response_text)
        ):
            raise ValueError("GAME_PACKET_NOT_CAPTURED")
        try:
            req_packet = json.loads(req_text)
            resp_packet = json.loads(response_text)
            req_xml = _xml(req_packet["packet"]["payload"])
            resp_xml = _xml(resp_packet["packet"]["payload"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("GAME_PACKET_SCHEMA_UNRECOGNIZED") from exc
        req_id, resp_id = req_xml.find("Id"), resp_xml.find("Id")
        req_node, resp_node = req_xml.find("Request"), resp_xml.find("Response")
        if any(x is None for x in (req_id, resp_id, req_node, resp_node)):
            raise ValueError("GAME_XML_SCHEMA_UNRECOGNIZED")
        for key, expected in (("mid", path_match.group(1)), ("cid", path_match.group(2))):
            if req_id.get(key) != expected or resp_id.get(key) != expected:
                raise ValueError("GAME_IDENTITY_MISMATCH")
        if req_id.get("sid") != resp_id.get("sid"):
            raise ValueError("GAME_SITE_MISMATCH")
        client_ids.add(path_match.groups())
        verb = req_node.get("verbex", "")
        action = req_node.get("action", "")
        if not SAFE_ACTION.fullmatch(verb) or (action and not SAFE_ACTION.fullmatch(action)):
            raise ValueError("INVALID_GAME_ACTION")
        if req_packet.get("packet", {}).get("packetType") != 7:
            raise ValueError("UNKNOWN_PACKET_TYPE")
        fin = resp_packet.get("context", {}).get("financials")
        balance = resp_packet.get("context", {}).get("balances", {}).get("totalInAccountCurrency")
        if not isinstance(fin, dict):
            raise ValueError("FINANCIAL_EVIDENCE_MISSING")
        spent = _money(fin.get("betAmount"))
        payout = _money(fin.get("payoutAmount"))
        current_balance = _money(balance)
        if last_balance is not None and last_balance - spent + payout != current_balance:
            mismatches.append(len(rows))
        last_balance = current_balance

        core = resp_node.find("Core")
        slot = resp_node.find("Slot")
        if (core is None) == (slot is None):
            raise ValueError("UNKNOWN_GAME_RESPONSE_DIALECT")
        stages: list[dict] = []
        base_available = False
        fs_remain = None
        if core is not None:
            for stage in core.findall("Stage"):
                name = stage.get("name", "")
                if not SAFE_ACTION.fullmatch(name):
                    raise ValueError("INVALID_STAGE_NAME")
                stages_seen.add(name)
                remain = _int(stage.get("remain"))
                played = _int(stage.get("played"))
                stages.append({
                    "name": name, "remain": remain, "played": played,
                    "available": stage.get("avail") == "True",
                })
                if name == "BaseGame" and remain and stage.get("avail") == "True":
                    base_available = True
                if name == "FreeSpins" and remain is not None:
                    fs_remain = remain
                possible = stage.find("PossibleBets")
                if possible is not None and stage.get("avail") == "True":
                    for a in possible.findall("Action"):
                        code = a.get("value", "")
                        if not SAFE_ACTION.fullmatch(code):
                            raise ValueError("UNSAFE_DECLARED_ACTION")
                        action_declarations.add(code)
            base_stage = next(
                (s for s in core.findall("Stage")
                 if s.get("name") == "BaseGame" and s.get("played") == "1"),
                None,
            )
            if base_stage is not None:
                cost_tag = base_stage.find("Bet")
                if verb == "Spin" and cost_tag is not None and cost_tag.get("cost") is not None:
                    price = _int(cost_tag.get("cost"))
                    if price is None or Decimal(price) / 100 != spent:
                        raise ValueError("SERVER_BET_COST_MISMATCH")
                    costs_checked += 1
        else:
            stages_seen.update([slot.get("stage", ""), slot.get("nextStage", "")])
            stages = [{
                "name": slot.get("stage", ""),
                "remain": _int(slot.get("freeSpins")),
                "played": None, "available": True,
            }]
            fs_remain = _int(slot.get("freeSpins"))
            base_available = slot.get("nextStage") == "BaseGame"

        action_counter[action or verb] += 1
        if action.startswith("FreeSpinOption") and fs_remain is not None:
            fs_selections.setdefault(action, set()).add(fs_remain)
        if verb == "Spin" and outstanding_bonus and outstanding_bonus.get("terminal"):
            # A purchase after a bonus proves base admission, but is NOT
            # equivalent to an ordinary-spin return probe.
            outstanding_bonus["subsequent_base_command"] = True
            if not action.startswith("PlayBonus"):
                outstanding_bonus["normal_base_probe"] = True
            outstanding_bonus = None
        if verb == "Spin" and action.startswith("PlayBonus"):
            outstanding_bonus = {
                "action": action, "price": _money_str(spent),
                "selection": None, "free_spin_requests": 0, "terminal": False,
                "subsequent_base_command": False, "normal_base_probe": False,
            }
            returns.append(outstanding_bonus)
        if core is None and verb == "Spin" and slot.get("nextStage") == "FreeSpins":
            outstanding_bonus = {
                "action": "NATURAL_FREE_SPINS", "trigger_bet": _money_str(spent),
                "initial_spins": fs_remain, "free_spin_requests": 0,
                "terminal": False, "subsequent_base_command": False,
                "normal_base_probe": False,
            }
            natural_sequences.append(outstanding_bonus)
        if action.startswith("FreeSpinOption") and outstanding_bonus:
            outstanding_bonus["selection"] = action
            outstanding_bonus["initial_spins"] = fs_remain
        if verb == "FreeSpin" and outstanding_bonus and (
            action == "FreeSpin" or (not action and core is None)
        ):
            outstanding_bonus["free_spin_requests"] += 1
            if fs_remain == 0 and base_available:
                outstanding_bonus["terminal"] = True

        rows.append({
            "action": action or verb, "verb": verb,
            "bet": _money_str(spent), "payout": _money_str(payout),
            "balance": _money_str(current_balance), "stages": stages,
            "free_spins_remaining": fs_remain, "base_available": base_available,
        })

    if not rows:
        raise ValueError("NO_GAME_PLAY_PACKETS")
    if len(client_ids) != 1:
        raise ValueError("MULTIPLE_GAME_CLIENT_PROTOCOLS")
    module, client = next(iter(client_ids))
    return {
        "schema": SCHEMA,
        "source_sha256": fingerprint,
        "capture_game_assets": _asset_names(entries),
        "module": module,
        "client": client,
        "protocol_dialect": (
            "staged-core"
            if any(s["name"] == "FreeSpinsOptionSelect" for r in rows for s in r["stages"])
            else "slot-legacy"
        ),
        "play_packets": len(rows),
        "actions_observed": dict(sorted(action_counter.items())),
        "server_advertised_actions": sorted(action_declarations),
        "advertised_actions_not_observed": sorted(action_declarations - set(action_counter)),
        "observed_spin_selections": {
            name: sorted(values) for name, values in sorted(fs_selections.items())
        },
        "stages_observed": sorted(s for s in stages_seen if s),
        "balance_mismatch_indices": mismatches,
        "server_costs_checked": costs_checked,
        "bonus_purchases_observed": returns,
        "natural_bonuses_observed": natural_sequences,
        "first_balance_after_packet": rows[0]["balance"],
        "last_balance_after_packet": rows[-1]["balance"],
        "last_result_base_available": rows[-1]["base_available"],
        "sample_actions": [
            {key: r[key] for key in ("action", "bet", "payout", "balance")}
            for r in rows
            if r["verb"] == "Spin" or r["action"].startswith("FreeSpinOption")
        ],
        "game_status": "PARCIAL",
        "limitations": [
            "HAR offline; no new live session verified",
            "Unexecuted advertised actions and spin choices remain uncovered",
            "No network calls or credentials are exported",
        ],
    }


def inspect_har_file(path: str | Path) -> dict:
    file = Path(path)
    if file.stat().st_size > MAX_HAR_BYTES:
        raise ValueError("HAR_TOO_LARGE")
    raw = file.read_bytes()
    return analyze_har(json.loads(raw), fingerprint=hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Offline Games Global HAR contract inspector (no replay)"
    )
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, help="Write sanitized JSON")
    args = parser.parse_args()
    output = [inspect_har_file(file) for file in args.files]
    result = {"schema": SCHEMA, "captures": output}
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
