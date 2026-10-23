"""Regression coverage anchored to the original 76-game fuzzer export.

The checked-in JSON is a strictly allowlisted snapshot of GPAS costConfiguration
and game codes (no credentials, URLs, socket frames or session data).
Historical names/costs describe candidate operations: they NEVER authorize
a wager or certify an OK by themselves.
"""
import json
import re
from pathlib import Path

FIXTURE=Path(__file__).parent/'fixtures/playtech_original_74_captured_costs.json'
WORKFLOW=Path(__file__).resolve().parents[1]/'.github/workflows/playtech-original-74.yml'


def load():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def test_all_74_original_game_identities_and_196_cost_rows_are_preserved():
    report=load()
    assert report['schema']=='tester-spin/playtech-original-74-captured-costs/v1'
    assert len(report['source_zip_sha256'])==64
    assert len(report['gpas'])==24 and len(report['ngm_codes'])==50
    assert sum(len(x['modes']) for x in report['gpas'])==196
    assert sum(x['configuration_captured'] for x in report['gpas'])==23
    names=[g['code'] for g in report['gpas']]+report['ngm_codes']
    assert len(names)==len(set(names))==74
    assert all(g.startswith('gpas_') for g in names[:24])
    assert all(not g.startswith('gpas_') for g in names[24:])
    for game in report['gpas']:
        identities=[r['name'] for r in game['modes']]
        assert len(identities)==len(set(identities))
        assert all(type(r['cost']) is int and r['cost']>0 for r in game['modes'])


def test_real_demo_workflow_runs_exactly_these_original_games():
    captured=load()
    text=WORKFLOW.read_text(encoding='utf-8')
    submitted=[code for line in re.findall(r"games: '([^']+)'",text)
               for code in line.split()]
    assert len(submitted)==74 and len(set(submitted))==74
    assert set(submitted)=={g['code'] for g in captured['gpas']}|set(captured['ngm_codes'])
    assert 'playtech-actions-sample.py' in text
    assert 'record_har_path' not in text
    assert 'path: evidence-summary/' in text  # Never upload raw session HAR.


def test_large_unknown_modes_are_not_assumed_to_be_bonus_purchases():
    captured={g['code']:g for g in load()['gpas']}
    assert len(captured['gpas_goalmsnjp_pop']['modes'])==90
    assert len(captured['gpas_fluffyf_pop']['modes'])==25
    assert captured['gpas_fluffyf_pop']['active']==['lines-25']
    assert {r['name'] for r in captured['gpas_gotzon_pop']['modes']
             if r['name'].startswith('BuyFeature')} == {
                 'BuyFeatureRed','BuyFeatureGreen','BuyFeatureBlue',
                 'BuyFeatureRedGreen','BuyFeatureRedBlue',
                 'BuyFeatureGreenBlue','BuyFeatureRedGreenBlue'}
    assert captured['gpas_coft_pop']['active']==['default','buyFeature','buyFeature2']
    assert captured['gpas_krluprising_pop']['modes'][1]['name']=='ShopFeature1'
    assert captured['gpas_mgaogkol_pop']['flags']['featureBetEnabled'] is False
    # A historic configuration cannot override a changed live client/bundle.
    assert load()['provenance'].endswith('NOT runtime authorization')


def test_historical_config_absence_is_preserved_instead_of_fabricating_modes():
    game=next(g for g in load()['gpas'] if g['code']=='gpas_cashrl_pop')
    assert not game['configuration_captured']
    assert game['modes']==[]
