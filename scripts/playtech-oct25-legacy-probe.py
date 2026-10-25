"""One-time GPAS legacy demo contract probe. No historical replay or retries.

For a two-row legacy configuration only: select the server's own cost UUID
and integer multiplier. One wager per isolated game session; stop on any
player-choice phase and never guess the missing ChooseFG payload.
"""
import json
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from tester_spin.providers.playtech.direct_runtime import DemoSession
from tester_spin.providers.playtech.primitives import client_contract,entry_command,RoundLedger
from tester_spin.providers.playtech.protocol import resolve_configuration


def probe(name):
    code='gpas_sorome_pop'
    result=dict(code=code,mode=name,commands_sent=0,closed=False,verified=False,
                execution_scope='fresh-official-demo')
    with TemporaryDirectory() as folder:
        try:
            with DemoSession(code,Path(folder),35,threading.Event()) as session:
                if not session.demo_verified:
                    raise ValueError('DEMO_MODE_NOT_CONFIRMED')
                contract=client_contract(session.manifest,session.sources,
                                         adapter_config=session.adapter_config)
                if contract['dialect']!='legacy':
                    raise ValueError('NOT_LEGACY_CONTRACT')
                game=resolve_configuration(session.config,{'betType':'default'}).get('game',{})
                costs=game.get('costConfiguration')
                if (not isinstance(costs,list) or len(costs)!=2 or
                    {row.get('name') for row in costs}!={'40','Buy feature'} or
                    game.get('featureBetEnabled') is not True):
                    raise ValueError('UNBOUND_LEGACY_GAME_DOMAIN')
                row=next(x for x in costs if x['name']==name)
                factors=game.get('baseCostMultipliers')
                if not isinstance(factors,list) or not factors or any(type(x) is not int or x<=0 for x in factors):
                    raise ValueError('UNBOUND_LEGACY_MULTIPLIERS')
                default=game.get('defaultBaseCostMultiplier')
                mul=default if name=='Buy feature' and type(default) is int and default in factors else min(factors)
                cost=row['cost']*mul
                maximum=game.get('maxBet')
                if (type(cost) is not int or cost<=0 or type(session.balance) is not int
                    or cost>session.balance or type(maximum) is not int or cost>maximum):
                    raise ValueError('LEGACY_BET_ECONOMY_INVALID')
                kind='PURCHASE' if name=='Buy feature' else 'SPIN'
                mode={'id':row['uuid'],'kind':kind,'cost':row['cost'],
                      'multiplier':mul,'name':name}
                result.update(stake=cost,multiplier=mul,client_dialect='legacy')
                ledger=RoundLedger(session.balance,row['uuid'],cost)
                command=entry_command(mode,contract)
                result['commands_sent']=1
                reply=session.exchange(command,contract)
                data=ledger.accept(reply)
                result.update(closed=ledger.closed,phase=data.get('nextRound'),
                              stage_types=[r.get('modeType') for r in data.get('playStack',[])
                                           if isinstance(r,dict) and r.get('remainingPlayCount',0)>0][:5],
                              options_seen=len(data.get('listPickPlayerPickOptions') or []))
                if ledger.closed:
                    session.wait(lambda:ledger.verify(session.balance),'BALANCE_NOT_RECONCILED')
                    result['verified']=True
                else:
                    result['next']='manual-player-choice-or-continuation; no resend'
        except Exception as e:
            result['error']=type(e).__name__+':'+str(e)[:160]
    return result


if __name__=='__main__':
    for name in ('40','Buy feature'):
        print('GPAS_OCT25_LEGACY',json.dumps(probe(name),ensure_ascii=False),flush=True)
