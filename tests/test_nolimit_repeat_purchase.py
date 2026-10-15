import copy
import threading
from decimal import Decimal
import pytest
from tester_spin.providers.nolimit_city.runtime import NolimitSession

SOURCE='n.zeroBet({playExtraSpin:"yes"});n.zeroBet({playExtraSpin:"no"})'

def offer(win=10,price=2):
    return {'game':{'mode':'FREESPIN','nextMode':'EXTRA_SPIN','win':0,'accumulatedRoundWin':win,
        'playedBetValue':1,'freespinsLeft':0,'extraSpinCost':price,'isExtraSpin':False},'features':{'available':[]},'remainingFreeSpins':0}

def reply(prompt,choice):
    g=prompt['game'];win=Decimal(str(g['accumulatedRoundWin']));price=Decimal(str(g['extraSpinCost']));yes=choice=='yes'
    return {'game':{**g,'mode':'EXTRA_SPIN','nextMode':'FREESPIN' if yes else 'NORMAL',
        'win':str(-price if yes else 0),'accumulatedRoundWin':str(win-price if yes else win),
        'freespinsLeft':1 if yes else 0,'isExtraSpin':yes},'features':{'available':[]},'remainingFreeSpins':0}

def test_both_choices_then_keep_accepting_until_current_prize_is_insufficient(tmp_path):
    s=NolimitSession();s.choice_client=SOURCE;mode={'id':'BUY'}
    s.begin_round('BUY');p=offer();c=s.next_command(p,tmp_path,'BUY')
    assert c['playerInteraction']=={'playExtraSpin':'no'}
    s.confirm_pending_choice(reply(p,'no'));s.finish_round('BUY')
    assert not s.sync_choices(mode)
    s.begin_round('BUY')
    for prize in (10,8,6,4,2):
        p=offer(prize);c=s.next_command(p,tmp_path,'BUY')
        assert c['playerInteraction']=={'playExtraSpin':'yes'}
        s.confirm_pending_choice(reply(p,'yes'))
        assert not s.sync_choices(mode)
    p=offer(0);c=s.next_command(p,tmp_path,'BUY')
    assert c['playerInteraction']=={'playExtraSpin':'no'}
    s.confirm_pending_choice(reply(p,'no'));s.finish_round('BUY')
    assert s.sync_choices(mode)
    probe=mode['choice_domains'][0]['repeat_purchase_probe']
    assert probe['accepted_purchases']==5 and Decimal(probe['spent'])==10
    assert probe['status']=='COMPLETE' and probe['terminal_reason']=='INSUFFICIENT_PENDING_PRIZE'

def test_discovered_accept_stays_uncovered_when_never_affordable(tmp_path):
    s=NolimitSession();s.choice_client=SOURCE;s.begin_round('BUY');mode={'id':'BUY'}
    p=offer(1,2);c=s.next_command(p,tmp_path,'BUY')
    assert c['playerInteraction']['playExtraSpin']=='no'
    s.confirm_pending_choice(reply(p,'no'));s.finish_round('BUY')
    assert not s.sync_choices(mode)
    assert mode['choice_domains'][0]['options']==['no','yes']
    assert mode['choice_domains'][0]['covered']==['no']

def test_server_can_end_a_paid_chain_before_funds_are_empty(tmp_path):
    s=NolimitSession();s.choice_client=SOURCE;mode={'id':'BUY'}
    s.begin_round('BUY');p=offer();s.next_command(p,tmp_path,'BUY');s.confirm_pending_choice(reply(p,'no'));s.finish_round('BUY')
    s.begin_round('BUY');s.next_command(p,tmp_path,'BUY');s.confirm_pending_choice(reply(p,'yes'))
    assert not s.sync_choices(mode)
    # Called by adapter only after a ledger-verified normal settlement.
    s.finish_round('BUY')
    assert s.sync_choices(mode)
    assert mode['choice_domains'][0]['repeat_purchase_probe']['terminal_reason']=='SERVER_CLOSED_ROUND'


def test_executor_notifies_round_start_and_only_verified_settlement(tmp_path,monkeypatch):
    from test_nolimit_executor import Demo,run
    class Tracked(Demo):
        def __init__(self,**kwargs):super().__init__(**kwargs);self.started=[];self.finished=[]
        def begin_round(self,root):self.started.append(root)
        def finish_round(self,root):self.finished.append(root)
    demo=Tracked();_,_,result=run(tmp_path,monkeypatch,demo)
    assert result.status=='OK',result.error
    assert demo.started==demo.finished and len(demo.started)==len(result.attempts)
    demo=Tracked(bad_money=True);_,_,result=run(tmp_path,monkeypatch,demo)
    assert result.status!='OK' and len(demo.started)==1 and not demo.finished


def test_farm_rejects_choices_covered_but_repeated_purchases_unfinished(tmp_path,monkeypatch):
    from test_nolimit_executor import Demo,run
    from tester_spin.providers.repeat_purchase import POLICY,new_probe
    provider,game,result=run(tmp_path,monkeypatch,Demo())
    result.discovered_modes[1]['choice_domains']=[{'state':'EXTRA_SPIN','request_field':'playExtraSpin',
        'options':['no','yes'],'covered':['no','yes'],'repeat_purchase_policy':POLICY,'repeat_purchase_probe':new_probe()}]
    contract=provider.build_farm_contract(game,result)
    assert not contract['ready']
    assert 'NOLIMIT_REPEAT_PURCHASE_NOT_COMPLETE' in provider.validate_farm_contract(contract)


class LongExtraDemo(NolimitSession):
    """Fake transport; real planner, confirmations and monetary ledger."""
    def __init__(self,stop_after=None):
        super().__init__()
        from test_nolimit_executor import INIT
        self.init=copy.deepcopy(INIT)
        self.init['allowedFeatureBets']=['FREESPIN_3_SCATTERS']
        self.init['featureBetLevels']={'FREESPIN_3_SCATTERS':['1.00']}
        self.init['game']['featureBuyTimesBetValue']=[{'name':'FREESPIN_3_SCATTERS','type':'FREESPIN','additionalTypes':[],'price':1}]
        self.balance=Decimal(self.init['balance']);self.prize=Decimal(0);self.stake=Decimal(1)
        self.choice_client=SOURCE;self.extra=False;self.purchases=0;self.stop_after=stop_after
    def open(self,game,http,timeout,stop,directory):self.stop=stop;return self.init
    def next_command(self,answer,directory,root_id,mode=None,raw_answer=None):
        if answer['game']['nextMode']=='FREESPIN':
            self.pending_contract=None
            return {'type':'zeroBet','bet':'0.00'}
        return super().next_command(answer,directory,root_id,mode,raw_answer=raw_answer)
    def exchange(self,content,directory):
        kind=content['type'];choice=content.get('playerInteraction',{}).get('playExtraSpin')
        delta=Decimal(0);left=0
        if kind!='zeroBet':
            self.stake=Decimal(content['bet']);self.balance-=self.stake;self.extra=False
            self.buy=kind=='featureBet';self.prize=Decimal(501) if self.buy else Decimal(0)
            delta=self.prize;phase='NORMAL';nxt='FREESPIN' if self.buy else 'NORMAL';left=int(self.buy)
        elif choice:
            phase='EXTRA_SPIN';nxt='FREESPIN' if choice=='yes' else 'NORMAL'
            if choice=='yes':
                delta=Decimal(-1);self.prize-=1;self.extra=True;left=1;self.purchases+=1
                if self.purchases==self.stop_after:self.stop.set()
        else:phase='FREESPIN';nxt='EXTRA_SPIN'
        if nxt=='NORMAL':self.balance+=self.prize
        return {'game':{'mode':phase,'nextMode':nxt,'win':str(delta),'accumulatedRoundWin':str(self.prize),
            'playedBetValue':str(self.stake),'freespinsLeft':left,'extraSpinCost':1 if kind=='zeroBet' else 0,
            'wasFeatureBuy':self.buy,'wasBoostedBet':False,'isExtraSpin':self.extra},
            'features':{'available':[]},'balance':str(self.balance),'remainingFreeSpins':0}


def test_real_executor_keeps_buying_beyond_500_steps_and_reconciles_each_cost(tmp_path,monkeypatch):
    from test_nolimit_executor import run
    demo=LongExtraDemo();provider,game,result=run(tmp_path,monkeypatch,demo)
    assert result.status=='OK',result.error
    assert demo.purchases==501
    assert max(a.wire_steps for a in result.attempts)>1000
    domain=next(m for m in result.discovered_modes if m['kind']=='PURCHASE')['choice_domains'][0]
    assert domain['repeat_purchase_probe']['status']=='COMPLETE'
    assert Decimal(domain['repeat_purchase_probe']['spent'])==501
    assert provider.build_farm_contract(game,result)['ready']


def test_interrupted_paid_chain_stays_pending(tmp_path,monkeypatch):
    from test_nolimit_executor import run
    demo=LongExtraDemo(stop_after=3);provider,game,result=run(tmp_path,monkeypatch,demo)
    assert result.status=='CANCELADO',result.error
    domain=next(m for m in result.discovered_modes if m['kind']=='PURCHASE')['choice_domains'][0]
    assert set(domain['covered'])=={'no','yes'}
    assert domain['repeat_purchase_probe']['status']=='PENDING'
    assert not provider.build_farm_contract(game,result)['ready']


def test_shared_coverage_requires_closed_repeat_chain():
    from tester_spin.models import GameTestResult
    from tester_spin.providers.path_coverage import _explicit_branch_points
    from tester_spin.providers.repeat_purchase import POLICY,new_probe
    result=GameTestResult('synthetic','example','Example','https://example.invalid',1,1,0,'OK')
    domain={'state':'EXTRA','options':['no','yes'],'covered':['no','yes'],
        'repeat_purchase_policy':POLICY,'repeat_purchase_probe':new_probe()}
    result.discovered_modes=[{'id':'BUY','choice_domains':[domain]}]
    points=_explicit_branch_points(result)
    point=next(p for p in points if p['source']=='repeat_purchase_probe')
    assert point['required'] and not point['covered']
    domain['repeat_purchase_probe'].update(status='COMPLETE',terminal_reason='SERVER_CLOSED_ROUND')
    point=next(p for p in _explicit_branch_points(result) if p['source']=='repeat_purchase_probe')
    assert point['required']==point['covered']


def test_new_paid_chain_cannot_reuse_previous_terminal_proof(tmp_path):
    s=NolimitSession();s.choice_client=SOURCE;mode={'id':'BUY'};p=offer()
    s.begin_round('BUY');s.next_command(p,tmp_path,'BUY');s.confirm_pending_choice(reply(p,'no'));s.finish_round('BUY')
    s.begin_round('BUY');s.next_command(p,tmp_path,'BUY');s.confirm_pending_choice(reply(p,'yes'));s.finish_round('BUY')
    assert s.sync_choices(mode)
    s.begin_round('BUY');s.next_command(p,tmp_path,'BUY');s.confirm_pending_choice(reply(p,'yes'))
    assert not s.sync_choices(mode)
    assert mode['choice_domains'][0]['repeat_purchase_probe']['terminal_reason'] is None


def test_older_extra_contract_needs_new_chain_proof(tmp_path,monkeypatch):
    from test_nolimit_executor import Demo,run
    provider,game,result=run(tmp_path,monkeypatch,Demo())
    result.discovered_modes[1]['choice_domains']=[{'state':'EXTRA_SPIN','request_field':'playExtraSpin',
        'options':['no','yes'],'covered':['no','yes']}]
    contract=provider.build_farm_contract(game,result)
    assert not contract['ready']
    assert 'NOLIMIT_REPEAT_PURCHASE_NOT_COMPLETE' in provider.validate_farm_contract(contract)
