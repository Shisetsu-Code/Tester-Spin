import copy,json,threading
from pathlib import Path
from decimal import Decimal
import pytest
from tester_spin.providers.nolimit_city import NolimitCityProvider
from tester_spin.providers.nolimit_city.catalog import games_from_rows

INIT=json.loads((Path(__file__).parent/'fixtures/nolimit_airport_protocol.json').read_text(encoding='utf-8'))[1]['message']

class Demo:
 def __init__(self,*,bad_money=False,choice=False):
  self.init=copy.deepcopy(INIT);self.balance=Decimal('10000');self.pending=False;self.calls=[]
  self.bad_money=bad_money;self.choice=choice;self.closed=False
 def open(self,game,http,timeout,stop,directory):return copy.deepcopy(self.init)
 def exchange(self,content,directory):
  self.calls.append(content);kind=content['type'];selector=content.get('featureName')
  if self.pending:
   assert kind=='zeroBet' and Decimal(content['bet'])==0
   self.pending=False;done=True;win=Decimal('2');buy=True;boost=False
   self.balance+=win
  else:
   assert kind in {'normalBet','featureBet'}
   buy=selector is not None and next(x for x in self.init['game']['featureBuyTimesBetValue'] if x['name']==selector)['type']=='FREESPIN'
   boost=selector is not None and not buy
   multiplier=next(x['price'] for x in self.init['game']['featureBuyTimesBetValue'] if x['name']==selector) if selector else 1
   self.balance-=Decimal(content['bet'])*Decimal(str(multiplier));self.pending=buy;done=not buy;win=Decimal(0)
  response={'game':{'mode':'FREESPIN' if kind=='zeroBet' else 'NORMAL','nextMode':'NORMAL' if done else 'FREESPIN',
    'freespinsLeft':0 if done else 1,'win':str(win),'accumulatedRoundWin':str(win),
    'playedBetValue':content['bet'] if kind!='zeroBet' else self.stake,
    'wasFeatureBuy':buy,'wasBoostedBet':boost,'wasExtraSpin':False},
    'features':{'available':['UNLEARNED_CHOICE'] if self.choice and buy else []},'balance':str(self.balance+int(self.bad_money))}
  if kind!='zeroBet':self.stake=content['bet']
  return response
 def close(self):self.closed=True

def run(tmp_path,monkeypatch,demo):
 import tester_spin.providers.nolimit_city.adapter as module
 monkeypatch.setattr(module,'NolimitSession',lambda:demo,raising=False)
 provider=NolimitCityProvider(tmp_path)
 game=games_from_rows([{'code':'RenamedExample','name':'Renamed Example','studio':'Nolimit City','url':'https://playin.com/embed/v1/demo/RenamedExample'}])[0]
 result=provider.test_game(game,spins=1,timeout_s=2,stop_event=threading.Event(),progress=lambda _:None)
 return provider,game,result

def test_live_executor_covers_server_selectors_prices_closure_and_return(tmp_path,monkeypatch):
 demo=Demo();provider,game,result=run(tmp_path,monkeypatch,demo)
 assert result.status=='OK',result.error
 assert demo.closed
 assert {c['featureName'] for c in demo.calls if c['type']=='featureBet'}==set(INIT['allowedFeatureBets'])
 assert sum(c['type']=='zeroBet' for c in demo.calls)==4
 assert [c['type'] for c in demo.calls[-2:]]==['normalBet','normalBet']
 assert len(result.feature_domains['purchase']['options'])==4
 assert len(result.feature_domains['feature_spin']['options'])==3
 assert provider.finalize_test_result(result,progress=lambda _:None).status=='OK'

def test_money_mismatch_never_certifies_or_sends_next_bet(tmp_path,monkeypatch):
 demo=Demo(bad_money=True);_,_,result=run(tmp_path,monkeypatch,demo)
 assert result.status!='OK' and 'saldo' in result.error.lower()
 assert len(demo.calls)==1 and demo.closed

def test_unknown_choice_preserved_without_inventing_continuation(tmp_path,monkeypatch):
 demo=Demo(choice=True);_,_,result=run(tmp_path,monkeypatch,demo)
 assert result.status=='PARCIAL'
 assert 'UNLEARNED_CHOICE' in result.error
 assert not any(c['type']=='zeroBet' for c in demo.calls)

@pytest.mark.parametrize('mutation',[lambda d:d.pop('featureBetLevels'),lambda d:d['featureBetLevels'].pop(d['allowedFeatureBets'][0]),
 lambda d:d['gameClientConfiguration'].update(featureBuyEnabled=False),lambda d:d['allowedFeatureBets'].append('UNQUOTED')])
def test_incomplete_or_contradictory_declaration_never_executes(tmp_path,monkeypatch,mutation):
 demo=Demo();mutation(demo.init);_,_,result=run(tmp_path,monkeypatch,demo)
 assert result.status!='OK' and not demo.calls

def test_unknown_server_category_is_not_guessed_by_name_or_price(tmp_path,monkeypatch):
 demo=Demo();demo.init['game']['featureBuyTimesBetValue'][0]['type']='NEW_PROVIDER_TYPE'
 _,_,result=run(tmp_path,monkeypatch,demo)
 assert result.status=='PARCIAL'
 assert any(m['kind']=='UNKNOWN_FEATURE' for m in result.discovered_modes)

def test_cancelled_does_not_open_session(tmp_path,monkeypatch):
 provider=NolimitCityProvider(tmp_path);game=games_from_rows([{'code':'Example','name':'Example','studio':'Nolimit City','url':'https://playin.com/embed/v1/demo/Example'}])[0]
 stop=threading.Event();stop.set()
 result=provider.test_game(game,spins=1,timeout_s=1,stop_event=stop,progress=lambda _:None)
 assert result.status=='CANCELADO'

def test_verified_executor_exports_session_free_contract(tmp_path,monkeypatch):
 demo=Demo();provider,game,result=run(tmp_path,monkeypatch,demo)
 contract=provider.build_farm_contract(game,result)
 assert contract['ready'],contract['unresolved']
 assert not provider.validate_farm_contract(contract)
 assert contract['protocol']['transport']=='websocket-rc4-lzw'
 result.structural_map={}
 assert not provider.build_farm_contract(game,result)['ready']

def test_boosts_do_not_invent_antebet_count(tmp_path,monkeypatch):
 from tester_spin.feature_summary import feature_table_counts,feature_summary
 _,_,result=run(tmp_path,monkeypatch,Demo())
 assert feature_table_counts(result.to_dict())==(4,None)
 assert 'Apuestas mejoradas: 3' in feature_summary(result.to_dict())

def test_websocket_wait_respects_stop_without_receiving():
 from tester_spin.providers.nolimit_city.runtime import NolimitSession,Unlearned
 session=NolimitSession();session.timeout=1;session.stop=threading.Event();session.stop.set()
 with pytest.raises(Unlearned,match='detenida'):session._receive()

def test_websocket_wait_has_deadline(monkeypatch):
 from tester_spin.providers.nolimit_city import runtime
 from curl_cffi import CurlError
 from curl_cffi.const import CurlECode
 class Curl:
  def getinfo(self,*args):return 123
 class Socket:
  curl=Curl()
  def recv_fragment(self):raise CurlError('retry',CurlECode.AGAIN)
 ticks=iter([0,0,0,2,2]);monkeypatch.setattr(runtime.time,'monotonic',lambda:next(ticks))
 monkeypatch.setattr(runtime,'select',lambda *args:None)
 session=runtime.NolimitSession();session.timeout=1;session.stop=threading.Event();session.socket=Socket()
 with pytest.raises(TimeoutError,match='no se reenvía'):session._receive()

def test_bootstrap_rate_limit_keeps_http_code_without_session_data(tmp_path,monkeypatch):
 import tester_spin.providers.nolimit_city.adapter as module
 class Limited:
  def open(self,*args):
   exc=RuntimeError('secret-session-url')
   exc.response=type('Response',(),{'status_code':429})()
   raise exc
  def close(self):pass
 monkeypatch.setattr(module,'NolimitSession',Limited)
 provider=NolimitCityProvider(tmp_path)
 game=games_from_rows([{'code':'Example','name':'Example','studio':'Nolimit City','url':'https://playin.com/embed/v1/demo/Example'}])[0]
 result=provider.test_game(game,spins=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
 assert 'HTTP 429' in result.error and 'secret-session-url' not in result.error


def test_unknown_initial_state_preserves_server_declared_counts_without_betting(tmp_path,monkeypatch):
 from tester_spin.feature_summary import feature_table_counts
 demo=Demo();demo.init['features']={'available':['FREESPINS']}
 _,_,result=run(tmp_path,monkeypatch,demo)
 assert result.status=='PARCIAL' and not demo.calls
 assert feature_table_counts(result.to_dict())[0]==4
 assert len(result.feature_domains['purchase']['options'])==4
 assert all(not mode['validated'] for mode in result.discovered_modes)
