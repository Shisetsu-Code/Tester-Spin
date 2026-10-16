import copy
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger,normalized_response
from tester_spin.providers.nolimit_city.operation_fields import modifier_ack

MODE={'kind':'FEATURE_SPIN','stake':'.20','price_multiplier':'1.5','server_declared':True,'selector':'ENHANCED',
      'server_type':'BOOSTED_BET','declared_feature_options':['ENHANCED']}
REQ={'type':'featureBet','bet':'.20','featureName':'ENHANCED','playerInteraction':{'featureName':'ENHANCED'}}
ANSWER={'game':{'mode':'NORMAL','nextMode':'NORMAL','win':0,'accumulatedRoundWin':0,'playedBetValue':'.20','freespinsLeft':0,
                'featureBet':False,'boostedBetPlayed':True},'features':{'available':[]},'remainingFreeSpins':0,'balance':'9999.70'}


def test_positive_boost_ack_and_exact_declared_debit_do_not_require_purchase_flag():
    ledger=RoundLedger('10000',MODE)
    assert ledger.accept(ANSWER,request=REQ)

@pytest.mark.parametrize('change',[
    lambda a:a['game'].update(boostedBetPlayed=False),
    lambda a:a['game'].update(wasFeatureBuy=True),
    lambda a:a.update(balance='9999.60'),
])
def test_boost_confirmation_never_hides_explicit_rejection_or_wrong_debit(change):
    answer=copy.deepcopy(ANSWER);change(answer)
    with pytest.raises(ValueError):RoundLedger('10000',MODE).accept(answer,request=REQ)


def test_explicit_boolean_purchase_alias_preserves_contradiction_check():
    answer=copy.deepcopy(ANSWER);answer['game'].update(featureBuy=False)
    assert normalized_response(answer,allow_unresolved_state=True)['game']['wasFeatureBuy'] is False
    answer['game']['wasFeatureBuy']=True
    with pytest.raises(ValueError):normalized_response(answer,allow_unresolved_state=True)


def test_modifier_wire_selector_requires_current_declared_modifier_and_request():
    answer=copy.deepcopy(ANSWER);answer['game'].update(wasFeatureBuy=False,boostedBetPlayed='ENHANCED')
    ledger=RoundLedger('10000',MODE)
    assert ledger.accept(answer,request=REQ)
    assert ledger.last_answer['game']['wasBoostedBet'] is True
    normalized_response(ledger.last_answer,allow_unresolved_state=True)
    for kind,selector in [('SPIN',None),('PURCHASE','OTHER'),('FEATURE_SPIN','OTHER')]:
        with pytest.raises(ValueError):RoundLedger('10000',{**MODE,'kind':kind,'selector':selector}).accept(answer,request=REQ)


def test_selector_dialect_feature_buy_is_not_a_boolean_alias():
    answer=copy.deepcopy(ANSWER);answer['game'].update(featureBuy='NORMAL_PLAY',wasFeatureBuy=False)
    assert normalized_response(answer,allow_unresolved_state=True)['game']['wasFeatureBuy'] is False
