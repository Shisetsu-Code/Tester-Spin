import copy
import pytest
from tester_spin.providers.redtiger.modifiers import declared_modifiers,modifier_executed

SETTINGS={'gameModes':[{'name':'Boost','gameMode':1,'priceMultiplier':'3'},{'name':'State','gameMode':2,'priceMultiplier':'1'}],
 'mathModes':[{'name':'Boost','type':'chanceIncrease','id':1,'priceMultiplier':'3'},{'name':'State','type':'stateSwitch','id':2,'priceMultiplier':'1'}]}


def test_modes_are_declared_by_matching_current_server_tables_not_names():
    modes,unknown=declared_modifiers(SETTINGS)
    assert not unknown
    assert [m['kind'] for m in modes]==['ANTE_BET','STATE_SWITCH']
    assert [m['gameMode'] for m in modes]==[1,2]


@pytest.mark.parametrize('change',[
 lambda d:d['mathModes'][0].update(priceMultiplier='4'),
 lambda d:d['mathModes'][0].update(id=True),
 lambda d:d['mathModes'][0].update(type='unknown'),
 lambda d:d['gameModes'].append(dict(d['gameModes'][0])),
])
def test_incomplete_or_conflicting_modifier_contracts_stay_unresolved(change):
    d=copy.deepcopy(SETTINGS);change(d)
    modes,unknown=declared_modifiers(d)
    assert unknown
    assert not any(m['gameMode']==1 for m in modes)


def test_modifier_ack_requires_declared_mode_exact_debit_and_settlement():
    spec=declared_modifiers(SETTINGS)[0][0]
    req={'stake':2,'gameMode':1,'extras':None,'bonusId':None}
    reply={'success':True,'result':{'game':{'gameMode':1,'stake':'2','win':{'total':'2.4'}},'user':{'balance':{'cash':{'atStart':'10000','afterBet':'9994','atEnd':'9996.4'}}}}}
    assert modifier_executed(reply,req,spec)
    for change in [lambda d:d['result']['game'].update(gameMode=0),lambda d:d['result']['user']['balance']['cash'].update(afterBet='9998'),lambda d:d['result']['user']['balance']['cash'].update(atEnd='9999')]:
        d=copy.deepcopy(reply);change(d)
        assert not modifier_executed(d,req,spec)
