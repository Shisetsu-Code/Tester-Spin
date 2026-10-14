import json,copy
from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.state import initial_state,feature_observation
ROWS=json.loads((Path(__file__).parent/'fixtures/nolimit_initial_states.json').read_text())
@pytest.mark.parametrize('row',ROWS)
def test_fresh_initial_state_is_independent_of_money_dialect(row):
 init=row['init'];game=init['game']
 if game.get('isRestoreState') is False and game.get('mode')=='NORMAL' and game.get('nextMode')=='NORMAL' and init['remainingFreeSpins']==0:
  assert initial_state(init)['state']=='IDLE'
def test_restored_or_pending_round_is_never_idle():
 init=next(copy.deepcopy(r['init']) for r in ROWS if r['init']['game'].get('isRestoreState') is False)
 for change in ({'isRestoreState':True},{'freespinsLeft':1},{'respinsLeft':1},{'secondStageFsLeft':1},{'wasFeatureBuy':True},{'nextMode':'PICK'}):
  bad=copy.deepcopy(init);bad['game'].update(change)
  with pytest.raises(ValueError):initial_state(bad)
def test_catalog_phase_and_unknown_menu_are_separate_observations():
 catalog=['FREE','SUPER']
 root={'game':{'mode':'NORMAL','nextMode':'NORMAL'},'features':{'available':catalog}}
 assert feature_observation(root,catalog,('NORMAL','FREE'))['kind']=='CATALOG'
 root['features']['available']=['NEW_CHOICE']
 assert feature_observation(root,catalog,('NORMAL','FREE'))['kind']=='UNRESOLVED_MENU'
 root={'game':{'mode':'FREE','nextMode':'FREE'},'features':{'active':'FREE'}}
 assert feature_observation(root,catalog,('NORMAL','FREE'))['kind']=='PHASE'
 root['features']['active']='UNKNOWN'
 assert feature_observation(root,catalog,('NORMAL','FREE'))['kind']=='UNRESOLVED_PHASE'

def test_monetary_fields_do_not_depend_on_feature_catalog_or_counter_spelling():
 from tester_spin.providers.nolimit_city.operation_fields import step_win,modifier_ack,root_ack
 assert step_win({'thisSpinWinning':0,'totalSpinWinnings':15})==0
 assert modifier_ack({'enhancedBet':2}) is True
 assert modifier_ack({'wasFeatureBuy':False}) is None
 with pytest.raises(ValueError):step_win({'win':1,'thisSpinWinning':2})
 with pytest.raises(ValueError):modifier_ack({'enhancedBet':False,'boostedBet':True})
 root_ack({}, {'kind':'SPIN','stake':'0.20'}, {'type':'normalBet','bet':'0.20'})
 with pytest.raises(ValueError):root_ack({}, {'kind':'SPIN','stake':'0.20'}, None)
 with pytest.raises(ValueError):root_ack({'wasFeatureBuy':True},{'kind':'SPIN','stake':'0.20'},{'type':'normalBet','bet':'0.20'})

def test_settlement_uses_explicit_counters_and_never_unknown_or_pending_values():
 from tester_spin.providers.nolimit_city.state import settled_state
 root={'game':{'nextMode':'NORMAL'},'features':{'available':[]},'remainingFreeSpins':0}
 assert settled_state(root)
 for value in (1,False,'0',None):
  bad=copy.deepcopy(root);bad['game']['respinsLeft']=value
  assert not settled_state(bad)
 bad=copy.deepcopy(root);bad['pendingWin']=True
 assert not settled_state(bad)
 root.pop('remainingFreeSpins');assert not settled_state(root)
def test_total_only_step_requires_round_accumulation_and_never_invents_a_discount():
 from decimal import Decimal
 from tester_spin.providers.nolimit_city.operation_fields import reconciled_step_win
 assert reconciled_step_win({'totalSpinWinnings':5,'accumulatedRoundWin':15},Decimal('10'))=='5'
 assert reconciled_step_win({'totalSpinWinnings':15,'accumulatedRoundWin':15},Decimal('10'))=='5'
 for total,accumulated in ((7,15),(5,9),(True,15),(5,None)):
  with pytest.raises(ValueError):reconciled_step_win({'totalSpinWinnings':total,'accumulatedRoundWin':accumulated},Decimal('10'))

def test_unresolved_active_phase_blocks_automatic_zero_bet_even_in_free_mode():
 from tester_spin.providers.nolimit_city.runtime import continuation
 answer={'game':{'win':0,'accumulatedRoundWin':0,'playedBetValue':1,'mode':'FREESPIN','nextMode':'FREESPIN','freespinsLeft':2},'features':{'available':[],'active':'CHOOSE'}}
 with pytest.raises(ValueError):continuation(answer,declared_catalog=[],declared_game_modes=['NORMAL','FREESPIN'])
def test_runtime_initial_gate_never_bypasses_active_flags_with_empty_catalog():
 from tester_spin.providers.nolimit_city.runtime import require_idle_initial_state
 init={'init':'ok','game':{'isRestoreState':False,'mode':'NORMAL','nextMode':'NORMAL','freespinsLeft':0,'wasFeatureBuy':True},'remainingFreeSpins':0,'features':{'available':[]}}
 with pytest.raises(ValueError):require_idle_initial_state(init)
 init['game']['wasFeatureBuy']=False;init['game'].pop('isRestoreState')
 with pytest.raises(ValueError):require_idle_initial_state(init)

def test_collect_operation_is_independent_of_rows_but_requires_server_ack():
 from decimal import Decimal
 from tester_spin.providers.nolimit_city.runtime import RoundLedger
 mode={'kind':'SPIN','stake':'1','price_multiplier':'1','declared_feature_catalog':[],'declared_game_modes':['NORMAL','GAMBLE']}
 ledger=RoundLedger('100',mode)
 root={'game':{'playedBetValue':1,'win':5,'accumulatedRoundWin':5,'mode':'NORMAL','nextMode':'GAMBLE','gambleCollect':False,'gambleOptions':{}},'features':{'available':[]},'balance':'99'}
 assert not ledger.accept(root,request={'type':'normalBet','bet':'1'})
 final={'game':{'win':0,'accumulatedRoundWin':5,'mode':'GAMBLE','nextMode':'NORMAL','gambleCollect':True},'features':{'available':[]},'remainingFreeSpins':0,'balance':'104'}
 for req in (None,{'type':'zeroBet','bet':'0.00'}):
  with pytest.raises(ValueError):copy.deepcopy(ledger).accept(final,request=req)
 assert ledger.accept(final,request={'type':'gambleBet','bet':'0.00','playerInteraction':{'gambleCollected':True}})
 assert ledger.after==Decimal('104')

def test_declared_selector_catalog_and_known_phase_do_not_need_money_signature():
 answer={'game':{'mode':'FREESPIN','nextMode':'FREESPIN'},'features':{'available':['BUY_A','BUY_B'],'active':'FREESPIN'}}
 assert feature_observation(answer,[],[],[],[['BUY_A','BUY_B']])['kind']=='PHASE'
def test_ledger_can_record_unknown_phase_but_cannot_close_or_automatically_execute_it():
 from tester_spin.providers.nolimit_city.runtime import RoundLedger,continuation
 mode={'kind':'SPIN','stake':'1','price_multiplier':'1','declared_feature_catalog':[],'declared_game_modes':[]}
 answer={'game':{'playedBetValue':1,'win':0,'accumulatedRoundWin':0,'mode':'NORMAL','nextMode':'FREESPIN','freespinsLeft':2},'features':{'available':[],'active':'CHOOSE'},'balance':'99'}
 ledger=RoundLedger('100',mode)
 assert not ledger.accept(answer,request={'type':'normalBet','bet':'1'})
 assert not ledger.closed
 with pytest.raises(ValueError):continuation(answer,declared_catalog=[])

def test_declared_free_category_matches_known_free_phase_family_only():
 answer={'game':{'mode':'FREESPIN_BETTER','nextMode':'FREESPIN_BETTER','freespinsLeft':3},'features':{'active':'FREESPIN','available':['FREESPIN']}}
 assert feature_observation(answer,['FREESPIN'],[],['FREESPIN'])['kind']=='PHASE'
 answer['game']['nextMode']='CHOOSE';assert feature_observation(answer,['FREESPIN'],[],['FREESPIN'])['kind']=='UNRESOLVED_PHASE'

def test_known_purchase_remains_detected_when_its_additional_mechanic_is_not_executable():
 from tester_spin.providers.nolimit_city.runtime import declaration
 init=json.loads((Path(__file__).parent/'fixtures/nolimit_rows_init.json').read_text());init['game']['featureBuyTimesBetValue'][0]['additionalTypes']=['NEW_MECHANIC']
 modes,domains=declaration(init)
 mode=next(m for m in modes if m.get('selector')=='FREESPIN_3_ROWS')
 assert mode['kind']=='PURCHASE' and not mode['executable']
 assert mode['execution_blocker']=='UNSUPPORTED_ADDITIONAL_TYPES'
 assert domains['purchase']['complete'] and len(domains['purchase']['options'])==3
def test_known_phase_observation_with_zero_free_spins_never_grants_auto_continue():
 from tester_spin.providers.nolimit_city.runtime import continuation
 answer={'game':{'win':0,'accumulatedRoundWin':10,'playedBetValue':1,'mode':'FREESPIN_BETTER','nextMode':'FREESPIN_BETTER','freespinsLeft':0},'features':{'available':['FREESPIN'],'active':'FREESPIN'}}
 with pytest.raises(ValueError):continuation(answer,declared_catalog=['FREESPIN'],declared_purchase_options=['FREESPIN'])

def test_offline_har_and_live_executor_share_the_same_collect_ledger():
 from tester_spin.providers.nolimit_city.protocol import analyze_messages
 init=json.loads((Path(__file__).parent/'fixtures/nolimit_rows_init.json').read_text())
 pairs=json.loads((Path(__file__).parent/'fixtures/nolimit_rows_collect.json').read_text())
 init['id']='init';rows=[{'direction':'sent','message':{'id':'init','type':'init'}},{'direction':'received','message':init}]
 for n,pair in enumerate(pairs):
  identifier=str(n);answer={**pair['answer'],'id':identifier}
  rows.extend([{'direction':'sent','message':{'id':identifier,'type':'normal','content':pair['request']}},{'direction':'received','message':answer}])
 report=analyze_messages(rows)
 assert report['paid_rounds']==report['closed_rounds']==1
 assert len(report['domains']['purchase']['options'])==3
 assert len(report['domains']['boosted_bet']['options'])==2
 assert report['final_balance']==str(pairs[-1]['answer']['balance'])
 assert not report['ok_certified']

def test_unknown_money_alias_is_partial_evidence_not_an_invented_zero_win():
 from tester_spin.providers.nolimit_city.runtime import RoundLedger,Unlearned
 mode={'kind':'SPIN','stake':'1','price_multiplier':'1','declared_feature_catalog':[]}
 answer={'game':{'totalBetWayWinnings':0,'playedBetValue':1,'accumulatedRoundWin':0,'mode':'NORMAL','nextMode':'NORMAL','freespinsLeft':0},'features':{},'balance':'99'}
 with pytest.raises(Unlearned):RoundLedger('100',mode).accept(answer,request={'type':'normalBet','bet':'1'})

@pytest.mark.parametrize('phase,extra',[
 ('STACKED_RESPIN_FREESPIN',{'pendingWin':True,'stackedSpinTriggered':True,'freespinsLeft':3}),
 ('NORMAL_AVALANCHE',{'pendingWin':True,'symbolsAfterTumbleForClient':[['X']]}),
 ('RESPIN',{'respinsLeft':2}),('FREESPIN_MINIGAME',{'freespinsLeft':2})])
def test_automatic_operation_does_not_require_a_monetary_dialect_signature(phase,extra):
 from tester_spin.providers.nolimit_city.runtime import continuation
 game={'win':1,'accumulatedRoundWin':1,'mode':'NORMAL','nextMode':phase}
 pending=extra.pop('pendingWin',None);game.update(extra)
 answer={'game':game,'features':{}}
 if pending is not None:answer['pendingWin']=pending
 assert continuation(answer,declared_catalog=[])=={'type':'zeroBet','bet':'0.00'}
def test_canonical_extra_false_does_not_replace_explicit_raw_no_extra_evidence():
 from tester_spin.providers.nolimit_city.runtime import continuation
 raw={'game':{'win':1,'mode':'NORMAL','nextMode':'NORMAL_AVALANCHE_RESPIN','extraSpinCost':0,'reelsAfterCollapse':[['X']]},'features':{}}
 canonical=copy.deepcopy(raw);canonical['game']['wasExtraSpin']=False
 with pytest.raises(ValueError):continuation(canonical,raw_answer=raw,declared_catalog=[])

def test_respin_with_a_quoted_extra_cost_is_not_an_automatic_free_operation():
 from tester_spin.providers.nolimit_city.runtime import continuation
 answer={'game':{'win':1,'mode':'NORMAL','nextMode':'RESPIN','respinsLeft':1,'extraSpinCost':10},'features':{}}
 with pytest.raises(ValueError):continuation(answer,declared_catalog=[])

def test_exported_selection_template_is_bound_to_its_request_field(tmp_path):
 from tester_spin.providers.nolimit_city.adapter import SPEC,NolimitCityProvider
 contract={'modes':[{'options':{'choice_domains':[{'request_field':'gambleCollected','options':[True],'covered':[True]}]}}], 'protocol':{'static':copy.deepcopy(SPEC.protocol_static)}}
 provider=NolimitCityProvider(tmp_path)
 assert 'NOLIMIT_CHOICE_FIELD_PRIMITIVE_REQUIRED' not in provider.validate_farm_contract(contract)
 contract['protocol']['static']['selection_primitives']['gambleCollected']=SPEC.protocol_static['selection_primitives']['selectedIndex']
 assert 'NOLIMIT_CHOICE_FIELD_PRIMITIVE_REQUIRED' in provider.validate_farm_contract(contract)
