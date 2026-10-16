import copy
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger
from tester_spin.providers.nolimit_city.errors import Unlearned
from test_nolimit_bulk_observations import MODE,ANSWER,REQ


def receipt(balance='10000.80'):
    answer=copy.deepcopy(ANSWER)
    answer['game'].update(win=1,accumulatedRoundWin=1)
    answer['features']['available']=['UNDECLARED_MENU']
    answer['balance']=balance
    return answer


def test_reconciled_credit_with_unknown_terminal_menu_is_unlearned_not_bad_money():
    ledger=RoundLedger('10000',MODE)
    with pytest.raises(Unlearned,match='catálogo terminal'):
        ledger.accept(receipt(),request=REQ)
    assert not ledger.closed


def test_unknown_menu_does_not_mask_inconsistent_wallet():
    with pytest.raises(ValueError) as error:
        RoundLedger('10000',MODE).accept(receipt('10000.70'),request=REQ)
    assert not isinstance(error.value,Unlearned)
