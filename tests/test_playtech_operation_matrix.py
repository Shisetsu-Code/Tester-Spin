"""All known GPAS operations must be inspected, even after one failed demo."""
import threading
from pathlib import Path

from tester_spin.models import Game
from tester_spin.providers.playtech.adapter import PlaytechProvider

SOURCE=('GLU.game.playMoney(x,y,z); GLU.game.playOut(x,y); ID:40021; ID:48775; '
        '"com.pt.gpas.platform.game.OgwCorosinGameCommand"; '
        'BuyFeatureModule ExtraBetsModule')

MODES=[
    dict(uuid='base-uuid',name='default',cost=10),
    dict(uuid='ante-uuid',name='extra',cost=20),
    *(dict(uuid='buy-'+str(i),name='BF'+str(i),cost=100*i) for i in range(1,5)),
]


class Demo:
    created=[]
    executed=[]
    break_ante=True
    def __init__(self,code,directory,timeout,stop):
        self.directory=Path(directory)
        self.source_hashes=['stable-verified-client']
        self.manifest={'setup':{'usesLegacyBetApi':False}}
        self.sources=[SOURCE]
        self.config=[dict(scope={},content=dict(game=dict(
            costConfiguration=MODES,baseCostMultipliers=[1],
            activeBetOptions=[m['name'] for m in MODES],
            featureBetEnabled=True,extraBetEnabled=True)))]
        self.balance=100000
        self.errors=[]
        self.closed=False
        self.poisoned=False
        self.__class__.created.append(self)
    def __enter__(self):
        return self
    def __exit__(self,*args):
        self.closed=True
    def wait(self,predicate,reason):
        if not predicate():raise ValueError(reason)
    def exchange(self,command,contract):
        assert not self.closed and not self.poisoned
        assert command['gameData']['ID']==40021
        name=command['featureType']
        mode=next(m for m in MODES if m['name']==name)
        self.__class__.executed.append((name,self))
        if name=='extra' and self.break_ante:
            self.poisoned=True
            raise ValueError('SIMULATED_ANTE_RESPONSE_UNKNOWN')
        self.balance-=mode['cost']
        return dict(stakeAmount=mode['cost'],betCost=mode['cost'],winAmount=0,
            gameRoundClosed=True,gameData=dict(stakeCostUuid=mode['uuid'],
                nextRound='BET_END_STATE_IDENTIFIER',totalWinAmount=0))


def run(tmp_path,broken):
    Demo.created=[]
    Demo.executed=[]
    Demo.break_ante=broken
    provider=PlaytechProvider(tmp_path)
    provider.session_factory=Demo
    return provider.test_game(Game('playtech','six-modes','Six Modes',
        'https://www.playtechone.com/',symbol='gpas_six_modes_fixture'),
        spins=1,timeout_s=10,stop_event=threading.Event(),progress=lambda _:None)


def test_one_ante_and_four_buys_are_all_attempted_even_when_ante_fails(tmp_path):
    result=run(tmp_path,broken=True)
    names=[name for name,_ in Demo.executed]
    assert names==['default','extra','BF1','BF2','BF3','BF4','default']
    assert len(Demo.created)==2
    assert Demo.created[0].closed
    assert all(session is Demo.created[1] for name,session in Demo.executed[2:])
    assert all(session is Demo.created[0] for name,session in Demo.executed[:2])
    assert result.status=='PARCIAL'
    assert len(result.attempts)==7
    assert result.successful_spins==6
    assert result.failed_spins==1
    assert result.structural_map['return_to_base_verified'] is True
    inv=result.structural_map['operation_inventory']
    assert inv['expected_by_kind']=={'SPIN':1,'ANTE_BET':1,'PURCHASE':4}
    assert inv['verified_by_kind']=={'SPIN':1,'ANTE_BET':0,'PURCHASE':4}
    assert inv['missing']==['ante-uuid']
    assert inv['all_declared_operations_verified'] is False


def test_all_known_operations_have_independent_receipts_and_return_ok(tmp_path):
    result=run(tmp_path,broken=False)
    assert result.status=='OK',result.error
    assert len(Demo.created)==1
    assert [name for name,_ in Demo.executed]==[
        'default','extra','BF1','BF2','BF3','BF4','default']
    inv=result.structural_map['operation_inventory']
    assert inv['expected_by_kind']=={'SPIN':1,'ANTE_BET':1,'PURCHASE':4}
    assert inv['verified_by_kind']==inv['expected_by_kind']
    assert inv['all_declared_operations_verified'] is True
    assert inv['missing']==[]
