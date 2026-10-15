import copy,json
from pathlib import Path
from decimal import Decimal
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger
from tester_spin.providers.nolimit_city.contracts import resolve_operation
ROW=json.loads((Path(__file__).parent/'fixtures/nolimit_literal_extra.json').read_text())
SOURCE='yes(){n.Game.apiPlugin.betHandler.zeroBet({playExtraSpin:"yes"})}no(){n.Game.apiPlugin.betHandler.zeroBet({playExtraSpin:"no"})}'

def replay(steps):
    before=None;ledger=None;previous=None;closed=0;discounts=[]
    for step in steps:
        req=step['request'];ans=copy.deepcopy(step['answer']);op=None
        if req['type']=='featureBet':
            mode=copy.deepcopy(next(m for m in ROW['modes_from_same_version_separate_demo_init'] if m.get('selector')==req['featureName']));mode['stake']=req['bet']
            # The HAR omits init. Its first opening balance is a derived test
            # context, never independent evidence or execution certification.
            if before is None:before=Decimal(ans['balance'])+Decimal(req['bet'])*Decimal(mode['price_multiplier'])
            assert ledger is None or ledger.closed
            ledger=RoundLedger(before,mode)
        elif req.get('playerInteraction'):
            op=resolve_operation(previous,ledger.mode,client_source=SOURCE)
        done=ledger.accept(ans,request=req,operation=op)
        if req.get('playerInteraction',{}).get('playExtraSpin')=='yes':discounts.append(ledger.extra_cost)
        if done:before=ledger.after;closed+=1
        previous=step['answer']
    return ledger,closed,discounts

def test_repeated_literal_offers_use_each_new_quote_and_sticky_flag_does_not_mean_acceptance():
    ledger,closed,discounts=replay(ROW['steps'])
    assert closed==10 and ledger.closed
    assert len(discounts)==6

def test_capture_without_init_stays_explicitly_unanchored_in_corpus():
    from tester_spin.providers.nolimit_city.corpus import audit_exchanges
    report=audit_exchanges([{'request':s['request'],'response':s['answer']} for s in ROW['steps']],client_source=SOURCE)
    assert report['initialization_error']=='MISSING_INIT' and not report['ok_certified']

@pytest.mark.parametrize('change',['discount','quote','decline_credit','target','counter'])
def test_literal_extra_preserves_quote_transition_and_money_validation(change):
    steps=copy.deepcopy(ROW['steps']);i=next(i for i,s in enumerate(steps) if s['request'].get('playerInteraction',{}).get('playExtraSpin')=='yes');g=steps[i]['answer']['game']
    if change=='discount':g['win']+=1
    elif change=='quote':g['extraSpinCost']+=1
    elif change=='target':g['nextMode']='UNKNOWN'
    elif change=='counter':g['freespinsLeft']=0
    elif change=='decline_credit':
        i=next(i for i,s in enumerate(steps) if s['request'].get('playerInteraction',{}).get('playExtraSpin')=='no');steps[i]['answer']['balance']='9999'
    with pytest.raises(ValueError):replay(steps[:i+1])
