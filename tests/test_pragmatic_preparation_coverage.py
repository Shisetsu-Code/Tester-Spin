import json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from tester_spin.models import GameTestResult,SpinAttempt
from tester_spin.providers.pragmatic_bonus_coverage import annotate_bonus_coverage
from tester_spin.providers.pragmatic_reel_coverage import collect_reel_coverage,expand_reel_choices

class PreparationCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.prep=self.root/'bootstrap-runs'/'linked';self.prep.mkdir(parents=True)
        self.attempt=self.root/'run'/'BUY'/'attempt-0001';(self.attempt/'bootstrap').mkdir(parents=True)
        (self.attempt/'bootstrap/protocol.json').write_text(json.dumps({'symbol':'vsfixture','preparation_dir':str(self.prep)}))
        (self.prep/'bootstrap').mkdir();(self.prep/'bootstrap/protocol.json').write_text(json.dumps({'symbol':'vsfixture'}))
        (self.attempt/'return-to-base.json').write_text(json.dumps({'status':'CONFIRMED','consecutive_base':2}))
        self.result=GameTestResult(provider='pragmatic',slug='test',game_name='Test',game_url='',symbol='vsfixture',requested_spins=1,successful_spins=1,failed_spins=0,status='OK',run_dir=str(self.root/'run'),attempts=[SpinAttempt(number=1,ok=True,terminal=True,mode_id='BUY',artifact_dir=str(self.attempt))])
    def tearDown(self):self.temp.cleanup()
    def selection(self,directory,kind,selected='0',signature='shared',source_hash='hash-a'):
        directory.mkdir(parents=True,exist_ok=True)
        (directory/f'step-001-choice.{kind}-selection.json').write_text(json.dumps({'domain':['0','1'],'selected':selected,'branch_signature':signature,'contract_sha256':source_hash,'contract_source':'official'}))
        (directory/'step-001-choice.response.json').write_text(json.dumps({'na':'s'}))
    def test_linked_reel_preparation_is_bootstrap_obligation_not_buy_coverage(self):
        self.selection(self.prep,'reel')
        groups=list(collect_reel_coverage(self.result).values())
        self.assertEqual(len(groups),1)
        self.assertEqual(groups[0]['mode_id'],'SPIN')
        self.assertEqual(groups[0]['source_phases'],{'bootstrap'})
        self.assertEqual(groups[0]['required'],{'0','1'})
        self.assertEqual(groups[0]['covered'],set())
    def test_linked_bonus_preparation_is_required_even_when_attempt_confirmed(self):
        self.selection(self.prep,'bonus');annotate_bonus_coverage(self.result)
        row=self.result.discovered_modes[0]
        self.assertEqual(row['origin_mode_id'],'SPIN')
        self.assertEqual(row['source_phases'],['bootstrap'])
        self.assertEqual(row['covered_options'],[])
        self.assertEqual(self.result.status,'PARCIAL')
    def test_unlinked_sibling_preparation_is_never_scanned(self):
        sibling=self.prep.parent/'unrelated';self.selection(sibling,'reel');self.selection(sibling,'bonus')
        self.assertEqual(collect_reel_coverage(self.result),{})
        annotate_bonus_coverage(self.result);self.assertEqual(self.result.discovered_modes,[])
    def test_link_to_other_symbol_is_rejected(self):
        self.selection(self.prep,'reel');self.selection(self.prep,'bonus')
        (self.prep/'bootstrap/protocol.json').write_text(json.dumps({'symbol':'other'}))
        self.assertEqual(collect_reel_coverage(self.result),{})
        annotate_bonus_coverage(self.result);self.assertEqual(self.result.discovered_modes,[])
    def test_later_spin_same_contract_covers_bootstrap_obligation(self):
        self.result.attempts[0].mode_id='SPIN'
        for kind in ['reel','bonus']:
            self.selection(self.prep,kind);self.selection(self.attempt,kind)
        groups=list(collect_reel_coverage(self.result).values())
        self.assertEqual(len(groups),1)
        self.assertEqual(groups[0]['covered'],{'0'});self.assertEqual(groups[0]['source_phases'],{'bootstrap','attempt'})
        annotate_bonus_coverage(self.result)
        self.assertEqual(len(self.result.discovered_modes),1)
        self.assertEqual(self.result.discovered_modes[0]['covered_options'],['0'])
    def test_expander_does_not_use_buy_mode_for_base_calibration(self):
        self.selection(self.prep,'reel')
        provider=SimpleNamespace(base_bet=1,_test_mode_once=Mock(),_write_json=Mock())
        with patch('tester_spin.providers.pragmatic_reel_coverage.discover_modes',return_value=SimpleNamespace(enabled=lambda:[SimpleNamespace(id='BUY')])):
            expand_reel_choices(provider,None,self.result,spins=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
        provider._test_mode_once.assert_not_called()
        self.assertEqual(self.result.status,'PARCIAL')
        self.assertEqual(self.result.discovered_modes[0]['source_phases'],['bootstrap'])

