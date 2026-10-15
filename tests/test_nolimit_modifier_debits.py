import copy,json
from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger
ROWS=json.loads((Path(__file__).parent/'fixtures/nolimit_modifier_debits.json').read_text())

@pytest.mark.parametrize('row',ROWS)
def test_declared_feature_request_and_exact_surcharge_confirm_an_omitted_modifier_flag(row):
    ledger=RoundLedger(row['before'],row['mode'])
    assert ledger.accept(copy.deepcopy(row['answer']),request=row['request'])
    assert ledger.proof()['root_ack_basis']=='DECLARED_PRICE_AND_DEBIT'

@pytest.mark.parametrize('mutation',['false_flag','wrong_balance','normal_price','not_declared','unknown_selector','wrong_request','purchase_flag'])
def test_money_cannot_invent_a_modifier_without_current_declaration_and_request(mutation):
    row=copy.deepcopy(ROWS[0]);mode=row['mode'];answer=row['answer'];request=row['request']
    if mutation=='false_flag':answer['game']['wasBoostedBet']=False
    elif mutation=='wrong_balance':answer['balance']='9999.99'
    elif mutation=='normal_price':mode['price_multiplier']='1'
    elif mutation=='not_declared':mode['server_declared']=False
    elif mutation=='unknown_selector':mode['declared_feature_options']=[]
    elif mutation=='wrong_request':request['featureName']='OTHER'
    elif mutation=='purchase_flag':answer['game']['wasFeatureBuy']=True
    with pytest.raises(ValueError):RoundLedger(row['before'],mode).accept(answer,request=request)
