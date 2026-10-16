import hashlib
import pytest
from tester_spin.providers.nolimit_city.client_counters import counter_contract,regular_counter

SOURCE='''{1(m,e,r){const q=r(2);class Host{init(){Host.model=new q.Model(api)}}e.NeutralHost=Host},2(m,e,r){const b=r(9);e.Model=class extends b.Base{onGame(data){super.onGame(data),this.left=data.remaining}}},3(m,e,r){const h=r(1);h.NeutralHost.keypadPlugin.setZeroBetSpinCounter(h.NeutralHost.model.left)}}'''

def test_active_model_parses_its_server_counter_before_the_keypad_consumes_property():
    contract=counter_contract(SOURCE)
    assert contract=={'field':'remaining','source_sha256':hashlib.sha256(SOURCE.encode()).hexdigest()}
    assert regular_counter({'game':{'remaining':0.0},'remainingFreeSpins':0},SOURCE)==0

@pytest.mark.parametrize('source',[
    SOURCE.replace('Host.model=new q.Model','Host.otherModel=new q.Model'),
    SOURCE.replace('Host.model=new q.Model','Host.model=new q.Other'),
    SOURCE.replace('this.left=data.remaining','if(this.conditional)this.left=data.remaining'),
    SOURCE.replace('super.onGame(data),this.left','super.onGame(data);return;this.left'),
    SOURCE.replace('this.left=data.remaining','data.remaining=3,this.left=data.remaining'),
    SOURCE.replace('this.left=data.remaining','this.left=data.remaining,this.left++'),
    SOURCE.replace('this.left=data.remaining','this.left=data.remaining,data=other'),
    SOURCE.replace('this.left=data.remaining','this.left=data.remaining+1'),
    SOURCE.replace('super.onGame(data)','super.onGame(other)'),
    SOURCE.replace('onGame(data)','onRestore(data)'),
    SOURCE.replace('this.left=data.remaining','this.left=data.remaining')+';g.keypadPlugin.setZeroBetSpinCounter(g.model.data.other)',
])
def test_inactive_ambiguous_mutated_or_unbound_flat_counter_is_not_authority(source):
    assert counter_contract(source) is None

@pytest.mark.parametrize('value',[True,'0',.5,float('nan'),float('inf'),-1.0,float(2**53)])
def test_flat_source_proof_never_accepts_non_integral_or_unsafe_values(value):
    with pytest.raises(ValueError):regular_counter({'game':{'remaining':value},'remainingFreeSpins':0},SOURCE)

def test_flat_source_counter_and_canonical_alias_must_agree():
    with pytest.raises(ValueError):regular_counter({'game':{'remaining':0.0,'freespinsLeft':1},'remainingFreeSpins':0},SOURCE)

def test_bound_canonical_float_is_normalized_without_treating_it_as_an_unbound_alias():
    source=SOURCE.replace('data.remaining','data.freespinsLeft')
    result=regular_counter({'game':{'freespinsLeft':0.0},'remainingFreeSpins':0},source)
    assert type(result) is int and result==0

@pytest.mark.parametrize('source',[
    SOURCE.replace('onGame(data){super.onGame(data)','onGame(data,replay=!1){var previous;super.onGame(data)'),
    SOURCE.replace('Host.model=new q.Model(api)','Host.model=new q.Model(api),Host.keypadPlugin.setZeroBetSpinCounter(Host.model.left)')
])
def test_bound_counter_parser_allows_unused_variable_declaration_or_local_game_owner(source):
    assert counter_contract(source)['field']=='remaining'

def test_nested_arrow_parameter_is_not_a_write_to_the_parser_argument():
    source=SOURCE.replace('this.left=data.remaining','this.left=data.remaining,this.copy=items.map(data=>data)')
    assert counter_contract(source)['field']=='remaining'

@pytest.mark.parametrize('source',[
    SOURCE.replace('e.NeutralHost=Host}','e.NeutralHost=Host,Host.model=new q.Other(api)}'),
    SOURCE.replace('this.left=data.remaining','this.left=data.remaining,this["left"]=99'),
    SOURCE.replace('this.left=data.remaining',"this.left=data.remaining,this['left']++"),
    SOURCE.replace('this.left=data.remaining','this.left=data.remaining,data["remaining"]=99'),
])
def test_module_model_rebinding_or_bracket_counter_mutation_invalidates_proof(source):
    assert counter_contract(source) is None

@pytest.mark.parametrize('source',[
    SOURCE.replace('e.NeutralHost=Host}','e.NeutralHost=Host,e.NeutralHost.model=new q.Other(api)}'),
    SOURCE.replace('e.NeutralHost=Host}','e.NeutralHost=Host;const Alias=Host;Alias.model=new q.Other(api)}'),
    SOURCE.replace('e.NeutralHost=Host}',"e.NeutralHost=Host,Host['model']=new q.Other(api)}"),
    SOURCE.replace('this.left=data.remaining','this.left=data.remaining;const key="left";this[key]=99'),
    SOURCE.replace('this.left=data.remaining','this.left=data.remaining;++this["left"]'),
    SOURCE.replace('this.left=data.remaining','this.left=data.remaining;delete this["left"]'),
])
def test_export_alias_model_writes_and_indirect_counter_mutations_remain_ambiguous(source):
    assert counter_contract(source) is None

def test_model_module_identity_checks_support_arrow_webpack_modules():
    source=SOURCE.replace('1(m,e,r){','1:(m,e,r)=>{').replace('2(m,e,r){','2:(m,e,r)=>{').replace('3(m,e,r){','3:(m,e,r)=>{')
    assert counter_contract(source)['field']=='remaining'
