"""Probe one source-bound GPAS demo operation at a CURRENT declared multiplier.

No historical wire replay. One wager per fresh demo session, no retries;
unresolved bonus is never certified. No raw HAR or credentials are exported.
"""
from __future__ import annotations
import json
import tempfile
import threading
from pathlib import Path
from tester_spin.providers.playtech.direct_runtime import DemoSession
from tester_spin.providers.playtech.primitives import RoundLedger, client_contract, discover_modes, entry_command, PickState, COMMAND
from tester_spin.providers.playtech.gpas_continuation import ContinuationPlanner
from tester_spin.providers.playtech.protocol import resolve_configuration


def probe(code, name, scale):
    result=dict(code=code,mode=name,multiplier=scale,verified=False,steps=0)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            with DemoSession(code,Path(tmp),20,threading.Event()) as session:
                contract=client_contract(session.manifest,session.sources,adapter_config=session.adapter_config)
                game=resolve_configuration(session.config,{'betType':'default'}).get('game',{})
                allowed=game.get('baseCostMultipliers')
                if type(scale) is not int or not isinstance(allowed,list) or scale not in allowed:
                    raise ValueError('UNDECLARED_MULTIPLIER')
                plan=discover_modes({'game':game},contract,session.sources)
                mode=next((x for x in plan['modes'] if x['name']==name and x['kind']!='UNKNOWN_FEATURE'),None)
                if mode is None:raise ValueError('MODE_NOT_SOURCE_BOUND')
                mode=dict(mode,multiplier=scale)
                cost=mode['cost']*scale
                before=session.balance
                if type(before) is not int or before<cost:raise ValueError('INSUFFICIENT_DEMO_BALANCE')
                ledger=RoundLedger(before,mode['id'],cost)
                planner=ContinuationPlanner()
                picks=PickState()
                request=entry_command(mode,contract)
                result.update(default_multiplier=game.get('defaultBaseCostMultiplier'),
                              wager=cost,initial_demo_balance=before,kind=mode['kind'])
                for i in range(200):
                    response=session.exchange(request,contract)
                    if type(response.get('gameRoundClosed')) is not bool:
                        raise ValueError('ROUND_TERMINAL_STATUS_MISSING')
                    data=ledger.accept(response)
                    result['steps']=i+1
                    if ledger.closed:break
                    parameters=planner.parameters(data,contract,picks)
                    request={'_type':COMMAND,'gameData':{
                        '_type':contract['class'],'ID':contract['continuation_id'],'parameters':parameters}}
                    if contract['dialect']=='modern':request['autoplay']=False
                if not ledger.closed:raise ValueError('ROUND_STEP_LIMIT')
                session.wait(lambda:ledger.verify(session.balance),'BALANCE_NOT_RECONCILED')
                result.update(verified=True,balance_after=session.balance)
        except Exception as exc:
            result['error']=type(exc).__name__+':'+str(exc)[:200]
    return result


if __name__=='__main__':
    for code,name,amount in (
        ('gpas_diamdhrbf_pop','BuyFeature',50),
        ('gpas_diamdhrbf_pop','BuyFeature',1),
        ('gpas_pigeonfs_pop','BuyBonus',50),
        ('gpas_ghgranny_pop','BuyFeature',50),
    ):
        print('GPAS_MULTIPLIER_TRIAL '+json.dumps(probe(code,name,amount),ensure_ascii=False),flush=True)
