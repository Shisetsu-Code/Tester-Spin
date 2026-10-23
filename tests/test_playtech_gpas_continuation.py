
import pytest
from tester_spin.providers.playtech.gpas_continuation import ContinuationPlanner
from tester_spin.providers.playtech.primitives import PickState, RoundLedger


def open_free_game(*, play_index=12, remaining=8, **more):
    result=dict(nextRound='FreeGame', playIndex=play_index,
        playStack=[
            dict(round='BaseGame', modeType='SLOTS', remainingPlayCount=0),
            dict(round='FreeGame', modeType='LIST_PICK', remainingPlayCount=remaining)],
        stakeCostUuid='captured-fresh-uuid',totalWinAmount=500)
    result.update(more)
    return result


def test_server_declares_eight_free_games_without_a_pick_domain():
    planner=ContinuationPlanner()
    assert planner.parameters(open_free_game(),dict(pick_bound=False),PickState())==[]
    assert planner.records[0]['selection_source']=='server-FreeGame-no-player-choice'
    assert planner.records[0]['remaining']==8
    with pytest.raises(ValueError,match='CONTINUATION_NO_PROGRESS'):
        planner.parameters(open_free_game(),{},PickState())
    assert planner.parameters(open_free_game(play_index=13,remaining=7),{},PickState())==[]


def test_explicit_pick_still_requires_a_client_binding_and_unique_option():
    data=open_free_game(listPickPlayerPickOptions=[dict(index=1),dict(index=2)])
    with pytest.raises(ValueError,match='PICK_COMMAND_NOT_BOUND'):
        ContinuationPlanner().parameters(data,dict(pick_bound=False),PickState())
    planner=ContinuationPlanner()
    assert planner.parameters(data,dict(pick_bound=True),PickState())==[
        dict(key='pick',value='1')]
    assert planner.records[0]['selection_source']=='server-choice-domain'


def test_empty_advertised_pick_domain_does_not_mean_auto_free_spin():
    with pytest.raises(ValueError,match='PICK_DOMAIN_UNKNOWN'):
        ContinuationPlanner().parameters(open_free_game(listPickPlayerPickOptions=[]),
                                         dict(pick_bound=True),PickState())


def test_unknown_or_duplicate_stage_and_terminal_are_not_continued():
    bad=open_free_game(playStack=[])
    with pytest.raises(ValueError,match='CONTINUATION_STAGE_UNBOUND'):
        ContinuationPlanner().parameters(bad,{},PickState())
    bad=open_free_game(nextRound='BET_END_STATE_IDENTIFIER')
    with pytest.raises(ValueError,match='CONTINUATION_STATE_UNKNOWN'):
        ContinuationPlanner().parameters(bad,{},PickState())
    bad=open_free_game(playIndex=None)
    with pytest.raises(ValueError,match='CONTINUATION_PROGRESS_UNKNOWN'):
        ContinuationPlanner().parameters(bad,{},PickState())


def test_declared_normal_stage_uses_empty_continuation_only_without_choices():
    planner=ContinuationPlanner()
    state=dict(nextRound='HoldAndWin',playIndex=2,
               playStack=[dict(round='HoldAndWin',modeType='SLOTS',remainingPlayCount=1)])
    assert planner.parameters(state,{},PickState())==[]
    state['listPickPlayerPickOptions']=[dict(index=0)]
    with pytest.raises(ValueError,match='UNHANDLED_CHOICES_FOR_STAGE'):
        ContinuationPlanner().parameters(state,{},PickState())


def test_ledger_blocks_repeated_charge_and_requires_terminal_and_return_balance():
    ledger=RoundLedger(1000,'captured-fresh-uuid',500)
    message=lambda stake,win,closed,next_round,total,stack:dict(
        stakeAmount=stake,betCost=stake,winAmount=win,gameRoundClosed=closed,
        gameData=dict(stakeCostUuid='captured-fresh-uuid',nextRound=next_round,
                      totalWinAmount=total,playIndex=12,playStack=stack))
    progress=ledger.accept(message(500,500,False,'FreeGame',500,open_free_game()['playStack']))
    assert not ledger.closed
    assert ContinuationPlanner().parameters(progress,{},PickState())==[]
    with pytest.raises(ValueError,match='UNEXPECTED_CHARGE'):
        ledger.accept(message(500,0,False,'FreeGame',500,open_free_game()['playStack']))
    ledger=RoundLedger(1000,'captured-fresh-uuid',500)
    ledger.accept(message(500,500,False,'FreeGame',500,open_free_game()['playStack']))
    ledger.accept(message(0,50,True,'BET_END_STATE_IDENTIFIER',550,[]))
    assert ledger.closed and ledger.verify(1050)
    assert not ledger.verify(1049)


def test_reject_nonprogressing_and_overlong_continuations():
    p=ContinuationPlanner(limit=1)
    p.parameters(open_free_game(),{},PickState())
    with pytest.raises(ValueError,match='ROUND_STEP_LIMIT'):
        p.parameters(open_free_game(play_index=13),{},PickState())


def test_explicit_pick_client_without_play_index_remains_supported():
    data=open_free_game(playIndex=None,listPickPlayerPickOptions=[dict(index=4)])
    assert ContinuationPlanner().parameters(data,dict(pick_bound=True),PickState())==[
        dict(key='pick',value='4')]
