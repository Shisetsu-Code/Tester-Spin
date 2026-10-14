import json,copy
from pathlib import Path
from decimal import Decimal
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger,continuation
ROWS=json.loads((Path(__file__).parent/'fixtures/nolimit_level_avalanche.json').read_text())
PRICES={'FREESPIN':66,'FREESPIN_LEVEL3':166,'FREESPIN_LEVEL5':55,'SUPER_FREESPIN':500}
def test_captured_level_rounds_and_avalanches_reconcile():
 before=Decimal('10000');ledger=None;closed=0
 for row in ROWS:
  req=row['request'];answer=row['answer']
  if req['type']!='zeroBet':
   assert ledger is None
   sel=req.get('featureName');ledger=RoundLedger(before,{'kind':'PURCHASE' if sel else 'SPIN','stake':req['bet'],'price_multiplier':str(PRICES.get(sel,1)),'declared_purchase_options':list(PRICES)})
  if ledger.accept(answer,request=req):before=ledger.after;ledger=None;closed+=1
  else:assert continuation(answer,declared_purchase_options=list(PRICES))=={'type':'zeroBet','bet':'0.00'}
 assert ledger is None and closed==11
 assert before==Decimal(str(ROWS[-1]['answer']['balance']))
def test_undeclared_phase_or_non_pending_avalanche_is_not_automatic():
 answer=copy.deepcopy(next(r['answer'] for r in ROWS if r['answer'].get('pendingWin') is True))
 answer['pendingWin']=False
 with pytest.raises(ValueError):continuation(answer,declared_purchase_options=list(PRICES))

@pytest.mark.parametrize('key',['respinsLeft','secondStageFsLeft'])
def test_normal_mode_with_pending_counter_is_not_closed(key):
 answer=copy.deepcopy(ROWS[0]['answer']);answer['game'][key]=1
 with pytest.raises(ValueError):RoundLedger('10000',{'kind':'SPIN','stake':'1','price_multiplier':'1'}).accept(answer)
