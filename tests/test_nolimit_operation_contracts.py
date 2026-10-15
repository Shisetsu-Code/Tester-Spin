from pathlib import Path
import json,copy
import pytest

def resolver(*args,**kwargs):
    from tester_spin.providers.nolimit_city.contracts import resolve_operation
    return resolve_operation(*args,**kwargs)

def test_normalized_contract_contains_action_ack_and_money():
    answer={'game':{'mode':'FREESPIN','nextMode':'FREESPIN','freespinsLeft':3},'features':{'available':[]}}
    c=resolver(answer)
    assert c['family']=='AUTOMATIC_CONTINUATION'
    assert c['request']=={'type':'zeroBet','bet':'0.00'}
    assert c['acknowledgment']=={'phase':'FREESPIN','kind':'PHASE_ENTRY'}
    assert c['money']['settlement']=='ROUND_LEDGER'

def test_shared_contract_does_not_invent_choice_domain_from_capture():
    from tester_spin.providers.nolimit_city.errors import Unlearned
    with pytest.raises(Unlearned):resolver({'game':{'nextMode':'UNKNOWN_PICK','selection':-1},'features':{'available':[]}})

def test_contract_ack_is_separate_from_monetary_closure():
    from tester_spin.providers.nolimit_city.contracts import confirm_operation
    c=resolver({'game':{'nextMode':'FREESPIN','freespinsLeft':2},'features':{'available':[]}})
    confirm_operation(c,{'game':{'mode':'FREESPIN','nextMode':'FREESPIN'}})
    with pytest.raises(ValueError):confirm_operation(c,{'game':{'mode':'WRONG','nextMode':'NORMAL'}})

def test_corpus_audits_later_rounds_even_when_an_earlier_action_is_unknown():
    from tester_spin.providers.nolimit_city.corpus import audit_exchanges
    row=next(r for r in json.loads((Path(__file__).parent/'fixtures/nolimit_reference_five_2.json').read_text()) if r['reference']=='infectious5')
    init=row['init'];root=copy.deepcopy(row['steps'][0]);unknown=copy.deepcopy(root)
    unknown['response']['game']['nextMode']='UNKNOWN_PICK';unknown['response']['features']={}
    # The next response closes the first round; another normal round follows.
    close=copy.deepcopy(root);close['request']={'type':'zeroBet','bet':'0.00'}
    close['response']['game']['mode']='UNKNOWN_PICK';close['response']['balance']=unknown['response']['balance']
    next_round=copy.deepcopy(root);next_round['response']['balance']=str(float(close['response']['balance'])-.2)
    report=audit_exchanges([{'request':{'type':'init'},'response':init},unknown,close,next_round])
    assert report['steps_checked']==3
    assert report['unresolved_actions'][0]['phase']=='UNKNOWN_PICK'
    assert report['ok_certified'] is False


def test_corpus_importer_separates_connections_and_rejects_unmatched_responses():
    from tester_spin.providers.nolimit_city.corpus import matched_sessions
    rows=[{'connection':0,'direction':'sent','message':{'id':'same','content':{'type':'init'}}},
          {'connection':1,'direction':'sent','message':{'id':'same','content':{'type':'init'}}},
          {'connection':0,'direction':'received','message':{'id':'same','init':'ok'}},
          {'connection':1,'direction':'received','message':{'id':'same','init':'ok'}}]
    sessions,issues=matched_sessions(rows)
    assert len(sessions)==2 and not issues
    sessions,issues=matched_sessions(rows+[{'connection':0,'direction':'received','message':{'id':'other'}}])
    assert issues[0]['reason']=='UNMATCHED_RESPONSE'
