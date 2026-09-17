import importlib
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path

from tester_spin.models import Game, GameTestResult, SpinAttempt
from tester_spin.providers.base import ProviderAdapter
from tester_spin.scheduler import run_game_tests


class RunDiagnosticsTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('tester_spin.run_diagnostics'),
                             'Missing persistent run diagnosis')
        return importlib.import_module('tester_spin.run_diagnostics')

    def result(self, root, **kwargs):
        defaults = dict(provider='synthetic', slug='game', game_name='Game',
                        game_url='https://example.invalid', requested_spins=1,
                        successful_spins=0, failed_spins=1, status='PARCIAL', run_dir=str(root))
        defaults.update(kwargs)
        return GameTestResult(**defaults)

    def test_paid_option_not_validated_when_coverage_is_missing(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attempt = root / 'attempt'
            attempt.mkdir()
            (attempt/'request.json').write_text('{"action":"buy","option":0}', encoding='utf-8')
            (attempt/'response.json').write_text('{"phase":"arbitrary-wire-state"}', encoding='utf-8')
            (root/'path-coverage.json').write_text(json.dumps({'complete':False,'branch_points':[
                {'mode_id':'PURCHASE_0','required':['0','1'],'covered':['0'],'missing':['1'],'complete':False}]}),encoding='utf-8')
            result=self.result(root, discovered_modes=[{'id':'PURCHASE_0','kind':'PURCHASE','price_x_base':100}],
                attempts=[SpinAttempt(number=1,ok=True,terminal=True,mode_id='PURCHASE_0',artifact_dir=str(attempt))])
            report=mod.write_run_diagnostics(result)
            self.assertEqual(report['modes'][0]['status'],'INCOMPLETE')
            self.assertEqual(report['modes'][0]['missing_options'],['1'])
            self.assertEqual(report['root_cause']['status'],'UNDETERMINED')
            self.assertTrue((root/'diagnostic.md').is_file())

    def test_request_comparison_distinguishes_missing_null_and_duplicate_values(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            a=root/'a.json'; b=root/'b.json'
            a.write_text('{"bet":1,"options":null,"token":"PRIVATE-A"}',encoding='utf-8')
            b.write_text('{"bet":2,"purchase":0,"token":"PRIVATE-B"}',encoding='utf-8')
            diff=mod.compare_captures(a,b)
            by_path={d['path']:d for d in diff['differences']}
            self.assertEqual(by_path['$.bet']['before'],1)
            self.assertEqual(by_path['$.bet']['after'],2)
            self.assertTrue(by_path['$.options']['before_present'])
            self.assertFalse(by_path['$.options']['after_present'])
            self.assertNotIn('PRIVATE',json.dumps(diff))
            a.write_text('action=spin&x=1&x=2&session=PRIVATE',encoding='utf-8')
            b.write_text('action=spin&x=2&x=1',encoding='utf-8')
            diff=mod.compare_captures(a,b)
            self.assertTrue(diff['differences'])
            self.assertNotIn('PRIVATE',json.dumps(diff))

    def test_missing_capture_stays_explicit_and_does_not_change_result(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            result=self.result(root, status='ERROR', error='HTTP 403 from https://example.invalid/?token=PRIVATE',
                attempts=[SpinAttempt(number=1,ok=False,error='HTTP 403',artifact_dir=str(root/'missing'))])
            report=mod.write_run_diagnostics(result)
            self.assertEqual(result.status,'ERROR')
            self.assertTrue(report['evidence_gaps'])
            self.assertFalse(report['modes'][0]['validated'])
            self.assertNotIn('PRIVATE',(root/'diagnostic.json').read_text(encoding='utf-8'))
            self.assertNotIn('PRIVATE',(root/'diagnostic.md').read_text(encoding='utf-8'))

    def test_evidence_hashes_and_last_step_without_inventing_wire_semantics(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); attempt=root/'attempt'; attempt.mkdir()
            request=attempt/'step-000.request.json'; response=attempt/'step-000.response.json'
            request.write_text('{"command":"unknown_7"}',encoding='utf-8')
            response.write_text('{"phaseNext":"X17"}',encoding='utf-8')
            before=response.read_bytes()
            result=self.result(root,discovered_modes=[{'id':'X17','kind':'UNRESOLVED_STATE','executable':False}],
                attempts=[SpinAttempt(number=1,ok=False,terminal=False,artifact_dir=str(attempt))])
            report=mod.write_run_diagnostics(result)
            self.assertEqual(response.read_bytes(),before)
            self.assertTrue(all(e['sha256'] for e in report['attempts'][0]['evidence']))
            self.assertTrue(report['unknown_actions'][0]['id'].startswith('UNCLASSIFIED_WIRE_VARIANT_'))
            self.assertEqual(report['attempts'][0]['last_response'],'attempt/step-000.response.json')

    def test_outside_attempt_directory_is_not_read(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            parent=Path(temp); root=parent/'run'; root.mkdir()
            outside=parent/'outside'; outside.mkdir()
            (outside/'response.json').write_text('{"confidential":"PRIVATE"}',encoding='utf-8')
            result=self.result(root,attempts=[SpinAttempt(number=1,ok=False,artifact_dir=str(outside))])
            report=mod.write_run_diagnostics(result)
            self.assertTrue(report['evidence_gaps'])
            self.assertFalse(report['attempts'][0]['evidence'])
            self.assertNotIn('PRIVATE',json.dumps(report))

    def test_scheduler_retains_pre_result_exception_and_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            class Broken(ProviderAdapter):
                key='broken'; display_name='Broken'; catalog_url='https://example.invalid'
                def farm_contract_dir(self,game): return Path(temp)/'game'
                def crawl_catalog(self,**kwargs): return []
                def test_game(self,game,**kwargs):
                    kwargs['progress']('launcher recibido; token=PRIVATE')
                    raise ValueError('invalid response shape')
            results=[]
            run_game_tests(Broken(),[Game(provider='broken',slug='game',name='Game',url='https://example.invalid')],
                concurrency=1,spins_per_game=1,delay_between_starts_s=0,timeout_s=1,
                stop_event=threading.Event(),progress=lambda _:None,on_result=results.append)
            self.assertEqual(results[0].status,'ERROR')
            self.assertTrue(results[0].run_dir,'Pre-result errors need an evidence directory')
            root=Path(results[0].run_dir)
            report=json.loads((root/'diagnostic.json').read_text(encoding='utf-8'))
            self.assertIn('invalid response shape',report['observed_error'])
            logs=list((Path(temp)/'game').rglob('events.jsonl'))
            self.assertTrue(logs)
            events=logs[0].read_text(encoding='utf-8')
            self.assertIn('launcher recibido',events)
            self.assertNotIn('PRIVATE',events)

    def test_exception_text_redacts_quoted_credentials_and_bearer_tokens(self):
        mod=self.module()
        observed='error {"token": "PRIVATE1"}; headers: Authorization: Bearer PRIVATE2; sid=PRIVATE3'
        cleaned=mod.sanitize(observed)
        self.assertNotIn('PRIVATE',cleaned)
        self.assertNotIn('PRIVATE',mod.sanitize('Cookie: sid=PRIVATE1; other=PRIVATE2\nHTTP 403'))

    def test_equal_python_numbers_of_different_types_are_a_real_difference(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            a=Path(temp)/'a.json'; b=Path(temp)/'b.json'
            a.write_text('{"flag":true}',encoding='utf-8')
            b.write_text('{"flag":1}',encoding='utf-8')
            self.assertEqual(len(mod.compare_captures(a,b)['differences']),1)

    def test_comparison_preserves_dotted_keys_and_array_types(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            a=Path(temp)/'a.json'; b=Path(temp)/'b.json'
            a.write_text('{"a.b":1,"list":[true]}',encoding='utf-8')
            b.write_text('{"a":{"b":1},"list":[1]}',encoding='utf-8')
            differences=mod.compare_captures(a,b)['differences']
            self.assertEqual(len(differences),3)

    def test_missing_coverage_does_not_certify_request_only_attempt(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); attempt=root/'attempt'; attempt.mkdir()
            (attempt/'request.json').write_text('{}',encoding='utf-8')
            result=self.result(root,status='OK',attempts=[SpinAttempt(number=1,ok=True,terminal=True,artifact_dir=str(attempt))])
            report=mod.write_run_diagnostics(result)
            self.assertFalse(report['modes'][0]['validated'])


if __name__=='__main__': unittest.main()
