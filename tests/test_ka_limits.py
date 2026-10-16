import threading
from unittest.mock import MagicMock
import pytest
from tester_spin.models import Game

def test_ka_gate_never_starts_more_than_30_requests_in_one_second():
 from tester_spin.providers.ka_gaming.limits import RequestGate
 now=[0.0]
 class Stop:
  def is_set(self):return False
  def wait(self,seconds):now[0]+=seconds;return False
 gate=RequestGate(clock=lambda:now[0]);starts=[]
 for _ in range(65):gate.acquire(Stop());starts.append(now[0])
 assert all(sum(t<=x<t+1 for x in starts)<=30 for t in starts)
 assert starts[30]>=1 and starts[60]>=2

def test_ka_waiting_request_can_be_cancelled():
 from tester_spin.providers.ka_gaming.limits import RequestGate
 gate=RequestGate();stop=threading.Event();stop.set()
 with pytest.raises(InterruptedError):gate.acquire(stop)

def test_start_404_preserves_shared_run_and_sends_no_session_cleanup(tmp_path):
 from tester_spin.providers.ka_gaming.runtime import run_rmp_game
 stop=threading.Event();http=MagicMock()
 response=MagicMock(status_code=404,text='Not Found');response.raise_for_status.side_effect=RuntimeError('HTTP 404');http.post.return_value=response
 g=Game('ka_gaming','example','Example','https://gamesdemo.kaga88.com/?g=Example&p=demo',symbol='Example')
 result=run_rmp_game(g,http=http,root=tmp_path,profile=('2070','version','literal'),modes=[{'id':'SPIN'}],spins=100,timeout_s=1,stop_event=stop,progress=lambda _:None)
 assert not stop.is_set() and http.post.call_count==1 and result.status=='ERROR'

def test_ka_provider_leaves_game_delay_to_user(tmp_path):
 from tester_spin.providers.ka_gaming.adapter import KAGamingProvider
 from tester_spin import scheduler
 provider=KAGamingProvider(tmp_path)
 assert getattr(provider, "min_game_start_interval_s", 0)==0


def test_404_during_spin_skips_cleanup_of_an_open_session(tmp_path):
    from tester_spin.providers.ka_gaming.runtime import run_rmp_game
    stop = threading.Event()
    http = MagicMock()
    initial = MagicMock(status_code=200, text='{}')
    initial.json.return_value = {'e':False,'ec':0,'un':'demo','si':'session',
        'sgr':{'lsd':{'fs':False,'rf':0,'acb':0,'sel':5,'cps':1,'atb':0,'dn':.01}}}
    blocked = MagicMock(status_code=404, text='Not Found')
    blocked.raise_for_status.side_effect = RuntimeError('HTTP 404')
    http.post.side_effect = [initial, blocked]
    game = Game('ka_gaming','example','Example','https://gamesdemo.kaga88.com/?g=Example&p=demo',symbol='Example')
    result = run_rmp_game(game,http=http,root=tmp_path,profile=('2070','version','literal'),
        modes=[{'id':'SPIN'}],spins=100,timeout_s=1,stop_event=stop,progress=lambda _:None)
    assert not stop.is_set() and http.post.call_count == 2
    assert result.successful_spins == 0


def test_scheduler_waits_60_seconds_even_when_ui_delay_is_zero(tmp_path, monkeypatch):
    from tester_spin import scheduler
    from test_scheduler import _OrderingProvider
    provider = _OrderingProvider(tmp_path)
    provider.min_game_start_interval_s = 60
    now = [0.0]
    class Stop:
        def is_set(self): return False
        def wait(self, seconds): now[0] += seconds; return False
    monkeypatch.setattr(scheduler.time, 'monotonic', lambda: now[0])
    starts = []
    def progress(message):
        if message.startswith('Iniciando'): starts.append(now[0])
    games = [Game('limited',str(i),str(i),'https://example.test') for i in range(2)]
    scheduler.run_game_tests(provider,games,concurrency=1,spins_per_game=1,
        delay_between_starts_s=0,timeout_s=1,stop_event=Stop(),progress=progress,on_result=lambda _:None)
    assert starts == [0,60]


def test_operation_delay_spaces_requests_across_games():
    from tester_spin.providers.ka_gaming.limits import RequestGate
    now=[0.0]
    class Stop:
        def is_set(self):return False
        def wait(self, seconds):now[0]+=seconds;return False
    gate=RequestGate(clock=lambda:now[0])
    gate.configure_delay(0.2)
    starts=[]
    for _ in range(5):gate.acquire(Stop());starts.append(now[0])
    assert starts==pytest.approx([0,.2,.4,.6,.8])
    gate.configure_delay(0)
    gate.acquire(Stop())
    assert now[0]==pytest.approx(.8)

@pytest.mark.parametrize('value',[-1,float('inf'),float('nan')])
def test_operation_delay_rejects_invalid_values(value):
    from tester_spin.providers.ka_gaming.limits import RequestGate
    with pytest.raises(ValueError):RequestGate().configure_delay(value)
