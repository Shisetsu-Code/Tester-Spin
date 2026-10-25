"""One-attempt GPAS demo probe for CURRENT server-declared but unbound variants.

Never a production fallback: records whether the current public demo accepts
an exactly named server cost UUID and a proposed selector. Does not promote
games, retry uncertain wagers or execute a second action in an open bonus.
"""
import argparse
import json
import re
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from tester_spin.providers.playtech.direct_runtime import DemoSession
from tester_spin.providers.playtech.primitives import COMMAND, RoundLedger, client_contract
from tester_spin.providers.playtech.protocol import resolve_configuration

NAME=re.compile(r'[A-Za-z0-9_-]{1,64}\Z')


def one(code, name, selector):
    result={'code':code,'mode':name,'selector':selector,'sent_wagers':0,
            'closed':False,'verified':False,'demo_only':True}
    if not code.startswith('gpas_') or not all(NAME.fullmatch(x) for x in (code,name,selector)):
        return dict(result,error='INVALID_PROBE_IDENTITY')
    with TemporaryDirectory() as directory:
        try:
            with DemoSession(code,Path(directory),20,threading.Event()) as session:
                if session.demo_verified is not True:
                    raise ValueError('DEMO_MODE_NOT_CONFIRMED')
                contract=client_contract(session.manifest,session.sources,
                    adapter_config=getattr(session,'adapter_config',None))
                if contract['dialect']!='modern':
                    raise ValueError('MODERN_SELECTOR_REQUIRED')
                game=resolve_configuration(session.config,{'betType':'default'}).get('game',{})
                costs=game.get('costConfiguration',[])
                if not isinstance(costs,list):
                    raise ValueError('SERVER_COST_DOMAIN_UNBOUND')
                matching=[m for m in costs if isinstance(m,dict) and m.get('name')==name]
                if len(matching)!=1 or type(matching[0].get('cost')) is not int or matching[0]['cost']<=0:
                    raise ValueError('SERVER_MODE_IDENTITY_UNBOUND')
                active=game.get('activeBetOptions')
                if active is not None and name not in active:
                    raise ValueError('SERVER_MODE_INACTIVE')
                factors=game.get('baseCostMultipliers')
                if not isinstance(factors,list) or not factors or not all(type(x) is int and x>0 for x in factors):
                    raise ValueError('SERVER_MULTIPLIER_UNBOUND')
                amount=matching[0]['cost']*min(factors)
                uuid=matching[0].get('uuid')
                if not isinstance(uuid,str) or not uuid:
                    raise ValueError('SERVER_COST_UUID_UNBOUND')
                before=session.balance
                if type(before) is not int or amount>before:
                    raise ValueError('DEMO_BALANCE_INSUFFICIENT')
                ledger=RoundLedger(before,uuid,amount)
                command={'_type':COMMAND,'gameData':{'_type':contract['class'],
                    'ID':contract['entry_id'],'parameters':[]},'autoplay':False,
                    'betCost':amount,'betType':'default','featureType':selector}
                result.update(source_verified=True,cost=amount,initial_balance=before)
                result['sent_wagers']=1
                response=session.exchange(command,contract)
                if type(response.get('gameRoundClosed')) is not bool:
                    raise ValueError('ROUND_TERMINAL_FLAG_INVALID')
                data=ledger.accept(response)
                result.update(closed=ledger.closed,phase=data.get('nextRound'))
                if ledger.closed:
                    session.wait(lambda:ledger.verify(session.balance),'BALANCE_NOT_RECONCILED')
                    result.update(verified=True,final_balance=session.balance)
                else:
                    result['error']='OPEN_ROUND_NO_ADDITIONAL_COMMANDS'
        except Exception as exc:
            result['error']=type(exc).__name__+':'+str(exc)[:190]
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('cases',nargs='+',help='gpas_code,server-mode-name,proposed-selector')
    args=p.parse_args()
    for x in args.cases:
        parts=x.split(',')
        if len(parts)!=3:
            p.error('Use CODE,NAME,SELECTOR')
        print('GPAS_DECLARED_PROBE '+json.dumps(one(*parts),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
