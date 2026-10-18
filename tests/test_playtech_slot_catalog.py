import pytest
from tester_spin.providers.catalogs.fetch import playtech_slot_rows


def fixture():
    games={c:{'name':n,'gameCode':c,'desktopGameType':'NGM','defaultGameImage':''} for c,n in [('slot','Roulette Adventure'),('table','Classic Roulette'),('unknown','Unclassified')]}
    return {'gameTypes':[{'name':'NGM','demoPlayUrl':'demo'}],'games':games}, {'name':'casino-2026','gamesFeedCategories':[{'seoFriendlyCategoryName':'slots','desktopCategoryConfiguration':{'isActive':True,'categoryGames':['slot'] }},{'seoFriendlyCategoryName':'table-and-cards','desktopCategoryConfiguration':{'isActive':True,'categoryGames':['table']}}]}


def test_official_slot_membership_not_engine_or_title_decides():
    data,feed=fixture();rows=playtech_slot_rows(data,feed)
    assert [r['symbol'] for r in rows]==['slot']
    assert rows[0]['game_kind']=='slot'
    assert rows[0]['category']=='NGM'


def test_missing_or_conflicting_slot_authority_is_rejected():
    data,feed=fixture()
    with pytest.raises(ValueError):playtech_slot_rows(data,{'gamesFeedCategories':[]})
    feed['gamesFeedCategories'][0]['desktopCategoryConfiguration']['categoryGames']=[]
    with pytest.raises(ValueError):playtech_slot_rows(data,feed)


def test_playtech_snapshot_contains_only_categorized_slots():
    import json
    from pathlib import Path
    doc=json.loads((Path(__file__).parents[1]/'tester_spin/providers/catalogs/snapshots/playtech.json').read_text(encoding='utf-8'))
    assert doc['coverage']=='official_slots_category'
    assert all(r.get('game_kind')=='slot' for r in doc['games'])


def test_live_slots_replace_legacy_snapshot_and_enable_reconciliation(tmp_path,monkeypatch):
    import threading
    from tester_spin.providers.playtech.adapter import PlaytechProvider
    provider=PlaytechProvider(tmp_path)
    data,feed=fixture();rows=playtech_slot_rows(data,feed)
    monkeypatch.setattr(provider,'fetch_live_rows',lambda *_:rows)
    games=provider.crawl_catalog(stop_event=threading.Event(),progress=lambda _:None)
    assert [g.symbol for g in games]==['slot']
    assert provider.catalog_crawl_authoritative


def test_failed_classification_keeps_verified_snapshot_without_pruning(tmp_path,monkeypatch):
    import threading
    from tester_spin.providers.playtech.adapter import PlaytechProvider
    provider=PlaytechProvider(tmp_path)
    def fail(*_):raise ValueError('Missing Slots')
    monkeypatch.setattr(provider,'fetch_live_rows',fail)
    games=provider.crawl_catalog(stop_event=threading.Event(),progress=lambda _:None)
    assert len(games)>100
    assert not provider.catalog_crawl_authoritative
