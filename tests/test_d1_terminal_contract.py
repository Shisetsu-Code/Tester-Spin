import json
from pathlib import Path
from tester_spin.models import Game, GameTestResult, SpinAttempt
from tester_spin.providers.one_spin4win import OneSpin4WinProvider
from tester_spin.providers.one_spin4win_exhaustive import apply_d1_path_audit

class Socket:
    def __init__(self,state):
        self.incoming=[json.dumps({'type':1,'l':10,'b3':0}),json.dumps({'type':3,'st':state,'l':10,'b3':0})]
        self.sent=[]
    def send(self,value): self.sent.append(value)
    def recv(self): return self.incoming.pop(0)
    def close(self): pass

def execute(tmp_path,state):
    p=OneSpin4WinProvider(tmp_path)
    ws=Socket(state)
    p._discover_runtime_spec=lambda *a,**k: dict(game_name='TenLuckySpins',version='01',wallet='1',currency='EUR',ws_url='wss://example.invalid')
    p._open_websocket=lambda *a: ws
    game=Game(provider=p.key,slug='10-lucky-spins',name='10 Lucky Spins',url='https://example.invalid')
    result=p._execute_direct_ws_spin(game,timeout_s=1,attempt_dir=tmp_path)
    return p,ws,result

def test_unknown_state_stops_without_claiming_terminal(tmp_path):
    _,ws,result=execute(tmp_path,99)
    assert result[0] is True
    assert result[1] is False
    assert [json.loads(value[4:])["type"] for value in ws.sent]==["0","1","3"]
    assert '99' in result[-1]

def test_official_client_state_three_is_terminal_and_resolves_old_audit(tmp_path):
    p,ws,actual=execute(tmp_path,3)
    assert actual[1] is True
    result=GameTestResult(provider=p.key,slug='10-lucky-spins',game_name='10 Lucky Spins',game_url='https://example.invalid',requested_spins=1,successful_spins=1,failed_spins=0,status='OK',run_dir=str(tmp_path))
    result.attempts=[SpinAttempt(number=1,ok=True,mode_id='SPIN',terminal=True,artifact_dir=str(tmp_path))]
    apply_d1_path_audit(p,result,progress=lambda m:None)
    assert result.status=='OK'
    mode=next(m for m in result.discovered_modes if m['id']=='D1_UNKNOWN_RESULT_STATES')
    assert mode['covered_options']==['3']
    assert mode['contract_source'].endswith('tenluckyspins_000264.js')

import unittest
import tempfile
class D1ContractTests(unittest.TestCase):
    def test_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            test_unknown_state_stops_without_claiming_terminal(Path(temp))
    def test_three(self):
        with tempfile.TemporaryDirectory() as temp:
            test_official_client_state_three_is_terminal_and_resolves_old_audit(Path(temp))

    def test_mixed_states_keep_one_unresolved_contract_with_three_resolved(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            p,_,_=execute(root,3)
            artifact=json.loads((root/'ws-attempt.json').read_text())
            artifact['frames'].append({'direction':'received','payload':{'kind':'text','text':json.dumps({'type':3,'st':99})}})
            (root/'ws-attempt.json').write_text(json.dumps(artifact))
            result=GameTestResult(provider=p.key,slug='mixed',game_name='Mixed',game_url='https://example.invalid',requested_spins=1,successful_spins=0,failed_spins=0,status='PARCIAL',run_dir=str(root))
            result.attempts=[SpinAttempt(number=1,ok=True,mode_id='SPIN',terminal=False,artifact_dir=str(root))]
            apply_d1_path_audit(p,result,progress=lambda m:None)
            rows=[m for m in result.discovered_modes if m['id']=='D1_UNKNOWN_RESULT_STATES']
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['required_options'],['3','99'])
            self.assertEqual(rows[0]['covered_options'],['3'])
            self.assertEqual(rows[0]['kind'],'UNRESOLVED_STATE')
