import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from tester_spin.providers import PragmaticProvider
from tester_spin.provider_return_checks import pragmatic_check
from tester_spin.return_to_base import audit_scope

class ManualBaseTests(unittest.TestCase):
    def test_required_manual_reel_phase_can_complete_two_normal_rounds(self):
        with tempfile.TemporaryDirectory() as tmp,audit_scope():
            p=PragmaticProvider(Path(tmp))
            responses=[{'na':'s','rs':'mc','trail':'sr~31','sw':'5'},{'na':'s'}, {'na':'s','rs':'mc','trail':'sr~2','sw':'5'},{'na':'s'}]
            p._post_and_store=Mock(side_effect=[(200,b'',r,{}) for r in responses])
            with patch('tester_spin.providers.pragmatic_reel_contract.reel_selection',side_effect=lambda r,c: {'fields':{'ind':'0'}} if r.get('rs')=='mc' else None):
                proof=pragmatic_check(p,SimpleNamespace(reel_contract={'certified':True}),{'na':'s'},{'action':'doSpin'},Path(tmp),1)
            self.assertEqual(proof['status'],'CONFIRMED')
            self.assertEqual(proof['consecutive_base'],2)
            self.assertEqual(p._post_and_store.call_count,4)
