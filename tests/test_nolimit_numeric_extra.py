import copy,json
from pathlib import Path
from decimal import Decimal
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger,NolimitSession
from tester_spin.providers.nolimit_city.contracts import resolve_operation,confirm_operation,observed_request_matches
ROWS=json.loads((Path(__file__).parent/'fixtures/nolimit_numeric_extra.json').read_text())
SOURCE='clickedYes(){n.Game.apiPlugin.betHandler.zeroBet({playerSelectedExtraSpin:1})}clickedNo(){n.Game.apiPlugin.betHandler.zeroBet({playerSelectedExtraSpin:0})}'

def prefix(row):
    before=row['initial_balance'];ledger=None
    for step in row['steps'][:-1]:
        req=step['request']
        if req['type']=='featureBet':
            assert ledger is None or ledger.closed
            mode=next(m for m in row['modes'] if m.get('selector')==req['featureName'])
            ledger=RoundLedger(before,mode)
        if ledger.accept(copy.deepcopy(step['answer']),request=req):before=ledger.after
    return ledger

@pytest.mark.parametrize('row',ROWS)
def test_numeric_offer_preserves_wire_type_and_reconciles_the_quoted_cost(row,tmp_path):
    ledger=prefix(row);previous=row['steps'][-2]['answer'];last=row['steps'][-1]
    operation=resolve_operation(previous,ledger.mode,client_source=SOURCE)
    matches,selected=observed_request_matches(operation,last['request']);assert matches
    confirm_operation(operation,last['answer'],selected)
    closed=ledger.accept(copy.deepcopy(last['answer']),request=last['request'],operation=operation)
    if selected==0:assert closed
    else:
        assert not closed and ledger.extra_cost==Decimal(str(previous['game']['extraSpinCost']))
        funded=resolve_operation(ledger.last_answer,ledger.mode,client_source=SOURCE,raw_answer=last['answer'])
        assert funded['request']=={'type':'zeroBet','bet':'0.00'}
    session=NolimitSession();session.choice_client=SOURCE
    command=session.next_command(previous,tmp_path,'BUY',ledger.mode)
    assert type(command['playerInteraction']['playerSelectedExtraSpin']) is int

@pytest.mark.parametrize('mutation',['missing_no','wrong_quote','wrong_discount','not_extra','wrong_phase','wrong_option'])
def test_numeric_extra_cannot_skip_price_domain_or_server_ack(mutation):
    row=copy.deepcopy(ROWS[1]);ledger=prefix(row);previous=row['steps'][-2]['answer'];last=row['steps'][-1];source=SOURCE
    if mutation=='missing_no':source=source.replace('playerSelectedExtraSpin:0','other:0')
    if mutation=='wrong_quote':last['answer']['game']['extraSpinCost']=100
    if mutation=='wrong_discount':last['answer']['game']['thisSpinWinning']=-.4
    if mutation=='not_extra':last['answer']['game']['wasExtraSpin']=False
    if mutation=='wrong_phase':last['answer']['game']['nextMode']='UNDECLARED_PICK'
    if mutation=='wrong_option':last['request']['playerInteraction']['playerSelectedExtraSpin']=8
    with pytest.raises(ValueError):
        operation=resolve_operation(previous,ledger.mode,client_source=source)
        ledger.accept(last['answer'],request=last['request'],operation=operation)


def test_followup_check_uses_client_binding_only_after_verified_numeric_funding():
    row=ROWS[1];ledger=prefix(row);last=row['steps'][-1]
    operation=resolve_operation(row['steps'][-2]['answer'],ledger.mode,client_source=SOURCE)
    ledger.accept(copy.deepcopy(last['answer']),request=last['request'],operation=operation)
    raw=copy.deepcopy(last['answer']);raw['game'].update(mode='FREESPIN',nextMode='UNSEEN_CHECK',thisSpinWinning=0)
    normalized={**raw,'_verified_numeric_extra_context':ledger.last_answer.get('_verified_numeric_extra_context')}
    source=SOURCE+';e.Auto=class{start(t){n.Game.apiPlugin.betHandler.zeroBet(),t.finish()}};g.gameFlowController.addGameModeFlowStatePresentationMap(b.Mode.UNSEEN_CHECK,new Map([[l.FlowState.IDLE,new C.Auto]]));'
    assert resolve_operation(normalized,ledger.mode,raw_answer=raw,client_source=source)['request']=={'type':'zeroBet','bet':'0.00'}
    with pytest.raises(ValueError):resolve_operation(raw,ledger.mode,raw_answer=raw,client_source=source)
    raw['_verified_numeric_extra_context']=True
    with pytest.raises(ValueError):resolve_operation(normalized,ledger.mode,raw_answer=raw,client_source=source)


def test_server_receipt_selects_the_extra_spin_variant_when_quote_omits_target():
    row=ROWS[1];ledger=prefix(row);previous=copy.deepcopy(row['steps'][-2]['answer']);last=copy.deepcopy(row['steps'][-1])
    last['answer']['game']['nextMode']='SUPER_FREESPIN'
    operation=resolve_operation(previous,ledger.mode,client_source=SOURCE)
    assert not ledger.accept(last['answer'],request=last['request'],operation=operation)
    funded=resolve_operation(ledger.last_answer,ledger.mode,client_source=SOURCE,raw_answer=last['answer'])
    assert funded['state']=='SUPER_FREESPIN'
    assert funded['request']=={'type':'zeroBet','bet':'0.00'}
