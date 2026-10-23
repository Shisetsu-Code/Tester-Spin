"""Observed indexed host reels must prove a base outcome, not only closure."""
from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from tester_spin.providers.yggdrasil.runtime import configuration, ordinary_round

FIXTURE=json.loads((Path(__file__).parent/'fixtures/yggdrasil_host_guest.json').read_text())


def context():
    return configuration(deepcopy(FIXTURE['game']),'20001','EUR')['ordinary_constraints']


def test_host_without_guest_and_synchronized_declared_strips_is_ordinary():
    for bet in FIXTURE['bets']:
        assert ordinary_round({'bets':[bet]},context())


def test_declared_realm_transition_and_counted_guest_round_are_known_features(tmp_path):
    from tester_spin.providers.yggdrasil.runtime import DemoRuntime
    recorded=json.loads((Path(__file__).parent/'fixtures/yggdrasil_cash_settlement.json').read_text())['host_active']
    for index,sequence in enumerate(recorded):
        runtime=DemoRuntime(None,'20001',1,threading.Event(),gate=None)
        runtime.config={'ordinary_constraints':context()}
        replies=iter(deepcopy(sequence));runtime.call=lambda *args,**kwargs:next(replies)
        bet=sequence[0]['data']['wager']['bets'][0]
        result=runtime.round({'coin':bet['betdata']['coin'],'amount':bet['betamount'],'coins':'50','lines':bet['betdata']['lines']},tmp_path/str(index))
        assert result['terminal'] and result['known'] and not result['base']
    assert all(not ordinary_round({'bets':[bet]},context()) for bet in FIXTURE['active_bets'])


@pytest.mark.parametrize('failure',['unlearned_feature','broken_mode_chain'])
def test_host_round_cannot_close_coverage_with_unknown_presentation_or_reset_state(tmp_path,failure):
    from tester_spin.providers.yggdrasil.runtime import DemoRuntime,Unsupported
    recorded=json.loads((Path(__file__).parent/'fixtures/yggdrasil_cash_settlement.json').read_text())['host'][0]
    runtime=DemoRuntime(None,'20001',1,threading.Event(),gate=None)
    runtime.config={'ordinary_constraints':context()}
    if failure=='unlearned_feature':recorded[0]['data']['wager']['bets'][0]['eventdata']['features'].append({'unknownTransform':True})
    else:runtime.host_mode=FIXTURE['active_bets'][-1]['eventdata']['gameModeNext']
    replies=iter(recorded);runtime.call=lambda *args,**kwargs:next(replies)
    bet=recorded[0]['data']['wager']['bets'][0]
    with pytest.raises(Unsupported):runtime.round({'coin':bet['betdata']['coin'],'amount':bet['betamount'],'coins':'50','lines':bet['betdata']['lines']},tmp_path)


@pytest.mark.parametrize('mutation',['count_increase','skipped_count','changed_feature','stacked_symbol','changed_stake','realm_flag'])
def test_known_guest_round_rejects_unproven_state_or_stacked_geometry(mutation):
    from tester_spin.providers.yggdrasil.host_guest import known
    bet=deepcopy(FIXTURE['active_bets'][1]);ed=bet['eventdata']
    if mutation=='count_increase':ed['gameModeNext']['remainingSpinInMode']=4
    if mutation=='skipped_count':ed['gameModeNext']['remainingSpinInMode']=0
    if mutation=='changed_feature':ed['gameModeNext']['currentGuestFeature']=0
    if mutation=='stacked_symbol':ed['features'][0]['stackedSymbol']=7
    if mutation=='changed_stake':ed['gameModeNext']['betAmount']=200000
    if mutation=='realm_flag':ed['realmChanged']=True
    assert not known(bet,context())


def test_guest_is_drained_in_the_same_session_before_two_ordinary_rounds(tmp_path):
    from tester_spin.providers.yggdrasil.runtime import DemoRuntime
    recorded=json.loads((Path(__file__).parent/'fixtures/yggdrasil_cash_settlement.json').read_text())['host_chain']
    runtime=DemoRuntime(None,'20001',1,threading.Event(),gate=None)
    runtime.config={'ordinary_constraints':context()}
    replies=iter(deepcopy([response for sequence in recorded for response in sequence]));runtime.call=lambda *args,**kwargs:next(replies)
    results=[]
    for index,sequence in enumerate(recorded):
        bet=sequence[0]['data']['wager']['bets'][0]
        results.append(runtime.round({'coin':bet['betdata']['coin'],'amount':bet['betamount'],'coins':'50','lines':bet['betdata']['lines']},tmp_path/str(index)))
    assert all(result['known'] and result['terminal'] for result in results)
    assert [result['base'] for result in results]==[False]*5+[True,True]


@pytest.mark.parametrize('mutation',[
    'guest','feature','remaining','changed_host','changed_next_coin','unknown_field',
    'board','index_map','strip','stop','sync_order','sync_duplicate','sync_mismatch',
    'cash','coins','paylines','boolean_host','unknown_reel','missing_configuration',
])
def test_host_outcome_rejects_active_modes_unproven_geometry_and_money(mutation):
    bet=deepcopy(FIXTURE['bets'][0]);ctx=context();ed=bet['eventdata']
    if mutation=='guest':ed['gameModeNext']['currentGuest']=1
    if mutation=='feature':ed['gameModeCurrent']['currentGuestFeature']=0
    if mutation=='remaining':ed['gameModeNext']['remainingSpinInMode']=1
    if mutation=='changed_host':ed['gameModeNext']['currentHost']=1
    if mutation=='changed_next_coin':ed['gameModeNext']['coin']='0.003'
    if mutation=='unknown_field':ed['choice']=['SPIN','BONUS']
    if mutation=='board':ed['reels'][0][0]='Wild'
    if mutation=='index_map':ed['reelMap'][0][2]='foreign'
    if mutation=='strip':ed['reelSet']='undeclared,'+','.join(ed['reelSet'].split(',')[1:])
    if mutation=='stop':ed['rpos'][0]=-1
    if mutation=='sync_order':ed['features'][0]['synchedReels']['reelsToSync']=[1,0,3,4]
    if mutation=='sync_duplicate':ed['features'][0]['synchedReels']['reelsToSync']=[0,0,3,4]
    if mutation=='sync_mismatch':ed['rpos'][1]+=1
    if mutation=='cash':ed['accWa']='1.00'
    if mutation=='coins':ed['accC']=1
    if mutation=='paylines':ed['paylineSet']='missing'
    if mutation=='boolean_host':ed['gameModeCurrent']['currentHost']=False
    if mutation=='unknown_reel':ed['features']=[{'respins':{'remaining':1}}]
    if mutation=='missing_configuration':ctx={}
    assert not ordinary_round({'bets':[bet]},ctx)


def test_host_contract_follows_current_declared_symbol_names():
    game=deepcopy(FIXTURE['game']);bet=deepcopy(FIXTURE['bets'][0])
    props={entry['prop']:entry for entry in game['cfg']['props']}
    renamed={name:'mapped_'+str(i) for i,name in enumerate(props['Icons']['value'])}
    props['Icons']['value']=[renamed[name] for name in props['Icons']['value']]
    props['Prizes']['value']=[[renamed[row[0]],*row[1:]] for row in props['Prizes']['value']]
    for key in ('reels','reelMap'):
        bet['eventdata'][key]=[[renamed[name] for name in col] for col in bet['eventdata'][key]]
    ctx=configuration(game,'20001','EUR')['ordinary_constraints']
    assert ordinary_round({'bets':[bet]},ctx)


@pytest.mark.parametrize('mutation',[
    'source','target','matrix','unexpected_transform','hex_mask','wrong_line',
    'wrong_prize','double_amount','double_count','uncashed_prize',
    'line_mask','board_mask','duplicate_win',
])
def test_wild_spread_and_hex_win_mask_must_match_declared_paylines(mutation):
    bet=deepcopy(FIXTURE['bets'][2]);ed=bet['eventdata']
    spreading=ed['features'][1]['spreadingWilds']
    if mutation=='source':spreading['positions'][0]['from']=0
    if mutation=='target':spreading['positions'][0]['to'].append(100)
    if mutation=='matrix':spreading['icons'][0][0]=0
    if mutation=='unexpected_transform':spreading['multiplier']=2
    if mutation=='hex_mask':ed['wtw'][0][2]='44880'
    if mutation=='wrong_line':ed['wtw'][0][0]=50
    if mutation=='wrong_prize':ed['wtw'][0][1]+=1
    if mutation=='double_amount':ed['doubleAmount']='0'
    if mutation=='double_count':ed['doubleCount']=2
    if mutation=='uncashed_prize':ed['nextCmds']='GAMBLE'
    if mutation=='line_mask':ed['wts'][0]='0'*len(ed['wts'][0])
    if mutation=='board_mask':ed['wts'][1]='0'*len(ed['wts'][1])
    if mutation=='duplicate_win':
        ed['wtw'].append(deepcopy(ed['wtw'][0]))
        ed['accC']+=20;ed['wonCoins']+=20
        ed['accWa']=str(float(ed['accWa'])+0.04);ed['doubleAmount']=ed['accWa']
    assert not ordinary_round({'bets':[bet]},context())
