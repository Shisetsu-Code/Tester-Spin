import tempfile,unittest
from pathlib import Path
from tester_spin.server_observations import write_observations

class ObservationPendingTests(unittest.TestCase):
    def test_readable_json_does_not_hide_unresolved_protocol_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=write_observations(Path(tmp),{'provider':'1spin4win','trajectories':[],
                'announced_branches':[{'mode_id':'D1_UNKNOWN_RESULT_STATES','missing':['99']}]})
            self.assertEqual(report['unparsed'],0)
            self.assertEqual(report['pending_branches'],1)
            self.assertEqual(report['pending_options'],1)
            self.assertIn('Pendientes de cobertura: 1',(Path(tmp)/'server-observations.md').read_text(encoding='utf-8'))
