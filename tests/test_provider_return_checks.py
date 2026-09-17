import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
import requests

from tester_spin.provider_return_checks import rubyplay_check, bgaming_check, d1_check
from tester_spin.return_to_base import audit_scope


class RubySession:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.sent = []
    def post(self, url, *, json, timeout):
        self.sent.append(json.copy())
        action = next(self.actions)
        response = requests.Response()
        response.status_code = 422 if action == 'HTTP_ERROR' else 200
        body = {'status': 'ok', 'topic': 'gameserver/'+json['action'], 'data': {'an': json['an']+1, 'next_action': action}}
        response._content = __import__('json').dumps(body).encode()
        return response


class ProviderReturnChecksTests(unittest.TestCase):
    def runtime(self, actions):
        return SimpleNamespace(session=RubySession(actions), default_bet=1, bets=[1], action_number=8,
            client_profile=SimpleNamespace(protocol_version=1, math_version=1), session_key='sensitive-key',
            fun_mode_data={}, active_feature_type='', gameserver_url='https://example.invalid', next_action='spin')

    def test_ruby_same_runtime_advances_action_numbers_and_resets_after_respin(self):
        runtime = self.runtime(['respin', 'spin', 'spin', 'spin'])
        with tempfile.TemporaryDirectory() as temp, audit_scope():
            proof = rubyplay_check(runtime, Path(temp), 1, threading.Event())
            self.assertEqual(proof['status'], 'CONFIRMED')
            self.assertEqual([r['an'] for r in runtime.session.sent], [8, 9, 10, 11])
            self.assertEqual([r['action'] for r in runtime.session.sent], ['spin', 'respin', 'spin', 'spin'])
            self.assertNotIn('sensitive-key', (Path(temp)/'return-to-base.json').read_text())

    def test_ruby_unknown_choice_stops_and_preserves_payload(self):
        runtime = self.runtime(['select'])
        with tempfile.TemporaryDirectory() as temp, audit_scope():
            proof = rubyplay_check(runtime, Path(temp), 1, threading.Event())
            self.assertEqual(proof['status'], 'REVIEW_REQUIRED')
            self.assertEqual(len(runtime.session.sent), 1)
            self.assertEqual(proof['probes'][0]['captures'][0]['response']['data']['next_action'], 'select')

    def test_ruby_http_error_is_saved_before_runtime_raises(self):
        runtime = self.runtime(['HTTP_ERROR'])
        with tempfile.TemporaryDirectory() as temp, audit_scope():
            proof = rubyplay_check(runtime, Path(temp), 1, threading.Event())
            self.assertEqual(proof['status'], 'ERROR')
            trace = next(Path(temp).rglob('server-responses.jsonl'))
            self.assertEqual(json.loads(trace.read_text())['http_status'], 422)

    def test_bgaming_does_not_send_purchase_options_in_base_probe(self):
        sent = []
        def send(command, options_payload=None, extra_data_payload=None):
            sent.append((command, options_payload))
            return SimpleNamespace(status_code=200), {'command': command, 'options': options_payload}, {'flow': {'state': 'closed', 'available_actions': ['spin']}}
        with tempfile.TemporaryDirectory() as temp, audit_scope():
            proof = bgaming_check(send, {'bet': 1}, Path(temp), threading.Event())
            self.assertEqual(proof['status'], 'CONFIRMED')
            self.assertEqual(sent, [('spin', {'bet': 1}), ('spin', {'bet': 1})])

    def test_d1_known_natural_event_finishes_before_two_base_confirmations(self):
        responses = iter([{'type': 3, 'st': 5}, {'type': 3, 'st': 0}, {'type': 3, 'st': 0}, {'type': 3, 'st': 0}])
        sent = []
        provider = SimpleNamespace(_wire_message=lambda kind, data: kind+':'+data,
            _frame_preview=lambda wire: wire, _int_field=lambda value, default: int(value),
            _d1_feature_active=lambda payload: payload.get('st') in {5, 6, 11, 12},
            _recv_protocol_json=lambda *args, **kwargs: next(responses))
        ws = SimpleNamespace(send=sent.append)
        with tempfile.TemporaryDirectory() as temp, audit_scope():
            proof = d1_check(provider, ws, [], 20, 0, 0, Path(temp), 1)
            self.assertEqual(proof['status'], 'CONFIRMED')
            self.assertEqual(len(sent), 4)
            self.assertEqual(proof['probes'][0]['base'], False)

    def test_d1_repeated_unknown_state_is_only_an_observation(self):
        provider = SimpleNamespace(_wire_message=lambda kind, data: kind+':'+data,
            _frame_preview=lambda wire: wire, _int_field=lambda value, default: int(value),
            _d1_feature_active=lambda payload: False,
            _recv_protocol_json=lambda *args, **kwargs: {'type': 3, 'st': 99})
        with tempfile.TemporaryDirectory() as temp, audit_scope():
            proof = d1_check(provider, SimpleNamespace(send=lambda wire: None), [], 20, 0, 99, Path(temp), 1)
            self.assertEqual(proof['status'], 'OBSERVED_RETURN')
            self.assertEqual(proof['consecutive_base'], 0)
            self.assertEqual(proof['consecutive_observed_state'], 2)

    def test_redtiger_pending_probe_is_partial_not_user_cancellation(self):
        from decimal import Decimal
        from unittest.mock import patch
        from tester_spin.models import Game
        from tester_spin.providers.redtiger import execution
        from tester_spin.providers.redtiger.adapter import RedTigerProvider
        from tester_spin.providers.redtiger.runtime import RedTigerRuntime
        from tests.test_redtiger_choice_continuation import FakeSession, RedTigerChoiceContinuationTests as Fixtures
        session = FakeSession([Fixtures._terminal('Normal'), Fixtures._pending_free_spins()])
        runtime = RedTigerRuntime(session=session, settings_url='https://example.invalid/settings',
            spin_url='https://example.invalid/spin', launcher_url='https://example.invalid/launcher',
            game_id='test', session_id='s', token='t', user_data={}, custom={},
            settings_request={'playMode': 'demo'}, settings_response={}, stakes=(Decimal('2'),),
            default_stake=Decimal('2'), currency_decimals=2, feature_buys=())
        with tempfile.TemporaryDirectory() as temp, audit_scope():
            provider = RedTigerProvider(Path(temp))
            game = Game(provider='redtiger', slug='test', name='Test', url='https://example.invalid', symbol='37498')
            with patch.object(execution, 'bootstrap_game', return_value=runtime):
                result = provider.test_game(game, spins=2, timeout_s=1, stop_event=threading.Event(), progress=lambda _: None)
            self.assertEqual(result.status, 'PARCIAL', result.error)
            self.assertEqual(len(session.calls), 2)

    def test_redtiger_normal_label_with_active_state_is_not_base(self):
        from decimal import Decimal
        from unittest.mock import patch
        from tester_spin.provider_return_checks import redtiger_check
        from tester_spin.providers.redtiger import execution
        from tests.test_redtiger_choice_continuation import RedTigerChoiceContinuationTests as Fixtures
        payload = Fixtures._terminal('Normal')
        payload['result']['game']['hasState'] = True
        runtime = SimpleNamespace(default_stake=Decimal('2'))
        with tempfile.TemporaryDirectory() as temp, audit_scope():
            with patch.object(execution, '_post_spin', return_value=(200, {}, payload, [])):
                proof = redtiger_check(runtime, Path(temp), 1, threading.Event())
            self.assertEqual(proof['status'], 'REVIEW_REQUIRED')
            self.assertEqual(len(proof['probes']), 1)
    def test_bgaming_error_envelope_cannot_confirm_stale_closed_flow(self):
        def send(command, options_payload=None, extra_data_payload=None):
            return SimpleNamespace(status_code=200), {}, {'errors': ['selection required'], 'flow': {'state': 'closed', 'available_actions': ['spin']}}
        with tempfile.TemporaryDirectory() as temp, audit_scope():
            proof = bgaming_check(send, {'bet': 1}, Path(temp), threading.Event())
            self.assertEqual(proof['status'], 'ERROR')
            self.assertEqual(len(proof['probes']), 1)