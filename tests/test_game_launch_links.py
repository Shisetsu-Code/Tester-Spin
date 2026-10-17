from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from tester_spin.models import Game


def test_existing_playtech_catalog_record_opens_ready_demo():
    g=Game('playtech','game-gpas_example_pop','Example','https://www.playtechone.com/',symbol='gpas_example_pop')
    u=urlsplit(g.launch_url)
    assert u.hostname=='cachedownload.playtechone.com'
    assert u.path=='/ngmdesktop/casinoclient.html'
    assert parse_qs(u.query)=={'game':['gpas_example_pop'],'preferedmode':['offline'],'real':['0']}
    assert g.url=='https://www.playtechone.com/'


def test_ngm_and_missing_symbol_use_catalog_identity():
    g=Game('playtech','game-ashhof','Heart','https://www.playtechone.com/',symbol='ashhof')
    assert parse_qs(urlsplit(g.launch_url).query)['game']==['ashhof']
    g.symbol='';g.slug='game-%20BookOfDuat'
    assert parse_qs(urlsplit(g.launch_url).query)['game']==['BookOfDuat']


def test_other_provider_links_are_preserved():
    g=Game('hacksaw','example','Example','https://example.com/demo',symbol='example')
    assert g.launch_url==g.url


def test_open_button_uses_resolved_link_without_network_or_browser():
    from tester_spin.app import TesterSpinApp
    game=Game('playtech','game-ashhof','Heart','https://www.playtechone.com/',symbol='ashhof')
    app=SimpleNamespace(tree=SimpleNamespace(selection=lambda:['id']),_games={'id':game})
    with patch('tester_spin.app.webbrowser.open') as open_url:
        TesterSpinApp._open_selected_url(app)
    open_url.assert_called_once_with(game.launch_url)


def test_hardfire_action_uses_same_demo_link():
    from tester_spin.app import TesterSpinApp
    import queue
    game=Game('playtech','game-ashhof','Heart','https://www.playtechone.com/',symbol='ashhof')
    app=SimpleNamespace(tree=SimpleNamespace(selection=lambda:['id']),_games={'id':game},
        _hardfire_opening=False,hardfire_btn=Mock(),_append_log=Mock(),_events=queue.Queue())
    with patch('tester_spin.app.threading.Thread') as thread, patch('tester_spin.hardfire_launcher.HardFireClient') as client:
        TesterSpinApp._open_selected_hardfire(app)
        thread.call_args.kwargs['target']()
    client.return_value.open_game.assert_called_once_with(game.launch_url)
    assert app._events.get()==('hardfire_opened','Heart')
