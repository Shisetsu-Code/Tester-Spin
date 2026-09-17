import json
import tempfile
import unittest
from pathlib import Path
from tester_spin.manual_review import review_item, render_review, write_review

class ManualReviewTests(unittest.TestCase):
    def row(self, **values):
        return dict(provider='bgaming', slug='a', game_name='Juego', status='OK', **values)

    def test_outcome_noise_does_not_require_review(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'run-tree.json').write_text(json.dumps({'trajectories':[]}))
            Path(d, 'server-observations.json').write_text(json.dumps({'observations':[{'classification':'NEW_RESPONSE','change_kind':'OUTCOME_VARIATION','review_required':False}]}))
            self.assertIsNone(review_item(self.row(run_dir=d)))

    def test_unknown_response_on_ok_is_included(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'server-observations.json').write_text(json.dumps({'observations':[{'review_required':True}]}))
            self.assertIn('respuesta', str(review_item(self.row(run_dir=d))).lower())

    def test_pending_purchase_and_failed_spin_both_explained(self):
        row=self.row(error='HTTPError 422', discovered_modes=[{'id':'PURCHASE_FREESPIN_BUY','executable':False}])
        row['status']='PARCIAL'
        item=review_item(row)
        text=render_review([row])
        self.assertIn('compra',text.lower())
        self.assertIn('rechaz',text.lower())
        self.assertEqual(text.count('1. Juego'),1)
        self.assertNotIn('HTTPError',text)

    def test_cancellation_and_missing_results_not_reported_as_success(self):
        text=render_review([], expected_count=3)
        self.assertIn('3 juegos sin resultado', text)

    def test_report_saved_and_names_single_line(self):
        with tempfile.TemporaryDirectory() as d:
            row=self.row(error='unknown');row.update(status='PARCIAL',game_name='Dos\nlineas')
            path=write_review([row],Path(d),expected_count=1)
            self.assertIn('1. Dos lineas',path.read_text(encoding='utf-8'))

    def test_missing_diagnostics_requires_review(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNotNone(review_item(self.row(run_dir=d)))

    def test_review_window_belongs_to_application(self):
        from tester_spin.app_current import CurrentTesterSpinApp
        self.assertTrue(callable(getattr(CurrentTesterSpinApp, '_show_manual_review', None)))
