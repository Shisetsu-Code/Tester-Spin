import pytest
from tester_spin.hardfire_launcher import HardFireClient,HardFireError

class Response:
 def __init__(self,value):self.value=value
 def raise_for_status(self):pass
 def json(self):return self.value

class Session:
 def __init__(self):self.calls=[];self.trust_env=True;self.error=False
 def get(self,url,**kwargs):return Response({'ok':True,'service':'hardfire-local-mcp'})
 def post(self,url,**kwargs):
  self.calls.append(kwargs['json'])
  return Response({'id':kwargs['json']['id'],'result':{'isError':self.error,'content':[{'type':'text','text':'{"tab_id":12}'}]}})

def test_game_opens_in_a_new_visible_hardfire_tab():
 session=Session();client=HardFireClient(session=session)
 assert client.open_game('https://example.com/demo')['tab_id']==12
 assert session.trust_env is False
 assert [(c['params']['name'],c['params']['arguments']) for c in session.calls]==[
  ('hardfire_browser',{'mode':'visible'}),('hardfire_tab_new',{'url':'https://example.com/demo','activate':True})]

def test_only_local_endpoints_and_http_games_are_allowed():
 for endpoint in ('https://example.com/mcp','http://example.com/mcp','http://127.0.0.1:8765/mcp?token=x'):
  with pytest.raises(HardFireError):HardFireClient(endpoint=endpoint)
 session=Session();client=HardFireClient(session=session)
 for url in ('file:///secret','javascript:alert(1)','https://u:p@example.com/'):
  with pytest.raises(HardFireError):client.open_game(url)
 assert not session.calls

def test_rpc_error_never_reports_the_game_opened():
 session=Session();session.error=True
 with pytest.raises(HardFireError):HardFireClient(session=session).open_game('https://example.com/')
