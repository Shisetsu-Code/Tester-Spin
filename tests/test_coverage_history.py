import json,tempfile,unittest
from pathlib import Path
from tester_spin.models import GameTestResult
from tester_spin.coverage_history import retain_pending_branches
from tester_spin.providers.path_coverage import enforce_complete_path_coverage

def result(modes):
    return GameTestResult(provider='test',slug='game',game_name='Game',game_url='https://example.invalid',requested_spins=1,successful_spins=1,failed_spins=0,status='OK',discovered_modes=modes)

class CoverageHistoryTests(unittest.TestCase):
    def test_current_mode_cannot_hide_historical_required_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            retain_pending_branches(root,result([{'id':'BUY','kind':'PURCHASE','coverage_required':True,'required_options':['A','B'],'covered_options':['A']}]))
            fresh=result([{'id':'BUY','kind':'PURCHASE','observed':True,'executable':True}])
            retain_pending_branches(root,fresh)
            enforce_complete_path_coverage(fresh)
            self.assertEqual(fresh.status,'PARCIAL')
            self.assertIn('B',fresh.error)

    def test_sample_deficit_survives_until_required_count_is_proven(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            mode={'id':'CHOICE','coverage_required':True,'required_options':['0'],'covered_options':['0'],'required_samples':2,'sample_counts':{'0':1}}
            retain_pending_branches(root,result([mode]))
            fresh=result([]);retain_pending_branches(root,fresh)
            enforce_complete_path_coverage(fresh)
            self.assertEqual(fresh.status,'PARCIAL')
            mode['sample_counts']={'0':2}
            retain_pending_branches(root,result([mode]))
            later=result([]);retain_pending_branches(root,later)
            self.assertEqual(later.discovered_modes,[])

    def test_missing_natural_branch_remains_pending_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            old=result([{'id':'DOUBLE','kind':'CHOICE_BRANCH','coverage_required':True,'required_options':['DECLINE','GAMBLE'],'covered_options':['DECLINE']}])
            retain_pending_branches(root,old)
            fresh=result([]);retain_pending_branches(root,fresh)
            enforce_complete_path_coverage(fresh)
            self.assertEqual(fresh.status,'PARCIAL')
            self.assertIn('GAMBLE',fresh.error)

    def test_current_proof_retires_old_unknown_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            retain_pending_branches(root,result([{'id':'UNKNOWN','coverage_required':True,'required_options':['3'],'covered_options':[]}]))
            fresh=result([{'id':'UNKNOWN','coverage_required':True,'required_options':['3'],'covered_options':['3']}])
            retain_pending_branches(root,fresh)
            later=result([]);retain_pending_branches(root,later)
            self.assertEqual(later.discovered_modes,[])

    def test_seeds_old_results_and_does_not_import_other_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=root/'tests'/'old';run.mkdir(parents=True)
            old=result([{'id':'BUY','coverage_required':True,'required_options':['0'],'covered_options':[]}])
            (run/'result.json').write_text(json.dumps(old.to_dict()),encoding='utf-8')
            fresh=result([]);retain_pending_branches(root,fresh)
            self.assertEqual(fresh.discovered_modes[0]['required_options'],['0'])
