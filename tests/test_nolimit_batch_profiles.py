import json,copy
from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger

ROWS=json.loads((Path(__file__).parent/'fixtures/nolimit_batch_base_responses.json').read_text())

@pytest.mark.parametrize('row',ROWS)
def test_recorded_catalog_or_missing_available_is_not_a_pending_choice(row):
 mode={'kind':'SPIN','stake':str(row['answer']['game']['playedBetValue']),'price_multiplier':'1',
       'declared_feature_options':row['declared'],'declared_feature_categories':row['categories'],'declared_purchase_options':[value for value in row['declared'] if value in row['purchase']]}
 assert RoundLedger(row['before'],mode).accept(row['answer'])

@pytest.mark.parametrize('row',ROWS)
def test_unknown_available_and_nonempty_unlearned_active_remain_blocked(row):
 mode={'kind':'SPIN','stake':'0.20','price_multiplier':'1','declared_feature_options':row['declared'],'declared_feature_categories':row['categories'],'declared_purchase_options':[value for value in row['declared'] if value in row['purchase']]}
 for features in ({'available':['NEW_CHOICE']},{'active':'NEW_CHOICE'}):
  answer=copy.deepcopy(row['answer']);answer['features']=features
  with pytest.raises(ValueError):RoundLedger(row['before'],mode).accept(answer)


def test_known_active_free_spin_category_matches_the_reported_phase():
 from tester_spin.providers.nolimit_city.runtime import normalized_response
 answer=copy.deepcopy(ROWS[2]['answer']);answer['features']['active']='FREESPIN'
 answer['game'].update(nextMode='FREESPIN',freespinsLeft=3,wasFeatureBuy=True)
 result=normalized_response(answer,ROWS[2]['declared'],ROWS[2]['categories'],ROWS[2]['purchase'])
 assert result['features']['available']==[] and result['features']['active']=='FREESPIN'
 answer['game']['nextMode']='NORMAL';answer['game']['freespinsLeft']=0
 with pytest.raises(ValueError):normalized_response(answer,ROWS[2]['declared'],ROWS[2]['categories'],ROWS[2]['purchase'])

def test_avalanche_requires_pending_win_and_recorded_state_shape():
 from tester_spin.providers.nolimit_city.runtime import continuation
 answer=copy.deepcopy(ROWS[0]['answer'])
 answer['game'].update(nextMode='FREESPIN_AVALANCHE',thisSpinWinning=.1,totalSpinWinnings=.1,accumulatedRoundWin=.1)
 answer['game']['reelsAfterCollapse']=[[1]];answer['pendingWin']=True
 assert continuation(answer)=={'type':'zeroBet','bet':'0.00'}
 answer['pendingWin']=False
 with pytest.raises(ValueError):continuation(answer)


PHASES=json.loads((Path(__file__).parent/'fixtures/nolimit_pending_phases.json').read_text())

@pytest.mark.parametrize('phase',PHASES[:2])
def test_captured_zero_charge_pending_phases_have_a_continuation(phase):
 from tester_spin.providers.nolimit_city.runtime import continuation
 assert continuation(phase['answer'],declared_options=phase['declared'],declared_purchase_options=phase['purchase'])=={'type':'zeroBet','bet':'0.00'}


def test_avalanche_respin_does_not_infer_an_explicit_no_extra_spin_ack():
 from tester_spin.providers.nolimit_city.runtime import continuation
 answer=copy.deepcopy(ROWS[0]['answer'])
 answer['game'].update(nextMode='NORMAL_AVALANCHE_RESPIN',extraSpinCost=0,reelsAfterCollapse=[[1]])
 with pytest.raises(ValueError):continuation(answer)
 answer['game']['wasExtraSpin']=False
 assert continuation(answer)=={'type':'zeroBet','bet':'0.00'}
