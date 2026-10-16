import copy
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger
from tester_spin.providers.nolimit_city.state import feature_observation

MODE={'kind':'SPIN','stake':'.20','price_multiplier':1,'server_declared':True,'declared_feature_catalog':[],
      'declared_game_modes':[],'declared_feature_options':['BASIC','STRONG','RANDOM'],
      'declared_purchase_options':['BASIC','STRONG','RANDOM'],'declared_feature_categories':['BONUS_BUY']}
ANSWER={'game':{'mode':'NORMAL','nextMode':'NORMAL','win':0,'accumulatedRoundWin':0,'playedBetValue':'.20','freespinsLeft':0},
        'features':{'available':['BASIC','STRONG']},'remainingFreeSpins':0,'balance':'9999.80'}
REQ={'type':'normalBet','bet':'.20'}

def test_subset_of_declared_purchases_is_terminal_metadata_only_after_reconciled_settlement():
    raw=copy.deepcopy(ANSWER);ledger=RoundLedger('10000',MODE)
    assert ledger.accept(raw,request=REQ)
    assert ledger.last_answer['feature_observation']['kind']=='SETTLED_CATALOG_SUBSET'
    assert raw==ANSWER
    assert feature_observation(raw,(),(),MODE['declared_purchase_options'])['kind']=='UNRESOLVED_MENU'

@pytest.mark.parametrize('change',[
    lambda a:a['features'].update(available=['BASIC','UNKNOWN']),
    lambda a:a['features'].update(available=['BASIC','BASIC']),
    lambda a:a['features'].update(active='PICK'),
    lambda a:a['game'].update(nextMode='PICK'),
    lambda a:a['game'].update(mode='UNKNOWN'),
    lambda a:a.update(pendingWin=True),
    lambda a:a['game'].update(freespinsLeft=1),
    lambda a:a['game'].update(gambleOptions={'choices':[0,1]}),
    lambda a:a.update(screens=[{'choices':[0,1]}]),
])
def test_subset_observation_does_not_hide_decisions_or_pending_counters(change):
    raw=copy.deepcopy(ANSWER);change(raw)
    assert not RoundLedger('10000',MODE).accept(raw,request=REQ)


def test_subset_requires_actual_settlement_balance():
    raw=copy.deepcopy(ANSWER);raw['balance']='9999.70'
    with pytest.raises(ValueError):RoundLedger('10000',MODE).accept(raw,request=REQ)
    raw=copy.deepcopy(ANSWER);raw.pop('balance')
    with pytest.raises(ValueError):RoundLedger('10000',MODE).accept(raw,request=REQ)


def test_ascii_blank_active_label_means_no_active_phase():
    raw=copy.deepcopy(ANSWER);raw['features']={'active':' ','available':['BASIC','STRONG','RANDOM']}
    assert RoundLedger('10000',MODE).accept(raw,request=REQ)


def test_ledger_uses_bound_integral_counter_without_reinterpreting_winnings():
    source='owner.keypadPlugin.setZeroBetSpinCounter(owner.model.data.freespinsRemaining)'
    raw=copy.deepcopy(ANSWER);raw['features']['available']=[]
    raw['game']['freespinsRemaining']=0.0;raw['game'].pop('freespinsLeft')
    ledger=RoundLedger('10000',MODE)
    assert ledger.accept(raw,request=REQ,client_source=source)
    assert type(ledger.last_answer['game']['freespinsLeft']) is int
    assert raw['game']['freespinsRemaining']==0.0


def test_existing_zero_canonical_counter_cannot_hide_pending_client_counter():
    source='owner.keypadPlugin.setZeroBetSpinCounter(owner.model.data.freespinsRemaining)'
    raw=copy.deepcopy(ANSWER);raw['features']['available']=[];raw['game']['freespinsRemaining']=1
    with pytest.raises(ValueError):RoundLedger('10000',MODE).accept(raw,request=REQ,client_source=source)
