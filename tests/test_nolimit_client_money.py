import json
from decimal import Decimal
from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.operation_fields import step_win, reconciled_step_win

CASES=json.loads((Path(__file__).parent/'fixtures/nolimit_client_money.json').read_text())

@pytest.mark.parametrize('case',CASES,ids=lambda case:case['reference'])
def test_current_client_getter_binds_independent_round_and_spin_observations(case):
    from tester_spin.providers.nolimit_city.client_money import monetary_fields
    fields=monetary_fields(case['source'])
    assert fields is not None
    for event in case['events']:
        game=event['game']
        assert Decimal(str(step_win(game,client_source=case['source'])))==Decimal(str(game[fields['spin']]))
        assert Decimal(reconciled_step_win(game,Decimal(0),client_source=case['source']))==Decimal(str(game[fields['round']]))


def test_border_base_win_does_not_replace_client_declared_total_spin_win():
    case=next(c for c in CASES if c['reference']=='theborder')
    game=case['events'][-1]['game']
    assert game['thisSpinWinnings']==0
    assert step_win(game,client_source=case['source'])==.08
    assert reconciled_step_win(game,Decimal(0),client_source=case['source'])=='0.08'


@pytest.mark.parametrize('change',[
    lambda s:s.replace('return t.totalSpinWin','return t.allowed?t.totalSpinWin:0'),
    lambda s:s.replace('getWin(t,e,i){return t.totalSpinWin}','getWin(t,e,i){const cb=()=>t.totalSpinWin;return 0}'),
    lambda s:s.replace('this.getWin(t,e,i)','this.unknown(t,e,i)'),
    lambda s:s.replace('totalWin:t.totalRoundWin','totalWin:this.history.totalRoundWin'),
])
def test_unproved_or_history_based_monetary_getter_is_rejected(change):
    from tester_spin.providers.nolimit_city.client_money import monetary_fields
    assert monetary_fields(change(CASES[0]['source'])) is None


def test_independent_total_reconciliation_rejects_conflicts_and_negative_deltas():
    source=CASES[0]['source']
    with pytest.raises(ValueError):reconciled_step_win({'totalSpinWin':.07,'totalRoundWin':.08},Decimal(0),client_source=source)
    with pytest.raises(ValueError):reconciled_step_win({'totalSpinWin':.08,'totalRoundWin':.08},Decimal('.1'),client_source=source)


@pytest.mark.parametrize('field,value',[('totalSpinWin',True),('totalSpinWin','NaN'),('totalRoundWin',float('inf'))])
def test_declared_monetary_values_still_require_finite_numbers(field,value):
    game={'totalSpinWin':.08,'totalRoundWin':.08,field:value}
    with pytest.raises(ValueError):reconciled_step_win(game,Decimal(0),client_source=CASES[0]['source'])


def test_running_total_uses_independent_increment_without_balance():
    source=CASES[0]['source']
    assert reconciled_step_win({'totalSpinWin':.12,'totalRoundWin':.12},Decimal('.08'),client_source=source)=='0.04'
    assert reconciled_step_win({'totalSpinWin':.04,'totalRoundWin':.12},Decimal('.08'),client_source=source)=='0.04'


def test_client_alias_does_not_silence_conflicting_native_win_or_accumulation():
    from tester_spin.providers.nolimit_city.operation_fields import round_win
    source=CASES[0]['source']
    with pytest.raises(ValueError):step_win({'totalSpinWin':.08,'win':.09},client_source=source)
    with pytest.raises(ValueError):round_win({'totalRoundWin':.08,'accumulatedRoundWin':.09},client_source=source)


def test_nested_history_fields_cannot_become_parser_output():
    from tester_spin.providers.nolimit_city.client_money import monetary_fields
    source='e.Parser=class{getActionSpinOptions(){return{getParsedData:(t,e,i)=>({history:()=>({totalWin:t.oldRound,totalSpinWinnings:this.getWin(t,e,i)})})}}getWin(t,e,i){return t.oldSpin}};'
    assert monetary_fields(source) is None


def test_later_duplicate_money_property_does_not_use_earlier_declared_value():
    from tester_spin.providers.nolimit_city.client_money import monetary_fields
    source=CASES[0]['source'].replace('totalWin:t.totalRoundWin,','totalWin:t.totalRoundWin,totalWin:historyValue,')
    assert monetary_fields(source) is None


@pytest.mark.parametrize('case',CASES,ids=lambda case:case['reference'])
def test_ledger_uses_client_fields_and_independent_wallet(case):
    from tester_spin.providers.nolimit_city.runtime import RoundLedger
    raw=case['events'][-1]['game']
    from tester_spin.providers.nolimit_city.operation_fields import round_win
    total=Decimal(str(round_win(raw,client_source=case['source'])))
    game={'mode':'NORMAL','nextMode':'NORMAL','freespinsLeft':0,'playedBetValue':'.20','wasFeatureBuy':False,'wasBoostedBet':False,**raw}
    answer={'game':game,'features':{'available':[]},'balance':str(Decimal('9999.80')+total)}
    ledger=RoundLedger('10000',{'kind':'SPIN','stake':'.20','price_multiplier':1})
    assert ledger.accept(answer,request={'type':'normalBet','bet':'.20'},client_source=case['source'])
    assert ledger.win==total
    assert ledger.proof()['closed']
    bad={**answer,'balance':str(Decimal(answer['balance'])+1)}
    with pytest.raises(ValueError,match='saldo'):
        RoundLedger('10000',{'kind':'SPIN','stake':'.20','price_multiplier':1}).accept(bad,request={'type':'normalBet','bet':'.20'},client_source=case['source'])


def test_client_mapping_never_turns_wallet_balance_into_prize():
    from tester_spin.providers.nolimit_city.client_money import monetary_fields
    source=CASES[0]['source'].replace('return t.totalSpinWin','return t.balance')
    assert monetary_fields(source) is None


@pytest.mark.parametrize('prefix', ['t.totalRoundWin=999,','t.totalRoundWin++,','change(t),','Object.assign(t,{totalRoundWin:999}),'])
def test_parser_side_effects_cannot_change_observed_money(prefix):
    from tester_spin.providers.nolimit_city.client_money import monetary_fields
    source=CASES[0]['source'].replace('=>({totalWin:', '=>('+prefix+'{totalWin:')
    assert monetary_fields(source) is None


def test_quoted_duplicate_key_cannot_override_monetary_observation():
    from tester_spin.providers.nolimit_city.client_money import monetary_fields
    source=CASES[0]['source'].replace('totalWin:t.totalRoundWin,', 'totalWin:t.totalRoundWin,"totalWin":999,')
    assert monetary_fields(source) is None


def test_client_canonical_view_remains_valid_when_planner_normalizes_again():
    from tester_spin.providers.nolimit_city.runtime import normalized_response
    case=next(c for c in CASES if c['reference']=='theborder')
    game={**case['events'][-1]['game'],'mode':'NORMAL','nextMode':'NORMAL_AVALANCHE','freespinsLeft':0}
    answer={'game':game,'features':{'available':[]}}
    first=normalized_response(answer,client_source=case['source'],allow_unresolved_state=True)
    second=normalized_response(first,allow_unresolved_state=True)
    assert second['game']['win']==.08
    assert answer['game']['thisSpinWinnings']==0


@pytest.mark.parametrize('step_field,total_field', [('thisSpinWinnings','totalSpinWinnings'),('thisAvalancheWinnings','totalAvalancheRoundWinnings')])
def test_proven_step_and_round_are_not_replaced_by_ui_subround_summary(step_field,total_field):
    from tester_spin.providers.nolimit_city.runtime import RoundLedger
    source='e.Parser=class{getActionSpinOptions(){return{getParsedData:(t,e,i)=>({totalWin:t.accumulatedRoundWin,totalSpinWinnings:this.getWin(t,e,i)})}}getWin(t,e,i){return t.'+total_field+'}};'
    ledger=RoundLedger('10000',{'kind':'SPIN','stake':'.20','price_multiplier':1})
    first={'game':{'mode':'NORMAL','nextMode':'NORMAL_RESPIN','freespinsLeft':0,'playedBetValue':'.20',step_field:'.76','accumulatedRoundWin':'.76',total_field:'.76'},'balance':'9999.80','features':{'available':[]}}
    assert not ledger.accept(first,request={'type':'normalBet','bet':'.20'},client_source=source)
    last={'game':{'mode':'NORMAL_RESPIN','nextMode':'NORMAL','freespinsLeft':0,step_field:0,'accumulatedRoundWin':'.76',total_field:'.20'},'balance':'10000.56','features':{'available':[]}}
    assert ledger.accept(last,request={'type':'zeroBet','bet':'0.00'},client_source=source)
    assert ledger.win==Decimal('.76')
