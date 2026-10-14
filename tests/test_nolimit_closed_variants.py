import copy,json
from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.runtime import declaration,RoundLedger,continuation,require_idle_initial_state

CAPTURES=json.loads((Path(__file__).parent/'fixtures/nolimit_closed_variants.json').read_text())

@pytest.mark.parametrize('capture',CAPTURES)
def test_complete_captured_dialects_close_all_declared_options(capture):
 init=capture['init'];modes,_=declaration(init);mapping={m.get('selector'):m for m in modes}
 before=init['balance'];ledger=None;observed=set();consecutive=0
 for row in capture['rows']:
  command=row['command'];answer=row['answer']
  if command['type']!='zeroBet':
   assert ledger is None
   mode=mapping[command.get('featureName')];assert command==mode['request_shape']
   ledger=RoundLedger(before,mode);observed.add(command.get('featureName'))
  else:assert command==continuation(previous,declared_options=init['allowedFeatureBets'])
  done=ledger.accept(answer)
  if done:
   before=str(ledger.after)
   consecutive=consecutive+1 if ledger.mode['kind']=='SPIN' and not ledger.had_feature else 0
   ledger=None
  previous=answer
 assert ledger is None and observed=={None,*init['allowedFeatureBets']} and consecutive>=2

def test_category_init_requires_fresh_idle_signature():
 for patch in ({'isRestoreState':True},{'freespinsLeft':1},{'freespinTriggeredThisSpin':True},{'numberOfFreespinsPlayed':1}):
  init=copy.deepcopy(CAPTURES[0]['init']);init['game'].update(patch)
  with pytest.raises(ValueError):require_idle_initial_state(init)

def test_category_response_does_not_discard_unrecognised_choices():
 init=CAPTURES[0]['init'];modes,_=declaration(init)
 answer=copy.deepcopy(CAPTURES[0]['rows'][0]['answer']);answer['features']['available'].append('CHOOSE')
 with pytest.raises(ValueError):RoundLedger(init['balance'],modes[0]).accept(answer)

def test_explicit_extra_spin_is_never_ignored_in_new_dialects():
 for capture in CAPTURES:
  modes,_=declaration(capture['init']);answer=copy.deepcopy(capture['rows'][0]['answer'])
  answer['game']['wasExtraSpin']=True
  with pytest.raises(ValueError):RoundLedger(capture['init']['balance'],modes[0]).accept(answer)


def test_pending_respin_requires_positive_integer_counter():
 answer=copy.deepcopy(CAPTURES[1]['rows'][0]['answer'])
 answer['game']['nextMode']='RESPIN'
 for value in (None,0,True,-1):
  answer['game']['respinsLeft']=value
  with pytest.raises(ValueError):continuation(answer)

def test_category_feature_bet_without_purchase_ack_is_not_normal():
 init=CAPTURES[0]['init'];modes,_=declaration(init)
 answer=copy.deepcopy(CAPTURES[0]['rows'][0]['answer']);answer['game']['featureBet']=True
 with pytest.raises(ValueError):RoundLedger(init['balance'],modes[0]).accept(answer)
