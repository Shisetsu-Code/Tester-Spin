import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import requests
from tester_spin.providers.pragmatic import PragmaticProvider

class ReelIntegrationTests(unittest.TestCase):
    def test_post_sends_certified_selection_and_persists_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=PragmaticProvider(Path(tmp))
            response=requests.Response();response.status_code=200;response._content=b'na=s&balance=100'
            response.request=requests.Request('POST','https://example.invalid').prepare()
            boot=SimpleNamespace(session=Mock(post=Mock(return_value=response)),endpoint='https://example.invalid',
                calibration_response={'rs':'mc','trail':'sr~2','sw':'5'},current_response=None,reel_contract={'certified':True},reel_override='1')
            selection={'fields':{'ind':'1'},'selected':'1','domain':['0','1'],'default':'0'}
            with patch('tester_spin.providers.pragmatic_reel_contract.reel_selection',return_value=selection):
                p._post_and_store(boot,{'action':'doSpin'},Path(tmp),step=0,label='entry',timeout_s=1)
            self.assertIn('ind=1',boot.session.post.call_args.kwargs['data'])
            self.assertEqual(boot.current_response['na'],'s')
            self.assertIsNone(boot.reel_override)
            saved=json.loads((Path(tmp)/'step-000-entry.reel-selection.json').read_text())
            self.assertEqual(saved['selected'],'1')
