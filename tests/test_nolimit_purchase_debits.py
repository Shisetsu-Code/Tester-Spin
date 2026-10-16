import copy
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger

MODE={'kind':'PURCHASE','stake':'.20','price_multiplier':'60','selector':'OFFER_A','server_declared':True,
      'declared_feature_options':['OFFER_A'],'declared_purchase_options':['OFFER_A']}
REQUEST={'type':'featureBet','bet':'.20','featureName':'OFFER_A','playerInteraction':{'featureName':'OFFER_A'}}
ANSWER={'balance':'9988','game':{'mode':'NORMAL','nextMode':'SETUP','featureBet':True,'playedBetValue':'.20',
        'win':0,'accumulatedRoundWin':0,'freespinsLeft':0},'features':{'available':[]},'pendingWin':True}

def test_current_declared_purchase_and_exact_debit_confirm_feature_ack_without_invented_buy_flag():
    ledger=RoundLedger('10000',MODE)
    assert not ledger.accept(copy.deepcopy(ANSWER),request=REQUEST)
    assert ledger.proof()['root_ack_basis']=='DECLARED_PURCHASE_AND_DEBIT'
    assert 'wasFeatureBuy' not in ledger.last_answer['game']

@pytest.mark.parametrize('mutation',['false_buy','null_buy','false_feature','null_feature','wrong_wallet','base_price','undeclared','unknown_selector','not_purchase_option','no_request','different_selector'])
def test_purchase_ack_requires_current_root_authority_and_explicit_positive_feature(mutation):
    mode=copy.deepcopy(MODE);answer=copy.deepcopy(ANSWER);request=copy.deepcopy(REQUEST)
    if mutation=='false_buy':answer['game']['wasFeatureBuy']=False
    elif mutation=='null_buy':answer['game']['wasFeatureBuy']=None
    elif mutation=='false_feature':answer['game']['featureBet']=False
    elif mutation=='null_feature':answer['game']['featureBet']=None
    elif mutation=='wrong_wallet':answer['balance']='9989'
    elif mutation=='base_price':mode['price_multiplier']='1';answer['balance']='9999.80'
    elif mutation=='undeclared':mode['server_declared']=False
    elif mutation=='unknown_selector':mode['declared_feature_options']=[]
    elif mutation=='not_purchase_option':mode['declared_purchase_options']=[]
    elif mutation=='no_request':request=None
    elif mutation=='different_selector':request['featureName']='OTHER'
    with pytest.raises(ValueError):RoundLedger('10000',mode).accept(answer,request=request)
