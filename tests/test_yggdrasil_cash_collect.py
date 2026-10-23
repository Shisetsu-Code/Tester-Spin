from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from tester_spin.providers.yggdrasil.runtime import ordinary_round

FIXTURE=json.loads((Path(__file__).parent/'fixtures/yggdrasil_cash_collect.json').read_text())


def test_paid_cash_win_already_includes_display_multiplier():
    bet=FIXTURE['bets'][2]
    assert bet['eventdata']['response']['clientData']['modifiersData']['activeMultiplier']==4
    assert ordinary_round({'bets':[bet]},FIXTURE['context'])


def test_paid_base_spin_clears_an_exhausted_purchase_history():
    bet=deepcopy(FIXTURE['bets'][3])
    assert ordinary_round({'bets':[bet]},FIXTURE['context'])
    bet['eventdata']['initialPlayerState']['freespinsRemaining']=1
    assert not ordinary_round({'bets':[bet]},FIXTURE['context'])


@pytest.mark.parametrize('mutation',['active_before','bad_final_state','bad_boost'])
def test_zero_win_cash_family_cannot_fall_back_to_presentation_only_flags(mutation):
    bet=deepcopy(FIXTURE['bets'][0]);ed=bet['eventdata']
    if mutation=='active_before':ed['initialPlayerState']['freespinsRemaining']=1
    if mutation=='bad_final_state':ed['playerState']=None
    if mutation=='bad_boost':ed['boostData']['multiplierx4Spins']=1
    assert not ordinary_round({'bets':[bet]},FIXTURE['context'])


@pytest.mark.parametrize('mutation',[
    'cash','double_multiplier','accumulated','free_spins','buy_bonus','currency',
    'position','duplicate_position','ways','unknown','prize_position','active_collect',
    'foreign_symbol','boost_multiplier','unlearned_multiplier',
])
def test_cash_win_rejects_inconsistent_money_geometry_or_active_bonus(mutation):
    bet=deepcopy(FIXTURE['bets'][2]);ed=bet['eventdata'];cd=ed['response']['clientData']
    if mutation=='cash':ed['response']['cashWin']='0.33'
    if mutation=='double_multiplier':cd['winningRows'][0]['payout']=1.28
    if mutation=='accumulated':ed['playerState']['accumulatedWins']=0.33
    if mutation=='free_spins':ed['playerState']['freespinsRemaining']=1
    if mutation=='buy_bonus':ed['playerState']['buyBonus']=True
    if mutation=='currency':bet['betcurrency']='USD'
    if mutation=='position':cd['winningRows'][0]['positions'][0]['reel']=5
    if mutation=='duplicate_position':cd['winningRows'][0]['positions'].append(cd['winningRows'][0]['positions'][0])
    if mutation=='ways':cd['winningRows'][0]['winning_ways']=2
    if mutation=='unknown':cd['choice']=['START']
    if mutation=='prize_position':cd['cashPrizes'][0]['position']['row']=5
    if mutation=='active_collect':cd['modifiersData']['collectFish']=True
    if mutation=='foreign_symbol':cd['screen'][1][1]=4096
    if mutation=='boost_multiplier':ed['boostData']['multiplierx4Spins']=0
    if mutation=='unlearned_multiplier':cd['modifiersData']['activeMultiplier']=8
    assert not ordinary_round({'bets':[bet]},FIXTURE['context'])


def test_cash_evidence_replaces_the_presentation_wager_reference(tmp_path):
    from tester_spin.providers.yggdrasil.runtime import DemoRuntime
    runtime=DemoRuntime(None,'20002',1,threading.Event(),gate=None)
    runtime.config={'ordinary_constraints':FIXTURE['context']}
    bet=deepcopy(FIXTURE['bets'][2])
    bet['eventdata']['response']['clientData']['wagerId']='private-presentation-reference'
    state={'wagerid':'private-round-id','status':'Pending','terminal':False,'commands':['C'],'bets':[bet]}
    runtime.save(tmp_path,1,{'amount':'0.2'},state)
    text=(tmp_path/'step-001-response.json').read_text()
    assert 'private-presentation-reference' not in text
    assert 'private-round-id' not in text
    outcome=json.loads(text)['ordinary_cash_collect_outcomes'][0]
    assert outcome['bet']['eventdata']['response']['cashWin']=='0.32'
