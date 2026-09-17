import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from tester_spin.providers.one_spin4win import OneSpin4WinProvider
from tester_spin.provider_return_checks import d1_check
from tester_spin.return_to_base import audit_scope

class D1ReturnContractTests(unittest.TestCase):
    def test_two_base_states_three_then_zero_confirm_same_session(self):
        replies=iter([{'type':3,'st':3},{'type':3,'st':0}])
        sent=[]
        provider=SimpleNamespace(_wire_message=lambda kind,data:kind+':'+data,
            _frame_preview=lambda wire:wire,_int_field=lambda value,default:int(value),
            _d1_feature_active=OneSpin4WinProvider._d1_feature_active,
            _d1_result_terminal=OneSpin4WinProvider._d1_result_terminal,
            D1_TERMINAL_STATES=OneSpin4WinProvider.D1_TERMINAL_STATES,
            _recv_protocol_json=lambda *args,**kwargs:next(replies))
        with tempfile.TemporaryDirectory() as tmp,audit_scope():
            proof=d1_check(provider,SimpleNamespace(send=sent.append),[],20,0,3,Path(tmp),1)
            self.assertEqual(proof['status'],'CONFIRMED')
            self.assertEqual(len(sent),2)
