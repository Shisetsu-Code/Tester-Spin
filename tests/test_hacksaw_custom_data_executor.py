import threading,json
from tests.test_hacksaw_provider import CLIENT_TYPES,with_money
from tester_spin.models import Game
from tester_spin.providers.hacksaw.adapter import HacksawProvider


def test_proven_custom_data_is_sent_on_roots_and_return_probes(tmp_path,monkeypatch):
    from tester_spin.providers.hacksaw import custom_bet_data
    monkeypatch.setattr(custom_bet_data,'client_custom_bet_data',lambda *a:{'proven':True,'default':{'volatility':'calm'},'by_selector':{}})
    class Response:
        def __init__(self,value,text=None):self.value=value;self.text=text if text is not None else json.dumps(value)
        def raise_for_status(self):pass
        def json(self):return self.value
    class HTTP:
        def __init__(self):self.bets=[]
        def get(self,url,**kw):
            if url.endswith('version.json'):return Response({'version':'1.0.0'})
            return Response({},CLIENT_TYPES+'updateCustomBetData')
        def post(self,url,**kw):
            if url.endswith('authenticate'):return Response({'statusCode':0,'sessionUuid':'test','roundStatus':'completed','betLevels':['10'],'bonusGames':[]})
            bet=kw['json']['bets'][0];self.bets.append(bet)
            assert bet.get('customData')=={'volatility':'calm'}
            return Response({'statusCode':0,'round':{'roundId':'r','status':'completed','possibleActions':[],'events':[]}})
    provider=HacksawProvider(tmp_path);provider.http=with_money(HTTP())
    result=provider.test_game(Game('hacksaw','999','Neutral','https://www.hacksawgaming.com/games/neutral',symbol='999'),spins=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
    assert result.status=='OK',result.error
    assert len(provider.http.bets)>=3
    contract=provider.build_farm_contract(Game('hacksaw','999','Neutral','https://www.hacksawgaming.com/games/neutral',symbol='999'),result)
    assert contract['modes'][0]['options']['custom_bet_data']=={'volatility':'calm'}

    assert not provider.validate_farm_contract(contract)
    contract['protocol']['static'].pop('custom_bet_data')
    assert 'HACKSAW_CUSTOM_BET_DATA_REQUIRED' in provider.validate_farm_contract(contract)
