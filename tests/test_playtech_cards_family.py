"""Source- and server-bound BF*Cards GPAS family regression tests."""
from copy import deepcopy
from tester_spin.providers.playtech.mode_families import card_buy_family
from tester_spin.providers.playtech.primitives import discover_modes, entry_command

CONTRACT={'dialect':'modern','class':'com.pt.gpas.platform.game.OgwCorosinGameCommand',
          'entry_id':40021,'continuation_id':48775,'adapter_maps':{},
          'standard_start_bound':False,'base_selector':'default','pick_bound':False}
SOURCE=('GLU.game.playMoney(stakeCostUuid,baseCostMultiplier,featureType) '
        'BuyFeatureController; id=40021; id=48775;')
SOURCE_NO_BUY=SOURCE.replace('BuyFeatureController','GameController')


def row(name,cost,version):
    return dict(name=name,cost=cost,uuid=f'fresh-cost-id-{version}',
        parameters={'startingMode':f'live-round-{version}','startingPlays':'1',
                    'winline':'30','evalPayout':'LEFT_TO_RIGHT'})


def config():
    items=[row('default',10,1),row('BF3Cards',1000,2),
           row('BF6Cards',1500,3),row('BF9Cards',2000,4)]
    game=dict(costConfiguration=items,featureBetEnabled=True,
              activeBetOptions=[r['name'] for r in items],
              baseCostMultipliers=[1,10,50],defaultBaseCostMultiplier=50,
              maxBet=100000)
    return {'game':game}


def test_three_cards_are_distinct_buys_using_live_current_configuration():
    game=config()['game']
    assert card_buy_family(game['costConfiguration'],game,CONTRACT,SOURCE)=={
        'BF3Cards','BF6Cards','BF9Cards'}
    plan=discover_modes(config(),CONTRACT,[SOURCE])
    assert plan['unresolved']==[]
    assert [m['kind'] for m in plan['modes']]==[
        'SPIN','PURCHASE','PURCHASE','PURCHASE']
    assert len(plan['domains']['purchase']['options'])==3
    for mode in plan['modes'][1:]:
        command=entry_command(mode,CONTRACT)
        assert mode['multiplier']==50
        assert command['featureType']==mode['name']
        assert command['betCost']==mode['cost']*50
        assert command['gameData']['ID']==40021
    # The previous ZIP BF9Cards witness captured 100000 internal units,
    # but this declaration cannot prove the bonus closed on its own.
    assert plan['modes'][-1]['cost']*plan['modes'][-1]['multiplier']==100000
    assert not any(m.get('validated') for m in plan['modes'])


def test_cards_never_authorized_from_names_without_binder_or_live_flags():
    for field,value in [('featureBetEnabled',False),('activeBetOptions',['default']),
                        ('activeBetOptions',None)]:
        cfg=deepcopy(config())
        cfg['game'][field]=value
        assert not card_buy_family(cfg['game']['costConfiguration'],cfg['game'],CONTRACT,SOURCE)
        plan=discover_modes(cfg,CONTRACT,[SOURCE])
        assert all(m['kind']!='PURCHASE' for m in plan['modes'])
    cfg=config()
    assert not card_buy_family(cfg['game']['costConfiguration'],cfg['game'],CONTRACT,SOURCE_NO_BUY)
    assert all(m['kind']!='PURCHASE' for m in discover_modes(cfg,CONTRACT,[SOURCE_NO_BUY])['modes'])


def test_cards_require_independent_uuid_stage_and_matching_lines():
    for key,value in [('uuid','fresh-cost-id-1'),('cost',5)]:
        cfg=deepcopy(config())
        cfg['game']['costConfiguration'][1][key]=value
        assert not card_buy_family(cfg['game']['costConfiguration'],cfg['game'],CONTRACT,SOURCE)
    cfg=deepcopy(config())
    cfg['game']['costConfiguration'][2]['parameters']['startingMode']='live-round-1'
    assert not card_buy_family(cfg['game']['costConfiguration'],cfg['game'],CONTRACT,SOURCE)
    cfg=deepcopy(config())
    cfg['game']['costConfiguration'][2]['parameters']['winline']='25'
    assert not card_buy_family(cfg['game']['costConfiguration'],cfg['game'],CONTRACT,SOURCE)
    cfg=deepcopy(config())
    cfg['game']['costConfiguration'].append(row('BF20Ultra',3000,6))
    cfg['game']['activeBetOptions'].append('BF20Ultra')
    assert not card_buy_family(cfg['game']['costConfiguration'],cfg['game'],CONTRACT,SOURCE)
