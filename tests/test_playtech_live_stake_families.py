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


def test_numeric_cost_ratio_never_substitutes_for_a_bound_feature_selector():
    names=['20','40','60','80','100']
    costs=[row(n,int(n)//2,start='s-'+n,line='20') for n in names]
    blocked=plan(costs)
    assert [m['kind'] for m in blocked['modes']]==['UNKNOWN_FEATURE']*5
    assert 'BASE_MODE_UNBOUND' in blocked['unresolved']
    # The live server refused 40/default and mapped 100/default to the wrong
    # UUID. Merely having proportional prices is not an executable contract.
    modified=[dict(c,parameters=dict(c['parameters'])) for c in costs]
    modified[0]['parameters']['startingMode']='Standard'
    assert plan(modified)['unresolved']


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


def test_source_bound_line_domain_uses_lines_prefix_and_all_declared_indices():
    costs=[row(str(n),n,start='Standard',line=str(n)) for n in (1,5,10)]
    game=dict(costConfiguration=costs,baseCostMultipliers=[1])
    current=discover_modes({'game':game},CONTRACT,[SOURCE+' winline stakeCostName'])
    assert [m['kind'] for m in current['modes']]==['SPIN']*3
    assert [m['selector'] for m in current['modes']]==['lines-1','lines-5','lines-10']
    assert not current['unresolved']
    missing=discover_modes({'game':game},CONTRACT,[SOURCE])
    assert missing['unresolved']
    assert all(m['kind']=='UNKNOWN_FEATURE' for m in missing['modes'])


def test_no_lines_prefix_if_one_configured_winline_disagrees():
    costs=[row(str(n),n,start='Standard',line=str(n)) for n in (1,2,3)]
    costs[1]['parameters']['winline']='20'
    current=discover_modes({'game':dict(costConfiguration=costs,baseCostMultipliers=[1])},
                           CONTRACT,[SOURCE+' winline stakeCostName'])
    assert current['unresolved']
    assert all(m['kind']=='UNKNOWN_FEATURE' for m in current['modes'])


def test_original_numbered_and_colored_feature_buy_options_need_all_three_authorities():
    purchase=['BuyFeatureRed','BuyFeatureGreen','BuyFeatureBlue',
              'BuyFeatureRedGreen','BuyFeatureRedBlue','BuyFeatureGreenBlue','BuyFeatureRedGreenBlue']
    costs=[row('default',20)]+[row(name,600+i*100,start='purchase-'+name)
                               for i,name in enumerate(purchase)]
    scopes={name:{'betType':'default','featureType':name} for name in purchase}
    active=['default']+purchase
    allowed=plan(costs,active=active,scopes=scopes,featureBetEnabled=True)
    assert [m['kind'] for m in allowed['modes']]==['SPIN']+['PURCHASE']*7
    assert allowed['domains']['purchase']['complete']
    assert len(allowed['domains']['purchase']['options'])==7
    unbound=plan(costs,active=active,scopes=scopes,featureBetEnabled=False)
    assert [m['kind'] for m in unbound['modes'][1:]]==['UNKNOWN_FEATURE']*7
    no_scope=plan(costs,active=active,featureBetEnabled=True)
    assert [m['kind'] for m in no_scope['modes'][1:]]==['UNKNOWN_FEATURE']*7
    no_client=discover_modes({'game':dict(costConfiguration=costs,baseCostMultipliers=[1],
                activeBetOptions=active,namedScopes=scopes,featureBetEnabled=True)},
                CONTRACT,[SOURCE])
    assert all(m['kind']=='UNKNOWN_FEATURE' for m in no_client['modes'][1:])


def test_second_numbered_buy_feature_uses_active_scope_and_live_client():
    modes=[row('default',10),row('buyFeature',700,start='bf'),
           row('buyFeature2',1200,start='bf2')]
    scopes={name:{'betType':'default','featureType':name}
            for name in ('buyFeature','buyFeature2')}
    p=plan(modes,active=['default','buyFeature','buyFeature2'],
           scopes=scopes,featureBetEnabled=True)
    assert [m['kind'] for m in p['modes']]==['SPIN','PURCHASE','PURCHASE']
    assert p['modes'][2]['selector']=='buyFeature2'
    assert not p['unresolved']
    negative=plan(modes,active=['default','buyFeature','buyFeature2'],
                  scopes=scopes,featureBetEnabled=False)
    assert negative['modes'][2]['kind']=='UNKNOWN_FEATURE'


def test_mixed_standard_winline_tiers_use_observed_gpas_lines_selectors():
    from tester_spin.providers.playtech.mode_families import mixed_standard_line_selectors
    rows=[row('5',5,start='Standard',line='25')]+[
          row(str(i),i,start='special-'+str(i),line=str(5*i)) for i in (1,2,3,4)]
    game=dict(costConfiguration=rows,baseCostMultipliers=[1])
    source=SOURCE+' winline'
    bound=mixed_standard_line_selectors(rows,game,CONTRACT,source)
    assert bound=={'5':'default','1':'lines-5','2':'lines-10',
                   '3':'lines-15','4':'lines-20'}
    planned=discover_modes({'game':game},CONTRACT,[source])
    assert [m['kind'] for m in planned['modes']]==['SPIN']*5
    assert [m['selector'] for m in planned['modes']]==[
        'default','lines-5','lines-10','lines-15','lines-20']
    assert not planned['unresolved']


def test_mixed_line_family_requires_complete_domain_not_price_ratios():
    from tester_spin.providers.playtech.mode_families import mixed_standard_line_selectors
    rows=[row('5',5,start='Standard',line='25')]+[
          row(str(i),i,start='special-'+str(i),line=str(5*i)) for i in (1,2,3,4)]
    config=dict(costConfiguration=rows,baseCostMultipliers=[1])
    source=SOURCE+' winline'
    assert not mixed_standard_line_selectors(rows,config,CONTRACT,SOURCE)
    bad=[dict(x,parameters=dict(x['parameters'])) for x in rows]
    bad[-1]['parameters']['winline']='20'
    assert not mixed_standard_line_selectors(bad,config,CONTRACT,source)
    bad=[dict(x) for x in rows]
    bad[-1]['uuid']=bad[0]['uuid']
    assert not mixed_standard_line_selectors(bad,config,CONTRACT,source)
    bad=[dict(x) for x in rows]
    bad[1]=dict(bad[1],cost=20)
    assert not mixed_standard_line_selectors(bad,config,CONTRACT,source)
    active=dict(config,activeBetOptions=['5','1'])
    assert not mixed_standard_line_selectors(rows,active,CONTRACT,source)
    # This is the previous unsafe pattern: numeric labels with same winline.
    other=[row(n,int(n)//2,start='id-'+n,line='20') for n in ('20','40','60','80','100')]
    assert not mixed_standard_line_selectors(other,config,CONTRACT,source)


def test_named_all_standard_line_set_with_complete_server_cost_invariants():
    from tester_spin.providers.playtech.mode_families import named_standard_line_selectors
    rows=[row(str(n),n//5,start='Standard',line=str(n))
          for n in (5,10,15,20)]
    rows.append(row('BasePP',5,start='Standard',line='25'))
    game=dict(costConfiguration=rows,baseCostMultipliers=[1])
    source=SOURCE+' winline stakeCostName'
    mapping=named_standard_line_selectors(rows,game,CONTRACT,source)
    assert mapping=={'5':'lines-5','10':'lines-10','15':'lines-15',
                     '20':'lines-20','BasePP':'lines-25'}
    result=discover_modes({'game':game},CONTRACT,[source])
    assert not result['unresolved']
    assert len(result['modes'])==5
    assert [m['kind'] for m in result['modes']]==['SPIN']*5
    assert [m['selector'] for m in result['modes']]==[
        'lines-5','lines-10','lines-15','lines-20','lines-25']


def test_named_standard_line_set_rejects_partial_or_economic_ambiguity():
    from tester_spin.providers.playtech.mode_families import named_standard_line_selectors
    rows=[row(str(n),n//5,start='Standard',line=str(n))
          for n in (5,10,15,20)]
    rows.append(row('BasePP',5,start='Standard',line='25'))
    good=dict(costConfiguration=rows,baseCostMultipliers=[1])
    source=SOURCE+' winline stakeCostName'
    def bound(values,config=good,src=source):
        return named_standard_line_selectors(values,config,CONTRACT,src)
    assert not bound(rows,src=SOURCE)
    assert not bound(rows,dict(good,featureBetEnabled=True))
    assert not bound(rows,dict(good,activeBetOptions=['5','10']))
    bad=[dict(x,parameters=dict(x['parameters'])) for x in rows]
    bad[0]['parameters']['startingMode']='another-paid-mode'
    assert not bound(bad)
    bad=[dict(x) for x in rows]
    bad[-1]['cost']=999
    assert not bound(bad)
    bad=[dict(x) for x in rows]
    bad[-1]['uuid']=bad[0]['uuid']
    assert not bound(bad)
    bad=[dict(x) for x in rows]
    bad[-1]['name']='buyFeature'
    assert not bound(bad)
    bad=[dict(x) for x in rows]
    bad[0]['name']='6'
    assert not bound(bad)
    assert bound(rows)=={'5':'lines-5','10':'lines-10','15':'lines-15',
                        '20':'lines-20','BasePP':'lines-25'}
