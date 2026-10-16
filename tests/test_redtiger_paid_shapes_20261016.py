import copy
import json
from pathlib import Path
import pytest
from tester_spin.providers.redtiger.base_state import classify_base_state
ROWS=json.loads(Path(__file__).with_name('fixtures').joinpath('redtiger_paid_shapes_20261016.json').read_text(encoding='utf-8'))

@pytest.mark.parametrize('row',ROWS,ids=lambda r:r['capture'])
def test_paid_settled_persistent_inline_and_unstaked_nsp(row):
    proof=classify_base_state(row['current'],request=row['request'],previous=row['previous'])
    assert proof['base'],proof

@pytest.mark.parametrize('change',['round','payment','settlement','choices','active','hasStateType'])
@pytest.mark.parametrize('row',ROWS,ids=lambda r:r['capture'])
def test_no_controls_or_ledger_failure_can_be_hidden(row,change):
    value=copy.deepcopy(row['current']);g=value['result']['game']
    if change=='round':value['result']['transactions']['roundId']=row['previous']['result']['transactions']['roundId']
    if change=='payment':value['result']['user']['balance']['cash']['afterBet']=value['result']['user']['balance']['cash']['atStart']
    if change=='settlement':value['result']['user']['balance']['cash']['atEnd']='123456'
    if change=='choices':g['choices']={'selected':None,'available':['collect','continue']}
    if change=='active':g['mandatoryFeature']=True
    if change=='hasStateType':g['hasState']='true'
    assert not classify_base_state(value,request=row['request'],previous=row['previous'])['base']

@pytest.mark.parametrize('row',[r for r in ROWS if 'nsp' in r['current']['result']['game']],ids=lambda r:r['capture'])
@pytest.mark.parametrize('change',['stakeMismatch','unknown','wild','spinning','winning'])
def test_unstaked_nsp_has_a_closed_typed_shape(row,change):
    value=copy.deepcopy(row['current']);nsp=value['result']['game']['nsp']
    if change=='stakeMismatch':nsp['stake']='1000'
    if change=='unknown':nsp['unknown']={'active':True}
    if change=='wild':nsp['randomWildOverlay']=[{'reel':0}]
    if change=='spinning':nsp.setdefault('spinning',{})['pending']=True
    if change=='winning':nsp['winning']='1000'
    assert not classify_base_state(value,request=row['request'],previous=row['previous'])['base']


@pytest.mark.parametrize('row',[r for r in ROWS if 'respin' in r['current']['result']['game']],ids=lambda r:r['capture'])
@pytest.mark.parametrize('change',['nestedChoice','nestedActive','nestedState','isLast','unknownStateType'])
def test_inline_history_keeps_nested_control_checks(row,change):
    value=copy.deepcopy(row['current']);frame=value['result']['game']['respin'][0]
    if change=='nestedChoice':frame['choices']={'selected':None,'available':['pick']}
    if change=='nestedActive':frame['mandatoryFeature']=True
    if change=='nestedState':frame['hasState']=True
    if change=='isLast':frame['isLast']=False
    if change=='unknownStateType':value['result']['game']['hasState']=None
    assert not classify_base_state(value,request=row['request'],previous=row['previous'])['base']
