from types import SimpleNamespace
from tester_spin.app_current import CurrentTesterSpinApp


def test_focus_refreshes_external_results_and_preserves_selection():
    calls=[]
    tree=SimpleNamespace(selection=lambda:('id',),yview=lambda:(.4,.7),exists=lambda x:True,selection_set=lambda x:calls.append(('selection',x)),yview_moveto=lambda x:calls.append(('scroll',x)))
    obj=SimpleNamespace(tree=tree,_worker=None,_refresh_games=lambda:calls.append('refresh'))
    CurrentTesterSpinApp._refresh_external_results(obj,SimpleNamespace(widget=obj))
    assert calls==['refresh',('selection',['id']),('scroll',.4)]


def test_child_focus_and_active_run_do_not_force_a_refresh():
    calls=[]
    obj=SimpleNamespace(_worker=SimpleNamespace(is_alive=lambda:True),_refresh_games=lambda:calls.append('refresh'))
    CurrentTesterSpinApp._refresh_external_results(obj,SimpleNamespace(widget=obj))
    CurrentTesterSpinApp._refresh_external_results(obj,SimpleNamespace(widget=object()))
    assert calls==[]
