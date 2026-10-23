"""Live-observed, provider-wide GPAS stake families. Never certify by name alone."""
from tester_spin.providers.playtech.primitives import discover_modes

SOURCE=('GLU.game.playMoney(x,y,z); GLU.game.playOut(x,y); '
        'ID:40021; ID:48775; "com.pt.gpas.platform.game.OgwCorosinGameCommand";'
        'GLU.game.stakeCostUuid=uuid; GLU.game.featureType=selection;')

CONTRACT={'dialect':'modern','adapter_maps':{},'standard_start_bound':False,'base_selector':None}


def row(name,cost,start='base-uuid',line='1'):
    return dict(uuid='unique-'+name,name=name,cost=cost,
        parameters=dict(startingMode=start,startingPlays='1',winline=line,
                        evalPayout='LEFT_TO_RIGHT',discountable='false'))


def plan(costs, *, active=None, scopes=None, **flags):
    game=dict(costConfiguration=costs,baseCostMultipliers=[1],namedScopes=scopes or {})
    if active is not None:game['activeBetOptions']=active
    game.update(flags)
    return discover_modes({'game':game},CONTRACT,[SOURCE+' ExtraBetsModule BuyFeatureModule'])


def test_scoped_monetary_stakes_require_exact_cost_and_same_base_mode():
    names=['DOLLAR-10','DOLLAR-25','DOLLAR-50']
    costs=[row(n,int(n.split('-')[1])) for n in names]
    costs += [row('PESOS-2',200)]
    scopes={n:{'betType':'default','featureType':n} for n in names}
    p=plan(costs,active=names,scopes=scopes)
    assert [m['kind'] for m in p['modes']]==['SPIN']*3
    assert [m['selector'] for m in p['modes']]==names
    assert p['domains']['purchase']['complete']
    damaged=[dict(x) for x in costs]
    damaged[0]=dict(damaged[0],cost=11)
    bad=plan(damaged,active=names,scopes=scopes)
    assert [m['kind'] for m in bad['modes']]==['UNKNOWN_FEATURE']*3
    assert bad['unresolved']


def test_numeric_stake_ladder_requires_coherent_cost_and_distinct_starting_mode():
    names=['20','40','60','80','100']
    costs=[row(n,int(n)//2,start='s-'+n,line='20') for n in names]
    good=plan(costs)
    assert [m['kind'] for m in good['modes']]==['SPIN']*5
    assert [m['selector'] for m in good['modes']]==['default']*5
    assert not good['unresolved']
    damaged=[dict(c,parameters=dict(c['parameters'])) for c in costs]
    damaged[-1]['parameters']['startingMode']=damaged[0]['parameters']['startingMode']
    broken=plan(damaged)
    assert broken['unresolved']
    assert all(m['kind']=='UNKNOWN_FEATURE' for m in broken['modes'])


def test_extra_fg_collector_are_ante_only_with_active_scopes_and_live_controller():
    default=row('default',10)
    modes=[default,row('extraFG',20,start='fg'),row('extraCollector',150,start='collect')]
    scopes={x['name']:{'betType':'default','featureType':x['name']} for x in modes[1:]}
    p=plan(modes,active=[m['name'] for m in modes],scopes=scopes,extraBetEnabled=True)
    assert [m['kind'] for m in p['modes']]==['SPIN','ANTE_BET','ANTE_BET']
    assert len(p['domains']['ante']['options'])==2
    q=plan(modes,active=[m['name'] for m in modes],scopes=scopes,extraBetEnabled=False)
    assert q['unresolved']
    assert [m['kind'] for m in q['modes'][1:]]==['UNKNOWN_FEATURE']*2


def test_disabling_explicit_bf_skips_only_that_declared_disabled_purchase():
    p=plan([row('Base',10,start='Standard'),row('BF',650,start='paid')],
           featureBetEnabled=False)
    assert [m['kind'] for m in p['modes']]==['SPIN']
    assert p['disabled_modes']==['BF']
    assert p['domains']['purchase']['options']==[]
    assert p['domains']['purchase']['complete']
    active=plan([row('Base',10,start='Standard'),row('BF',650,start='paid')],
                featureBetEnabled=False,active=['Base','BF'])
    assert active['disabled_modes']==[]  # conflicting config must remain visible


def test_single_extra_disabled_is_base_only_if_server_marks_extra_off():
    rows=[row('default',5),row('extra',7,start='ante'),row('extra_disabled',5,start='disabled')]
    p=plan(rows,active=['extra_disabled'],extraBetEnabled=False)
    assert len(p['modes'])==1 and p['modes'][0]['kind']=='SPIN'
    assert p['modes'][0]['selector']=='extra_disabled'
    off=plan(rows,active=['extra_disabled'],extraBetEnabled=True)
    assert off['unresolved']


def test_unique_standard_base_does_not_authorize_unbound_held_respin_prices():
    p=plan([row('20',20,start='Standard'),row('HR10',200,start='bonus')],
           featureBetEnabled=None)
    assert p['modes'][0]['kind']=='SPIN' and p['modes'][0]['selector']=='default'
    assert p['modes'][1]['kind']=='UNKNOWN_FEATURE'
    assert p['unresolved']
