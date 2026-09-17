import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from tester_spin.models import Game
from tester_spin.providers import PragmaticProvider
from tester_spin.return_to_base import audit_scope
from tester_spin.providers.pragmatic_protocol import analyze_response

class PublicAuditTests(unittest.TestCase):
    def test_frozen_server_error_is_not_idle(self):
        payload={'balance':'99998','frozen':'Internal server error. The game will be restarted.','msg_code':'7','ext_code':'SystemError'}
        self.assertTrue(PragmaticProvider._server_error(payload))
        self.assertEqual(analyze_response(payload)['state_kind'],'server_error')

    def test_public_executor_requires_two_normal_confirmations_before_close(self):
        with tempfile.TemporaryDirectory() as tmp,audit_scope():
            p=PragmaticProvider(Path(tmp))
            boot=SimpleNamespace(session=Mock(),symbol='test',mgckey='secret',cver=None,endpoint='https://example.invalid',spin_template={},init_response={},calibration_response={'na':'s','index':'1','counter':'1'})
            p._http_bootstrap=Mock(return_value=boot)
            p._write_http_bootstrap=Mock()
            p._post_and_store=Mock(return_value=(200,b'na=s',{'na':'s','index':'2','counter':'3'},{}))
            mode=SimpleNamespace(id='SPIN',kind='SPIN',provider_bl=0,provider_pur=None)
            catalog=SimpleNamespace(base_coin=1,base_scale=10,base_bet=10)
            game=Game(provider='pragmatic',slug='test',name='Test',url='https://example.invalid')
            attempt=p._test_mode_once(game,symbol='test',cver=None,mode=mode,catalog=catalog,attempt_number=1,repetition=1,run_root=Path(tmp),timeout_s=1)
            self.assertTrue(attempt.terminal,attempt.error)
            self.assertEqual(p._post_and_store.call_count,3)
            self.assertTrue((Path(attempt.artifact_dir)/'return-to-base.json').exists())
