import pytest
from tests.test_hacksaw_custom_bet_data import SOURCE,SDK
from tester_spin.providers.hacksaw.custom_bet_data import client_custom_bet_data

@pytest.mark.parametrize('literal',['NaN','Infinity','-Infinity'])
def test_custom_data_requires_finite_literal_numbers(literal):
    source=SOURCE.replace('risk:"calm"','risk:'+literal,1)
    assert client_custom_bet_data(source,SDK)['default'] is None
