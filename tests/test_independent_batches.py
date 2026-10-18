import contextlib,json,threading
from pathlib import Path
import pytest
from tester_spin.models import Game,GameTestResult

def games(n=5):return [Game('nolimit_city','game'+str(i),'Game '+str(i),'https://playin.com/embed/v1/demo/Game'+str(i),symbol='Game'+str(i)) for i in range(n)]
def result(game,error=''):return GameTestResult(game.provider,game.slug,game.name,game.url,1,0,1,'PARCIAL',symbol=game.symbol,error=error)

class Tunnel:
 def __init__(self,ip,events):self.ip=ip;self.events=events
 def __enter__(self):self.events.append(('up',self.ip));return self
 def __exit__(self,*a):self.events.append(('down',self.ip))
 def verify(self):return self.ip

def test_batches_change_only_between_completed_games_and_share_ip_quota():
 from tester_spin.independent.batches import run_batches
 events=[];outputs=[];profiles=['first','same','last'];ips={'first':'203.0.113.1','same':'203.0.113.1','last':'203.0.113.2'}
 def execute(game):events.append(('game',game.slug));return result(game)
 report=run_batches(games(),execute=execute,record=outputs.append,profiles=profiles,games_per_ip=2,
  tunnel_factory=lambda p:Tunnel(ips[p],events),stop_event=threading.Event())
 assert report['attempted']==4 and report['pending']==1 and report['reason']=='IP_QUOTA_EXHAUSTED'
 assert len(outputs)==4
 assert report['ip_counts']=={'203.0.113.1':2,'203.0.113.2':2}
 assert events==[('up','203.0.113.1'),('game','game0'),('game','game1'),('down','203.0.113.1'),
  ('up','203.0.113.1'),('down','203.0.113.1'),('up','203.0.113.2'),('game','game2'),('game','game3'),('down','203.0.113.2')]

def test_rate_limit_stops_without_switching_ip():
 from tester_spin.independent.batches import run_batches
 events=[]
 report=run_batches(games(),execute=lambda g:result(g,'HTTP 429'),record=lambda _:None,profiles=['one','two'],games_per_ip=2,
  tunnel_factory=lambda p:Tunnel('203.0.113.'+('1' if p=='one' else '2'),events),stop_event=threading.Event())
 assert report['attempted']==1 and report['reason']=='RATE_LIMIT'
 assert events==[('up','203.0.113.1'),('down','203.0.113.1')]

def test_no_vpn_run_uses_normal_finalized_result():
 from tester_spin.independent.batches import run_batches
 outputs=[]
 report=run_batches(games(2),execute=result,record=outputs.append,profiles=[],games_per_ip=None,stop_event=threading.Event())
 assert report['attempted']==2 and report['reason']=='COMPLETED' and len(outputs)==2

def test_vpn_failure_does_not_fall_back_to_direct_network():
 from tester_spin.independent.batches import run_batches
 from tester_spin.vpn.wireguard import NetworkContextError
 calls=[]
 def failed(p):raise NetworkContextError('unavailable')
 report=run_batches(games(),execute=lambda g:calls.append(g),record=lambda _:None,profiles=['one'],games_per_ip=2,
  tunnel_factory=failed,stop_event=threading.Event())
 assert not calls and report['reason']=='VPN_ERROR' and report['pending']==5

def test_network_change_after_game_downgrades_ok_before_recording():
 from tester_spin.independent.batches import run_batches
 from tester_spin.vpn.wireguard import NetworkContextError
 class Changed(Tunnel):
  def verify(self):
   self.events.append('verify')
   if self.events.count('verify')>1:raise NetworkContextError('changed')
   return self.ip
 outputs=[]
 def execute(g):r=result(g);r.status='OK';return r
 report=run_batches(games(1),execute=execute,record=outputs.append,profiles=['one'],games_per_ip=2,
  tunnel_factory=lambda p:Changed('203.0.113.1',[]),stop_event=threading.Event())
 assert outputs[0].status=='PARCIAL' and report['reason']=='VPN_ERROR'

def test_cancelled_before_start_does_not_activate_tunnel():
 from tester_spin.independent.batches import run_batches
 stop=threading.Event();stop.set()
 report=run_batches(games(),execute=lambda _:pytest.fail('execute'),record=lambda _:None,profiles=['one'],games_per_ip=2,
  tunnel_factory=lambda _:pytest.fail('activate'),stop_event=stop)
 assert report['attempted']==0 and report['reason']=='CANCELLED'

@pytest.mark.parametrize('status,set_stop',[('CANCELADO',True),('CANCELADO',False),('PARCIAL',True)])
def test_last_game_cancellation_is_reported_with_no_pending_games(status,set_stop):
 from tester_spin.independent.batches import run_batches
 stop=threading.Event();outputs=[]
 def execute(game):
  if set_stop:stop.set()
  value=result(game);value.status=status;return value
 report=run_batches(games(1),execute=execute,record=outputs.append,profiles=[],games_per_ip=None,stop_event=stop)
 assert report['attempted']==1 and report['pending']==0
 assert len(outputs)==1
 assert report['reason']=='CANCELLED'

def test_last_game_rate_limit_retains_priority_over_cancellation():
 from tester_spin.independent.batches import run_batches
 stop=threading.Event()
 def execute(game):stop.set();return result(game,'HTTP 429')
 report=run_batches(games(1),execute=execute,record=lambda _:None,profiles=[],games_per_ip=None,stop_event=stop)
 assert report['pending']==0 and report['reason']=='RATE_LIMIT'

def test_last_game_vpn_error_retains_priority_over_cancellation():
 from tester_spin.independent.batches import run_batches
 from tester_spin.vpn.wireguard import NetworkContextError
 stop=threading.Event()
 class Changed(Tunnel):
  def verify(self):
   if stop.is_set():raise NetworkContextError('changed')
   return self.ip
 def execute(game):stop.set();return result(game)
 report=run_batches(games(1),execute=execute,record=lambda _:None,profiles=['one'],games_per_ip=1,
  tunnel_factory=lambda p:Changed('203.0.113.1',[]),stop_event=stop)
 assert report['pending']==0 and report['reason']=='VPN_ERROR'

def test_reconstructing_result_preserves_attempts_and_feature_evidence():
 from tester_spin.independent.worker import result_from_payload
 from tester_spin.models import SpinAttempt
 r=result(games(1)[0]);r.attempts=[SpinAttempt(1,True,terminal=True)];r.feature_domains={'purchase':{'complete':True,'options':[]}}
 restored=result_from_payload(r.to_dict())
 assert isinstance(restored.attempts[0],SpinAttempt) and restored.attempts[0].terminal
 assert restored.feature_domains==r.feature_domains

def test_failed_tree_cleanup_is_fatal_and_never_rotates_or_continues():
 from tester_spin.independent.batches import run_batches
 from tester_spin.independent.processes import UnsafeProcessTree
 calls=[]
 class Hold(Tunnel):
  def __exit__(self,kind,exc,tb):self.events.append(('hold' if getattr(exc,'preserve_network',False) else 'down',self.ip))
 def execute(game):calls.append(game.slug);raise UnsafeProcessTree('live')
 with pytest.raises(UnsafeProcessTree):
  run_batches(games(),execute=execute,record=lambda _:None,profiles=['one','two'],games_per_ip=2,
   tunnel_factory=lambda p:Hold('203.0.113.1',calls),stop_event=threading.Event())
 assert calls==[('up','203.0.113.1'),'game0',('hold','203.0.113.1')]
