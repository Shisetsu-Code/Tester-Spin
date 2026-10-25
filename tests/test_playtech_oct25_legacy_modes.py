"""Strict GPAS legacy two-option bound family and ChooseFG non-promotion."""
from copy import deepcopy
import pytest

from tester_spin.providers.playtech.mode_families import legacy_numeric_base_with_named_buy
from tester_spin.providers.playtech.primitives import discover_modes,entry_command,RoundLedger,PickState
from tester_spin.providers.playtech.gpas_continuation import ContinuationPlanner

CONTRACT=dict(dialect='legacy',
    class_='not-used',adapter_maps={},entry_id=40021,continuation_id=48775,
    standard_start_bound=False,base_selector=None,pick_bound=False)
CONTRACT['class']='com.pt.gpas.platform.game.OgwCorosinGameCommand'
SOURCE='GLU.game.bet(mode); stakeCostUuid; baseCostMultiplier;'


def cfg():
    return {'game':{
        'costConfiguration':[
            {'name':'40','cost':10,'uuid':'server-base-uuid',
             'parameters':{'startingMode':'regular','startingPlays':'1','winline':'40'}},
            {'name':'Buy feature','cost':800,'uuid':'server-feature-uuid',
             'parameters':{'startingMode':'feature','startingPlays':'1','winline':'40'}}],
        'featureBetEnabled':True,
        'baseCostMultipliers':[1,5,50], 'defaultBaseCostMultiplier':50,
        'maxBet':100000}}


def test_legacy_modes_allow_live_numeric_base_and_feature_but_do_not_verify_picks():
    data=cfg()
    mapping=legacy_numeric_base_with_named_buy(data['game']['costConfiguration'],
                                                  data['game'],CONTRACT,SOURCE)
    assert mapping=={'40':'SPIN','Buy feature':'PURCHASE'}
    plan=discover_modes(data,CONTRACT,[SOURCE])
    assert plan['unresolved']==[]
    assert [m['kind'] for m in plan['modes']]==['SPIN','PURCHASE']
    assert plan['modes'][0]['multiplier']==1
    assert plan['modes'][1]['multiplier']==50
    normal=entry_command(plan['modes'][0],CONTRACT)
    buy=entry_command(plan['modes'][1],CONTRACT)
    assert normal['gameData']['bet']==10
    assert normal['gameData']['stakeCostUuid']=='server-base-uuid'
    assert buy['gameData']['bet']==40000
    assert buy['gameData']['stakeCostUuid']=='server-feature-uuid'
    assert buy['gameData']['baseCostMultiplier']==50
    assert 'featureType' not in buy
    assert all(m.get('validated') is not True for m in plan['modes'])


def test_legacy_named_buy_never_authorized_without_server_live_contract():
    for key,value in [('featureBetEnabled',False),
                      ('activeBetOptions',['40']),
                      ('activeBetOptions',['40','Buy feature','Extra'])]:
        data=cfg();data['game'][key]=value
        assert not legacy_numeric_base_with_named_buy(
            data['game']['costConfiguration'],data['game'],CONTRACT,SOURCE)
    data=cfg()
    assert not legacy_numeric_base_with_named_buy(
        data['game']['costConfiguration'],data['game'],
        {**CONTRACT,'dialect':'modern'},SOURCE)
    assert not legacy_numeric_base_with_named_buy(
        data['game']['costConfiguration'],data['game'],CONTRACT,'GLU.game.bet')


def test_legacy_uuid_identity_mismatch_disables_both_modes():
    for violation in ('same_uuid','winline','starting_mode','unexpected_buy'):
        data=cfg()
        base,bonus=data['game']['costConfiguration']
        if violation=='same_uuid':bonus['uuid']=base['uuid']
        if violation=='winline':bonus['parameters']['winline']='20'
        if violation=='starting_mode':bonus['parameters']['startingMode']='regular'
        if violation=='unexpected_buy':bonus['name']='BuyFeature'
        assert not legacy_numeric_base_with_named_buy(
            data['game']['costConfiguration'],data['game'],CONTRACT,SOURCE)


def test_choose_fg_with_no_bound_pick_serializer_stays_open():
    data={'nextRound':'ChooseFG','playIndex':2,
          'playStack':[{'round':'ChooseFG','modeType':'LIST_PICK',
                        'remainingPlayCount':1}]}
    with pytest.raises(ValueError,match='PICK_COMMAND_NOT_BOUND'):
        ContinuationPlanner().parameters(data,CONTRACT,PickState())
    ledger=RoundLedger(100000,'server-feature-uuid',40000)
    response={'stakeAmount':40000,'betCost':40000,'winAmount':0,
              'gameRoundClosed':False,'gameData':{
                'stakeCostUuid':'server-feature-uuid','nextRound':'ChooseFG',
                'totalWinAmount':0,**{k:v for k,v in data.items() if k!='nextRound'},
              }}
    ledger.accept(response)
    assert ledger.closed is False
    assert ledger.verify(60000) is False
