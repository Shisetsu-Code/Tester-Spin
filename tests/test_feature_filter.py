import pytest
from tester_spin.feature_filter import matches_features
from tester_spin.models import Game
from tester_spin.app_current import CurrentTesterSpinApp
from types import SimpleNamespace


def result(buys,antes):
    return {'feature_domains':{k:{'complete':True,'source':'server','options':list(range(n))} for k,n in [('purchase',buys),('ante',antes)]}}


@pytest.mark.parametrize('buys,antes,mode,expected',[(1,0,'purchase',True),(0,1,'purchase',False),(0,1,'ante',True),(1,0,'either',True),(0,1,'either',True),(0,0,'either',False),(1,1,'both',True),(1,0,'both',False)])
def test_counts_filter(buys,antes,mode,expected):
    assert matches_features(result(buys,antes),mode)==expected


def test_unknown_is_not_presence():
    assert matches_features({},'all')
    assert not matches_features({},'either')


def test_export_can_include_ok_games_with_features_and_excludes_zero():
    games=[Game('x',s,s,'https://example.com/'+s,last_status='OK') for s in ['buy','ante','none']]
    rows=[dict(result(b,a),slug=s) for s,b,a in [('buy',2,0),('ante',0,1),('none',0,0)]]
    app=SimpleNamespace(storage=SimpleNamespace(list_games=lambda _:games,latest_results=lambda _:rows),_feature_filter_var=SimpleNamespace(get=lambda:'Con compras o antebets'))
    filtered=CurrentTesterSpinApp._filtered_export_games(app,'x')
    assert [g.slug for g in filtered]==['buy','ante']
