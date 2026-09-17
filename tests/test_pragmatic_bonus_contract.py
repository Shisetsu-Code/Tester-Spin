import json
import unittest
from pathlib import Path
from tester_spin.providers.pragmatic_bonus_contract import certify_bonus_contract, bonus_selection
FIXTURE=json.loads(Path(__file__).with_name('fixtures').joinpath('pragmatic_bonus_pick_client.json').read_text())

class BonusContractTests(unittest.TestCase):
    def setUp(self):
        self.contract=certify_bonus_contract(FIXTURE['source_excerpt'],FIXTURE['source_url'])
        self.response={'na':'b','bgt':'21','bw':'1','end':'0','rw':'0.00','level':'0','status':'0,0,0,0','wins':'0,0,0,0','wins_mask':'h,h,h,h'}
    def test_certifies_complete_source_chain(self):
        self.assertIsNotNone(self.contract)
        self.assertEqual(self.contract['wire_field'],'ind')
        self.assertEqual(self.contract['status_key'],'status')
        self.assertEqual(self.contract['initialized_key'],'rw')
    def test_selection_uses_available_status_and_does_not_invent_official_default(self):
        selection=bonus_selection(self.response,self.contract)
        self.assertEqual(selection['fields'],{'ind':'0'})
        self.assertEqual(selection['domain'],['0','1','2','3'])
        self.assertIsNone(selection['default'])
        self.assertEqual(selection['selection_policy'],'first_available_test_choice')
    def test_level_status_participate_in_branch_identity(self):
        first=bonus_selection(self.response,self.contract)
        next_stage=bonus_selection(dict(self.response,level='1',status='1,0,-1,0'),self.contract,override=2)
        self.assertNotEqual(first['branch_signature'],next_stage['branch_signature'])
        self.assertEqual(next_stage['domain'],['1','2','3'])
        self.assertEqual(next_stage['fields'],{'ind':'2'})
    def test_rejects_selected_and_outside_or_invalid_overrides(self):
        response=dict(self.response,status='1,0,0,0')
        for value in [0,4,-1,True,'x',1.2]:
            with self.subTest(value=value),self.assertRaises(ValueError):bonus_selection(response,self.contract,value)
    def test_requires_initialized_bonus_and_honors_terminal(self):
        for extra in [{'na':'s'},{'end':'1'}]:self.assertIsNone(bonus_selection(dict(self.response,**extra),self.contract))
        raw=dict(self.response);raw.pop('rw')
        self.assertIsNone(bonus_selection(raw,self.contract))
        self.assertIsNone(bonus_selection(self.response,None))
    def test_malformed_tables_and_empty_domain_fail_closed(self):
        for extra in [{'status':'1,1,1,1'},{'status':'0,x,0,0'},{'status':'0,0'},{'status':','.join(['0']*129)}]:
            with self.subTest(extra=extra),self.assertRaises(ValueError):bonus_selection(dict(self.response,**extra),self.contract)
    def test_changed_availability_or_picktype_not_certified(self):
        for old,new in [('ItemsStatus[itemIndex]<=0','ItemsStatus[itemIndex]>=0'),('this.PickType=0','this.PickType=1'),('Number(param.Index).toString()','Number(param.Index+1).toString()')]:
            self.assertIsNone(certify_bonus_contract(FIXTURE['source_excerpt'].replace(old,new)))
