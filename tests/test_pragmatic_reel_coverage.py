import json,tempfile,unittest
import threading
from types import SimpleNamespace
from unittest.mock import Mock,patch
from pathlib import Path
from tester_spin.models import GameTestResult,SpinAttempt
from tester_spin.providers.pragmatic_reel_coverage import collect_reel_coverage,expand_reel_choices

class ReelCoverageTests(unittest.TestCase):
    def test_missing_natural_selector_is_retried_without_false_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def attempt(number,selection):
                directory=root/'SPIN'/f'attempt-{number:04d}';directory.mkdir(parents=True)
                (directory/'return-to-base.json').write_text(json.dumps({'status':'CONFIRMED','consecutive_base':2}))
                if selection is not None:
                    (directory/'step-001-choice.reel-selection.json').write_text(json.dumps({'domain':['0','1'],'selected':selection}))
                    (directory/'step-001-choice.response.json').write_text(json.dumps({'na':'s'}))
                return SpinAttempt(number=number,ok=True,terminal=True,artifact_dir=str(directory))
            result=GameTestResult(provider='pragmatic',slug='test',game_name='Test',game_url='',requested_spins=1,successful_spins=1,failed_spins=0,status='OK',run_dir=str(root),attempts=[attempt(1,'0')])
            provider=SimpleNamespace(base_bet=1,_test_mode_once=Mock(side_effect=[attempt(2,None),attempt(3,'1')]),_write_json=Mock())
            with patch('tester_spin.providers.pragmatic_reel_coverage.discover_modes',return_value=SimpleNamespace(enabled=lambda:[SimpleNamespace(id='SPIN')])):
                expand_reel_choices(provider,None,result,spins=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
            self.assertEqual(provider._test_mode_once.call_count,2)
            self.assertEqual(result.status,'OK')
            self.assertEqual(result.discovered_modes[0]['covered_options'],['0','1'])

    def test_choices_require_successful_response_terminal_and_two_base_probes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            result=GameTestResult(provider='pragmatic',slug='test',game_name='Test',game_url='',requested_spins=1,successful_spins=1,failed_spins=0,status='OK',run_dir=str(root))
            result.attempts=[SpinAttempt(number=1,ok=True,terminal=True,artifact_dir=str(root))]
            (root/'step-001-choice.reel-selection.json').write_text(json.dumps({'domain':['0','1'],'selected':'1'}))
            (root/'step-001-choice.response.json').write_text(json.dumps({'na':'s'}))
            self.assertEqual(next(iter(collect_reel_coverage(result).values()))['covered'],set())
            (root/'return-to-base.json').write_text(json.dumps({'status':'CONFIRMED','consecutive_base':2}))
            self.assertEqual(next(iter(collect_reel_coverage(result).values()))['covered'],{'1'})
            (root/'step-001-choice.response.json').write_text(json.dumps({'frozen':'error'}))
            self.assertEqual(next(iter(collect_reel_coverage(result).values()))['covered'],set())
            (root/'step-002-choice.reel-selection.json').write_text(json.dumps({'domain':['0','1','2','3'],'selected':'2','branch_signature':'width2'}))
            groups=collect_reel_coverage(result)
            self.assertEqual(len(groups),2)
            self.assertEqual(sorted(len(g['required']) for g in groups.values()),[2,4])
