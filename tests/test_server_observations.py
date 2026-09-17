import unittest
import tempfile
import json
from pathlib import Path
from tester_spin.server_observations import ResponseObserver


class ResponseObserverTests(unittest.TestCase):
    def test_money_and_array_length_do_not_create_events(self):
        o = ResponseObserver('d1')
        self.assertEqual(o.observe({'st': 3, 'win': 0, 'symbols': [1]}, action='spin')['classification'], 'BASELINE')
        self.assertEqual(o.observe({'st': 3, 'win': 900, 'symbols': [2, 5]}, action='spin')['classification'], 'SEEN')

    def test_same_shape_new_state_is_reviewable_and_deduplicated(self):
        o = ResponseObserver('d1')
        o.observe({'st': 3}, action='spin')
        event = o.observe({'st': 5}, action='spin')
        self.assertEqual(event['classification'], 'NEW_RESPONSE')
        self.assertIn('/st', event['changed_paths'])
        self.assertEqual(o.observe({'st': 5}, action='spin')['classification'], 'SEEN')

    def test_nested_new_option_and_type_change_are_detected(self):
        o = ResponseObserver('rubyplay')
        o.observe({'data': {'next_action': 'spin', 'win': 0}}, action='spin')
        e = o.observe({'data': {'next_action': 'select', 'win': '0', 'choices': [0, 1]}}, action='spin')
        self.assertEqual(e['classification'], 'NEW_RESPONSE')
        self.assertIn('/data/choices', e['changed_paths'])
        self.assertIn('/data/win', e['changed_paths'])

    def test_action_baselines_are_independent_and_raw_text_is_unparsed(self):
        o = ResponseObserver('rubyplay')
        o.observe({'next_action': 'spin'}, action='spin')
        self.assertEqual(o.observe({'next_action': 'pick'}, action='buy')['classification'], 'BASELINE')
        self.assertEqual(o.observe('<html>Error</html>', action='spin')['classification'], 'UNPARSED')

    def test_live_records_survive_before_finalization_and_games_are_isolated(self):
        from tester_spin.return_to_base import audit_scope
        from tester_spin.server_observations import set_capture_directory, observe_live
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with audit_scope():
                set_capture_directory(root/'a')
                observe_live({'st': 3, 'key': 'secret'}, action='spin')
                observe_live({'st': 5}, action='spin')
                rows = [json.loads(s) for s in (root/'a/server-responses.jsonl').read_text().splitlines()]
                self.assertEqual(rows[-1]['classification'], 'NEW_RESPONSE')
                self.assertNotIn('secret', (root/'a/server-responses.jsonl').read_text())
            with audit_scope():
                set_capture_directory(root/'b')
                observe_live({'st': 5}, action='spin')
                row = json.loads((root/'b/server-responses.jsonl').read_text())
                self.assertEqual(row['classification'], 'BASELINE')

    def test_live_trace_does_not_erase_an_offline_trajectory(self):
        from tester_spin.server_observations import write_observations
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'live').mkdir()
            entry = {'classification': 'BASELINE', 'changed_paths': [], 'review_required': False, 'action': 'spin'}
            (root/'live/server-responses.jsonl').write_text(json.dumps(entry)+'\n')
            paths = [dict(id='one', origin={'mode_id': 'SPIN'}, capture_directory='live', steps=[], events=[]),
                     dict(id='two', origin={'mode_id': 'BUY'}, capture_directory='offline', steps=[
                         {'id': 'two:1', 'request': [], 'response': [], 'observed_response': {'state': 'choice'}}], events=[])]
            report = write_observations(root, {'provider': 'test', 'trajectories': paths})
            self.assertEqual({o['trajectory_id'] for o in report['observations']}, {'one', 'two'})

    def test_active_state_flag_value_is_not_ignored(self):
        o = ResponseObserver('redtiger')
        o.observe({'spinMode': 'Normal', 'hasState': False}, action='spin')
        change = o.observe({'spinMode': 'Normal', 'hasState': True}, action='spin')
        self.assertEqual(change['classification'], 'NEW_RESPONSE')
        self.assertIn('/hasState', change['changed_paths'])