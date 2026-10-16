import json,copy
from pathlib import Path
import pytest
from tester_spin.providers.redtiger.base_state import classify_base_state


def example():
    rows=json.loads(Path('tests/fixtures/redtiger_persistent_rounds.json').read_text(encoding='utf-8'))
    previous,current=copy.deepcopy(rows[1]['rounds'][:2])
    current['response']['result']['game'].update(mode={'active':False})
    return previous,current


def test_inactive_mode_marker_requires_independent_paid_settlement():
    p,c=example()
    assert classify_base_state(c['response'],request=c['request'],previous=p['response'])['base']
    assert not classify_base_state(c['response'])['base']


@pytest.mark.parametrize('change',[
 lambda d:d['result']['game'].update(mode={'active':True}),
 lambda d:d['result']['game'].update(mode={'active':False,'unknown':1}),
 lambda d:d['result']['game'].update(mode={'active':0}),
 lambda d:d['result']['game'].update(features=[{'type':'bonus'}]),
 lambda d:d['result']['user']['balance']['cash'].update(atEnd='0'),
])
def test_inactive_marker_never_hides_pending_features_or_invalid_money(change):
    p,c=example();change(c['response'])
    assert not classify_base_state(c['response'],request=c['request'],previous=p['response'])['base']
