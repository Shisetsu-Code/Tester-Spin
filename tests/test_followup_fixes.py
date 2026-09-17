import unittest
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from tester_spin.provider_return_checks import bgaming_check
from tester_spin.return_to_base import audit_scope
from tester_spin.server_observations import ResponseObserver


class FollowupFixTests(unittest.TestCase):
    def test_known_events_finish_then_require_two_new_normal_spins(self):
        for event, command in [('freespins', 'freespin'), ('respin', 'respin')]:
            with self.subTest(event=event), tempfile.TemporaryDirectory() as temp, audit_scope():
                payloads = iter([
                    {'flow': {'state': event, 'available_actions': ['init', command]}},
                    {'flow': {'state': 'closed', 'available_actions': ['spin']}},
                    {'flow': {'state': 'closed', 'available_actions': ['spin']}},
                    {'flow': {'state': 'closed', 'available_actions': ['spin']}},
                ])
                calls = []
                def send(cmd, options_payload=None, extra_data_payload=None):
                    calls.append(cmd)
                    return SimpleNamespace(status_code=200), {'command': cmd}, next(payloads)
                proof = bgaming_check(send, {'bet': 1}, Path(temp), threading.Event())
                self.assertEqual(proof['status'], 'CONFIRMED')
                self.assertEqual(calls, ['spin', command, 'spin', 'spin'])
                self.assertFalse(proof['probes'][0]['base'])

    def test_unknown_choice_is_never_sent(self):
        calls = []
        def send(cmd, **kwargs):
            calls.append(cmd)
            return SimpleNamespace(status_code=200), {}, {'flow': {'state': 'select_bonus', 'available_actions': ['play_bonus_game']}}
        with tempfile.TemporaryDirectory() as temp, audit_scope():
            proof = bgaming_check(send, {'bet': 1}, Path(temp), threading.Event())
            self.assertEqual(proof['status'], 'REVIEW_REQUIRED')
            self.assertEqual(calls, ['spin'])

    def test_hyperhive_accepts_explicit_spin_but_not_pending_actions(self):
        from tester_spin.providers.bgaming.hyperhive import is_base_return
        self.assertTrue(is_base_return({'final': True, 'next_action': 'SPIN', 'freespins': None}))
        self.assertTrue(is_base_return({'final': True, 'next_action': None}))
        self.assertFalse(is_base_return({'final': False, 'next_action': 'SPIN'}))
        self.assertFalse(is_base_return({'final': True, 'next_action': 'SELECT'}))
        self.assertFalse(is_base_return({'final': True, 'next_action': 'SPIN', 'freespins': {'remaining': 2}}))

    def test_outcome_changes_remain_recorded_but_are_not_protocol_alerts(self):
        o = ResponseObserver('bgaming')
        o.observe({'flow': {'state': 'closed'}, 'outcome': {'wins': []}}, action='spin')
        change = o.observe({'flow': {'state': 'closed'}, 'outcome': {'wins': [[0, 4, 50]]}}, action='spin')
        self.assertEqual(change['classification'], 'NEW_RESPONSE')
        self.assertEqual(change['change_kind'], 'OUTCOME_VARIATION')
        self.assertFalse(change['review_required'])
        event = o.observe({'flow': {'state': 'freespins'}, 'outcome': {'wins': []}}, action='spin')
        self.assertEqual(event['change_kind'], 'PROTOCOL_CHANGE')
        self.assertTrue(event['review_required'])

    def test_unrecognized_added_field_is_not_silenced(self):
        o = ResponseObserver('bgaming')
        o.observe({'flow': {'state': 'closed'}}, action='spin')
        event = o.observe({'flow': {'state': 'closed'}, 'unknown_prompt': [1, 2]}, action='spin')
        self.assertTrue(event['review_required'])

    def test_unknown_prompt_inside_outcome_is_still_reviewable(self):
        o = ResponseObserver('bgaming')
        o.observe({'outcome': {'wins': []}}, action='spin')
        event = o.observe({'outcome': {'wins': {'unknown_prompt': [1, 2]}}}, action='spin')
        self.assertTrue(event['review_required'])