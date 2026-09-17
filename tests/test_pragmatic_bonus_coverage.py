import json,tempfile,unittest
from pathlib import Path
from tester_spin.models import GameTestResult,SpinAttempt
from tester_spin.providers.pragmatic_bonus_coverage import annotate_bonus_coverage

class BonusCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.result=GameTestResult(provider='pragmatic',slug='test',game_name='Test',game_url='https://example.invalid',requested_spins=1,successful_spins=1,failed_spins=0,status='OK',run_dir=str(self.root))
    def tearDown(self):self.temp.cleanup()
    def add(self,*,number=1,selected='0',domain=None,signature='bonus:level0',source_hash='hash-a',terminal=True,proof='CONFIRMED',consecutive=2,response=None,subdir=''):
        directory=self.root/f'attempt-{number}'
        directory.mkdir(exist_ok=True)
        existing=next((a for a in self.result.attempts if a.number==number),None)
        if not existing:self.result.attempts.append(SpinAttempt(number=number,ok=True,terminal=terminal,mode_id='SPIN',artifact_dir=str(directory)))
        (directory/'return-to-base.json').write_text(json.dumps({'status':proof,'consecutive_base':consecutive}))
        target=directory/subdir;target.mkdir(parents=True,exist_ok=True)
        count=len(list(target.glob('*.bonus-selection.json')))
        stem=f'step-{count:03d}-bonus'
        (target/(stem+'.bonus-selection.json')).write_text(json.dumps({'domain':domain or ['0','1','2','3'],'selected':selected,'branch_signature':signature,'contract_sha256':source_hash,'contract_source':'https://example.invalid/build.js'}))
        (target/(stem+'.response.json')).write_text(json.dumps({'na':'cb'} if response is None else response))
    def rows(self):return [m for m in self.result.discovered_modes if m.get('kind')=='CHOICE_BRANCH']
    def test_only_selected_option_is_covered_and_other_choices_stay_pending(self):
        self.add();annotate_bonus_coverage(self.result)
        self.assertEqual(self.rows()[0]['covered_options'],['0'])
        self.assertEqual(self.rows()[0]['required_options'],['0','1','2','3'])
        self.assertEqual(self.result.status,'PARCIAL')
    def test_recursive_base_probes_contribute_with_parent_terminal_proof(self):
        self.add(subdir='return-to-base/probe-002',domain=['0'])
        annotate_bonus_coverage(self.result)
        self.assertEqual(self.rows()[0]['sample_counts'],{'0':1})
        self.assertEqual(self.result.status,'OK')
    def test_nonterminal_or_missing_two_confirmations_never_cover(self):
        self.add(terminal=False,consecutive=1)
        annotate_bonus_coverage(self.result)
        self.assertEqual(self.rows()[0]['covered_options'],[])
    def test_server_error_never_covers_selected_option(self):
        self.add(response={'frozen':'Internal server error','ext_code':'SystemError'})
        annotate_bonus_coverage(self.result)
        self.assertEqual(self.rows()[0]['covered_options'],[])
    def test_signature_and_source_hash_are_separate_branches(self):
        self.add(signature='bonus:level0',selected='0')
        self.add(signature='bonus:level1',selected='1')
        self.add(signature='bonus:level0',source_hash='hash-b',selected='2')
        annotate_bonus_coverage(self.result)
        self.assertEqual(len(self.rows()),3)
        self.assertEqual(sorted(row['covered_options'] for row in self.rows()),[['0'],['1'],['2']])
    def test_samples_count_independent_attempts_not_multiple_probes(self):
        self.result.samples_per_path=2
        self.add(domain=['0']);self.add(domain=['0'],subdir='return-to-base/probe-001')
        annotate_bonus_coverage(self.result)
        self.assertEqual(self.rows()[0]['sample_counts'],{'0':1})
        self.assertEqual(self.rows()[0]['covered_options'],[])
        self.add(number=2,domain=['0']);annotate_bonus_coverage(self.result)
        self.assertEqual(len(self.rows()),1)
        self.assertEqual(self.rows()[0]['sample_counts'],{'0':2})
        self.assertEqual(self.rows()[0]['covered_options'],['0'])
    def test_empty_response_and_selected_outside_domain_do_not_cover(self):
        self.add(response={});self.add(number=2,selected='9')
        annotate_bonus_coverage(self.result)
        self.assertEqual(self.rows()[0]['covered_options'],[])
    def test_cancelled_state_is_preserved(self):
        self.add();self.result.status='CANCELADO';annotate_bonus_coverage(self.result)
        self.assertEqual(self.result.status,'CANCELADO')
