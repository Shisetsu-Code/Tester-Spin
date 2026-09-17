import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import requests
from tester_spin.providers.pragmatic import PragmaticProvider
from tester_spin.providers.pragmatic_bonus_contract import certify_bonus_contract

class BonusWireTests(unittest.TestCase):
    def test_initialized_bonus_sends_available_index_and_saves_evidence(self):
        fixture=json.loads(Path(__file__).with_name('fixtures').joinpath('pragmatic_bonus_pick_client.json').read_text())
        contract=certify_bonus_contract(fixture['source_excerpt'],fixture['source_url'])
        with tempfile.TemporaryDirectory() as tmp:
            provider=PragmaticProvider(Path(tmp))
            response=requests.Response();response.status_code=200;response._content=b'na=cb&end=1'
            response.request=requests.Request('POST','https://example.invalid').prepare()
            boot=SimpleNamespace(session=Mock(post=Mock(return_value=response)),endpoint='https://example.invalid',
                calibration_response={},current_response={'na':'b','end':'0','rw':'0','bgt':'21','level':'0','status':'1,0,0,0'},bonus_contract=contract)
            fields={'action':'doBonus'}
            provider._post_and_store(boot,fields,Path(tmp),step=1,label='bonus',timeout_s=1)
            self.assertEqual(fields['ind'],'1')
            self.assertIn('ind=1',boot.session.post.call_args.kwargs['data'])
            saved=json.loads((Path(tmp)/'step-001-bonus.bonus-selection.json').read_text())
            self.assertEqual(saved['domain'],['1','2','3'])
            self.assertEqual(saved['selected'],'1')
            boot.current_response={'na':'b','end':'0','rw':'0','bgt':'21','level':'0','status':'1,0,0,0'}
            second={'action':'doBonus'}
            provider._post_and_store(boot,second,Path(tmp),step=2,label='bonus',timeout_s=1)
            self.assertEqual(second['ind'],'2')


    def test_unknown_bonus_never_sends_a_guessed_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider=PragmaticProvider(Path(tmp));provider._resolve_bonus_contract=Mock(return_value=None)
            boot=SimpleNamespace(session=Mock(),calibration_response={},current_response={'na':'b'})
            with self.assertRaisesRegex(RuntimeError,'Bonus pendiente'):
                provider._post_and_store(boot,{'action':'doBonus'},Path(tmp),step=0,label='bonus',timeout_s=1)
            boot.session.post.assert_not_called()
