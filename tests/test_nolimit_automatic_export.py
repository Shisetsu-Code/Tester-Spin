import copy
import pytest
from tester_spin.providers.nolimit_city.runtime import NolimitSession
from tests.test_nolimit_fixed_signals import SOURCE,ANSWER
from tests.test_nolimit_executor import Demo,run

MODE={'id':'SPIN','kind':'SPIN','stake':'.20'}

def test_confirmed_automatic_payload_is_retained_per_root_without_invented_choices(tmp_path):
    session=NolimitSession();session.choice_client=SOURCE;mode=copy.deepcopy(MODE)
    request=session.next_command(ANSWER,tmp_path,'SPIN',mode,raw_answer=ANSWER)
    session.sync_choices(mode)
    assert mode.get('automatic_actions',[])==[]
    session.confirm_pending_choice({'game':{'mode':'UNSEEN_SIGNAL','nextMode':'NORMAL'}})
    assert session.sync_choices(mode)
    assert mode['choice_domains']==[]
    assert mode['automatic_actions'][0]['request']==request
    assert len(mode['automatic_actions'][0]['evidence']['client_sha256'])==64
    assert mode['automatic_actions'][0]['acknowledgment']['phase']=='UNSEEN_SIGNAL'


def test_unacknowledged_action_is_not_exported(tmp_path):
    session=NolimitSession();session.choice_client=SOURCE;mode=copy.deepcopy(MODE)
    session.next_command(ANSWER,tmp_path,'SPIN',mode,raw_answer=ANSWER)
    with pytest.raises(ValueError):session.confirm_pending_choice({'game':{'mode':'WRONG','nextMode':'NORMAL'}})
    session.sync_choices(mode)
    assert mode.get('automatic_actions',[])==[]


def test_automatic_action_observation_and_semantics_survive_farm_export(tmp_path,monkeypatch):
    provider,game,result=run(tmp_path,monkeypatch,Demo())
    action={'state':'SIGNAL','request':{'type':'zeroBet','bet':'0.00','playerInteraction':{'selectedIndex':'7'}},'evidence':{'client_sha256':'a'*64}}
    result.discovered_modes[0]['automatic_actions']=[action]
    contract=provider.build_farm_contract(game,result)
    assert contract['modes'][0]['options']['automatic_actions']==[action]
    assert not provider.validate_farm_contract(contract)
    contract['protocol']['static'].pop('source_bound_automatic_observations')
    assert 'NOLIMIT_AUTOMATIC_OBSERVATIONS_REQUIRED' in provider.validate_farm_contract(contract)
