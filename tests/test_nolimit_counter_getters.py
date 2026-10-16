from pathlib import Path
import pytest
from tests.test_nolimit_flat_counters import SOURCE
from tester_spin.providers.nolimit_city.client_counters import counter_contract,regular_counter

DIRECT=SOURCE.replace('onGame(data){super.onGame(data),this.left=data.remaining}','get left(){return this.data.remaining}')
NULLISH=SOURCE.replace('onGame(data){super.onGame(data),this.left=data.remaining}','get left(){var value;return null!==(value=this.data.remaining)&&void 0!==value?value:0}')

@pytest.mark.parametrize('source',[DIRECT,NULLISH])
def test_bound_passthrough_getter_proves_raw_counter_without_manufacturing_default(source):
    proof=counter_contract(source)
    assert proof is not None
    assert proof['field']=='remaining'
    assert regular_counter({'game':{'remaining':0.0},'remainingFreeSpins':0},source)==0
    for game in [{},{'remaining':None},{'remaining':.5},{'remaining':True},{'remaining':float(2**53)}]:
        with pytest.raises(ValueError):regular_counter({'game':game,'remainingFreeSpins':0},source)

@pytest.mark.parametrize('source',[
    DIRECT.replace('return this.data.remaining','return this.data.remaining+1'),
    NULLISH.replace('?value:0','?value:1'),
    NULLISH.replace('void 0!==value','void 0!==other'),
    DIRECT.replace('get left()','get left(unexpected)'),
    DIRECT.replace('get left(){','set left(value){}get left(){'),
    DIRECT.replace('get left(){','constructor(){this.left=99}get left(){'),
    DIRECT.replace('get left(){','get left(){this.data.remaining=99;'),
    DIRECT.replace('get left(){return this.data.remaining}','get left(){return this.data.remaining}get left(){return 99}'),
    DIRECT.replace('}}},3(m,e,r)', '}};e.Model.prototype.left=99},3(m,e,r)'),
])
def test_counter_getter_rejects_transforms_defaults_setters_and_mutations(source):
    assert counter_contract(source) is None

PUBLIC=Path('data/providers/nolimit_city/_clients/SoakedBySeamen/1.0.264.js')
@pytest.mark.skipif(not PUBLIC.is_file(),reason='Exact public client cache not supplied')
def test_exact_public_nullish_counter_getter_keeps_integral_float_evidence():
    source=PUBLIC.read_text(encoding='utf-8')
    proof=counter_contract(source)
    assert proof is not None
    assert proof['field']=='freespinsLeft'
    assert regular_counter({'game':{'freespinsLeft':0.0},'remainingFreeSpins':0},source)==0
