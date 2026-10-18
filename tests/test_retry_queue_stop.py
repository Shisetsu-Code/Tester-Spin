import threading
from types import SimpleNamespace
from unittest.mock import patch

def retry_harness(monkeypatch, *, mode='stopped', fail_cleanup=False, fail_bind=False):
    """Model OS ownership; detached descendants outlive the direct process."""
    import time
    from pathlib import Path
    import tools.run_retry_queue as queue
    import tester_spin.independent.processes as processes
    state=SimpleNamespace(owned=set(),starts=[],events=[],trees=[],gates=[],recorded=[],clock=0.0)
    shared=threading.Event();state.stop=shared
    class Gate(threading.Event):
        def set(self):
            assert state.trees[-1].bound, 'provider gate opened before process ownership'
            state.events.append('release')
            super().set()
            state.owned.add('browser'+str(len(state.starts)))
            if mode=='finished':
                state.starts[-1].alive=False
                state.owned.discard(state.starts[-1].pid)
    event_count=0
    def event():
        nonlocal event_count
        event_count+=1
        if event_count==1:return shared
        gate=Gate();state.gates.append(gate);return gate
    class Process:
        exitcode=0
        def __init__(self,target,args):
            self.args=args;self.alive=False;self.pid=100+len(state.starts)
        def start(self):
            assert not state.owned, 'next worker started while an earlier descendant was alive'
            state.events.append('start');state.starts.append(self);self.alive=True;state.owned.add(self.pid)
        def join(self,timeout):
            state.clock+=timeout
            if mode=='stopped':shared.set()
        def is_alive(self):return self.alive
        def terminate(self):
            state.events.append('terminate');self.alive=False;state.owned.discard(self.pid)
        def kill(self):self.terminate()
        def close(self):
            assert not self.alive
            state.events.append('process_close')
    class Tree:
        def __init__(self):self.bound=False;state.trees.append(self)
        def bind(self,pid):
            assert not state.gates[-1].is_set()
            if fail_bind:raise RuntimeError('cannot bind')
            state.events.append('bind');self.bound=True
        def stop_and_wait(self):
            state.events.append('tree_stop')
            if fail_cleanup:raise processes.UnsafeProcessTree('descendant remains alive')
            state.owned.clear()
            for process in state.starts:process.alive=False
        def close(self):
            self.stop_and_wait();state.events.append('tree_close')
    context=SimpleNamespace(Event=event,Process=Process)
    games=[SimpleNamespace(last_status='PENDIENTE',slug=str(i),name=str(i),provider='ka_gaming',
        url='https://example.invalid/'+str(i),symbol='') for i in range(2)]
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    monkeypatch.setattr(time,'monotonic',lambda:state.clock)
    monkeypatch.setattr(queue.mp,'get_context',lambda _:context)
    monkeypatch.setattr(processes,'ProcessTree',Tree)
    monkeypatch.setattr(queue,'provider_for',lambda *args:SimpleNamespace(key='ka_gaming'))
    monkeypatch.setattr(queue.sys,'argv',['run_retry_queue','ka_gaming','--statuses','PENDIENTE','--wall-timeout','1','--spins','3'])
    monkeypatch.setattr('tester_spin.storage.Storage',lambda *args:SimpleNamespace(list_games=lambda _:games,record_result=state.recorded.append))
    return queue,state


def test_provider_stop_cleans_descendants_before_returning(monkeypatch):
    queue,state=retry_harness(monkeypatch)
    assert queue.main()==0
    assert len(state.starts)==1
    assert not state.owned
    assert state.events[:3]==['start','bind','release']
    assert 'tree_close' in state.events and 'process_close' in state.events
    assert not state.recorded, 'a provider stop must not be mislabeled as a wall timeout'


def test_wall_timeout_cleans_descendants_before_next_game(monkeypatch):
    queue,state=retry_harness(monkeypatch,mode='timeout')
    assert queue.main()==0
    assert len(state.starts)==2
    assert not state.owned
    assert len(state.recorded)==2
    assert all(r.status=='ERROR' and r.error.startswith('RUNNER_WALL_TIMEOUT:') for r in state.recorded)
    assert all(r.requested_spins==3 and r.failed_spins==3 for r in state.recorded)
    assert state.events.index('tree_close')<state.events.index('start',1)


def test_normal_exit_still_cleans_detached_descendants(monkeypatch):
    queue,state=retry_harness(monkeypatch,mode='finished')
    assert queue.main()==0
    assert len(state.starts)==2 and not state.owned
    assert not state.recorded


def test_failed_cleanup_aborts_queue_without_next_worker(monkeypatch):
    import pytest
    from tester_spin.independent.processes import UnsafeProcessTree
    queue,state=retry_harness(monkeypatch,mode='timeout',fail_cleanup=True)
    with pytest.raises(UnsafeProcessTree):queue.main()
    assert len(state.starts)==1
    assert state.owned
    assert not state.recorded, 'unconfirmed cleanup cannot be reported as an ordinary timeout'


def test_failed_binding_never_releases_provider_gate(monkeypatch):
    import pytest
    queue,state=retry_harness(monkeypatch,fail_bind=True)
    with pytest.raises(RuntimeError,match='cannot bind'):queue.main()
    assert len(state.starts)==1 and not state.owned
    assert not state.gates[0].is_set()
    assert 'terminate' in state.events


def test_worker_entry_waits_for_ownership_before_loading_provider(monkeypatch):
    from pathlib import Path
    import tools.run_retry_queue as queue
    entered=threading.Event();release=threading.Event();created=threading.Event();failures=[]
    class Gate:
        def wait(self):
            entered.set()
            assert release.wait(2), 'ownership gate was never released'
    def provider(*args):created.set();return SimpleNamespace()
    monkeypatch.setattr(queue,'provider_for',provider)
    monkeypatch.setattr('tester_spin.storage.Storage',lambda *args:SimpleNamespace())
    monkeypatch.setattr('tester_spin.scheduler.run_game_tests',lambda *args,**kwargs:None)
    def run():
        try:queue._run_one(str(Path(__file__).resolve().parents[1]),'synthetic',SimpleNamespace(name='synthetic'),1,1,threading.Event(),Gate())
        except BaseException as exc:failures.append(exc)
    worker=threading.Thread(target=run);worker.start()
    try:
        assert entered.wait(2), 'worker did not reach ownership gate'
        assert not created.is_set()
    finally:
        release.set();worker.join(2)
    assert not worker.is_alive() and not failures
    assert created.is_set()


def test_stop_before_gate_release_prevents_provider_loading(monkeypatch):
    import tools.run_retry_queue as queue
    shared=threading.Event();gate=threading.Event();gate.set();shared.set()
    def forbidden(*args):raise AssertionError('cancelled worker must not load a provider')
    monkeypatch.setattr(queue,'provider_for',forbidden)
    monkeypatch.setattr('tester_spin.storage.Storage',forbidden)
    queue._run_one('unused','synthetic',SimpleNamespace(name='synthetic'),1,1,shared,gate)


def test_rate_rejection_sets_shared_stop_after_recording(monkeypatch):
    from pathlib import Path
    import tools.run_retry_queue as queue
    shared=threading.Event();recorded=[]
    game=SimpleNamespace(name='synthetic')
    monkeypatch.setattr(queue,'provider_for',lambda *args:SimpleNamespace(key='synthetic'))
    result=SimpleNamespace(error='Yggdrasil: HTTP 429 en authenticate; petición no reintentada')
    def scheduler(*args,**kwargs):kwargs['on_result'](result)
    with patch('tester_spin.storage.Storage',return_value=SimpleNamespace(record_result=recorded.append)),patch('tester_spin.scheduler.run_game_tests',scheduler):
        queue._run_one(str(Path(__file__).resolve().parents[1]),'synthetic',game,1,1,shared)
    assert recorded==[result]
    assert shared.is_set()
