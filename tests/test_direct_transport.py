import threading
import pytest
from tester_spin.direct_transport import CorrelatedSocket

class Wire:
    def __init__(self, frames): self.frames=list(frames);self.sent=[];self.closed=False
    def send(self, value): self.sent.append(value)
    def recv(self): return self.frames.pop(0)
    def settimeout(self, value): pass
    def close(self): self.closed=True

def test_heartbeat_and_correlation_do_not_repeat_command():
    w=Wire(['2::', 'other', 'answer'])
    with CorrelatedSocket(w, threading.Event(), 1, heartbeat_response={'2::':'2::'}) as transport:
        assert transport.exchange('request', lambda v:v=='answer')=='answer'
    assert w.sent==['request','2::']
    assert w.closed

def test_timeout_never_retries_a_wager():
    class TimeoutWire(Wire):
        def recv(self): raise TimeoutError('timeout')
    w=TimeoutWire([])
    with CorrelatedSocket(w, threading.Event(), 0.01) as t:
        with pytest.raises(TimeoutError): t.exchange('purchase', lambda v:True)
    assert w.sent==['purchase']

def test_cancel_before_send():
    stop=threading.Event();stop.set();w=Wire([])
    with CorrelatedSocket(w, stop, 1) as t:
        with pytest.raises(InterruptedError):t.exchange('purchase', lambda v:True)
    assert not w.sent


def test_universal_policy_never_falls_back_after_dispatch():
    from tester_spin.transport_policy import POLICY, execution_profile
    assert POLICY.may_fallback(dispatched=False,bootstrap_only=True,contract_supported=True)
    assert not POLICY.may_fallback(dispatched=True,bootstrap_only=True,contract_supported=True)
    assert not POLICY.may_fallback(dispatched=False,bootstrap_only=False,contract_supported=True)
    assert not POLICY.may_fallback(dispatched=False,bootstrap_only=True,contract_supported=False)
    assert execution_profile('new_provider')['gameplay']=='unimplemented'
    assert execution_profile('playtech')['gameplay']=='websocket'
    assert execution_profile('redtiger')['bootstrap']=='browser'


def test_playtech_independent_install_has_direct_socket_dependency():
    import tomllib
    from pathlib import Path
    project=tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))
    assert any(v.startswith('websocket-client') for v in project['project']['optional-dependencies']['playtech'])
