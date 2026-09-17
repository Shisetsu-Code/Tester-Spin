import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from tester_spin.models import Game, GameTestResult
from tester_spin.storage import Storage
from tester_spin.project_actions import export_reports, clear_history, publish


class ProjectActionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.data=self.root/'data'
        self.storage=Storage(self.data/'tester-spin.sqlite3')

    def result(self, provider='demo', slug='a', run='new'):
        self.storage.upsert_games([Game(provider,slug,slug,'https://example.invalid')])
        path=self.data/'providers'/provider/slug/'tests'/run;path.mkdir(parents=True,exist_ok=True)
        r=GameTestResult(provider,slug,slug,'https://example.invalid',1,1,0,'OK',run_dir=str(path))
        self.storage.record_result(r)
        (path/'diagnostic.json').write_text(json.dumps({'token':'private','value':42}))
        return path

    def test_export_latest_only_and_redacts_and_replaces_stale(self):
        self.result(run='old');self.result(run='new')
        old=self.root/'test-evidence/stale.json';old.parent.mkdir();old.write_text('{}')
        logs=[];export_reports(self.root,self.storage,logs.append)
        files=list((self.root/'test-evidence').rglob('diagnostic.json'))
        self.assertEqual(len(files),1)
        self.assertNotIn('private',files[0].read_text())
        self.assertFalse(old.exists());self.assertTrue(logs)

    def test_clear_provider_preserves_catalog_other_provider_and_manual_captures(self):
        run=self.result();other=self.result('other')
        game=run.parent.parent
        (game/'coverage-history.json').write_text('{}')
        (game/'game.json').write_text(json.dumps({'name':'A','last_test':{'status':'OK'}}))
        manual=game/'analysis/browser.har';manual.parent.mkdir();manual.write_text('manual')
        backup=clear_history(self.root,self.storage,'demo',lambda _:None)
        self.assertTrue(backup.exists());self.assertFalse(run.exists());self.assertTrue(other.exists())
        self.assertFalse((game/'coverage-history.json').exists());self.assertTrue(manual.exists())
        self.assertNotIn('last_test',json.loads((game/'game.json').read_text()))
        self.assertEqual(self.storage.list_games('demo')[0].last_status,'PENDIENTE')
        with self.storage._connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM test_results WHERE provider=?',('demo',)).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM test_results WHERE provider=?',('other',)).fetchone()[0],1)

    def test_clear_rejects_path_traversal(self):
        with self.assertRaises(ValueError):clear_history(self.root,self.storage,'../other',lambda _:None)

    def git(self,*args):
        return subprocess.run(['git','-C',str(self.root),*args],check=True,capture_output=True,text=True).stdout

    def repo(self):
        self.git('init');self.git('config','user.name','Test');self.git('config','user.email','test@example.invalid')
        (self.root/'run.py').write_text('print(1)')
        self.git('add','run.py');self.git('commit','-m','initial')
        remote=self.root.parent/(self.root.name+'-remote.git')
        subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
        import shutil
        self.addCleanup(lambda:shutil.rmtree(remote,ignore_errors=True))
        self.git('remote','add','origin',str(remote))

    def test_publish_program_excludes_reports_and_pushes_to_local_remote(self):
        self.repo();(self.root/'run.py').write_text('print(2)')
        evidence=self.root/'test-evidence';evidence.mkdir();(evidence/'result.json').write_text('{}')
        publish(self.root,'program',lambda _:None)
        self.assertEqual(self.git('show','HEAD:run.py').strip(),'print(2)')
        self.assertNotIn('test-evidence',self.git('ls-tree','-r','--name-only','HEAD'))

    def test_publish_rejects_pre_staged_unrelated_changes(self):
        self.repo();(self.root/'unrelated.txt').write_text('x');self.git('add','unrelated.txt')
        with self.assertRaisesRegex(RuntimeError,'preparados'):publish(self.root,'program',lambda _:None)

    def test_publish_reports_does_not_commit_code(self):
        self.repo();(self.root/'run.py').write_text('print(2)')
        evidence=self.root/'test-evidence';evidence.mkdir();(evidence/'result.json').write_text('{}')
        publish(self.root,'reports',lambda _:None)
        self.assertEqual(self.git('show','HEAD:run.py').strip(),'print(1)')
        self.assertIn('test-evidence/result.json',self.git('ls-tree','-r','--name-only','HEAD'))

    def test_clear_failure_restores_files_and_database(self):
        from unittest.mock import patch
        run=self.result();game=run.parent.parent
        metadata=game/'game.json';metadata.write_text('{invalid')
        with self.assertRaises(json.JSONDecodeError):
            clear_history(self.root,self.storage,'demo',lambda _:None)
        self.assertTrue(run.exists())
        self.assertEqual(self.storage.list_games('demo')[0].last_status,'OK')
        with self.storage._connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM test_results').fetchone()[0],1)

    def test_failed_export_leaves_previous_export_intact(self):
        run=self.result();(run/'diagnostic.json').write_text('{invalid')
        previous=self.root/'test-evidence/previous.json';previous.parent.mkdir();previous.write_text('{}')
        with self.assertRaises(json.JSONDecodeError):export_reports(self.root,self.storage,lambda _:None)
        self.assertTrue(previous.exists())

    def test_desktop_contains_three_buttons(self):
        import tkinter as tk
        from tkinter import ttk
        from tester_spin.app_project_actions import ProjectActionsMixin
        root=tk.Tk();root.withdraw()
        try:
            parent=ttk.Frame(root);parent.pack()
            before=ttk.Frame(parent);before.pack()
            from types import SimpleNamespace
            host=SimpleNamespace(_project_action=lambda _:None)
            ProjectActionsMixin._build_project_actions(host,parent,before)
            self.assertEqual([b.cget('text') for b in host.project_action_buttons],
                ['Subir programa a GitHub','Borrar historial del proveedor','Subir reportes a GitHub'])
        finally:
            root.destroy()
