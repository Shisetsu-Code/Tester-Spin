import importlib
import importlib.util
import json
import tempfile
import os
import unittest
from pathlib import Path

from tester_spin.models import GameTestResult, SpinAttempt


class RunTreeTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('tester_spin.run_tree'), 'Missing origin-preserving tree')
        return importlib.import_module('tester_spin.run_tree')

    def fixture(self, root):
        modes=[]; attempts=[]
        for i, (mid,kind) in enumerate([('SPIN','SPIN'),('ANTE_BET_1','ANTE_BET'),('PURCHASE_0','PURCHASE')]):
            directory=root/mid; directory.mkdir()
            for n in (0,1):
                (directory/f'step-{n:03}.request.json').write_text(json.dumps({'mode':mid,'step':n}),encoding='utf-8')
                (directory/f'step-{n:03}.response.json').write_text(json.dumps({'state':'same-observed-state','choice':n}),encoding='utf-8')
            modes.append({'id':mid,'kind':kind})
            attempts.append(SpinAttempt(number=i+1,ok=True,terminal=True,mode_id=mid,mode_kind=kind,artifact_dir=str(directory)))
        return GameTestResult(provider='synthetic',slug='game',game_name='Game',game_url='https://example.invalid',requested_spins=1,successful_spins=3,failed_spins=0,status='OK',run_dir=str(root),discovered_modes=modes,attempts=attempts)

    def test_same_state_keeps_three_different_entry_origins(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            result=self.fixture(Path(temp))
            tree=mod.write_run_tree(result)
            paths=tree['trajectories']
            self.assertEqual([p['origin']['mode_id'] for p in paths],['SPIN','ANTE_BET_1','PURCHASE_0'])
            self.assertEqual(len({p['id'] for p in paths}),3)
            self.assertTrue(all(len(p['steps'])==2 for p in paths))
            self.assertTrue(all(p['steps'][0]['parent_id']==p['id'] for p in paths))
            self.assertTrue(all(p['steps'][1]['parent_id']==p['steps'][0]['id'] for p in paths))
            self.assertFalse(tree['exact_remote_outcome_reproducible'])

    def test_offline_replay_verifies_captures_and_rejects_tampering(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); tree=mod.write_run_tree(self.fixture(root))
            replay=mod.replay_capture(root/'run-tree.json',tree['trajectories'][1]['id'])
            self.assertEqual(replay['origin']['mode_id'],'ANTE_BET_1')
            self.assertEqual(len(replay['steps']),2)
            (root/'ANTE_BET_1'/'step-001.response.json').write_text('{}',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'hash|integrity'):
                mod.replay_capture(root/'run-tree.json',tree['trajectories'][1]['id'])

    def test_unordered_files_do_not_create_a_fictional_sequence(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); result=self.fixture(root)
            for f in (root/'SPIN').iterdir(): f.unlink()
            for name in ['alpha','omega']:
                (root/'SPIN'/f'{name}.request.json').write_text('{}',encoding='utf-8')
                (root/'SPIN'/f'{name}.response.json').write_text('{}',encoding='utf-8')
            tree=mod.write_run_tree(result)
            trajectory=tree['trajectories'][0]
            self.assertEqual(trajectory['sequence_status'],'UNRESOLVED')
            self.assertFalse(trajectory['offline_replay_ready'])

    def test_provider_declared_sequence_orders_named_steps(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); result=self.fixture(root)
            for f in (root/'SPIN').iterdir(): f.unlink()
            for name in ['zeta','alpha']:
                (root/'SPIN'/f'{name}.request.json').write_text('{}',encoding='utf-8')
                (root/'SPIN'/f'{name}.response.json').write_text('{}',encoding='utf-8')
            result.discovered_modes[0]['state_machine']=['zeta','alpha']
            tree=mod.write_run_tree(result)
            self.assertEqual([s['label'] for s in tree['trajectories'][0]['steps']],['zeta','alpha'])

    def test_latest_report_is_chosen_only_inside_selected_game(self):
        mod=self.module()
        self.assertTrue(hasattr(mod,'latest_run_report'))
        with tempfile.TemporaryDirectory() as temp:
            game=Path(temp)/'game'
            older=game/'tests'/'a'/'run-tree.html'; newer=game/'diagnostics'/'b'/'run-tree.html'
            for path in (older,newer):
                path.parent.mkdir(parents=True); path.write_text('report',encoding='utf-8')
            os.utime(older,(10,10)); os.utime(newer,(20,20))
            self.assertEqual(mod.latest_run_report(game),newer.resolve())

    def test_bootstrap_and_analysis_sidecars_do_not_replace_gameplay_responses(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); result=self.fixture(root)
            bootstrap=root/'SPIN'/'bootstrap'; bootstrap.mkdir()
            (bootstrap/'init.request.json').write_text('{}',encoding='utf-8')
            (bootstrap/'init.response.json').write_text('{}',encoding='utf-8')
            (root/'SPIN'/'step-000.response.analysis.json').write_text('{"analysis":"not-wire"}',encoding='utf-8')
            path=mod.write_run_tree(result)['trajectories'][0]
            self.assertEqual(path['sequence_status'],'ARTIFACT_STEP_INDEX')
            self.assertEqual(len(path['steps']),2)
            self.assertEqual(path['steps'][0]['observed_response']['state'],'same-observed-state')

    def test_ordered_frame_capture_keeps_directions_and_replays_offline(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); result=self.fixture(root)
            for f in (root/'SPIN').iterdir(): f.unlink()
            (root/'SPIN'/'ws-attempt.json').write_text(json.dumps({'frames':[
                {'direction':'sent','payload':{'text':'request','truncated':False}},
                {'direction':'received','payload':{'text':'response','truncated':False}}]}),encoding='utf-8')
            path=mod.write_run_tree(result)['trajectories'][0]
            self.assertEqual(path['sequence_status'],'RECORDED_FRAME_ARRAY')
            self.assertEqual([e['direction'] for e in path['events']],['sent','received'])
            replay=mod.replay_capture(root/'run-tree.json',path['id'])
            self.assertEqual(len(replay['events']),2)

    def test_entry_alias_is_not_an_extra_exchange(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); result=self.fixture(root)
            directory=root/'SPIN'
            for direction in ['request','response']:
                (directory/f'{direction}.json').write_bytes((directory/f'step-000.{direction}.json').read_bytes())
            path=mod.write_run_tree(result)['trajectories'][0]
            self.assertEqual(len(path['steps']),2)

    def test_missing_whole_step_disables_complete_replay(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); result=self.fixture(root)
            for direction in ['request','response']:
                (root/'SPIN'/f'step-001.{direction}.json').rename(root/'SPIN'/f'step-003.{direction}.json')
            path=mod.write_run_tree(result)['trajectories'][0]
            self.assertFalse(path['offline_replay_ready'])
            self.assertTrue(path['gaps'])


if __name__=='__main__': unittest.main()
