import json
import tempfile
import threading
import unittest
from pathlib import Path
from tester_spin.return_to_base import verify_return_to_base


class ReturnToBaseTests(unittest.TestCase):
    def run_sequence(self, sequence, **kwargs):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        queue = iter(sequence)
        def play(directory):
            state = next(queue)
            if isinstance(state, Exception):
                raise state
            return state
        return verify_return_to_base(Path(self.tmp.name), play, **kwargs)

    def test_event_resets_two_consecutive_confirmations(self):
        base = {'ok': True, 'base': True, 'known': True}
        event = {'ok': True, 'base': False, 'known': True}
        proof = self.run_sequence([base, event, base, base])
        self.assertEqual(proof['status'], 'CONFIRMED')
        self.assertEqual(len(proof['probes']), 4)
        self.assertEqual(proof['consecutive_base'], 2)

    def test_unknown_state_stops_without_another_wager(self):
        proof = self.run_sequence([{'ok': True, 'base': False, 'known': False}])
        self.assertEqual(proof['status'], 'REVIEW_REQUIRED')

    def test_error_is_not_classified_as_hidden_choice(self):
        proof = self.run_sequence([RuntimeError('HTTP 422')])
        self.assertEqual(proof['status'], 'ERROR')
        self.assertEqual(proof['cause'], 'UNDETERMINED')
        self.assertTrue((Path(self.tmp.name)/'return-to-base.json').is_file())

    def test_cancelled_and_limit_never_confirm(self):
        stop = threading.Event(); stop.set()
        self.assertEqual(self.run_sequence([], stop_event=stop)['status'], 'CANCELLED')
        e = {'ok': True, 'base': False, 'known': True}
        self.assertEqual(self.run_sequence([e, e], max_probes=2)['status'], 'LIMIT_REACHED')
