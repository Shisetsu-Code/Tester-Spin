import pytest
from tester_spin.providers.nolimit_city.contracts import resolve_operation
from tester_spin.providers.nolimit_city.runtime import NolimitSession

ANSWER={'game':{'mode':'NORMAL','nextMode':'SPECIAL','freespinsLeft':0},'features':{'available':[]}}

def test_direct_demo_context_is_explicit_caller_policy_not_response_data(monkeypatch):
    import tester_spin.providers.nolimit_city.client_actions as actions
    def automatic(source,answer,*,direct_demo_transport=False):
        return {'type':'zeroBet','bet':'0.00'} if direct_demo_transport is True else None
    monkeypatch.setattr(actions,'automatic_command',automatic)
    contract=resolve_operation(ANSWER,client_source='CLIENT',direct_demo_transport=True)
    assert contract['request']=={'type':'zeroBet','bet':'0.00'}
    with pytest.raises(ValueError):resolve_operation({**ANSWER,'direct_demo_transport':True},client_source='CLIENT')


def test_unopened_session_does_not_attest_direct_demo_context(tmp_path,monkeypatch):
    import tester_spin.providers.nolimit_city.contracts as contracts
    def resolve(answer,mode,**context):
        assert context['direct_demo_transport'] is False
        return {'state':'SPECIAL','request':{'type':'zeroBet','bet':'0.00'},'domain':None,'evidence':{'source':'CLIENT'}}
    monkeypatch.setattr(contracts,'resolve_operation',resolve)
    session=NolimitSession();session.choice_client='CLIENT'
    assert session.next_command(ANSWER,tmp_path,'SPIN')=={'type':'zeroBet','bet':'0.00'}


@pytest.mark.parametrize('fresh',[True,False])
def test_demo_transport_attestation_requires_fresh_server_initialization(tmp_path,monkeypatch,fresh):
    import copy,threading
    from types import SimpleNamespace
    from tests.test_nolimit_executor import INIT
    reply=copy.deepcopy(INIT);reply['game']['isRestoreState']=not fresh
    session=NolimitSession()
    monkeypatch.setattr(session,'_exchange',lambda *args,**kwargs:reply)
    class Http:
        def get(self,*args,**kwargs):return SimpleNamespace(json=lambda:{'name':'Example','version':'1.2.3'},raise_for_status=lambda:None)
        def post(self,*args,**kwargs):return SimpleNamespace(json=lambda:{'key':'test-only','url':'https://demo.nolimitcity.com/EjsGameWeb/gs'},raise_for_status=lambda:None,status_code=200)
        def ws_connect(self,*args,**kwargs):return object()
    directory=tmp_path/'game'/'tests'/'run'/'bootstrap';directory.mkdir(parents=True)
    session.open(SimpleNamespace(symbol='Example'),Http(),1,threading.Event(),directory)
    assert session.direct_demo_transport is fresh
