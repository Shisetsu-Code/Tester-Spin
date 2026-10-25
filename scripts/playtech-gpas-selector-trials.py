"""One fresh demo-only GPAS wager per case to diagnose client selectors.

No historical replay, no real-money mode, no retries and no raw HAR export.
Every trial has an isolated, disposable DemoSession.
"""
import argparse
import json
import tempfile
import threading
from pathlib import Path

from tester_spin.providers.playtech.direct_runtime import DemoSession
from tester_spin.providers.playtech.primitives import client_contract, discover_modes, entry_command, RoundLedger
from tester_spin.providers.playtech.protocol import resolve_configuration


def trial(code, name, selector):
    outcome=dict(game=code,mode=name,selector=selector,simulation='fresh-official-demo',
                 sent_wagers=0,verified=False)
    with tempfile.TemporaryDirectory() as temp:
        try:
            with DemoSession(code,Path(temp),12,threading.Event()) as sess:
                contract=client_contract(sess.manifest,sess.sources,adapter_config=sess.adapter_config)
                config=resolve_configuration(sess.config,{'betType':'default'})
                plan=discover_modes(config,contract,sess.sources)
                mode=next((r for r in plan['modes'] if r['name']==name),None)
                if mode is None or mode['kind']!='SPIN':
                    raise ValueError('UNBOUND_ENTRY_MODE')
                effective=dict(mode,selector=selector)
                before=sess.balance
                cost=effective['cost']*effective['multiplier']
                outcome.update(balance_before=before,requested_stake=cost,
                               declared_selector=mode['selector'])
                if type(before) is not int or before<cost:
                    outcome.update(error='DEMO_BALANCE_INSUFFICIENT_BEFORE_WAGER')
                    return outcome
                command=entry_command(effective,contract)
                outcome['sent_wagers']=1  # count *before* the uncertain dispatch
                response=sess.exchange(command,contract)
                ledger=RoundLedger(before,mode['id'],cost)
                data=ledger.accept(response)
                outcome.update(round_closed=ledger.closed,returned_phase=data.get('nextRound'),
                               response_count=1)
                if ledger.closed:
                    sess.wait(lambda:ledger.verify(sess.balance),'BALANCE_NOT_RECONCILED')
                    outcome.update(verified=True,balance_after=sess.balance)
                else:
                    outcome['error']='OPEN_ROUND_NOT_SETTLED_NO_AUTOMATIC_RETRY'
        except Exception as e:
            outcome.update(error=type(e).__name__+':'+str(e)[:180])
    return outcome


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cases',nargs='+',required=True,
                        help='CODE,NAME,SELECTOR')
    args=parser.parse_args()
    for case in args.cases:
        values=case.split(',')
        if len(values)!=3:parser.error('Case format CODE,NAME,SELECTOR')
        result=trial(*values)
        print('GPAS_DEMO_TRIAL '+json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
