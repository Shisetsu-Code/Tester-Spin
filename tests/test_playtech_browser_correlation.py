
"""Checks for first GPAS command correlation without a network or browser."""
import json
from threading import Event
from types import SimpleNamespace

import pytest
from tester_spin.providers.playtech.runtime import DemoSession
from tester_spin.providers.playtech.primitives import COMMAND


def session(tmp_path, *, sent=1, wrong_response=False, omit_response=False):
    runtime=DemoSession('gpas_fixture_pop',tmp_path,5,Event())
    runtime.bindings={'1':'gpas_fixture_pop'}
    runtime.socket_urls={'1':'wss://frontend.playtechhorizon.com/socket.io/1/websocket/fixture'}
    def evaluate(*args):
        for i in range(sent):
            packet={'correlationId':'correct-'+str(i),
                    'data':{'_type':COMMAND,'gameData':{'ID':40021},'betType':'default'}}
            runtime._packet('1','sent','3:::'+json.dumps(packet))
        if wrong_response:
            runtime.replies.append(('unrelated',dict(wrong=True)))
        if not omit_response:
            runtime.replies.append(('correct-0',dict(wrong=False)))
        return {'ok':True}
    runtime.page=SimpleNamespace(evaluate=evaluate,wait_for_timeout=lambda _:None)
    def wait(predicate,reason):
        if not predicate():
            raise TimeoutError(reason)
    runtime.wait=wait
    return runtime


def test_first_client_dispatched_wager_uses_its_own_correlation_id(tmp_path):
    runtime=session(tmp_path,wrong_response=True)
    reply=runtime.exchange(dict(gameData={'_type':'fixture'},betCost=10,featureType='default'),
                           dict(dialect='modern'))
    assert reply==dict(wrong=False)
    assert runtime.sent_game_commands==[('1','correct-0')]
    assert not runtime.uncertain_dispatch


def test_wager_sent_without_a_correlated_reply_poisoned_and_never_retried(tmp_path):
    runtime=session(tmp_path,wrong_response=True,omit_response=True)
    with pytest.raises(TimeoutError,match='GAME_COMMAND_TIMEOUT'):
        runtime.exchange(dict(gameData={'_type':'fixture'}),dict(dialect='modern'))
    with pytest.raises(ValueError,match='GAME_COMMAND_OUTCOME_UNCERTAIN'):
        runtime.exchange(dict(gameData={'_type':'fixture'}),dict(dialect='modern'))
    assert runtime.uncertain_dispatch is True


def test_two_client_side_dispatches_are_ambiguous_even_with_one_response(tmp_path):
    runtime=session(tmp_path,sent=2)
    with pytest.raises(ValueError,match='CLIENT_WAGER_DISPATCH_AMBIGUOUS'):
        runtime.exchange(dict(gameData={'_type':'fixture'}),dict(dialect='modern'))
    assert runtime.uncertain_dispatch


def test_no_command_sent_cannot_accept_an_unrelated_answer(tmp_path):
    runtime=session(tmp_path,sent=0,wrong_response=True,omit_response=True)
    with pytest.raises(TimeoutError,match='CLIENT_GAME_COMMAND_NOT_OBSERVED'):
        runtime.exchange(dict(gameData={'_type':'fixture'}),dict(dialect='modern'))
    assert runtime.uncertain_dispatch


def test_sent_command_must_have_a_valid_correlation_id(tmp_path):
    runtime=session(tmp_path)
    packet={'correlationId':None,'data':{'_type':COMMAND}}
    runtime._packet('1','sent','3:::'+json.dumps(packet))
    assert 'GAME_COMMAND_CORRELATION_MISSING' in runtime.errors
