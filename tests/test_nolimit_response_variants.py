import copy,json
from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.runtime import declaration,RoundLedger,continuation

ROWS=json.loads((Path(__file__).parent/'fixtures/nolimit_legacy_response.json').read_text(encoding='utf-8'))

def test_captured_legacy_response_rounds_are_paid_and_closed_without_choices():
 init=ROWS[1]['message'];modes,_=declaration(init)
 by_selector={m.get('selector'):m for m in modes};before=init['balance'];ledger=None;roots=closed=0
 for request_row,response_row in zip(ROWS[2::2],ROWS[3::2]):
  request=request_row['message']['content'];response=response_row['message']
  if request['type']!='zeroBet':
   assert ledger is None
   mode=copy.deepcopy(by_selector[request.get('featureName')]);mode['stake']=request['bet']
   domain=init['featureBetLevels'][request['featureName']] if request.get('featureName') else init['betLevels']['availableBetLevels']
   assert float(request['bet']) in [float(value) for value in domain]
   ledger=RoundLedger(before,mode);roots+=1
  else:assert request==continuation(previous,declared_options=init['allowedFeatureBets'])
  terminal=ledger.accept(response)
  if terminal:before=str(ledger.after);ledger=None;closed+=1
  previous=response
 assert roots==closed==37 and ledger is None

def test_unknown_available_option_cannot_be_treated_as_catalog():
 init=ROWS[1]['message'];modes,_=declaration(init);modes[0]['stake']='1.00'
 answer=copy.deepcopy(ROWS[3]['message']);answer['features']['available'].append('NEW_CHOICE')
 with pytest.raises(ValueError):RoundLedger(init['balance'],modes[0]).accept(answer)

def test_conflicting_boost_ack_and_win_fields_are_rejected():
 init=ROWS[1]['message'];modes,_=declaration(init);modes[0]['stake']='1.00'
 for change in ({'wasBoostedBet':True},{'win':99}):
  answer=copy.deepcopy(ROWS[3]['message']);answer['game'].update(change)
  with pytest.raises(ValueError):RoundLedger(init['balance'],modes[0]).accept(answer)

def test_unrecognised_missing_flags_are_not_assumed_false():
 init=ROWS[1]['message'];modes,_=declaration(init);modes[0]['stake']='1.00'
 answer=copy.deepcopy(ROWS[3]['message']);answer['game'].pop('enhancedBet')
 with pytest.raises(ValueError):RoundLedger(init['balance'],modes[0]).accept(answer)

def test_declared_catalog_recognition_is_independent_of_monetary_dialect():
 init=ROWS[1]['message'];modes,_=declaration(init);modes[0]['stake']='1.00'
 answer=copy.deepcopy(ROWS[3]['message']);game=answer['game']
 for key in ('thisSpinWinning','totalSpinWinnings','enhancedBet','featureName','firstStage','secondStage','secondStageFsLeft'):game.pop(key,None)
 game.update(win=0,wasBoostedBet=False,wasExtraSpin=False)
 ledger=RoundLedger(init['balance'],modes[0]);ledger.accept(answer)
 assert ledger.closed

def test_unknown_second_stage_counter_never_becomes_terminal():
 init=ROWS[1]['message'];modes,_=declaration(init);modes[0]['stake']='1.00'
 answer=copy.deepcopy(ROWS[3]['message']);answer['game']['secondStageFsLeft']=1
 with pytest.raises(ValueError):RoundLedger(init['balance'],modes[0]).accept(answer)
