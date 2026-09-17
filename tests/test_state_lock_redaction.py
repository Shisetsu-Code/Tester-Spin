import unittest
from tester_spin.run_diagnostics import sanitize

class StateLockRedactionTests(unittest.TestCase):
    def test_lock_is_redacted_in_probe_request_and_summary(self):
        report={'request':{'params':{'state_lock':'live-lock'}},'summary':{'state_lock':'next-lock'}}
        cleaned=sanitize(report)
        self.assertEqual(cleaned['request']['params']['state_lock'],'[REDACTED]')
        self.assertEqual(cleaned['summary']['state_lock'],'[REDACTED]')
