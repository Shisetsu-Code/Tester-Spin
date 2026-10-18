import json
import threading
from pathlib import Path
from unittest.mock import patch
import pytest
from tester_spin.providers.playtech.direct_runtime import DemoSession

class Wire:
    def __init__(self):self.queue=['1::'];self.sent=[];self.closed=False
    def settimeout(self,t):pass
    def close(self):self.closed=True
    def recv(self):return self.queue.pop(0)
    def send(self,p):
        self.sent.append(p)
        if not p.startswith('3:::'):return
        q=json.loads(p[4:]);d=q['data'];kind=d['_type']
        response={'InitGameSession':'InitGameSessionResponse','GetClientState':'GetClientStateResponse','com.pt.gpas.config.GetGameConfigurationRequest':'GetGameConfigurationResponse'}[kind]
        self.queue.append('3:::'+json.dumps({'correlationId':q['correlationId'],'data':{'_type':response,'data':{}}}))
        if kind=='GetClientState':self.queue.append('3:::'+json.dumps({'data':{'_type':'BalanceNotification','balance':[{'_type':'MonetaryBalanceData','amount':1000}]}}))

class Session(DemoSession):
    def _get(self,url,*,as_json=True):
        if 'gpasclientconf' in url:return {'id':'1.2'}
        if 'logical_bundle' in url:return {'games':{self.code:'/gpasdistributed/igv/'+self.code+'/1/'}}
        if 'manifest.json' in url:return {'gameCode':self.code,'javascript':['client.js'],'setup':{'usesScopedConfiguration':False}}
        if 'client.js' in url:return '''document.createElement("script").setAttribute("src","../game/js/bundle.js")'''
        if 'bundle.js' in url:return 'GLU.game.playMoney 40021 48775'
        if 'env_config' in url:return {'server':{'host':'gpas-stg.playtechone.com','secure':'true'}}
        if 'socket.io' in url:return 'freshid:60:60:websocket'
        raise AssertionError(url)

def test_fresh_identity_each_session_and_no_browser(tmp_path):
    identities=[]
    for i in range(2):
        w=Wire()
        with patch('websocket.create_connection',return_value=w):
            with Session('gpas_fixture',tmp_path/str(i),1,threading.Event()) as s:
                assert s.demo_verified and s.balance==1000
                init=json.loads(w.sent[0][4:])['data']
                assert init['real']==0 and init['resume'] is False
                assert init['username']==init['token']
                identities.append(init['username'])
                assert s.browser is None
                config=json.loads(w.sent[-1][4:])['data']
                assert config['scoped'] is True
        assert w.closed
        assert (tmp_path/str(i)/'session.har').is_file()
    assert identities[0]!=identities[1]

def test_unconfirmed_session_cannot_send_wager(tmp_path):
    s=Session('gpas_fixture',tmp_path,1,threading.Event())
    with pytest.raises(ValueError,match='DEMO_MODE_NOT_CONFIRMED'):s.exchange({}, {})
    s.http.close()

def test_cleanup_on_bootstrap_failure(tmp_path):
    w=Wire()
    with patch('websocket.create_connection',return_value=w),patch.object(Session,'_request',side_effect=ValueError('rejected')):
        with pytest.raises(ValueError,match='rejected'):
            with Session('gpas_fixture',tmp_path,1,threading.Event()):pass
    assert w.closed


def test_glu6_manifest_scripts_use_game_directory(tmp_path):
    class Glu6(Session):
        def _get(self,url,*,as_json=True):
            if 'manifest.json' in url:return {'gameCode':self.code,'env':{'glu6':True},'javascript':['index.js']}
            if url.endswith('index.js'):
                assert url.endswith('/game/index.js')
                return 'GLU.game.playMoney 40021 48775'
            return super()._get(url,as_json=as_json)
    with patch('websocket.create_connection',return_value=Wire()):
        with Glu6('gpas_fixture',tmp_path,1,threading.Event()) as s:
            assert s.demo_verified
