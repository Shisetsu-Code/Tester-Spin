import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from tester_spin.providers.pragmatic_endpoint import PragmaticProvider
from tester_spin.providers.pragmatic_live import PragmaticProvider as Live

class CalibrationTests(unittest.TestCase):
    def test_respin_total_marks_completed_cycle_even_with_counters(self):
        self.assertFalse(PragmaticProvider._feature_active({'na':'s','rs':'mc','rs_p':'1','rs_c':'1','rs_t':'1'}))
        self.assertTrue(PragmaticProvider._feature_active({'na':'s','rs':'mc','rs_p':'0','rs_c':'1','rs_m':'1'}))
        self.assertTrue(PragmaticProvider._feature_active({'na':'s','rs_t':'1','fs':'1','fsmax':'10'}))

    def test_calibration_finishes_feature_in_same_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=PragmaticProvider(Path(tmp))
            boot=SimpleNamespace(session=Mock(),symbol='test',mgckey='redacted',cver=None,endpoint='https://example.invalid',launch_url='https://example.invalid',spin_template={'action':'doSpin','index':'2','counter':'4'},init_response={'index':'1'},init_request_raw='',init_response_raw=b'',calibration_request_raw='',calibration_response_raw=b'',calibration_response={'na':'s','rs':'mc','rs_p':'0','rs_c':'1','index':'2','counter':'4'})
            p._post_and_store=Mock(return_value=(200,b'na=s&rs_t=1',{'na':'s','rs_t':'1','index':'3','counter':'5'},{}))
            with patch('tester_spin.providers.pragmatic.PragmaticProvider._http_bootstrap',return_value=boot) as create:
                result=Live._http_bootstrap(p,'https://example.invalid','test',None,1,5)
            self.assertIs(result,boot)
            self.assertEqual(create.call_count,1)
            boot.session.close.assert_not_called()
            self.assertEqual(p._post_and_store.call_args.args[1]['index'],'3')
            self.assertEqual(result.calibration_response['rs_t'],'1')

    def test_bonus_calibration_uses_bonus_collect(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=PragmaticProvider(Path(tmp));p._write_http_bootstrap=Mock()
            boot=SimpleNamespace(session=Mock(),spin_template={'action':'doSpin'},calibration_response={'na':'b'})
            p._post_and_store=Mock(side_effect=[(200,b'',{'na':'c'},{}),(200,b'',{'na':'s'}, {})])
            with patch('tester_spin.providers.pragmatic.PragmaticProvider._http_bootstrap',return_value=boot):
                Live._http_bootstrap(p,'https://example.invalid','test',None,1,5)
            self.assertEqual([c.args[1]['action'] for c in p._post_and_store.call_args_list],['doBonus','doCollectBonus'])

    def test_missing_next_action_is_not_assumed_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=PragmaticProvider(Path(tmp));p._write_http_bootstrap=Mock();p._post_and_store=Mock()
            boot=SimpleNamespace(session=Mock(),spin_template={'action':'doSpin'},calibration_response={})
            with patch('tester_spin.providers.pragmatic.PragmaticProvider._http_bootstrap',return_value=boot):
                with self.assertRaisesRegex(RuntimeError,'Calibración pendiente'):
                    Live._http_bootstrap(p,'https://example.invalid','test',None,1,5)
            p._post_and_store.assert_not_called()
