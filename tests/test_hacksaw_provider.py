import json
import threading
from pathlib import Path
import pytest

CLIENT_TYPES = '\n'.join([
    'x["hacksaw.common.types.FeatureBuyItem"]=Q;',
    'function Q(a,b,c){this.bonusGameId=a;this.featureBuyItemType=null;null!=c&&(this.featureBuyItemType=c)}',
    'getFeatureBuyItems:function(){return[new Q("fs","title","BonusBuyItem"),new Q("mod_bonus","title","FeatureSpinItem"),new Q("bonus","title","BonusBuyItem")]}',
])



def with_money(http):
    original=getattr(http,'post',None)
    if original is None:return http
    cash=500000;pending=0;factors={};wire_id=None;original_id=None
    def post(url,**kw):
        nonlocal cash,pending,factors,wire_id,original_id
        body=kw['json'];response=original(url,**kw);value=response.value
        if url.endswith('/authenticate'):
            value.setdefault('bonusGames',[])
            factors={str(b['bonusGameId']):float(b['betCostMultiplier']) for b in value['bonusGames']}
        else:
            if 'bets' in body:
                b=body['bets'][0];cash-=int(int(b['betAmount'])*factors.get(str(b.get('buyBonus')),1));pending=0
            rd=value.get('round',{})
            if 'bets' in body:
                original_id=rd.get('roundId');wire_id=str(original_id)+'-'+str(body['seq'])
                if original_id:rd['roundId']=wire_id
            elif rd.get('roundId')==original_id:
                rd['roundId']=wire_id
            for e in value.get('round',{}).get('events',[]):
                pending+=int(e.get('wa',0))
                for k in ['ba','bc','wc','awc']:e.setdefault(k,'0')
                e.setdefault('wa','0');e.setdefault('awa',str(pending))
            if value.get('round',{}).get('status')=='completed':cash+=pending
        value['accountBalance']={'currencyCode':'EUR','balance':str(cash)}
        response.text=json.dumps(value)
        return response
    http.post=post
    return http

def api():
    from tester_spin.providers import HacksawProvider
    from tester_spin.providers.hacksaw.catalog import games_from_html
    from tester_spin.providers.hacksaw.runtime import discover_modes, checked_response
    return HacksawProvider, games_from_html, discover_modes, checked_response


def test_catalog_preserves_numeric_ids_and_native_encoded_urls():
    _, parse, *_=api()
    html='''<li class="GridListItem" data-gameid="2465" aria-label="Le Bandit Hold &amp; Win | casino game image"><a href="https://www.hacksawgaming.com/games/le-bandit-hold-%26-win"></a><div data-bg-image="https://www-live.hacksawgaming.com/casino_thumbnails/2465.jpg"></div></li><li class="GridListItem" data-gameid="1042" aria-label="Stick’Em | casino game image"></li>'''
    games=parse(html)
    assert len(games)==2
    assert games[0].symbol=='2465' and games[0].slug=='2465'
    assert games[0].name=='Le Bandit Hold & Win'
    assert games[0].url=='https://www.hacksawgaming.com/games/le-bandit-hold-%26-win'
    assert games[1].url=='https://www.hacksawgaming.com/games/slots#game-1042'


def test_duplicate_catalog_ids_and_foreign_urls_are_rejected():
    _, parse, *_=api()
    row='<li class="GridListItem" data-gameid="2465" aria-label="Game | casino game image"><a href="https://attacker.example/games/x"></a></li>'
    with pytest.raises(ValueError):parse(row)
    row='<li class="GridListItem" data-gameid="2465" aria-label="Game | casino game image"></li>'
    with pytest.raises(ValueError):parse(row+row)


def test_advertised_bonus_ids_remain_distinct_and_unvalidated():
    _,_,discover,_=api()
    modes=discover({'bonusGames':[{'bonusGameId':'buy_a','betCostMultiplier':100},{'bonusGameId':'buy_b','betCostMultiplier':300}]})
    assert [m['id'] for m in modes]==['SPIN','BUY_buy_a','BUY_buy_b']
    assert modes[1]['buyBonus']=='buy_a' and modes[2]['feature_multiplier']==300
    assert not any(m['validated'] or m['executable'] for m in modes)


def test_http_200_provider_error_and_missing_status_fail_closed():
    *_,check=api()
    class Response:
        def __init__(self,data):self.data=data
        def raise_for_status(self):pass
        def json(self):return self.data
    for value in [{'statusCode':1}, {'sessionUuid':'secret'}, {'statusCode':False}]:
        with pytest.raises(ValueError):check(Response(value))
    assert check(Response({'statusCode':0}))=={'statusCode':0}


def test_offline_catalog_does_not_authorize_deletions(tmp_path):
    Provider,*_=api();p=Provider(tmp_path)
    class HTTP:
        def get(self,*a,**kw):raise OSError('offline')
    p.http=with_money(HTTP())
    games=p.crawl_catalog(stop_event=threading.Event(),progress=lambda _:None)
    assert len(games)==187 and len({g.symbol for g in games})==187
    assert not p.catalog_crawl_authoritative


def test_runtime_stops_after_auth_and_exports_no_session_values(tmp_path):
    Provider,*_=api();p=Provider(tmp_path)
    from tester_spin.models import Game
    game=Game('hacksaw','2536','Example','https://www.hacksawgaming.com/games/example',symbol='2536')
    class Response:
        def __init__(self,value):self.value=value;self.text=json.dumps(value)
        def raise_for_status(self):pass
        def json(self):return self.value
    class HTTP:
        def get(self,url,**kw):
            answer=Response({'version':'1.12.3'})
            answer.text=CLIENT_TYPES
            return answer
        def post(self,url,**kw):
            assert url.endswith('/authenticate'), 'No apuesta con terminal desconocido'
            return Response({'statusCode':0,'sessionUuid':'PRIVATE_SESSION','bonusGames':[{'bonusGameId':'buy_a','betCostMultiplier':100}]})
    p.http=with_money(HTTP())
    result=p.test_game(game,spins=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
    assert result.status=='PARCIAL' and not result.successful_spins
    assert [m['id'] for m in result.discovered_modes]==['SPIN','BUY_buy_a']
    exported=json.dumps(p.build_farm_contract(game,result))
    assert 'PRIVATE_SESSION' not in exported
    assert not p.build_farm_contract(game,result)['ready']


def test_invalid_gameid_cannot_escape_storage_or_start_session(tmp_path):
    Provider,*_=api();p=Provider(tmp_path)
    from tester_spin.models import Game
    with pytest.raises(ValueError):p.game_dir(Game('hacksaw','../other','Bad','https://www.hacksawgaming.com',symbol='../other'))


def test_recovery_queue_selects_hacksaw(tmp_path):
    from tools.run_retry_queue import provider_for
    assert provider_for('hacksaw',tmp_path).display_name=='Hacksaw Gaming'


def test_real_string_costs_are_preserved_as_multipliers():
    _,_,discover,_=api()
    modes=discover({'bonusGames':[{'bonusGameId':'mod_bonus','betCostMultiplier':'3'}, {'bonusGameId':'fs','betCostMultiplier':'110'}]})
    assert [m.get('feature_multiplier') for m in modes[1:]]==[3,110]


def test_failed_retry_retains_previously_advertised_purchase_selectors(tmp_path):
    Provider,_,discover,_=api();p=Provider(tmp_path)
    from tester_spin.models import Game
    g=Game('hacksaw','2536','Example','https://www.hacksawgaming.com/games/example',symbol='2536')
    (p.game_dir(g)/'game.json').write_text(json.dumps({'discovered_modes':discover({'bonusGames':[{'bonusGameId':'fs','betCostMultiplier':'110'}]})}))
    class HTTP:
        def get(self,*a,**kw):raise OSError('temporary403')
    p.http=with_money(HTTP())
    result=p.test_game(g,spins=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
    assert result.status=='ERROR'
    assert [m['id'] for m in result.discovered_modes]==['SPIN','BUY_fs']
    assert [m['id'] for m in json.loads((p.game_dir(g)/'game.json').read_text())['discovered_modes']]==['SPIN','BUY_fs']


def test_spins_and_purchases_complete_same_round_and_finalize_with_independent_samples(tmp_path):
    Provider,*_=api();p=Provider(tmp_path)
    from tester_spin.models import Game
    g=Game('hacksaw','2536','Example','https://www.hacksawgaming.com/games/example',symbol='2536')
    class Response:
        def __init__(self,value):self.value=value;self.text=json.dumps(value)
        def raise_for_status(self):pass
        def json(self):return self.value
    class HTTP:
        def get(self,*a,**kw):
            answer=Response({'version':'1.12.3'})
            answer.text=CLIENT_TYPES
            return answer
        def post(self,url,**kw):
            body=kw['json']
            if url.endswith('/authenticate'):
                return Response({'statusCode':0,'sessionUuid':'SECRET','betLevels':['10'],'defaultBetLevel':'10',
                    'bonusGames':[{'bonusGameId':'fs','betCostMultiplier':'110'},{'bonusGameId':'mod_bonus','betCostMultiplier':'3'}]})
            if body.get('continueInstructions'):
                return Response({'statusCode':0,'round':{'roundId':body['roundId'],'status':'completed','possibleActions':[],'events':[]}})
            assert body['bets'][0]['betAmount']=='10'
            return Response({'statusCode':0,'round':{'roundId':str(body['seq']),'status':'wfwpc' if 'buyBonus' in body['bets'][0] else 'completed','possibleActions':[],'events':[{'et':2}]}})
    p.http=with_money(HTTP())
    result=p.test_game(g,spins=2,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
    p.finalize_test_result(result,progress=lambda _:None)
    assert result.status=='OK',result.error
    assert result.successful_spins==2 and len(result.attempts)==4
    assert len({attempt.artifact_dir for attempt in result.attempts})==4
    assert [a.wire_steps for a in result.attempts]==[1,1,2,2]
    contract=p.build_farm_contract(g,result)
    assert contract['ready'],contract['unresolved']
    assert 'SECRET' not in json.dumps(contract)
    confirmation=next(m for m in contract['modes'] if m['id']=='CONFIRM_WIN')
    assert confirmation['options']['request_shape']['continueInstructions']=={'action':'win_presentation_complete'}


@pytest.mark.parametrize('status,actions', [('started',[]),('completed',['gamble'])])
def test_unknown_continuation_stays_partial_without_guessing(tmp_path,status,actions):
    Provider,*_=api();p=Provider(tmp_path)
    from tester_spin.models import Game
    g=Game('hacksaw','2536','Example','https://www.hacksawgaming.com/games/example',symbol='2536')
    class Response:
        def __init__(self,value):self.value=value;self.text=json.dumps(value)
        def raise_for_status(self):pass
        def json(self):return self.value
    class HTTP:
        def get(self,*a,**kw):
            answer=Response({'version':'1.12.3'})
            answer.text=CLIENT_TYPES
            return answer
        def post(self,url,**kw):
            if url.endswith('/authenticate'):return Response({'statusCode':0,'sessionUuid':'SECRET','betLevels':['10'],'defaultBetLevel':'10'})
            assert 'continueInstructions' not in kw['json']
            return Response({'statusCode':0,'round':{'roundId':'r','status':status,'possibleActions':actions,'events':[]}})
    p.http=with_money(HTTP())
    result=p.test_game(g,spins=2,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
    assert result.status==('PARCIAL' if status=='started' else 'ERROR') and result.successful_spins==0
    assert len(result.attempts)==1


def test_confirmation_must_not_complete_a_different_round(tmp_path):
    Provider,*_=api();p=Provider(tmp_path)
    from tester_spin.models import Game
    g=Game('hacksaw','2536','Example','https://www.hacksawgaming.com/games/example',symbol='2536')
    class Response:
        def __init__(self,value):self.value=value;self.text=json.dumps(value)
        def raise_for_status(self):pass
        def json(self):return self.value
    class HTTP:
        def get(self,*a,**kw):
            answer=Response({'version':'1.12.3'})
            answer.text=CLIENT_TYPES
            return answer
        def post(self,url,**kw):
            if url.endswith('/authenticate'):return Response({'statusCode':0,'sessionUuid':'SECRET','betLevels':['10'],'defaultBetLevel':'10'})
            confirm='continueInstructions' in kw['json']
            return Response({'statusCode':0,'round':{'roundId':'other' if confirm else 'r','status':'completed' if confirm else 'wfwpc','possibleActions':[],'events':[]}})
    p.http=with_money(HTTP())
    result=p.test_game(g,spins=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
    assert result.status!='OK' and result.successful_spins==0


@pytest.mark.parametrize('value,seconds', [('2000',2.0),('2',2.0),('100',0.1),('0',0.0)])
def test_minimum_duration_uses_client_units(value,seconds):
    from tester_spin.providers.hacksaw.runtime import minimum_round_seconds
    assert minimum_round_seconds(value)==seconds


@pytest.mark.parametrize('primary,secondary', [('play','gamble'),('wild','warehouse'),('fs','lives'),('ts','fs'),('fs','labyrinth'),('new_option_a','new_option_b')])
def test_purchase_choice_covers_play_and_gamble_and_keeps_sample_paths_distinct(tmp_path,primary,secondary):
    Provider,*_=api();p=Provider(tmp_path)
    from tester_spin.models import Game
    from tester_spin.sample_catalog import build_sample_catalog
    g=Game('hacksaw','2185','Choice','https://www.hacksawgaming.com/games/choice',symbol='2185')
    sequences=[]
    class Response:
        def __init__(self,value):self.value=value;self.text=json.dumps(value)
        def raise_for_status(self):pass
        def json(self):return self.value
    class HTTP:
        def get(self,*a,**kw):
            answer=Response({'version':'1.2.3'})
            answer.text=CLIENT_TYPES
            return answer
        def post(self,url,**kw):
            body=kw['json'];sequences.append(body['seq'])
            if url.endswith('/authenticate'):return Response({'statusCode':0,'sessionUuid':'PRIVATE','betLevels':['10'],
                'bonusGames':[{'bonusGameId':'bonus','betCostMultiplier':'100'}]})
            action=body.get('continueInstructions',{}).get('action')
            if action=='win_presentation_complete':status,actions='completed',[]
            elif action==primary:status,actions='wfwpc',[]
            elif action==secondary:status,actions=('started',[primary]) if secondary=='gamble' else ('wfwpc',[])
            elif 'buyBonus' in body['bets'][0]:status,actions='started',[primary,secondary]
            else:status,actions='completed',[]
            return Response({'statusCode':0,'round':{'roundId':'r','status':status,'possibleActions':actions,'events':[]}})
    p.http=with_money(HTTP())
    result=p.test_game(g,spins=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
    p.finalize_test_result(result,progress=lambda _:None)
    assert result.status=='OK',result.error
    choice=next(m for m in result.discovered_modes if m['id']=='CHOICE_BUY_bonus')
    assert set(choice['covered_options'])=={primary,secondary}
    assert choice['validated']
    assert len(result.attempts)==3
    samples=build_sample_catalog(result)
    assert len([g for g in samples['groups'] if g['mode_id']=='BUY_bonus'])==2
    assert sequences==list(range(1,12 if secondary=='gamble' else 11))
    assert p.build_farm_contract(g,result)['ready']

@pytest.mark.parametrize('scenario', ['late_choice', 'missing_choice'])
def test_choice_coverage_stays_pending_and_retries_are_bounded(tmp_path, scenario):
    Provider,*_=api();p=Provider(tmp_path)
    from tester_spin.models import Game
    g=Game('hacksaw','2185','Choice','https://www.hacksawgaming.com/games/choice',symbol='2185')
    class Response:
        def __init__(self,value):self.value=value;self.text=json.dumps(value)
        def raise_for_status(self):pass
        def json(self):return self.value
    class HTTP:
        roots=0
        decisions=0
        def get(self,*a,**kw):
            answer=Response({'version':'1.2.3'})
            answer.text=CLIENT_TYPES
            return answer
        def post(self,url,**kw):
            body=kw['json']
            if url.endswith('/authenticate'):return Response({'statusCode':0,'sessionUuid':'PRIVATE','betLevels':['10']})
            if 'continueInstructions' not in body:
                self.roots+=1;self.decisions=0
                assert self.roots<=3, 'unbounded root retries'
                status='started'
                actions=['play'] if scenario=='late_choice' or self.roots>1 else ['play','gamble']
            else:
                self.decisions+=1
                status='started' if scenario=='late_choice' and self.decisions==1 else 'completed'
                actions=['play','gamble'] if status=='started' else []
            return Response({'statusCode':0,'round':{'roundId':'r','status':status,'possibleActions':actions,'events':[]}})
    p.http=with_money(HTTP())
    result=p.test_game(g,spins=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
    assert result.status=='PARCIAL'
    choice=next(m for m in result.discovered_modes if m['id']=='CHOICE_SPIN')
    assert set(choice['required_options'])=={'play','gamble'}
    assert choice['covered_options']==['play'] and not choice['validated']
    assert p.http.roots<=3


def test_legacy_ready_contract_cannot_bypass_new_verification(tmp_path):
    Provider,*_=api();provider=Provider(tmp_path)
    from tester_spin.models import Game,GameTestResult
    game=Game('hacksaw','2536','Example','https://www.hacksawgaming.com/games/example',symbol='2536')
    result=GameTestResult('hacksaw','2536',game.name,game.url,1,1,0,'OK',symbol='2536')
    result.discovered_modes=[{'id':'SPIN','kind':'SPIN','executable':True,'validated':True,
        'required_options':['spin'],'covered_options':['spin'],'sample_counts':{'spin':1}}]
    contract=provider.build_farm_contract(game,result)
    assert not contract['ready']
    assert 'HACKSAW_CURRENT_MONEY_AND_RETURN_PROOF_REQUIRED' in contract['unresolved']
    contract['ready']=True
    contract['protocol']['static'].pop('verification_contract',None)
    assert 'HACKSAW_CURRENT_VERIFICATION_REQUIRED' in provider.validate_farm_contract(contract)
