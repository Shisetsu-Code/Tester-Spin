"""A source-proven prefix walker binds only its current consecutive domain."""
from copy import deepcopy
import pytest

from tester_spin.providers.playtech.operation_coverage import operation_coverage
from tester_spin.providers.playtech.primitives import discover_modes
from tester_spin.providers.playtech.protocol import resolve_configuration


CONTRACT = dict(dialect='modern', base_selector='default', adapter_maps={},
                feature_prefix_bindings={'buyFeature': 'PURCHASE', 'extraBet': 'ANTE_BET'})
SOURCE = 'getBuyFeatureOptions getExtraBetOptions parseFeatureOptions'


def configuration(names):
    return {'game': dict(costConfiguration=[
        dict(name=name, cost=10 if i == 0 else 100*i, uuid='prefix-id-'+str(i))
        for i, name in enumerate(names)], activeBetOptions=list(names),
        baseCostMultipliers=[1, 5], defaultBaseCostMultiplier=5,
        maxBet=10000, featureBetEnabled=True, extraBetEnabled=True)}


def test_source_bound_prefixes_classify_only_the_declared_consecutive_modes():
    cfg = configuration(['default', 'buyFeature', 'buyFeature2', 'buyFeature3',
                         'extraBet', 'buyFeature2ExtraBet'])
    plan = discover_modes(cfg, CONTRACT, [SOURCE])
    assert [m['kind'] for m in plan['modes']] == [
        'SPIN', 'PURCHASE', 'PURCHASE', 'PURCHASE', 'ANTE_BET', 'UNKNOWN_FEATURE']
    assert plan['unresolved'] == ['UNBOUND_STAKE_MODE:buyFeature2ExtraBet']
    inventory = operation_coverage(plan)
    assert inventory['expected_by_kind'] == {'SPIN': 1, 'ANTE_BET': 1, 'PURCHASE': 3}
    assert inventory['declared_unknown'] == ['prefix-id-5']
    assert not inventory['all_declared_operations_verified']


@pytest.mark.parametrize('names, kinds', [
    (['default', 'buyFeature2', 'buyFeature3'], ['SPIN', 'UNKNOWN_FEATURE', 'UNKNOWN_FEATURE']),
    (['default', 'buyFeature', 'buyFeature3'], ['SPIN', 'PURCHASE', 'UNKNOWN_FEATURE']),
    (['default', 'buyFeature', 'buyFeature2', 'buyFeature4'],
     ['SPIN', 'PURCHASE', 'PURCHASE', 'UNKNOWN_FEATURE']),
])
def test_missing_base_or_numbered_option_does_not_authorize_later_suffixes(names, kinds):
    plan = discover_modes(configuration(names), CONTRACT, [SOURCE])
    assert [m['kind'] for m in plan['modes']] == kinds
    assert plan['unresolved']


def test_prefix_algorithm_is_not_tied_to_known_labels_or_prices():
    cfg = configuration(['default', 'ticketMode', 'ticketMode2', 'boostOption', 'boostOption2'])
    cfg['game']['costConfiguration'][1]['cost'] = 1
    contract = dict(CONTRACT, feature_prefix_bindings={
        'ticketMode': 'PURCHASE', 'boostOption': 'ANTE_BET'})
    plan = discover_modes(cfg, contract, [SOURCE])
    assert [m['kind'] for m in plan['modes']] == [
        'SPIN', 'PURCHASE', 'PURCHASE', 'ANTE_BET', 'ANTE_BET']
    assert plan['unresolved'] == []


def test_helper_names_and_prices_alone_do_not_bind_prefix_modes():
    cfg = configuration(['default', 'buyFeature', 'buyFeature2', 'extraBet'])
    contract = {key: value for key, value in CONTRACT.items() if key != 'feature_prefix_bindings'}
    plan = discover_modes(cfg, contract, [SOURCE])
    assert [m['kind'] for m in plan['modes']] == [
        'SPIN', 'UNKNOWN_FEATURE', 'UNKNOWN_FEATURE', 'UNKNOWN_FEATURE']


def test_prefix_binding_requires_the_active_option_domain_used_by_the_client():
    cfg = configuration(['default', 'buyFeature', 'buyFeature2'])
    cfg['game'].pop('activeBetOptions')
    plan = discover_modes(cfg, CONTRACT, [SOURCE])
    assert [m['kind'] for m in plan['modes']] == ['SPIN', 'UNKNOWN_FEATURE', 'UNKNOWN_FEATURE']
    assert 'FEATURE_PREFIX_DOMAIN_UNKNOWN' in plan['unresolved']


@pytest.mark.parametrize('bindings', [[], {'': 'PURCHASE'}, {'buyFeature': 'SPIN'}, {'buyFeature': True}])
def test_malformed_semantic_bindings_fail_before_creating_operations(bindings):
    with pytest.raises(ValueError, match='FEATURE_PREFIX_BINDINGS_INVALID'):
        discover_modes(configuration(['default', 'buyFeature']),
                       dict(CONTRACT, feature_prefix_bindings=bindings), [SOURCE])


def test_conflicting_client_semantics_remain_unknown_in_the_inventory():
    source = SOURCE + ' baseCostName:"buyFeature",betParams:{betType:Kinds.DEFAULT}'
    plan = discover_modes(configuration(['default', 'buyFeature']), CONTRACT, [source])
    assert plan['modes'][1]['kind'] == 'UNKNOWN_FEATURE'
    assert 'STAKE_KIND_CONFLICT:buyFeature' in plan['unresolved']
    assert operation_coverage(plan)['declared_unknown'] == ['prefix-id-1']


def test_scoped_disabled_prefix_mode_is_removed_from_executable_inventory():
    cfg = configuration(['default', 'buyFeature', 'buyFeature2'])
    rows = [dict(scope={}, content=deepcopy(cfg)),
            dict(scope=dict(betType='default', featureType='buyFeature2'),
                 content=dict(game=dict(featureBetEnabled=False)))]
    plan = discover_modes(resolve_configuration(rows, {'betType': 'default'}),
                          CONTRACT, [SOURCE], configuration_rows=rows)
    assert [m['name'] for m in plan['modes']] == ['default', 'buyFeature']
    assert plan['disabled_modes'] == ['buyFeature2']
    inventory = operation_coverage(plan)
    assert inventory['expected_by_kind']['PURCHASE'] == 1
    assert inventory['disabled_not_offered'] == ['buyFeature2']
