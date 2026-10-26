"""Wire builders and current-source bindings, independent of game names."""
import json
import re
from pathlib import Path

import pytest

from tester_spin.providers.playtech import primitives

SOURCE = (Path(__file__).parent / 'fixtures/playtech_quickspin_binding.js').read_text()
MANIFEST = {'setup': {'useExtendedBetApi': True}}
QUICKSPIN = 'quickspin.game.playMoney'
COROSIN = 'com.pt.gpas.platform.game.OgwCorosinGameCommand'
COMMAND = 'com.pt.casino.platform.game.GameCommand'
MODE = {'id': 'fresh-server-uuid', 'name': 'buyFeature2', 'kind': 'PURCHASE',
        'selector': 'buyFeature2', 'cost': 150, 'multiplier': 50, 'bet_type': 'default'}


def bound(source=SOURCE, manifest=MANIFEST):
    return primitives.client_contract(manifest, [source])


def test_current_policy_binds_exact_null_commands_and_current_mode_selector():
    contract = bound()
    assert contract['command_family'] == 'quickspin-modern'
    assert contract['command_binding_validated'] is True
    assert contract['binding_source'] == 'current_client_source'
    assert primitives.entry_command(MODE, contract) == {
        '_type': COMMAND, 'gameData': {'_type': QUICKSPIN, 'ID': 40021, 'parameters': None},
        'autoplay': False, 'betCost': 7500, 'betType': 'default', 'featureType': 'buyFeature2',
    }
    assert primitives.continuation_command([], contract) == {
        '_type': COMMAND, 'gameData': {'_type': QUICKSPIN, 'ID': 48775, 'parameters': None},
        'autoplay': False,
    }


def test_policy_binding_survives_private_identifier_renaming():
    renamed = SOURCE
    for old, new in {'playID': 'commandKey', 'DefaultPlayPolicy': 'PaidRoundPolicy',
                     'info': 'roundInfo', 'GPASBridge': 'ClientBridge',
                     'playPolicies': 'policyMap', 'createPlatformBridge': 'createClient',
                     'getPlatformBridgeHandle': 'getClient', 'bridge': 'clientInstance',
                     'bridge2': 'activeClient', 'getCurrentGameMode': 'contextValue',
                     'getCurrentBetType': 'featureValue', 'checkForFeature': 'collectOptions',
                     'featureBaseString': 'prefix', 'featureIndex': 'nextIndex',
                     'betOptions': 'declaredOptions',
                     'setCurrentBetType': 'assignFeature', 'activateFeature': 'activateOption',
                     'getMatchingFeatureBetOption': 'findDeclaredOption',
                     'requestedOptionString': 'requestedSelector'}.items():
        renamed = re.sub(r'\b' + old + r'\b', new, renamed)
    assert bound(renamed)['command_family'] == 'quickspin-modern'
    assert bound(renamed)['feature_prefix_bindings'] == {
        'buyFeature': 'PURCHASE', 'extraBet': 'ANTE_BET'}


def test_unrelated_named_class_expressions_do_not_hide_the_policy():
    # Bundled libraries reuse expression-local class names for separate exports.
    prelude = 'let One=class LocalName{};let Two=class LocalName{};'
    assert bound(prelude + SOURCE)['command_family'] == 'quickspin-modern'


@pytest.mark.parametrize('source', [
    'const label = "quickspin.game.playMoney"; 40021; 48775; GLU.game.playMoney(); GLU.game.playOut();',
    '/* ' + SOURCE + ' */',
    'const documentation = ' + json.dumps(SOURCE) + ';',
    'if (false) { ' + SOURCE + ' }',
    'function unused() { ' + SOURCE + ' }',
    SOURCE.replace('new DefaultPlayPolicy()', 'new UnboundPolicy()'),
    SOURCE.replace('this.playPolicies.set(Glu6.Context.Default', 'this.playPolicies.set(Glu6.Context.Freespin'),
    SOURCE.replace('this.playPolicies.set(Glu6.Context.Default, new DefaultPlayPolicy());',
                   'if (false) { this.playPolicies.set(Glu6.Context.Default, new DefaultPlayPolicy()); }'),
    SOURCE.replace('createPlatformBridge("gpas")', 'createPlatformBridge("other")'),
    SOURCE.replace('bootstrap({});', ''),
    SOURCE.replace('bootstrap({});', 'if (false) bootstrap({});'),
    SOURCE.replace('bootstrap({});', 'false && bootstrap({});'),
    SOURCE.replace('this.playPolicies.set(Glu6.Context.Default, new DefaultPlayPolicy());',
                   'if (false) this.playPolicies.set(Glu6.Context.Default, new DefaultPlayPolicy());'),
    SOURCE.replace('this.playPolicies.set(Glu6.Context.Default, new DefaultPlayPolicy());',
                   'this.playPolicies.set(Glu6.Context.Default, new DefaultPlayPolicy()); '
                   'this.playPolicies.set(Glu6.Context.Default, new UnboundPolicy());'),
    SOURCE.replace('info.featureType);', '"default");'),
    SOURCE.replace('featureType: getCurrentBetType()', 'featureType: "default"'),
    SOURCE.replace('info.roundCost', 'differentInfo.roundCost'),
    SOURCE.replace('ID: 48775', 'ID: 48776'),
    SOURCE.replace('parameters: null', 'parameters: []'),
    SOURCE.replace('playOut(playID', 'playOut(otherClass'),
], ids=lambda value: 'unsupported-source')
def test_literals_dead_policies_and_changed_arguments_do_not_bind(source):
    with pytest.raises(ValueError, match='CLIENT_COMMAND_BINDING_UNKNOWN'):
        bound(source)


@pytest.mark.parametrize('mutation', [
    'this.playPolicies.clear();',
    'this.playPolicies = new Map();',
    'this.playPolicies.set(Glu6.Context.Default, otherPolicy);',
    'this.playPolicies.delete(Glu6.Context.Default);',
    'const alias = this.playPolicies; alias.clear();',
    'this["playPolicies"].clear();',
], ids=['clear', 'replace-map', 'replace-default', 'delete-default', 'escape-map', 'computed-member'])
def test_policy_map_cannot_be_mutated_or_escape_after_its_supported_registration(mutation):
    registration = 'this.playPolicies.set(Glu6.Context.Default, new DefaultPlayPolicy());'
    source = SOURCE.replace(registration, registration + mutation)
    with pytest.raises(ValueError, match='CLIENT_COMMAND_BINDING_UNKNOWN'):
        bound(source)


@pytest.mark.parametrize('call', [
    'for (; false; bootstrap({})) {}',
    'for (; bootstrap({}); false) {}',
    'for (; false; (bootstrap({}))) {}',
    'for (; false; [bootstrap({})]) {}',
], ids=['for-update', 'for-condition', 'nested-parens', 'nested-array'])
def test_bootstrap_requires_a_statement_outside_expression_delimiters(call):
    with pytest.raises(ValueError, match='CLIENT_COMMAND_BINDING_UNKNOWN'):
        bound(SOURCE.replace('bootstrap({});', call))


@pytest.mark.parametrize('prelude', [
    r'const pattern = /;(?![^(]*\))/g;',
    r'const pattern = /[(})]/;',
    'const ratio = 10 / 2;',
], ids=['current-client-regexp', 'regexp-delimiters', 'division-expression'])
def test_expression_literals_do_not_change_the_program_statement_depth(prelude):
    assert bound(prelude + SOURCE)['command_family'] == 'quickspin-modern'


def test_conflicting_command_families_and_legacy_manifest_are_rejected():
    corosin = '"' + COROSIN + '"; GLU.game.playMoney(c, {ID:40021}); ID:48775;'
    with pytest.raises(ValueError, match='CLIENT_COMMAND_BINDING_AMBIGUOUS'):
        bound(SOURCE + corosin)
    with pytest.raises(ValueError, match='CLIENT_BET_API_UNKNOWN'):
        bound(manifest={'setup': {'usesLegacyBetApi': True, 'useExtendedBetApi': True}})


def test_null_parameter_family_cannot_accept_an_unbound_pick():
    contract = bound()
    assert contract['pick_bound'] is False
    with pytest.raises(ValueError, match='CLIENT_PARAMETER_BINDING_UNKNOWN'):
        primitives.continuation_command([{'key': 'pick', 'value': '1'}], contract)


def test_quickspin_feature_prefixes_require_the_current_config_collector():
    assert bound()['feature_prefix_bindings'] == {'buyFeature': 'PURCHASE', 'extraBet': 'ANTE_BET'}
    for before, after in [('config.game.activeBetOptions', 'config.game.unrelatedOptions'),
                          ('featureIndex = 2', 'featureIndex = 1'),
                          ('featureIndex++', 'featureIndex += 2'),
                          ('hasMoreFeatures = false', 'hasMoreFeatures = true')]:
        assert bound(SOURCE.replace(before, after))['feature_prefix_bindings'] == {}


def test_feature_collector_must_feed_the_active_bridge_feature_api():
    hidden = SOURCE.replace('return getAvailableFeatureConfig(featureName);', 'return [];')
    assert bound(hidden)['feature_prefix_bindings'] == {}
    unused = SOURCE.replace('function parseFeatureOptions()', 'function unusedParser()')
    assert bound(unused)['feature_prefix_bindings'] == {}
    wrong_domain = SOURCE.replace('buyFeatureOptions.forEach', 'otherDomain.forEach')
    assert bound(wrong_domain)['feature_prefix_bindings'] == {'extraBet': 'ANTE_BET'}
    overwritten = SOURCE.replace('extraBetOptions = checkForFeature(extraBetName, options);',
        'extraBetOptions = checkForFeature(extraBetName, options); '
        'buyFeatureOptions = new Set(); extraBetOptions = new Set();')
    assert bound(overwritten)['feature_prefix_bindings'] == {}
    constant_selector = SOURCE.replace('currentBetType = betType;', 'unrelatedType = betType;')
    assert bound(constant_selector)['feature_prefix_bindings'] == {}


def test_current_source_binding_drives_discovery_and_builders_as_one_path():
    costs = [{'uuid': 'uuid-' + name, 'name': name, 'cost': cost}
             for name, cost in [('default', 7), ('buyFeature', 311),
                                ('buyFeature2', 419), ('extraBet', 11)]]
    config = {'game': {'costConfiguration': costs, 'baseCostMultipliers': [1],
                      'activeBetOptions': [cost['name'] for cost in costs]}}
    contract = bound()
    plan = primitives.discover_modes(config, contract, [SOURCE])
    assert plan['unresolved'] == []
    assert [mode['kind'] for mode in plan['modes']] == ['SPIN', 'PURCHASE', 'PURCHASE', 'ANTE_BET']
    assert [primitives.entry_command(mode, contract)['featureType'] for mode in plan['modes']] == [
        'default', 'buyFeature', 'buyFeature2', 'extraBet']
    assert all(primitives.entry_command(mode, contract)['gameData']['parameters'] is None
               for mode in plan['modes'])
    unbound_source = SOURCE.replace('config.game.activeBetOptions', 'config.game.unrelatedOptions')
    pending = primitives.discover_modes(config, bound(unbound_source), [unbound_source])
    assert [mode['kind'] for mode in pending['modes']] == [
        'SPIN', 'UNKNOWN_FEATURE', 'UNKNOWN_FEATURE', 'UNKNOWN_FEATURE']
    assert pending['unresolved']


@pytest.mark.parametrize('dialect', ['modern', 'legacy'])
def test_corosin_empty_entry_omits_parameters_but_continuation_keeps_typed_list(dialect):
    contract = {'dialect': dialect, 'class': COROSIN, 'entry_id': 40021,
                'continuation_id': 48775, 'command_family': 'corosin-' + dialect}
    entry = primitives.entry_command(MODE, contract)
    assert 'parameters' not in entry['gameData']
    if dialect == 'legacy':
        assert entry == {'_type': COMMAND, 'betType': 'default', 'gameData': {
            '_type': COROSIN, 'ID': 40021, 'bet': 7500,
            'stakeCostUuid': 'fresh-server-uuid', 'baseCostMultiplier': 50}}
    parameters = [{'key': 'extraBetSupported', 'value': 'true'},
                  {'key': 'extraBetActive', 'value': 'false'}]
    continuation = primitives.continuation_command(parameters, contract)
    assert continuation['gameData'] == {'_type': COROSIN, 'ID': 48775, 'parameters': parameters}
    assert ('autoplay' in continuation) == (dialect == 'modern')
    continuation['gameData']['parameters'][0]['value'] = 'false'
    assert parameters[0]['value'] == 'true'


def test_wire_only_contract_builds_comparable_bytes_without_source_certification():
    contract = {'dialect': 'modern', 'class': QUICKSPIN, 'entry_id': 40021,
                'continuation_id': 48775, 'command_family': 'quickspin-modern',
                'command_binding_validated': False, 'binding_source': 'wire_observation'}
    assert primitives.entry_command(MODE, contract)['gameData']['parameters'] is None
    assert contract['command_binding_validated'] is False
    assert contract['binding_source'] == 'wire_observation'
