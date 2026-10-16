import json,copy,unittest
from pathlib import Path
from tester_spin.providers.redtiger.base_state import classify_base_state
class PaidBaseTests(unittest.TestCase):
 def test_settled_nsp_empty_nested_state_is_not_an_active_feature(self):
  row=json.loads((Path(__file__).parent/'fixtures/redtiger_empty_container_state.json').read_text())
  verdict=classify_base_state(row['response'],request=row['request'],previous=row['previous'])
  self.assertTrue(verdict['base'],verdict)
  for change in [lambda r:r['result']['game']['win'].update(choices={'unknown':True}),
                 lambda r:r['result']['game']['win'].update(choices='unknown'),
                 lambda r:r['result']['game']['nsp'].update(state={'expand':[1]}),
                 lambda r:r['result']['game']['nsp'].update(state={'unknown':True}),
                 lambda r:r['result']['game']['nsp'].update(choices={'selected':None,'available':['x']}),
                 lambda r:r['result']['user']['balance']['cash'].update(afterBet='0')]:
   value=copy.deepcopy(row['response']);change(value)
   self.assertFalse(classify_base_state(value,request=row['request'],previous=row['previous'])['base'])

 def test_persistent_states_are_independent_paid_settled_normal_rounds(self):
  rows=json.loads((Path(__file__).parent/'fixtures/redtiger_persistent_rounds.json').read_text(encoding='utf-8'))
  for row in rows:
   for prev,current in zip(row['rounds'],row['rounds'][1:]):
    with self.subTest(capture=row['capture']):
     verdict=classify_base_state(current['response'],request=current['request'],previous=prev['response'])
     self.assertTrue(verdict['base'],verdict)
 def test_missing_payment_repeat_round_unsettled_win_or_bonus_stays_unknown(self):
  rows=json.loads((Path(__file__).parent/'fixtures/redtiger_persistent_rounds.json').read_text(encoding='utf-8'))
  prev,current=rows[1]['rounds'][:2]
  changes=[lambda r:r['result']['transactions'].update(roundId=prev['response']['result']['transactions']['roundId']),lambda r:r['result']['user']['balance']['cash'].update(afterBet=r['result']['user']['balance']['cash']['atStart']),lambda r:r['result']['user']['balance']['cash'].update(atEnd='0'),lambda r:r['result']['game'].update(features=[{'bonus':True}]),lambda r:r['result']['game'].update(spinMode='FreeSpins')]
  for change in changes:
   value=copy.deepcopy(current['response']);change(value)
   self.assertFalse(classify_base_state(value,request=current['request'],previous=prev['response'])['base'])
  self.assertFalse(classify_base_state(current['response'])['base'])
  request=dict(current['request'],extras={'features':{'featureBuy':'X'}})
  self.assertFalse(classify_base_state(current['response'],request=request,previous=prev['response'])['base'])

 def test_live_return_checker_confirms_two_paid_rounds_with_persisted_state(self):
  import tempfile,threading
  from unittest.mock import patch
  from tester_spin.provider_return_checks import redtiger_check
  rows=json.loads((Path(__file__).parent/'fixtures/redtiger_persistent_rounds.json').read_text(encoding='utf-8'))
  for row in rows:
   rounds=row['rounds']
   replies=[(200,step['request'],step['response'],[]) for step in rounds[1:3]]
   with tempfile.TemporaryDirectory() as directory,patch('tester_spin.providers.redtiger.execution._post_spin',side_effect=replies):
    from types import SimpleNamespace
    runtime=SimpleNamespace(default_stake=2)
    proof=redtiger_check(runtime,Path(directory),1,threading.Event(),initial_response=rounds[0]['response'])
    self.assertEqual(proof['status'],'CONFIRMED',proof)
    self.assertEqual(proof['consecutive_base'],2)

 def test_invalid_nonpositive_round_ids_are_not_evidence(self):
  rows=json.loads((Path(__file__).parent/'fixtures/redtiger_persistent_rounds.json').read_text(encoding='utf-8'))
  prev,current=rows[1]['rounds'][:2]
  for before,after in [(-2,-1),(0,1)]:
   a,b=copy.deepcopy(prev['response']),copy.deepcopy(current['response'])
   a['result']['transactions']['roundId']=before;b['result']['transactions']['roundId']=after
   self.assertFalse(classify_base_state(b,request=current['request'],previous=a)['base'])

 def test_missing_mode_requires_explicit_no_mandatory_feature(self):
  rows=json.loads((Path(__file__).parent/'fixtures/redtiger_persistent_rounds.json').read_text(encoding='utf-8'))
  prev,current=rows[3]['rounds'][:2]
  for marker in [True,None,'false']:
   value=copy.deepcopy(current['response']);value['result']['game']['mandatoryFeature']=marker
   self.assertFalse(classify_base_state(value,request=current['request'],previous=prev['response'])['base'])


def test_settled_normal_root_can_include_completed_respin_history():
    import json
    from pathlib import Path
    from tester_spin.providers.redtiger.base_state import classify_base_state
    f=json.loads(Path(__file__).with_name('fixtures').joinpath('redtiger_settled_inline_results.json').read_text())
    assert classify_base_state(f['current'],request=f['request'],previous=f['previous'])['base']


def test_inline_history_never_overrides_pending_controls_or_broken_ledger():
    import json
    from pathlib import Path
    from copy import deepcopy
    from tester_spin.providers.redtiger.base_state import classify_base_state
    f=json.loads(Path(__file__).with_name('fixtures').joinpath('redtiger_settled_inline_results.json').read_text())
    for change in ['ledger','pending','state','mandatory']:
        value=deepcopy(f['current']);game=value['result']['game']
        if change=='ledger':value['result']['user']['balance']['cash']['atEnd']='123456'
        if change=='pending':game['choices']={'selected':None,'available':['collect','continue']}
        if change=='state':game['hasState']='true'
        if change=='mandatory':game['mandatoryFeature']=True
        assert not classify_base_state(value,request=f['request'],previous=f['previous'])['base'],change
