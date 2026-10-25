"""Negative and positive offline checks for captured Games Global packets."""
import json
import unittest
from decimal import Decimal
from copy import deepcopy

from tester_spin.providers.games_global_har import analyze_har

PLAY = "https://api32.gameassists.co.uk/casino/play/public/v1/games/module/101789/client/40300/play"


def packet(
    action, *, verb="Spin", name="BaseGame", price="2.00",
    payout="0.00", balance="998.00", stage="base", fs=0,
    advertised=("Play", "PlayBonus1x3"),
):
    attrs = 'verbex="' + verb + '"'
    attrs += (' action="' + action + '"') if action else ""
    attrs += (' name="' + name + '"') if name else ""
    request = (
        '<Pkt version="6.1"><Id mid="101789" cid="40300" sid="22619" '
        'verb="AdvSlot"/><Request ' + attrs + '/></Pkt>'
    )
    if stage == "base":
        core = (
            '<Stage name="BaseGame" played="1" remain="0">'
            '<Bet cost="' + str(int(Decimal(price) * 100)) + '"/></Stage>'
            '<Stage name="BaseGame" remain="1" avail="True"><PossibleBets>'
            + "".join('<Action value="' + a + '"/>' for a in advertised)
            + '</PossibleBets></Stage>'
        )
    elif stage == "select":
        core = (
            '<Stage name="BaseGame" played="1" remain="0">'
            '<Bet cost="' + str(int(Decimal(price) * 100)) + '"/></Stage>'
            '<Stage name="FreeSpinsOptionSelect" remain="1" avail="True"/>'
        )
    elif stage == "fs":
        core = (
            '<Stage name="BaseGame" played="1" remain="0"><Bet cost="2000"/></Stage>'
            '<Stage name="FreeSpinsOptionSelect" played="1" remain="0"/>'
            f'<Stage name="FreeSpins" played="{15-fs}" remain="{fs}"/>'
            + ('<Stage name="BaseGame" remain="1" avail="True"/>' if fs == 0 else '')
        )
    else:
        raise ValueError(stage)
    response = (
        '<Pkt><Id mid="101789" cid="40300" sid="22619" verb="Spin"/>'
        '<Response><User id="SENSITIVE-123" bal="99800"/>'
        '<Core>' + core + '</Core></Response></Pkt>'
    )
    return {
        "request": {
            "method": "POST",
            "url": PLAY,
            "postData": {"text": json.dumps({"packet": {"packetType": 7, "payload": request}})},
        },
        "response": {
            "status": 200,
            "content": {"text": json.dumps({
                "packet": {"payload": response},
                "context": {
                    "financials": {
                        "betAmount": float(price), "payoutAmount": float(payout),
                    },
                    "balances": {"totalInAccountCurrency": float(balance)},
                },
            })},
        },
    }


def har(*entries):
    return {"log": {"entries": list(entries)}}


class GamesGlobalHarTests(unittest.TestCase):
    def test_advertised_options_are_not_executed_options(self):
        sample = har(packet(
            "Play",
            advertised=("Play", "PlayBonus1x3", "PlayBonus5x4Guarantee"),
        ))
        result = analyze_har(sample)
        self.assertEqual(
            result["server_advertised_actions"],
            ["Play", "PlayBonus1x3", "PlayBonus5x4Guarantee"],
        )
        self.assertEqual(
            result["advertised_actions_not_observed"],
            ["PlayBonus1x3", "PlayBonus5x4Guarantee"],
        )
        self.assertEqual(result["game_status"], "PARCIAL")
        self.assertEqual(result["server_costs_checked"], 1)
        self.assertNotIn("SENSITIVE-123", json.dumps(result))

    def test_bonus_purchase_choice_terminal_and_normal_probe(self):
        entries = [
            packet("Play", balance="998.00"),
            packet("PlayBonus1x3", price="20.00", balance="978.00", stage="select"),
            packet(
                "FreeSpinOption2", verb="FreeSpin", name="FreeSpinsOptionSelect",
                price="0", balance="978.00", stage="fs", fs=15,
            ),
            packet(
                "FreeSpin", verb="FreeSpin", name="FreeSpins",
                price="0", balance="980.00", payout="2.00",
                stage="fs", fs=0,
            ),
            packet("Play", price="2.00", balance="978.00"),
        ]
        result = analyze_har(har(*entries))
        self.assertEqual(result["balance_mismatch_indices"], [])
        self.assertEqual(
            result["observed_spin_selections"], {"FreeSpinOption2": [15]}
        )
        bonus = result["bonus_purchases_observed"][0]
        self.assertEqual(bonus["price"], "20.00")
        self.assertTrue(bonus["terminal"])
        self.assertTrue(bonus["normal_base_probe"])
        self.assertEqual(bonus["free_spin_requests"], 1)

    def test_accounting_mismatch_is_recorded_and_not_ok(self):
        result = analyze_har(har(
            packet("Play", balance="998.00"),
            packet("Play", balance="998.00"),
        ))
        self.assertEqual(result["balance_mismatch_indices"], [1])
        self.assertEqual(result["game_status"], "PARCIAL")

    def test_reject_mismatched_server_cost(self):
        with self.assertRaisesRegex(ValueError, "SERVER_BET_COST_MISMATCH"):
            analyze_har(har(packet("Play", price="2", stage="fs", balance="998")))

    def test_reject_xxe_and_origin_substitution(self):
        original = packet("Play")
        bad = deepcopy(original)
        payload = json.loads(bad["request"]["postData"]["text"])
        payload["packet"]["payload"] = (
            '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            + payload["packet"]["payload"]
        )
        bad["request"]["postData"]["text"] = json.dumps(payload)
        with self.assertRaisesRegex(ValueError, "UNSAFE_OR_OVERSIZED_XML"):
            analyze_har(har(bad))
        other = deepcopy(original)
        other["request"]["url"] = PLAY.replace(
            "api32.gameassists.co.uk", "evil.example"
        )
        with self.assertRaisesRegex(ValueError, "GAME_PROTOCOL_UNEXPECTED_ORIGIN"):
            analyze_har(har(other))

    def test_reject_mismatched_game_identity(self):
        item = packet("Play")
        body = json.loads(item["response"]["content"]["text"])
        body["packet"]["payload"] = body["packet"]["payload"].replace(
            'mid="101789"', 'mid="0000"'
        )
        item["response"]["content"]["text"] = json.dumps(body)
        with self.assertRaisesRegex(ValueError, "GAME_IDENTITY_MISMATCH"):
            analyze_har(har(item))


if __name__ == "__main__":
    unittest.main()
