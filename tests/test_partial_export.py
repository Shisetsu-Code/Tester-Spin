from tester_spin.models import Game
from tester_spin.partial_export import partial_urls,write_partial_export


def game(slug,status='PARCIAL',**kw):
    return Game('playtech',slug,slug,'https://www.playtechone.com/',symbol=slug.removeprefix('game-'),last_status=status,**kw)


def test_only_visible_partial_games_are_exported_as_direct_demo_urls():
    rows=[game('game-z'),game('game-a'),game('game-ok','OK'),game('game-error','ERROR'),game('game-pending','PENDIENTE'),game('game-manual',manual_ok_at='2026-10-18')]
    urls=partial_urls(rows)
    assert len(urls)==2 and 'game=a&' in urls[0] and 'game=z&' in urls[1]
    assert all('casinoclient.html?' in u and 'real=0' in u for u in urls)


def test_utf8_plain_lines_keep_query_and_remove_duplicates(tmp_path):
    a=Game('pragmatic','a','Árbol','https://www.pragmaticplay.com/en/games/tree/?demo=1&lang=es',last_status='PARCIAL')
    path=tmp_path/'list.txt';count=write_partial_export(path,[a,a])
    assert count==1
    assert path.read_text(encoding='utf-8')==a.launch_url+'\n'
    assert not path.read_bytes().startswith(b'\xef\xbb\xbf')


def test_export_action_reads_persisted_results_and_writes_importable_file(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import patch
    from tester_spin.app_current import CurrentTesterSpinApp
    path=tmp_path/'batch.txt';logs=[]
    app=SimpleNamespace(_provider=lambda:SimpleNamespace(key='playtech',display_name='Playtech'),storage=SimpleNamespace(list_games=lambda provider:[game('game-a')]),_append_log=logs.append,status_var=SimpleNamespace(set=logs.append))
    with patch('tester_spin.app_current.filedialog.asksaveasfilename',return_value=str(path)),patch('tester_spin.app_current.messagebox.showinfo'):
        CurrentTesterSpinApp._export_partials(app)
    assert 'game=a&' in path.read_text(encoding='utf-8')
    assert logs


def test_cancel_export_does_not_change_results_or_write_files(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import patch
    from tester_spin.app_current import CurrentTesterSpinApp
    row=game('game-a');app=SimpleNamespace(_provider=lambda:SimpleNamespace(key='playtech',display_name='Playtech'),storage=SimpleNamespace(list_games=lambda provider:[row]))
    with patch('tester_spin.app_current.filedialog.asksaveasfilename',return_value=''):
        CurrentTesterSpinApp._export_partials(app)
    assert row.last_status=='PARCIAL'
    assert not list(tmp_path.iterdir())
