import copy,json
from decimal import Decimal
from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger,normalized_response

ROWS=json.loads((Path(__file__).parent/'fixtures/nolimit_boosted_response.json').read_text())

@pytest.mark.parametrize('row',ROWS)
def test_captured_boosted_dialect_normal_round(row):
 mode={'kind':'SPIN','stake':row['request']['bet'],'price_multiplier':'1'}
 ledger=RoundLedger(row['before'],mode)
 assert ledger.accept(row['answer'])
 assert ledger.after==Decimal(str(row['answer']['balance']))

def test_boosted_alias_requires_boolean_and_consistent_canonical_ack():
 for change in ({'boostedBet':0},{'wasBoostedBet':True}):
  answer=copy.deepcopy(ROWS[0]['answer']);answer['game'].update(change)
  with pytest.raises(ValueError):normalized_response(answer)

def test_total_winnings_alias_cannot_override_conflicting_win():
 answer=copy.deepcopy(ROWS[-1]['answer']);answer['game'].update(win=123)
 with pytest.raises(ValueError):normalized_response(answer)

def test_pending_respin_not_certified_closed():
 answer=copy.deepcopy(ROWS[0]['answer']);answer['game']['respinsLeft']=1
 with pytest.raises(ValueError):RoundLedger(ROWS[0]['before'],{'kind':'SPIN','stake':'1','price_multiplier':'1'}).accept(answer)


def test_boosted_free_round_does_not_invent_extra_flag_or_step_win():
 answer=copy.deepcopy(ROWS[-1]['answer'])
 answer['game'].update(mode='FREESPIN',nextMode='FREESPIN',freespinsLeft=2,freespinsPlayed=1)
 answer['game'].pop('freespinsPlayed')
 normalized=normalized_response(answer)
 assert 'win' not in normalized['game'] and 'wasExtraSpin' not in normalized['game']
 with pytest.raises(ValueError):RoundLedger(ROWS[-1]['before'],{'kind':'SPIN','stake':'1','price_multiplier':'1'}).accept(answer)
