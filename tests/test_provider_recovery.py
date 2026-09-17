import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from tester_spin.models import Game
from tester_spin.providers.redtiger.adapter import RedTigerProvider
from tester_spin.providers.pragmatic_symbol_resolver import PragmaticProvider

class CatalogRecoveryTests(unittest.TestCase):
    def test_legacy_redtiger_resolves_exact_official_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=RedTigerProvider(Path(tmp))
            p._wp_catalog_get=Mock(return_value=Mock(json=lambda:[{'id':123,'slug':'777-money-strike','title':{'rendered':'777 Money Strike'},'link':'https://games.evolution.com/slots/777-money-strike/','acf':{'game_provider':{'post_title':'Red Tiger'}}}]))
            game=Game(provider='redtiger',slug='777-money-strike',name='777 Money Strike',url='https://redtiger.com/games/777-money-strike',symbol='777moneystrike00')
            p.resolve_launch_game(game,timeout_s=5)
            self.assertEqual(game.symbol,'123')
            self.assertEqual(game.url,'https://games.evolution.com/slots/777-money-strike/')

    def test_legacy_redtiger_never_uses_unrelated_search_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=RedTigerProvider(Path(tmp))
            p._wp_catalog_get=Mock(return_value=Mock(json=lambda:[{'id':123,'slug':'other','title':{'rendered':'Other'},'link':'https://games.evolution.com/slots/other/','acf':{}}]))
            game=Game(provider='redtiger',slug='missing',name='Missing',url='https://redtiger.com/games/missing',symbol='old')
            with self.assertRaisesRegex(ValueError,'catálogo'):
                p.resolve_launch_game(game,timeout_s=5)
            self.assertEqual(game.symbol,'old')

    def test_bootstrap_error_keeps_original_cause_without_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=PragmaticProvider(Path(tmp))
            response=Mock(url='https://example.invalid/game',text='{"gameSymbol":"vs10chkchase"}')
            p._http_bootstrap=Mock(side_effect=RuntimeError('no idle; mgckey=SECRET'))
            with patch('tester_spin.providers.pragmatic_symbol_resolver._resolver_session',return_value=Mock(get=Mock(return_value=response))):
                with self.assertRaises(RuntimeError) as caught:
                    p._resolve_symbol_http('https://example.invalid/game',5)
            self.assertIn('no idle',str(caught.exception))
            self.assertNotIn('SECRET',str(caught.exception))
