import json,copy
from pathlib import Path
from decimal import Decimal
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger,continuation,normalized_response,Unlearned

ROWS=json.loads((Path(__file__).parent/'fixtures/nolimit_extra_spin.json').read_text())
PRICES={'BOOSTED_BET':2,'BOOSTED_BET_BONUS_HUNT':30,'COIN_SPIN_FEATURE':200,'FREESPIN':120,'SUPER_FREESPIN':400,'LUCKY_DRAW':190}

def test_captured_rounds_reconcile_extra_cost_and_all_settlements():
 before=Decimal('10000');ledger=None;closed=0
 for row in ROWS:
  req=row['request']
  if req['type']!='zeroBet':
   assert ledger is None
   selector=req.get('featureName')
   ledger=RoundLedger(before,{'kind':'SPIN' if selector is None else 'FEATURE_SPIN' if selector.startswith('BOOSTED_BET') else 'PURCHASE','stake':req['bet'],'price_multiplier':str(PRICES.get(selector,1))})
  if ledger.accept(row['answer'],request=req):before=ledger.after;ledger=None;closed+=1
 assert ledger is None and closed==19 and before==Decimal('11482.45')

@pytest.mark.parametrize('phase',['FREESPIN_TRIGGER','COIN_SPIN'])
def test_captured_zero_cost_phases_continue(phase):
 answer=next(r['answer'] for r in ROWS if r['answer']['game']['nextMode']==phase)
 assert continuation(answer)=={'type':'zeroBet','bet':'0.00'}
 answer=copy.deepcopy(answer);answer['game']['isExtraSpin']=True
 with pytest.raises(ValueError):continuation(answer)

def test_missing_request_or_wrong_extra_cost_never_accepts_negative_win():
 ledger=None
 for row in ROWS:
  req=row['request']
  if ledger is None:ledger=RoundLedger('9998',{'kind':'PURCHASE','stake':'1','price_multiplier':'400'})
  if req.get('featureName')=='SUPER_FREESPIN':started=True
  elif 'started' not in locals():continue
  if (req.get('playerInteraction')or{}).get('playExtraSpin')=='yes':
   for request in (None,{'type':'zeroBet','bet':'0.00','playerInteraction':{'playExtraSpin':'no'}}):
    with pytest.raises(ValueError):copy.deepcopy(ledger).accept(row['answer'],request=request)
   bad=copy.deepcopy(row['answer']);bad['game']['win']=-39
   with pytest.raises(ValueError):copy.deepcopy(ledger).accept(bad,request=req)
   break
  ledger.accept(row['answer'],request=req)


def test_extra_selection_exports_correct_template_and_requires_monetary_rule(tmp_path):
 from tester_spin.providers.nolimit_city.adapter import SPEC,NolimitCityProvider
 contract={'modes':[{'options':{'choice_domains':[{'request_field':'playExtraSpin','options':['yes','no'],'covered':['yes','no']}]}}],
   'protocol':{'static':copy.deepcopy(SPEC.protocol_static)}}
 provider=NolimitCityProvider(tmp_path)
 assert 'NOLIMIT_EXTRA_SPIN_CONTRACT_REQUIRED' not in provider.validate_farm_contract(contract)
 for key in ('extra_spin_selection_primitive','extra_spin_monetary_contract'):
  bad=copy.deepcopy(contract);bad['protocol']['static'].pop(key)
  assert 'NOLIMIT_EXTRA_SPIN_CONTRACT_REQUIRED' in provider.validate_farm_contract(bad)

def test_extra_choice_uses_client_declared_yes_no_and_tracks_coverage(tmp_path):
 from tester_spin.providers.nolimit_city.runtime import NolimitSession
 session=NolimitSession();session.choice_client='a.zeroBet({playExtraSpin:"yes"});a.zeroBet({playExtraSpin:"no"})'
 prompt=next(r['answer'] for r in ROWS if r['answer']['game']['nextMode']=='EXTRA_SPIN')
 session.begin_round('root')
 no=session.choice_command(prompt,tmp_path,'root')
 assert no['playerInteraction']=={'playExtraSpin':'no'}
 answer=next(r['answer'] for r in ROWS if (r['request'].get('playerInteraction')or{}).get('playExtraSpin')=='no')
 session.confirm_pending_choice(answer);session.finish_round('root')
 assert not session.sync_choices({'id':'root'})
 session.begin_round('root')
 yes=session.choice_command(prompt,tmp_path,'root')
 assert yes['playerInteraction']=={'playExtraSpin':'yes'}
 answer=next(r['answer'] for r in ROWS if (r['request'].get('playerInteraction')or{}).get('playExtraSpin')=='yes')
 session.confirm_pending_choice(answer)
 assert not session.sync_choices({'id':'root'})
 session.finish_round('root')
 assert session.sync_choices({'id':'root'})
 session.choice_client='a.zeroBet({playExtraSpin:"yes"})'
 with pytest.raises(ValueError):session.choice_command(prompt,tmp_path,'other')
