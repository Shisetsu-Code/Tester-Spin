"""Regressions for source- and wire-backed families seen in HardFire 2026-10-25.

These fixtures contain only allowlisted economic declarations from demo
captures. No HAR frames, tokens, cookies or copied client JavaScript.
"""
import copy
from tester_spin.providers.playtech.primitives import discover_modes
from tester_spin.providers.playtech.two_option_contracts import infer_two_option_modes

LIVE_SOURCE='GLU.game.playMoney stakeCostUuid featureType GLU.game.playOut ExtraBetsModule BuyFeatureModule'
CONTRACT={'dialect':'modern','standard_start_bound':False,'base_selector':None,'adapter_maps':{}}


def cost(name,amount,winline,mode,*,idx=0):
    return {'name':name,'cost':amount,'uuid':'stub-cost-'+name,
            'parameters':{'startingMode':mode,'startingPlays':'1',
                          'winline':str(winline),'evalPayout':'LEFT_TO_RIGHT'}}


def modes(rows,*,active=None,flags=None,scopes=None,source=LIVE_SOURCE,contract=None):
    game={'costConfiguration':copy.deepcopy(rows),
          'baseCostMultipliers':[1],'namedScopes':scopes or {}}
    if active is not None:game['activeBetOptions']=active
    game.update(flags or {})
    return discover_modes({'game':game},contract or CONTRACT,[source])


def test_ultra_scoped_ante_and_buy_feature_are_distinct_active_modes():
    rows=[cost('default',10,1,'base'),cost('extra',15,1,'extra'),
          cost('ultra',25,1,'ultra'),cost('BuyFeature',700,1,'buy')]
    scope={name:{'betType':'default','featureType':name}
           for name in ('extra','ultra','BuyFeature')}
    result=modes(rows,active=[x['name'] for x in rows],
                 flags={'extraBetEnabled':True,'featureBetEnabled':True},scopes=scope)
    assert [r['kind'] for r in result['modes']]==[
        'SPIN','ANTE_BET','ANTE_BET','PURCHASE']
    assert [r['selector'] for r in result['modes']]==['default','extra','ultra','BuyFeature']
    assert not result['unresolved']
    removed=modes(rows,active=[x['name'] for x in rows],
        flags={'extraBetEnabled':False,'featureBetEnabled':True},scopes=scope)
    assert removed['modes'][2]['kind']=='UNKNOWN_FEATURE'


def test_classic_is_base_variant_only_for_exact_two_row_winline_family():
    rows=[cost('20',20,40,'Standard'),cost('Classic',20,40,'classic-mode')]
    result=modes(rows)
    assert [r['kind'] for r in result['modes']]==['SPIN','SPIN']
    assert [r['selector'] for r in result['modes']]==['default','classic']
    assert not result['unresolved']
    bad=copy.deepcopy(rows);bad[1]['parameters']['winline']='50'
    result=modes(bad)
    assert result['modes'][1]['kind']=='UNKNOWN_FEATURE'
    bad=copy.deepcopy(rows);bad[1]['cost']=21
    assert modes(bad)['unresolved']
    assert modes(rows,flags={'featureBetEnabled':True})['unresolved']


def test_feature_boost_pair_has_distinct_base_and_ante_with_verified_cost_ratio():
    rows=[cost('default-20',20,20,'base'),cost('feature-20',30,20,'boost')]
    result=modes(rows,flags={'featureBetEnabled':True})
    assert [r['kind'] for r in result['modes']]==['SPIN','ANTE_BET']
    assert [r['selector'] for r in result['modes']]==['default','feature-20']
    assert not result['unresolved']
    assert modes(rows,flags={'featureBetEnabled':False})['unresolved']
    bad=copy.deepcopy(rows);bad[1]['cost']=40
    assert modes(bad,flags={'featureBetEnabled':True})['unresolved']
    bad=copy.deepcopy(rows);bad[1]['uuid']=bad[0]['uuid']
    assert infer_two_option_modes(bad,{'featureBetEnabled':True},CONTRACT,LIVE_SOURCE)=={}


def test_buy_bonus_pair_binds_client_default_and_hyphenated_purchase_selector():
    rows=[cost('10',10,36,'base'),cost('BuyBonus',550,36,'bonus')]
    result=modes(rows,flags={'featureBetEnabled':True})
    assert [r['kind'] for r in result['modes']]==['SPIN','PURCHASE']
    assert [r['selector'] for r in result['modes']]==['default','buy-bonus']
    assert len(result['domains']['purchase']['options'])==1
    assert not result['unresolved']
    bad=copy.deepcopy(rows);bad[1]['parameters']['winline']='25'
    assert modes(bad,flags={'featureBetEnabled':True})['unresolved']
    bad=copy.deepcopy(rows);bad[1]['cost']=50
    assert modes(bad,flags={'featureBetEnabled':True})['unresolved']
    assert modes(rows,flags={'featureBetEnabled':False})['unresolved']


def test_guards_reject_stale_or_incomplete_client_binding():
    rows=[cost('10',10,36,'base'),cost('BuyBonus',550,36,'bonus')]
    assert not infer_two_option_modes(rows,{'featureBetEnabled':True},CONTRACT,'no client binding')
    assert not infer_two_option_modes(rows,{'featureBetEnabled':True},
                                      dict(CONTRACT,dialect='legacy'),LIVE_SOURCE)
    assert not infer_two_option_modes(rows,
        {'featureBetEnabled':True,'activeBetOptions':['10']},CONTRACT,LIVE_SOURCE)
    assert not infer_two_option_modes(rows,
        {'featureBetEnabled':True,'namedScopes':{'BuyBonus':{
            'betType':'default','featureType':'another-option'}}},CONTRACT,LIVE_SOURCE)
    assert not infer_two_option_modes(rows+[cost('surprise',1,36,'other')],
                                      {'featureBetEnabled':True},CONTRACT,LIVE_SOURCE)


def test_observed_buy_bonus_free_game_auto_continuation_stays_unpaid_and_terminal():
    from tester_spin.providers.playtech.gpas_continuation import ContinuationPlanner
    from tester_spin.providers.playtech.primitives import PickState, RoundLedger
    ledger=RoundLedger(10000,'buy-bonus-uuid',550)
    plan=ContinuationPlanner()
    for i,remaining in enumerate((6,5,4,3,2,1,0),start=1):
        terminal=remaining==0
        next_round='BET_END_STATE_IDENTIFIER' if terminal else 'FreeGame'
        stack=[] if terminal else [
            {'round':'FreeGame','modeType':'SLOTS','remainingPlayCount':remaining},
            {'round':'VacuumEvaluation','modeType':'SLOTS','remainingPlayCount':1}]
        msg={'stakeAmount':550 if i==1 else 0,
             'betCost':550 if i==1 else 0,'winAmount':0,
             'gameRoundClosed':terminal,
             'gameData':{'_type':'ryota:GameResponse','stakeCostUuid':'buy-bonus-uuid',
                         'stake':550,'playIndex':i,'totalWinAmount':0,
                         'nextRound':next_round,'playStack':stack}}
        data=ledger.accept(msg)
        if not terminal:
            assert plan.parameters(data,{'pick_bound':False},PickState())==[]
    assert len(plan.records)==6
    assert ledger.closed and ledger.verify(9450)
    assert all(rec['chosen_options']==[] for rec in plan.records)
