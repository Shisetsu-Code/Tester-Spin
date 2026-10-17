import pytest
from tester_spin.providers.playtech.ngm_observation import spin_request_contract, observation_points
from tester_spin.providers.playtech.ngm_execution import NGMRoundLedger

SOURCE = """
function Spin(){base.call(this,box(40200))}
register(710,105,{710:1},Spin);var kind=type(ns,'SpinRequest',710,parent);
function encode(req,out){var model,v;check(req,710);model=req;v=box(model.cost);v!=null&&put(out,'bet',number(v));v=box(model.coins);v!=null&&put(out,'numCoins',number(v));v=model.phase;v!=null&&put(out,'spinType',text(v))}
"""

def test_request_fields_come_from_matching_class_and_serializer():
    assert spin_request_contract(SOURCE)=={'constructor':'Spin','message_id':40200,'fields':{'bet':'cost','numCoins':'coins','spinType':'phase'}}
    assert spin_request_contract(SOURCE.replace('check(req,710)','check(req,711)')) is None
    assert spin_request_contract(SOURCE.replace("'spinType'", "'unknown'")) is None

def test_ambiguous_serializer_is_rejected():
    assert spin_request_contract(SOURCE+SOURCE[SOURCE.index('function encode'):].replace('encode','other')) is None

def round_events(win=60):
    return [('message',{'classifier':'GameRoundStartNotification'}),
            ('message',{'classifier':'ISetGameBalanceRequest','amount':980}),
            ('spin',{'bet':20,'numCoins':1,'spinType':'regular'}),
            ('response',{}),('payout',{'calculatedWin':win}),
            ('message',{'classifier':'ISetGameBalanceRequest','amount':980+win}),
            ('message',{'classifier':'GameRoundEndNotification'}),
            ('message',{'classifier':'NextGameRoundAllowed'})]

def apply(events,before=1000):
    ledger=NGMRoundLedger(before)
    for kind,value in events:ledger.accept(kind,value)
    return ledger

def test_positive_and_zero_rounds_reconcile_and_return_to_base():
    for win in (0,60):
        ledger=apply(round_events(win))
        assert ledger.verified
        assert ledger.summary()['win']==win
        assert ledger.summary()['stake']==20

def test_end_notification_without_independent_payout_is_insufficient():
    ledger=apply([e for e in round_events() if e[0]!='payout'])
    assert not ledger.verified
    assert 'PAYOUT_COUNT_MISMATCH' in ledger.issues

def test_balance_mismatch_does_not_verify():
    ledger=apply(round_events(),before=1001)
    assert not ledger.verified
    assert 'BALANCE_NOT_RECONCILED' in ledger.issues

def test_continuations_need_matching_responses_and_independent_wins():
    events=round_events(60)
    events[6:6]=[('spin',{'bet':20,'numCoins':1,'spinType':'free'}),('response',{}),('payout',{'calculatedWin':10}),('message',{'classifier':'ISetGameBalanceRequest','amount':1050})]
    ledger=apply(events)
    assert ledger.verified and ledger.summary()['win']==70
    assert ledger.summary()['stake']==20 and ledger.summary()['steps']==2

def test_open_round_or_next_spin_without_allowance_stays_pending():
    assert not apply(round_events()[:-1]).verified
    assert not apply(round_events()[:-2]).verified
    ledger=apply(round_events()+[('spin',{'bet':20,'numCoins':1,'spinType':'regular'})])
    assert not ledger.verified

def test_unknown_feature_and_ambiguous_financial_values_stay_pending():
    for field,value in [('spinType','purchase'),('bet',True),('bet',-20),('bet',float('nan'))]:
        events=round_events();events[2]=('spin',dict(events[2][1],**{field:value}))
        assert not apply(events).verified
    assert not apply(round_events()+[('payout',{'calculatedWin':float('nan')})]).verified

def test_free_spin_cannot_start_a_base_round():
    events=round_events();events[2]=('spin',dict(events[2][1],spinType='free'))
    assert not apply(events).verified


def test_ngm_adapter_runs_base_and_keeps_unknown_inventory_partial(tmp_path):
    import threading
    from tester_spin.models import Game
    from tester_spin.providers.playtech.adapter import PlaytechProvider
    class Session:
        transport_kind='local-client-engine'
        def __init__(self,*args): self.source_hashes=['hash'];self.contract={'fields':{'bet':'cost'}};self.errors=[]
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def spin(self):return apply(round_events()).summary()
    provider=PlaytechProvider(tmp_path)
    provider.ngm_session_factory=Session
    game=Game('playtech','game-legacy','Legacy','https://www.playtechone.com/games/legacy',symbol='legacy')
    result=provider.test_game(game,spins=2,timeout_s=10,stop_event=threading.Event(),progress=lambda x:None)
    assert result.successful_spins==3
    assert result.status=='PARCIAL'
    assert result.structural_map['return_to_base_verified'] is True
    assert result.structural_map['playtech_protocol']['transport']=='local-client-engine'
    assert result.feature_domains['purchase']['declaration_state']=='UNKNOWN'
    assert 'NGM_FEATURE_INVENTORY_UNKNOWN' in result.error


def test_ngm_adapter_stops_after_unclosed_round(tmp_path):
    import threading
    from tester_spin.models import Game
    from tester_spin.providers.playtech.adapter import PlaytechProvider
    class Session:
        calls=0
        source_hashes=[];contract={};errors=[]
        def __init__(self,*args):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def spin(self):
            Session.calls+=1
            raise ValueError('ROUND_NOT_CLOSED_AND_READY')
    provider=PlaytechProvider(tmp_path);provider.ngm_session_factory=Session
    result=provider.test_game(Game('playtech','game-legacy','Legacy','https://www.playtechone.com/games/legacy',symbol='legacy'),spins=3,timeout_s=10,stop_event=threading.Event(),progress=lambda x:None)
    assert Session.calls==1 and result.successful_spins==0
    assert result.status=='PARCIAL' and result.attempts[0].ok is False


def make_runtime(tmp_path):
    import threading
    from types import SimpleNamespace
    from tester_spin.providers.playtech.ngm_runtime import NGMDemoSession
    session=NGMDemoSession('legacy',tmp_path,10,threading.Event())
    session.demo_verified=True;session.contract={'fields':{}};session.balance=1000
    session.timeout=0.001
    calls=[]
    body=SimpleNamespace(press=lambda *args,**kwargs:calls.append(args))
    frame=SimpleNamespace(url='https://cachedownload.playtechone.com/ngmdistributed/legacy/1/index.html',locator=lambda *args:body,evaluate=lambda expression: True if expression.startswith('typeof') else calls.append(expression))
    session.page=SimpleNamespace(frames=[frame],locator=lambda *args:body,wait_for_timeout=lambda *args:None)
    return session,calls

def test_uncertain_wager_is_never_retried(tmp_path):
    session,calls=make_runtime(tmp_path)
    with pytest.raises(TimeoutError):session.spin()
    with pytest.raises(ValueError,match='NGM_NOT_READY'):session.spin()
    assert len(calls)==1

def test_stop_is_checked_before_any_keyboard_action(tmp_path):
    session,calls=make_runtime(tmp_path);session.stop.set()
    with pytest.raises(InterruptedError):session.spin()
    assert calls==[]

def test_live_request_binding_adds_semantic_fields_to_observation():
    source=SOURCE+'function dispatch(x,q){var out,h,v;out=new List;for(h=iter(q);h.more();){v=h.vf(q);append(out,v)}return out}'
    points=observation_points(source)
    assert 'instanceof Spin' in points[0]['expression']
    assert 'bet:q.cost,numCoins:q.coins,spinType:q.phase' in points[0]['expression']


def test_unexpected_spin_outside_round_poison_session(tmp_path):
    import json
    from types import SimpleNamespace
    session,_=make_runtime(tmp_path)
    row={'type':'offline.request','frame':'https://cachedownload.playtechone.com/ngmdistributed/legacy/1/index.html','data':{'value':{'spin':{'bet':20,'numCoins':1,'spinType':'regular'}}}}
    session._console(SimpleNamespace(text='__TESTER_NGM__'+json.dumps(row)))
    assert 'NGM_UNEXPECTED_SPIN_OUTSIDE_ROUND' in session.errors


def test_spin_action_is_derived_from_declared_event_and_ui_dispatch():
    from tester_spin.providers.playtech.ngm_observation import spin_action_binding
    source="function Event(){base.call(this)}register(549,23,{549:1},Event);var kind=type(ns,'SpinEvent',549,parent);function send(e){bus(globalBus,e)}function clicked(){send(new Event)}"
    binding=spin_action_binding(source)
    assert binding['constructor']=='Event' and binding['function']=='send'
    assert spin_action_binding(source+'function other(e){bus(globalBus,e)}function clicked2(){other(new Event)}') is None
    assert spin_action_binding(source.replace("'SpinEvent'","'UnknownEvent'")) is None


def test_break_even_round_without_balance_notifications_is_not_verified():
    events=[e for e in round_events(20) if not(e[0]=='message' and e[1].get('classifier')=='ISetGameBalanceRequest')]
    assert not apply(events).verified

def test_final_balance_without_observed_debit_is_not_verified():
    events=round_events();events.pop(1)
    assert not apply(events).verified


def test_poisoned_session_never_dispatches_another_spin(tmp_path):
    session,calls=make_runtime(tmp_path);session.errors.append('NGM_UNEXPECTED_SPIN_OUTSIDE_ROUND')
    with pytest.raises(ValueError):session.spin()
    assert calls==[]


def test_failed_bootstrap_does_not_claim_verified_fresh_demo(tmp_path):
    import threading
    from tester_spin.models import Game
    from tester_spin.providers.playtech.adapter import PlaytechProvider
    class Session:
        def __init__(self,*args):raise ValueError('NGM_CONTRACT_UNBOUND')
    provider=PlaytechProvider(tmp_path);provider.ngm_session_factory=Session
    result=provider.test_game(Game('playtech','game-legacy','Legacy','https://www.playtechone.com/games/legacy',symbol='legacy'),spins=1,timeout_s=10,stop_event=threading.Event(),progress=lambda x:None)
    assert result.structural_map['playtech_protocol']['fresh_demo'] is False
    assert result.status=='PARCIAL' and not result.attempts
