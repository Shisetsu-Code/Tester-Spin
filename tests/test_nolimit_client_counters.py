import pytest
from tester_spin.providers.nolimit_city.client_counters import regular_counter, counter_contract
SOURCE='g.keypadPlugin.setZeroBetSpinCounter(g.model.data.spinsRemaining)'

def test_source_selected_counter_is_independent_of_outer_special_spin_total():
    answer={'game':{'spinsRemaining':2},'remainingFreeSpins':3}
    assert regular_counter(answer,SOURCE)==2
    assert counter_contract(SOURCE)['field']=='spinsRemaining'

@pytest.mark.parametrize('value',[True,None,-1,'2'])
def test_source_counter_must_be_nonnegative_integer(value):
    with pytest.raises(ValueError):regular_counter({'game':{'spinsRemaining':value},'remainingFreeSpins':3},SOURCE)

def test_ambiguous_counter_consumers_do_not_select_a_counter():
    assert counter_contract(SOURCE+';g.keypadPlugin.setZeroBetSpinCounter(g.model.data.otherRemaining)') is None

def test_unbound_similar_field_never_authorizes_counter():
    assert counter_contract('other.setZeroBetSpinCounter(server.spinsRemaining)') is None

def test_canonical_alias_conflict_is_rejected_even_with_source():
    with pytest.raises(ValueError):regular_counter({'game':{'spinsRemaining':2,'freespinsLeft':4},'remainingFreeSpins':3},SOURCE)

@pytest.mark.parametrize('contract',[{}, {'field':'spinsRemaining','source_sha256':'bad'}, {'field':'x.y','source_sha256':'a'*64}])
def test_counter_snapshot_requires_a_field_and_source_digest(contract):
    from tester_spin.providers.nolimit_city.client_counters import counter_from_contract
    with pytest.raises(ValueError):counter_from_contract({'game':{'spinsRemaining':2}},contract)

def test_counter_contract_snapshots_do_not_share_mutable_cached_objects():
    first=counter_contract(SOURCE);first['field']='wrong'
    assert counter_contract(SOURCE)['field']=='spinsRemaining'

@pytest.mark.parametrize('value',[0.0,2.0,float(2**53-1)])
def test_bound_json_number_counter_accepts_safe_integral_float(value):
    answer={'game':{'spinsRemaining':value},'remainingFreeSpins':0}
    result=regular_counter(answer,SOURCE)
    assert result==int(value) and type(result) is int

@pytest.mark.parametrize('value',[.5,float('nan'),float('inf'),-0.5,float(2**53)])
def test_bound_counter_rejects_fractional_nonfinite_negative_and_unsafe_float(value):
    with pytest.raises(ValueError):regular_counter({'game':{'spinsRemaining':value},'remainingFreeSpins':0},SOURCE)

def test_float_counter_without_source_proof_stays_rejected():
    with pytest.raises(ValueError):regular_counter({'game':{'spinsRemaining':0.0},'remainingFreeSpins':0},'')

def test_float_outer_total_stays_rejected_with_source_counter():
    with pytest.raises(ValueError):regular_counter({'game':{'spinsRemaining':0.0},'remainingFreeSpins':0.0},SOURCE)
