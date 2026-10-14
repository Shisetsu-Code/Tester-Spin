import json,copy
from pathlib import Path
from decimal import Decimal
import pytest
from tester_spin.providers.nolimit_city.runtime import declaration,RoundLedger,continuation,require_idle_initial_state
from tester_spin.providers.nolimit_city.choices import choice_domain,confirm_choice
FIX=Path(__file__).parent/'fixtures'
INIT=json.loads((FIX/'nolimit_rows_init.json').read_text())
ROWS=json.loads((FIX/'nolimit_rows_collect.json').read_text())
def test_rows_server_declares_three_purchases_and_two_boosts():
 modes,domains=declaration(INIT)
 assert domains['purchase']['complete'] and len(domains['purchase']['options'])==3
 assert len(domains['feature_spin']['options'])==2
 assert all(m['executable'] for m in modes)
def test_captured_purchase_preset_choice_and_collect_reconcile():
 mode=next(m for m in declaration(INIT)[0] if m.get('selector')=='FREESPIN_3_ROWS')
 mode=copy.deepcopy(mode);mode['stake']=ROWS[0]['request']['bet']
 ledger=RoundLedger('10000',mode)
 for row in ROWS:ledger.accept(row['answer'],request=row['request'])
 assert ledger.closed and ledger.after==Decimal(str(ROWS[-1]['answer']['balance']))
 assert continuation(ROWS[0]['answer'],declared_purchase_options=mode['declared_purchase_options'])=={'type':'zeroBet','bet':'0.00'}
def test_collect_requires_explicit_request_and_server_ack():
 mode=next(m for m in declaration(INIT)[0] if m.get('selector')=='FREESPIN_3_ROWS')
 mode=copy.deepcopy(mode);mode['stake']=ROWS[0]['request']['bet']
 ledger=RoundLedger('10000',mode)
 for row in ROWS[:-1]:ledger.accept(row['answer'],request=row['request'])
 with pytest.raises(ValueError):ledger.accept(ROWS[-1]['answer'])
 bad=copy.deepcopy(ROWS[-1]['answer']);bad['game']['gambleCollect']=False
 with pytest.raises(ValueError):ledger.accept(bad,request=ROWS[-1]['request'])
def test_static_literal_row_options_use_server_player_selection_ack():
 source='bonusGame:{options:[{name:"a",id:1},{name:"b",id:2},{name:"c",id:3}],type:s.ASBonusPickOptions.PICK_MODE,pickNeededForModes:[m.FREESPIN_PICK]}'
 domain=choice_domain(source,{'game':{'nextMode':'FREESPIN_PICK','playerSelection':-1}})
 assert domain['options']==[1,2,3] and domain['ack_field']=='playerSelection'
 confirm_choice(domain,2,{'game':{'playerSelection':2}})
 with pytest.raises(ValueError):confirm_choice(domain,2,{'game':{'playerSelection':1}})

def test_classified_selector_retires_unknown_obligation_only_after_same_quote_proof():
 from types import SimpleNamespace
 from tester_spin.coverage_history import _archive_classified_selector_replacements
 old={'kind':'UNKNOWN_FEATURE','selector':'a','server_type':'BOOSTED_BET_X_ROWS','stake':'0.10','price_multiplier':'1.5','required_options':['a']}
 mode={**old,'id':'BOOST_a','kind':'FEATURE_SPIN','validated':True,'observed':True,'evidence_level':'REMOTE_EXECUTION','monetary_contract':'nolimit-city/round-ledger/v1','sample_counts':{'a':1}}
 for field,value in (('validated',False),('price_multiplier','2'),('stake','0.20')):
  pending={'UNKNOWN_a':copy.deepcopy(old)};bad={**mode,field:value}
  _archive_classified_selector_replacements(pending,SimpleNamespace(provider='nolimit_city',discovered_modes=[bad]),[], 'test')
  assert pending
 pending={'UNKNOWN_a':copy.deepcopy(old)};migrations=[]
 _archive_classified_selector_replacements(pending,SimpleNamespace(provider='nolimit_city',discovered_modes=[mode]),migrations,'test')
 assert not pending and len(migrations)==1

def test_collect_contract_binds_same_parameter_to_zero_stake_request():
 from tester_spin.providers.nolimit_city.choices import has_collect_contract
 call='collectWin(){return"GAMBLE"!==this._nextMode?Promise.resolve(!1):(this.gambleBet(!0),this.ready())}'
 method='gambleBet(t,e,i,n=!1){const o={};null!=e&&(o.gambleOption=e),null!=i&&(o.gambleSelection=i),o.gambleCollected=t;const a={type:s.APIBetType.GAMBLE_BET,bet:"0.00",playerInteraction:o};n&&(a.playerInteraction.actionSpin=!0),this.sendRequest(a)}'
 assert has_collect_contract(call+method)
 for bad in (call+'other(){gambleCollected=true}',call+method.replace('gambleCollected=t','gambleCollected=e'),call+method.replace('bet:"0.00"','bet:"1.00"')):
  assert not has_collect_contract(bad)
