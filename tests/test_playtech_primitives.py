import json
import tempfile
import threading
import unittest
from pathlib import Path
from tester_spin.models import Game
from tester_spin.providers.playtech.protocol import configuration_domains, round_evidence, inspect_evidence


def configuration():
    cost={"uuid":"cost-a","cost":15,"name":"default","parameters":{"startingMode":"Standard"}}
    return [{"scope":{"betType":t},"content":{"game":{"coinSizes":[1,2,5],"baseCostMultipliers":[1,2],"costConfiguration":[cost]}}} for t in ("default","freespin")]


class PlaytechPrimitiveTests(unittest.TestCase):
    def test_stake_sizes_and_freespin_scope_are_not_purchases(self):
        result=configuration_domains(configuration())
        self.assertEqual(len(result["costs"]),2)
        self.assertEqual(result["purchase"]["declaration_state"],"UNKNOWN")
        self.assertEqual(result["antebet"]["declaration_state"],"UNKNOWN")
        self.assertEqual(result["purchase"]["options"],[])
        self.assertEqual(result["costs"][0]["parameters"]["startingMode"],"Standard")

    def test_unknown_cost_variant_is_retained_not_promoted(self):
        cfg=configuration();cfg[0]["content"]["game"]["costConfiguration"].append({"uuid":"new","cost":150,"parameters":{"startingMode":"MYSTERY","choices":[0,1]}})
        r=configuration_domains(cfg)
        self.assertEqual(r["costs"][1]["parameters"]["choices"],[0,1])
        self.assertEqual(r["purchase"]["declaration_state"],"UNKNOWN")

    def test_invalid_cost_does_not_disappear_or_become_executable(self):
        cfg=configuration();cfg[0]["content"]["game"]["costConfiguration"][0]["cost"]=True
        r=configuration_domains(cfg)
        self.assertIn("INVALID_COST",r["unresolved"])

    def test_closed_round_requires_consistent_money_and_terminal_state(self):
        message={"stakeAmount":100,"winAmount":60,"gameRoundClosed":True,"gameData":{"nextRound":"BET_END_STATE_IDENTIFIER"}}
        self.assertTrue(round_evidence(message,1000000,999960)["settlement_verified"])
        self.assertFalse(round_evidence(message,1000000,999961)["settlement_verified"])
        message["betCost"]=200
        self.assertFalse(round_evidence(message,1000000,999960)["settlement_verified"])
        message.pop("betCost")
        message["gameData"]={"nextRound":"PICK","requestParameters":{"selectedIndex":1}}
        r=round_evidence(message,1000000,999960)
        self.assertFalse(r["settlement_verified"])
        self.assertEqual(r["continuation"]["requestParameters"],{"selectedIndex":1})

    def test_nested_pick_options_are_preserved_without_inventing_actions(self):
        message={"gameRoundClosed":False,"gameData":{"nextRound":"PICK","playStack":[{"round":"Bonus","listPickPlayerPickOptions":[{"id":0},{"id":1}]}]}}
        r=round_evidence(message)
        self.assertEqual(r["decisions"][0]["path"],"playStack.0.listPickPlayerPickOptions")
        self.assertEqual(r["decisions"][0]["value"],[{"id":0},{"id":1}])
        self.assertFalse(r["settlement_verified"])

    def test_no_balances_or_bool_closed_is_not_success(self):
        message={"stakeAmount":100,"winAmount":60,"gameRoundClosed":1,"gameData":{"nextRound":"BET_END_STATE_IDENTIFIER"}}
        self.assertFalse(round_evidence(message,None,None)["settlement_verified"])

    def test_historical_report_never_certifies_execution(self):
        report={"schema":"aislador/playtech-evidence/v1","provider":"playtech","game_codes":["gpas_fixture"],"configurations":[{"ref":"ws:1","game_code":"gpas_fixture","data":configuration()}],"rounds":[],"coverage":"observations_only","certifies_game_ok":False}
        r=inspect_evidence(report,"gpas_fixture")
        self.assertFalse(r["certifies_game_ok"])
        self.assertEqual(len(r["costs"]),2)
        with self.assertRaises(ValueError):inspect_evidence(report,"gpas_other")
        report["certifies_game_ok"]=True
        with self.assertRaises(ValueError):inspect_evidence(report,"gpas_fixture")

    def test_error_provenance_survives_handoff(self):
        report={"schema":"aislador/playtech-evidence/v1","provider":"playtech","game_codes":["gpas_fixture"],
            "configurations":[{"ref":"ws:1","game_code":"gpas_fixture","data":configuration(),"issues":["SERVER_ERROR"]}],
            "unresolved":[{"ref":"ws:2","issues":["OPAQUE_WEBSOCKET"]}],"warnings":["WS_CAPTURE_LIMIT"],
            "rounds":[],"coverage":"observations_only","certifies_game_ok":False}
        r=inspect_evidence(report,"gpas_fixture")
        self.assertIn("SERVER_ERROR",r["unresolved"])
        self.assertIn("OPAQUE_WEBSOCKET",r["unresolved"])
        self.assertIn("WS_CAPTURE_LIMIT",r["unresolved"])
        self.assertTrue(any(row.get("ref")=="ws:2" for row in r["evidence_issues"]))

    def test_catalog_adapter_consumes_matching_evidence_without_fake_ok(self):
        from tester_spin.providers.registry import create_provider
        report={"schema":"aislador/playtech-evidence/v1","provider":"playtech","game_codes":["gpas_fixture"],"configurations":[{"ref":"ws:1","game_code":"gpas_fixture","data":configuration()}],"rounds":[],"coverage":"observations_only","certifies_game_ok":False}
        with tempfile.TemporaryDirectory() as td:
            provider=create_provider("playtech",Path(td))
            game=Game("playtech","fixture","Fixture","https://www.playtechone.com/fixture",symbol="gpas_fixture")
            folder=provider.har_artifact_dir(game);(folder/"protocol-evidence.json").write_text(json.dumps(report))
            result=provider.test_game(game,spins=1,timeout_s=10,stop_event=threading.Event(),progress=lambda _:None)
            self.assertEqual(result.status,"PARCIAL")
            self.assertEqual(len(result.structural_map["playtech_protocol"]["costs"]),2)
            self.assertEqual(result.successful_spins,0)
            self.assertEqual(result.feature_domains["purchase"]["declaration_state"],"UNKNOWN")

if __name__=="__main__":unittest.main()
