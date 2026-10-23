"""Finite math-variant wire modes and stake conversion from a modern client."""
import pytest

from test_bgaming_modern_purchase_levels import SOURCE as API_SOURCE, profile


CONFIG = '''function merge(base,extra){const copy=JSON.parse(JSON.stringify(base));return extra=JSON.parse(JSON.stringify(extra)),Object.assign(copy,extra),copy}
function rotate(base,extra){const copy=merge(base,extra);if(copy.reels)for(const reel in copy.reels){const strips=copy.reels[reel];for(const strip of strips)strip.push(strip.shift())}return copy}
const defaults={base_bet:10,bet_adding:0},first=merge(defaults,{name:"20 Lines",base_bet:20}),second=rotate(first,{name:"40 Lines",base_bet:40}),third=rotate(second,{name:"60 Lines",base_bet:60}),fourth=rotate(third,{name:"80 Lines",base_bet:80}),fifth=rotate(fourth,{name:"100 Lines",base_bet:100}),variants=[first,second,third,fourth,fifth];
const ConfigHolder=class ConfigClass{static get currentConfig(){return variants[this.currentVariantId]}};property(ConfigHolder,"currentVariantId",0);property(ConfigHolder,"allOptions",variants);let Config=ConfigHolder;
'''
SOURCE = CONFIG + API_SOURCE


def test_client_finite_variants_supply_wire_mode_and_effective_stake():
    evidence = profile(SOURCE)
    assert evidence["spin_options"] == {"mode": "0"}
    assert evidence["spin_option_choices"] == {"mode": ["0", "1", "2", "3", "4"]}
    assert evidence["effective_bet_selector"] == "mode"
    assert evidence["effective_bet_multipliers"] == {"0": 1, "1": 2, "2": 3, "3": 4, "4": 5}


@pytest.mark.parametrize("before,after", [
    ('options:options}', 'options:other}'),
    ('variants[0].base_bet', 'other[0].base_bet'),
    ('options.mode=Config.currentVariantId.toString()', 'options.mode=other.currentVariantId.toString()'),
    ('return variants[this.currentVariantId]', 'return other[this.currentVariantId]'),
    ('let Config=ConfigHolder', 'let Config=Other'),
    ('base_bet:40', 'base_bet:unknown'),
    ('base_bet:40', 'base_bet:0'),
    ('base_bet:40', 'base_bet:40,requestOptions:{purchased_feature:"chance"}'),
    ('base_bet:40', 'base_bet:40,bet_adding:20'),
    ('Object.assign(copy,extra)', 'Object.assign(copy,other)'),
    ('return copy}', 'copy.base_bet=2;return copy}'),
    ('property(ConfigHolder,"allOptions",variants)', 'property(ConfigHolder,"allOptions",other)'),
    ('function*(callback,options={})', 'function*(Config,options={})'),
    ('let command="spin";', 'options.mode="0";let command="spin";'),
    ('let command="spin";', 'options.bet=1;let command="spin";'),
    ('let command="spin";', 'options.bet++;let command="spin";'),
    ('let command="spin";', 'delete options.mode;let command="spin";'),
])
def test_unbound_or_modified_variant_contract_is_not_a_mode_domain(before, after):
    evidence = profile(SOURCE.replace(before, after))
    assert evidence["spin_option_choices"] == {}
    assert evidence["effective_bet_multipliers"] == {}


@pytest.mark.parametrize("suffix", [
    'variants.push(first);',
    'variants[1]=first;',
    'second.base_bet=20;',
    'const alias=second;alias.base_bet=20;',
    'const alias=variants;alias.pop();',
    'mutate(variants);',
    'variants.forEach(item=>item.base_bet=20);',
    'mutate(second);',
])
def test_mutable_variant_declarations_are_not_exhaustive(suffix):
    assert profile(SOURCE+suffix)["spin_option_choices"] == {}


def test_unrelated_function_parameter_does_not_shadow_the_module_binding():
    assert profile(SOURCE+'function unrelated(Config){return Config}')['spin_option_choices'] == {'mode': ['0', '1', '2', '3', '4']}


def test_property_keys_and_strict_identity_checks_do_not_escape_configuration():
    assert profile(SOURCE+'const labels={first:"display"};first!==defaults;')['spin_option_choices'] == {'mode': ['0', '1', '2', '3', '4']}


def test_math_instances_only_retain_and_read_configured_stake():
    consumer = 'class MathView{constructor(options){this.options=options}stake(){return this.options.base_bet}}variants.map(item=>new MathView(item));'
    assert profile(SOURCE+consumer)['spin_option_choices'] == {'mode': ['0', '1', '2', '3', '4']}
    assert profile(SOURCE+consumer.replace('this.options=options', 'rewrite(options);this.options=options'))['spin_option_choices'] == {}
    assert profile(SOURCE+consumer.replace('return this.options.base_bet', 'this.options.base_bet=1;return this.options.base_bet'))['spin_option_choices'] == {}


@pytest.mark.parametrize("use", [
    'Object.assign(payload.options,{bet:1,mode:"0"});',
    'const alias=payload.options;alias.bet=1;',
])
def test_variant_stake_cannot_change_in_the_serialization_layer(use):
    source = SOURCE.replace('let request;return', use+'let request;return')
    evidence = profile(source)
    assert evidence['spin_option_choices'] == {}
    assert evidence['effective_bet_multipliers'] == {}
