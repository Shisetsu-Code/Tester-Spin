import copy
import json
from pathlib import Path
import pytest
from tester_spin.providers.redtiger.base_state import classify_base_state
ROWS=json.loads(Path(__file__).with_name('fixtures').joinpath('redtiger_nsp_winners_20261016.json').read_text(encoding='utf-8'))

@pytest.mark.parametrize('row',ROWS,ids=lambda r:r['capture'])
def test_settled_nsp_line_multipliers_are_separate_from_total_stake_units(row):
    proof=classify_base_state(row['current'],request=row['request'],previous=row['previous'])
    assert proof['base'],proof

@pytest.mark.parametrize('row',ROWS,ids=lambda r:r['capture'])
@pytest.mark.parametrize('change',['lineSum','rootPayout','nspPayout','unknownLine','nestedChoice','active','lineType','cellsType','countType','negativeWin','ledger','stake','round'])
def test_winner_shape_and_ledger_must_all_be_proven(row,change):
    value=copy.deepcopy(row['current']);g=value['result']['game'];nsp=g['nsp'];line=nsp['lines'][0]
    if change=='lineSum':line['winMul']+=1
    if change=='rootPayout':g['win']['winMul']=1000
    if change=='nspPayout':nsp['winning']='1000'
    if change=='unknownLine':line['unknown']={'foo':1}
    if change=='nestedChoice':line['choices']={'selected':None,'available':['pick']}
    if change=='active':line['mandatoryFeature']=True
    if change=='lineType':nsp['lines']=[5]
    if change=='cellsType':line['cells']=[1,1,1]
    if change=='countType':line['winCount']=True
    if change=='negativeWin':line['winMul']=-1
    if change=='ledger':value['result']['user']['balance']['cash']['afterBet']='0'
    if change=='stake':nsp['stake']='1000'
    if change=='round':value['result']['transactions']['roundId']=row['previous']['result']['transactions']['roundId']
    assert not classify_base_state(value,request=row['request'],previous=row['previous'])['base']
