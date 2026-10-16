import unittest
from copy import deepcopy
from tester_spin.providers.playtech.protocol import round_evidence


class StakeEvidenceTests(unittest.TestCase):
    def test_captured_stake_identity_and_parameters_survive_round_summary(self):
        message = {"gameData": {
            "stakeCostUuid": "cost-uuid",
            "stakeCostName": "declared", "stakeCostParameters": {"startingMode": "Unknown", "choices": [0, 1]},
            "baseCostMultiplier": 2, "stake": 20}}
        before = deepcopy(message)
        result = round_evidence(message)
        self.assertEqual(result.get("stake_selection"), {
            "stakeCostUuid": "cost-uuid", "stakeCostName": "declared",
            "stakeCostParameters": {"startingMode": "Unknown", "choices": [0, 1]},
            "baseCostMultiplier": 2})
        result.get("stake_selection")["stakeCostParameters"]["choices"].append(2)
        self.assertEqual(message, before)
        self.assertFalse(result["settlement_verified"])
        self.assertFalse(result["certifies_game_ok"])

    def test_absent_selection_stays_unknown_without_using_stake_as_identity(self):
        self.assertEqual(round_evidence({"stakeAmount": 100, "gameData": {"stake": 100}}).get("stake_selection"), {})

    def test_unknown_selection_values_are_preserved_without_defaults(self):
        self.assertEqual(round_evidence({"gameData": {"stakeCostUuid": None, "baseCostMultiplier": 0}}).get("stake_selection"),
                         {"stakeCostUuid": None, "baseCostMultiplier": 0})
