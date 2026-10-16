import copy
from tester_spin.providers.redtiger.runtime import purchase_declaration


def test_other_typed_math_modes_do_not_erase_independent_purchase_declaration():
    game={'hasFeatureBuy':True,'featureBuy':[{'name':'BUY','price':50}],
      'mathModes':[{'type':'chanceIncrease','name':'BOOST','id':1,'priceMultiplier':'3'},
                   {'type':'stateSwitch','name':'STATE','id':2,'priceMultiplier':'1'},
                   {'type':'featureBuy','name':'BUY','id':101,'priceMultiplier':'50'}]}
    assert purchase_declaration(game)['options']==['BUY']
    assert purchase_declaration(game)['complete']
    game['mathModes'][-1]['priceMultiplier']='51'
    assert not purchase_declaration(game)['complete']
