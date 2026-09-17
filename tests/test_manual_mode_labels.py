import unittest
from tester_spin.manual_review import render_review


class ModeLabelTests(unittest.TestCase):
    def test_failed_selector_mode_is_readable(self):
        row={'provider':'bgaming','game_name':'Juego','status':'PARCIAL',
             'attempts':[{'mode_id':'PURCHASE_BONUS_BUY_MODE_3','ok':False,'terminal':False,'error':'HTTPError 422'}]}
        text=render_review([row])
        self.assertIn('compra de bonus (modo 3)',text)
        self.assertNotIn('PURCHASE_BONUS_BUY_MODE_3',text)
