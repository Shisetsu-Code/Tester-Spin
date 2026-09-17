import tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from tester_spin.providers import PragmaticProvider
from tester_spin.provider_return_checks import pragmatic_check
from tester_spin.return_to_base import audit_scope

class BonusReturnTests(unittest.TestCase):
    def test_natural_bonus_is_completed_before_two_paid_rounds(self):
        with tempfile.TemporaryDirectory() as tmp, audit_scope():
            provider=PragmaticProvider(Path(tmp))
            responses=[{'na':'b','status':'0,0,0,0','rw':'0'}, {'na':'cb'}, {'na':'s'}, {'na':'s'}, {'na':'s'}]
            provider._post_and_store=Mock(side_effect=[(200,b'',r,{}) for r in responses])
            proof=pragmatic_check(provider,SimpleNamespace(),{'na':'s'}, {'action':'doSpin'},Path(tmp),1)
            self.assertEqual(proof['status'],'CONFIRMED')
            self.assertEqual(proof['consecutive_base'],2)
            actions=[call.args[1]['action'] for call in provider._post_and_store.call_args_list]
            self.assertEqual(actions,['doSpin','doBonus','doCollectBonus','doSpin','doSpin'])
