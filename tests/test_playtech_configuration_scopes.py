import unittest
from copy import deepcopy
from tester_spin.providers.playtech.protocol import resolve_configuration,configuration_domains,inspect_evidence


def cost(identifier="normal",price=10):
    return {"uuid":identifier,"cost":price,"name":identifier,"parameters":{"startingMode":"Standard","startingPlays":"1"}}


def rows():
    return [{"scope":{},"content":{"game":{"costConfiguration":[cost(),cost("old")],"baseCostMultipliers":[1,2,5],"defaultBaseCostMultiplier":2},"limits":{"minBet":1,"maxBet":500}}},
            {"scope":{"betType":["default","freespin"]},"content":{"game":{"costConfiguration":[cost()]}}},
            {"scope":{"betType":"freespin"},"content":{"game":{"baseCostMultipliers":[1],"defaultBaseCostMultiplier":1},"limits":{"maxBet":10}}}]


class ScopeTests(unittest.TestCase):
    def test_client_scope_merge_replaces_lists_and_preserves_nested_defaults(self):
        source=rows();before=deepcopy(source)
        default=resolve_configuration(source,{"betType":"default"})
        fs=resolve_configuration(source,{"betType":"freespin"})
        self.assertEqual([v["uuid"] for v in default["game"]["costConfiguration"]],["normal"])
        self.assertEqual(default["game"]["baseCostMultipliers"],[1,2,5])
        self.assertEqual(fs["game"]["baseCostMultipliers"],[1])
        self.assertEqual(fs["limits"],{"minBet":1,"maxBet":10})
        self.assertEqual(source,before)

    def test_order_matches_client_instead_of_sorting_by_specificity(self):
        source=[{"scope":{"betType":"default"},"content":{"game":{"baseCostMultipliers":[2]}}},
                {"scope":{},"content":{"game":{"baseCostMultipliers":[1]}}}]
        self.assertEqual(resolve_configuration(source,{"betType":"default"})["game"]["baseCostMultipliers"],[1])

    def test_unknown_scope_keys_do_not_match_implicitly(self):
        source=rows()+[{"scope":{"featureType":"special"},"content":{"game":{"costConfiguration":[cost("special",100)]}}}]
        r=resolve_configuration(source,{"betType":"default"})
        self.assertEqual([v["uuid"] for v in r["game"]["costConfiguration"]],["normal"])
        r=resolve_configuration(source,{"betType":"default","featureType":"special"})
        self.assertEqual([v["uuid"] for v in r["game"]["costConfiguration"]],["special"])

    def test_effective_modes_are_not_scopes_or_stake_size_counts(self):
        r=configuration_domains(rows())
        self.assertEqual(len(r["effective_modes"]),1)
        self.assertEqual(r["effective_modes"][0]["contexts"],["default","freespin"])
        self.assertEqual(r["contexts"]["freespin"]["stake_domain"]["baseCostMultipliers"],[1])
        self.assertEqual(r["contexts"]["default"]["limits"],{"minBet":1,"maxBet":500})
        self.assertEqual(r["contexts"]["freespin"]["limits"],{"minBet":1,"maxBet":10})
        self.assertFalse(r["effective_modes"][0]["executable"])
        self.assertEqual(r["purchase"]["declaration_state"],"UNKNOWN")
        self.assertEqual(r["antebet"]["options"],[])

    def test_same_uuid_with_different_parameters_remains_separate(self):
        source=rows();alternative=cost();alternative["parameters"]["startingMode"]="UnknownFeature"
        source[2]["content"]["game"]["costConfiguration"]=[alternative]
        self.assertEqual(len(configuration_domains(source)["effective_modes"]),2)

    def test_missing_cost_identity_stays_unresolved_instead_of_inflating_modes(self):
        source=rows();source[1]["content"]["game"]["costConfiguration"][0].pop("uuid")
        r=configuration_domains(source)
        self.assertEqual(r["effective_modes"],[])
        self.assertIn("COST_ID_MISSING",r["unresolved"])
        self.assertTrue(r["costs"])

    def test_malformed_or_absent_matching_configuration_is_explicit(self):
        for source,query in ((rows(),{}),([{"scope":[],"content":{}}],{"betType":"default"}),
                             ([{"scope":{"betType":"other"},"content":{}}],{"betType":"default"})):
            with self.assertRaises(ValueError):resolve_configuration(source,query)

    def test_inspection_exposes_effective_modes_without_certifying_historical_spins(self):
        report={"schema":"aislador/playtech-evidence/v1","provider":"playtech","game_codes":["gpas_fixture"],
            "configurations":[{"game_code":"gpas_fixture","ref":"ws:1","data":rows()}],"rounds":[],
            "coverage":"observations_only","certifies_game_ok":False}
        r=inspect_evidence(report,"gpas_fixture")
        self.assertEqual(len(r["effective_modes"]),1)
        self.assertEqual(r["configuration_snapshots"][0]["source_ref"],"ws:1")
        self.assertFalse(r["certifies_game_ok"])
        report["configurations"][0]["issues"]=["SERVER_ERROR"]
        self.assertEqual(inspect_evidence(report,"gpas_fixture")["effective_modes"],[])


if __name__=="__main__":unittest.main()
