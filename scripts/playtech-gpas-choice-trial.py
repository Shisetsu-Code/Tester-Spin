"""Probe an observed, source-bound GPAS pick event in a new demo only.

This is not a production fallback. Three isolated attempts are used to observe
stochastic choice branches, with no retries inside an uncertain session.
"""
import json
import re
import tempfile
import threading
from pathlib import Path

from tester_spin.providers.playtech.direct_runtime import DemoSession
from tester_spin.providers.playtech.primitives import (
    COMMAND, RoundLedger, PickState, client_contract, discover_modes, entry_command)
from tester_spin.providers.playtech.gpas_continuation import ContinuationPlanner
from tester_spin.providers.playtech.protocol import resolve_configuration
from tester_spin.providers.playtech.client_sources import _function_bodies

CODE='gpas_jdice_pop'
NAME='extra2'


def demo():
    result={'code':CODE,'mode':NAME,'source_is_live_demo':False,'pick_events':0,
            'closed':False,'balance_verified':False,'messages':0,'choices':{}}
    with tempfile.TemporaryDirectory() as temp:
        try:
            with DemoSession(CODE,Path(temp),20,threading.Event()) as session:
                source='\n'.join(session.sources)
                functions=_function_bodies(source)
                patterns=[name for name,(args,body) in functions.items()
                    if len(args)==2 and re.search(r'["\x27]pick["\x27]',body) and
                    re.search(r'new [A-Za-z_$][\w$]*',body) and
                    re.search(r'["\x22]["\x22]\s*\+\s*'+re.escape(args[1]),body)]
                if len(patterns)!=1 or 'GLU.game.playOut' not in source or '48775' not in source:
                    raise ValueError('SOURCE_PICK_EVENT_UNBOUND')
                contract=client_contract(session.manifest,session.sources,
                                         adapter_config=session.adapter_config)
                if contract['pick_bound']:
                    raise ValueError('ALREADY_BOUND_BY_LEGACY_EXTRACTOR')
                current=resolve_configuration(session.config,{'betType':'default'})
                options=discover_modes(current,contract,session.sources)
                mode=next(x for x in options['modes'] if x['name']==NAME and x['kind']=='ANTE_BET')
                before=session.balance
                ledger=RoundLedger(before,mode['id'],mode['cost']*mode['multiplier'])
                picks=PickState()
                planner=ContinuationPlanner(limit=50)
                # Hypothesis under test: the literal event is encoded as
                # standard GPAS list-pick continuation parameters.
                probe_contract=dict(contract,pick_bound=True)
                request=entry_command(mode,contract)
                result.update(source_is_live_demo=True,initial_balance=before,
                              cost=mode['cost']*mode['multiplier'])
                for _ in range(51):
                    reply=session.exchange(request,contract)
                    if type(reply.get('gameRoundClosed')) is not bool:
                        raise ValueError('ROUND_TERMINAL_FLAG_UNKNOWN')
                    data=ledger.accept(reply)
                    result['messages']+=1
                    if ledger.closed:break
                    params=planner.parameters(data,probe_contract,picks)
                    result['pick_events']+=int(bool(params))
                    request={'_type':COMMAND,
                        'gameData':{'_type':contract['class'],
                                    'ID':contract['continuation_id'],
                                    'parameters':params},
                        'autoplay':False}
                result['closed']=ledger.closed
                if ledger.closed:
                    session.wait(lambda:ledger.verify(session.balance),'BALANCE_NOT_RECONCILED')
                    result['balance_verified']=True
                    result['balance_after']=session.balance
                result['choices']={str(k):dict(offered=sorted(v),chosen=sorted(picks.selected.get(k,set())))
                                    for k,v in picks.offered.items()}
        except Exception as e:
            result['error']=type(e).__name__+':'+str(e)[:200]
    return result


if __name__=='__main__':
    print('PICK_PROTOCOL_TRIAL '+json.dumps(demo(),ensure_ascii=False),flush=True)
