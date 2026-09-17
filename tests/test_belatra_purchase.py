import tempfile
import unittest
import json
import threading
from pathlib import Path
from tester_spin.providers.belatra_exhaustive import _purchase_request, _continue_round
from tester_spin.providers.belatra_exhaustive import expand_belatra_paths
from tester_spin.providers.belatra_exhaustive import _gamble_round
from tester_spin.providers.belatra_exhaustive import _execute_gamble_choices
from tester_spin.providers.belatra_exhaustive import _execute_gamble_samples
from tester_spin.providers.belatra import BelatraProvider
from tester_spin.models import Game, GameTestResult, SpinAttempt

class PurchaseTests(unittest.TestCase):
    def test_cancelled_run_keeps_unexecuted_gamble_domains_visible(self):
        enter={'gs':{'nlines':20,'betPerLine':1,'gdenom':1,'doubleActive':'redblack','doubleAssortment':['off','dealer','redblack']}}
        class Provider:
            _base_spin_request=staticmethod(BelatraProvider._base_spin_request)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'bootstrap').mkdir();(root/'bootstrap'/'enter.response.json').write_text(json.dumps(enter))
            result=GameTestResult(provider='belatra',slug='test',game_name='Test',game_url='',requested_spins=1,successful_spins=1,failed_spins=0,status='OK',run_dir=folder,attempts=[SpinAttempt(number=1,ok=True,terminal=True)])
            stop=threading.Event();stop.set()
            result=expand_belatra_paths(Provider(),Game('belatra','test','Test',''),result,repetitions=2,timeout_s=1,stop_event=stop,progress=lambda _:None)
        mode=next(m for m in result.discovered_modes if m['id']=='BELATRA_DOUBLE_DEALER_HALF_1')
        self.assertEqual(mode['required_options'],['1','2','3','4'])
        self.assertEqual(mode['required_samples'],2)
        self.assertEqual(mode['covered_options'],[])
    def test_gamble_samples_repeat_each_choice_and_keep_separate_evidence(self):
        from unittest.mock import patch
        def execute(provider,game,choices,**kwargs):
            return {'Red':(True,3,'finished','toIdle',str(kwargs['artifact_dir']/'trigger-001')),'DECLINE':(True,2,'finished','toIdle')}
        with tempfile.TemporaryDirectory() as folder, patch('tester_spin.providers.belatra_exhaustive._execute_gamble_choices',side_effect=execute):
            result=_execute_gamble_samples(None,None,['Red'],repetitions=2,timeout_s=1,artifact_dir=Path(folder),stop_event=threading.Event())
        self.assertEqual(len(result['Red']),2)
        self.assertNotEqual(result['Red'][0][4],result['Red'][1][4])
    def test_gamble_rejects_unacknowledged_choice(self):
        class Provider:
            def _post_direct_game(self,state,request,**kwargs):
                if request['q']=='finish': return {'gs':{'phaseCur':'finished','phaseNext':'toIdle','historyId':12}}
                return {'gs':{'phaseNext':'toPaid','historyId':12,'subGameInfo':[{'category':'Double','type':'redblack','attempt':0,'userChoice':''}]}}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError,'acknowledge'):
                _gamble_round(Provider(),{},'Red',timeout_s=1,artifact_dir=Path(folder))
    def test_gamble_outcome_points_to_its_own_trigger_evidence(self):
        enter={'gs':{'nlines':20,'betPerLine':1,'gdenom':1,'doubleActive':'redblack'}}
        class Provider:
            _base_spin_request=staticmethod(BelatraProvider._base_spin_request)
            def _open_direct_game(self,*args,**kwargs): return {'enter':enter}
            def _post_direct_game(self,state,request,**kwargs):
                if request['q']=='start': return {'gs':{'phaseNext':'toDoubleDialog','curWin':10,'historyId':12}}
                if request.get('userAction')=='askDouble': return {'gs':{'historyId':12,'subGameInfo':[{'category':'Double','type':'redblack','attempt':0}]}}
                if request['q']=='play': return {'gs':{'phaseNext':'toPaid','historyId':12,'subGameInfo':[{'category':'Double','type':'redblack','attempt':1,'userChoice':'Red'}]}}
                return {'gs':{'phaseCur':'finished','phaseNext':'toIdle','historyId':12}}
        with tempfile.TemporaryDirectory() as folder:
            results=_execute_gamble_choices(Provider(),Game('belatra','test','Test',''),['Red'],timeout_s=1,artifact_dir=Path(folder),stop_event=threading.Event(),max_spins=2)
            self.assertTrue(results['Red'][0])
            self.assertEqual(Path(results['Red'][4]).name,'trigger-001')
            self.assertTrue((Path(results['Red'][4])/'gamble-option.json').exists())
    def test_nonspin_attempt_does_not_prove_base_coverage(self):
        enter={'gs':{'nlines':20,'betPerLine':1,'gdenom':1}}
        class Provider:
            _base_spin_request=staticmethod(BelatraProvider._base_spin_request)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'bootstrap').mkdir(); (root/'bootstrap'/'enter.response.json').write_text(json.dumps(enter))
            result=GameTestResult(provider='belatra',slug='test',game_name='Test',game_url='',requested_spins=1,successful_spins=1,failed_spins=0,status='OK',run_dir=folder,attempts=[SpinAttempt(number=1,ok=True,terminal=True,mode_id='OTHER')])
            result=expand_belatra_paths(Provider(),Game('belatra','test','Test',''),result,repetitions=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
        self.assertEqual(result.status,'PARCIAL')
    def test_dealer_half_uses_numbered_card(self):
        requests=[]
        class Provider:
            def _post_direct_game(self,state,request,**kwargs):
                requests.append(request)
                if len(requests)==1: return {'gs':{'historyId':12,'subGameInfo':[{'category':'Double','type':'dealer','attempt':0}]}}
                if len(requests)==2: return {'gs':{'phaseNext':'toPaid','historyId':12,'subGameInfo':[{'category':'Double','type':'dealer','attempt':1,'userChoice':'4'}]}}
                return {'gs':{'phaseCur':'finished','phaseNext':'toIdle','historyId':12}}
        with tempfile.TemporaryDirectory() as folder:
            result=_gamble_round(Provider(),{},'4',gamble_type='dealer',half=1,timeout_s=1,artifact_dir=Path(folder))
        self.assertTrue(result[0])
        self.assertEqual(requests[0]['dblhalf'],1)
        self.assertEqual(requests[1]['userAction'],'askDouble4')
    def test_announced_dealer_remains_pending(self):
        enter={'gs':{'nlines':20,'betPerLine':1,'gdenom':1,'doubleActive':'dealer','doubleAssortment':['off','dealer','redblack']}}
        class Provider:
            _base_spin_request=staticmethod(BelatraProvider._base_spin_request)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'bootstrap').mkdir(); (root/'bootstrap'/'enter.response.json').write_text(json.dumps(enter))
            result=GameTestResult(provider='belatra',slug='test',game_name='Test',game_url='',requested_spins=1,successful_spins=1,failed_spins=0,status='OK',run_dir=folder,attempts=[SpinAttempt(number=1,ok=True,terminal=True)])
            result=expand_belatra_paths(Provider(),Game('belatra','test','Test',''),result,repetitions=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
        self.assertEqual(result.status,'PARCIAL')
        mode=next(m for m in result.discovered_modes if m['id']=='BELATRA_DOUBLE_TYPES')
        self.assertEqual(mode['required_options'],['dealer','redblack'])
        self.assertEqual(mode['covered_options'],[])
    def test_no_double_event_is_uncovered_not_success(self):
        enter={'gs':{'nlines':20,'betPerLine':1,'gdenom':1,'doubleActive':'redblack'}}
        class Provider:
            _base_spin_request=staticmethod(BelatraProvider._base_spin_request)
            def _open_direct_game(self,*args,**kwargs): return {'enter':enter}
            def _post_direct_game(self,state,request,**kwargs):
                return {'gs':{'historyId':12,'phaseCur':'finished' if request['q']=='finish' else 'deal','phaseNext':'toIdle' if request['q']=='finish' else 'toPaid'}}
        with tempfile.TemporaryDirectory() as folder:
            results=_execute_gamble_choices(Provider(),Game('belatra','test','Test',''),['Red'],timeout_s=1,artifact_dir=Path(folder),stop_event=threading.Event(),max_spins=2)
        self.assertFalse(results['Red'][0])
    def test_redblack_gamble_uses_attempt_counter_and_collects_win(self):
        requests=[]
        class Provider:
            def _post_direct_game(self,state,request,**kwargs):
                requests.append(request)
                if len(requests)==1: return {'gs':{'phaseCur':'Double_redblack','phaseNext':'Double_redblack','historyId':12,'subGameInfo':[{'category':'Double','type':'redblack','attempt':0}]}}
                if len(requests)==2: return {'gs':{'phaseCur':'Double_redblack','phaseNext':'Double_redblack','historyId':12,'subGameInfo':[{'category':'Double','type':'redblack','attempt':1,'userChoice':'Red'}]}}
                if len(requests)==3: return {'gs':{'phaseNext':'toPaid','historyId':12}}
                return {'gs':{'phaseCur':'finished','phaseNext':'toIdle','historyId':12}}
        with tempfile.TemporaryDirectory() as folder:
            result=_gamble_round(Provider(),{},'Red',timeout_s=1,artifact_dir=Path(folder))
        self.assertTrue(result[0])
        self.assertEqual([r.get('userAction') for r in requests],['askDouble','askDoubleRed','askDoubleBackToGame',None])
        self.assertEqual(requests[2]['wasAttempt'],1)
    def test_expand_executes_every_purchase_and_records_terminal_coverage(self):
        enter={'gs':{'nlines':20,'betPerLine':1,'gdenom':1,'buyBonus':{'buyTotalBetK':[{'prefix2':99,'cost':50},{'prefix2':88,'cost':100}]}}}
        purchases=[]
        class Provider:
            _base_spin_request=staticmethod(BelatraProvider._base_spin_request)
            def _open_direct_game(self,*args,**kwargs): return {'enter':enter}
            def _post_direct_game(self,state,request,**kwargs):
                if request['q']=='start':
                    purchases.append(request['selectId'])
                    return {'gs':{'phaseNext':'toPaid','historyId':12}}
                return {'gs':{'phaseCur':'finished','phaseNext':'toIdle','historyId':12}}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'bootstrap').mkdir(); (root/'bootstrap'/'enter.response.json').write_text(json.dumps(enter))
            result=GameTestResult(provider='belatra',slug='test',game_name='Test',game_url='',requested_spins=1,successful_spins=1,failed_spins=0,status='OK',run_dir=folder,attempts=[SpinAttempt(number=1,ok=True,terminal=True)])
            result=expand_belatra_paths(Provider(),Game('belatra','test','Test',''),result,repetitions=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
        self.assertEqual(purchases,[0,1])
        mode=next(m for m in result.discovered_modes if m['id']=='BELATRA_BUY_BONUS')
        self.assertEqual(mode['covered_options'],['0','1'])
        self.assertEqual(result.status,'OK')
    def test_purchase_uses_index_not_advertised_prefix(self):
        enter={'gs':{'nlines':20,'betPerLine':1,'gdenom':1,'buyBonus':{'buyTotalBetK':[{'prefix2':99,'cost':50},{'prefix2':88,'cost':100}]}}}
        request=_purchase_request(enter,'1')
        self.assertEqual((request['q'],request['buyBonus'],request['selectId'],request['vipOn']),('start',1,1,0))
        with self.assertRaises(ValueError): _purchase_request(enter,'88')

    def test_free_round_continues_using_server_counters_then_finishes(self):
        requests=[]
        class Provider:
            def _post_direct_game(self,state,request,**kwargs):
                requests.append(request)
                if request['q']=='play': return {'gs':{'phaseCur':'deal','phaseNext':'toPaid','historyId':12}}
                return {'gs':{'phaseCur':'finished','phaseNext':'toIdle','historyId':12}}
        with tempfile.TemporaryDirectory() as folder:
            outcome=_continue_round(Provider(),{}, {'gs':{'phaseCur':'deal','phaseNext':'toNextFG','historyId':12,'freeInfo':{'remain':2,'total':10}}},timeout_s=1,artifact_dir=Path(folder))
        self.assertTrue(outcome[0])
        self.assertEqual(requests,[{'q':'play','userAction':'askNextFG','remainFG':2,'totalWasFG':10},{'q':'finish','ghistId':12}])

    def test_unknown_phase_does_not_send_finish(self):
        class Provider:
            def _post_direct_game(self,*args,**kwargs): raise AssertionError('unexpected request')
        with tempfile.TemporaryDirectory() as folder:
            result=_continue_round(Provider(),{}, {'gs':{'phaseNext':'toBonusMystery','historyId':12}},timeout_s=1,artifact_dir=Path(folder))
        self.assertFalse(result[0])

    def test_unacknowledged_finish_is_not_replayed(self):
        requests=[]
        class Provider:
            def _post_direct_game(self,state,request,**kwargs):
                requests.append(request)
                return {'gs':{'phaseNext':'toPaid','historyId':12}}
        with tempfile.TemporaryDirectory() as folder:
            result=_continue_round(Provider(),{}, {'gs':{'phaseNext':'toPaid','historyId':12}},timeout_s=1,artifact_dir=Path(folder))
        self.assertFalse(result[0])
        self.assertEqual(len(requests),1)

if __name__=='__main__': unittest.main()
