"""Per-operation GPAS configuration, without historical sessions or live traffic."""
from copy import deepcopy
import threading
import pytest

from tester_spin.models import Game
from tester_spin.providers.playtech.adapter import PlaytechProvider
from tester_spin.providers.playtech.primitives import discover_modes
from tester_spin.providers.playtech.protocol import resolve_configuration


CONTRACT = dict(dialect='modern', entry_id=40021, continuation_id=48775,
                adapter_maps={}, standard_start_bound=False,
                base_selector='default', pick_bound=False)
CONTRACT['class'] = 'com.pt.gpas.platform.game.OgwCorosinGameCommand'
SOURCE = ('GLU.game.playMoney(stakeCostUuid,baseCostMultiplier,featureType); '
          'GLU.game.playOut(x,y); BuyFeatureController; ID:40021; ID:48775; '
          '"com.pt.gpas.platform.game.OgwCorosinGameCommand";')


def card_rows():
    """Allowlisted Wild Roll scope shape; synthetic identities and client source."""
    costs = [dict(name=name, cost=amount, uuid='scope-cost-'+str(i),
                  parameters=dict(startingMode='scope-stage-'+str(i),
                                  startingPlays='1', winline='30',
                                  evalPayout='LEFT_TO_RIGHT'))
             for i, (name, amount) in enumerate((
                 ('default', 10), ('BF3Cards', 1000),
                 ('BF6Cards', 1500), ('BF9Cards', 2000)))]
    game = dict(costConfiguration=costs,
                activeBetOptions=[c['name'] for c in costs],
                baseCostMultipliers=[1, 10, 50], defaultBaseCostMultiplier=50,
                featureBetEnabled=True, minBet=10, maxBet=19000)
    return [dict(scope={}, content=dict(game=game)),
            dict(scope=dict(betType='freespin'), content=dict(game=dict(
                baseCostMultipliers=[1], defaultBaseCostMultiplier=1,
                featureBetEnabled=False, activeBetOptions=['default'],
                minBet=10, maxBet=10))),
            *[dict(scope=dict(betType='default', featureType=name),
                   content=dict(game=dict(minBet=low, maxBet=high)))
              for name, low, high in (('BF3Cards', 1000, 500000),
                                     ('BF6Cards', 1500, 600000),
                                     ('BF9Cards', 2000, 600000))]]


def run_adapter(tmp_path, *, fail_first=False, rows=None):
    configuration = deepcopy(rows if rows is not None else card_rows())
    costs = configuration[0]['content']['game']['costConfiguration']
    emitted = []
    sessions = []

    class Demo:
        source_hashes = ['scope-fixture-stable-client']
        manifest = {'setup': {'usesLegacyBetApi': False}}
        sources = [SOURCE]

        def __init__(self, *args):
            self.config = deepcopy(configuration)
            self.balance = 1000000
            self.errors = []
            sessions.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def wait(self, predicate, reason):
            if not predicate():
                raise ValueError(reason)

        def exchange(self, command, contract):
            assert command['gameData']['ID'] == 40021
            emitted.append((command['featureType'], command['betCost']))
            if fail_first and len(emitted) == 1:
                raise ValueError('SIMULATED_COMMAND_OUTCOME_UNKNOWN')
            cost = next(c for c in costs if c['name'] == command['featureType'])
            charge = command['betCost']
            self.balance -= charge
            return dict(stakeAmount=charge, betCost=charge, winAmount=0,
                gameRoundClosed=True, gameData=dict(stakeCostUuid=cost['uuid'],
                    stake=charge, nextRound='BET_END_STATE_IDENTIFIER', totalWinAmount=0))

    provider = PlaytechProvider(tmp_path)
    provider.session_factory = Demo
    result = provider.test_game(Game('playtech', 'scoped-fixture', 'Scoped fixture',
        'https://www.playtechone.com/', symbol='gpas_scoped_fixture'),
        spins=1, timeout_s=10, stop_event=threading.Event(), progress=lambda _: None)
    return result, emitted, sessions


def test_adapter_uses_each_purchase_limit_instead_of_base_limit(tmp_path):
    result, emitted, _ = run_adapter(tmp_path)
    assert emitted == [('default', 10), ('BF3Cards', 50000),
                       ('BF6Cards', 75000), ('BF9Cards', 100000), ('default', 10)]
    assert result.status == 'OK', result.error


def test_reopened_demo_rediscovers_the_same_scoped_purchase_amounts(tmp_path):
    result, emitted, sessions = run_adapter(tmp_path, fail_first=True)
    assert emitted == [('default', 10), ('BF3Cards', 50000),
                       ('BF6Cards', 75000), ('BF9Cards', 100000), ('default', 10)]
    assert len(sessions) == 2
    assert result.successful_spins == 4
    assert result.failed_spins == 1
    assert result.status == 'PARCIAL'


def scoped_plan(rows, *, source=SOURCE, contract=CONTRACT):
    return discover_modes(resolve_configuration(rows, {'betType': 'default'}),
                          contract, [source], configuration_rows=rows)


def by_name(plan):
    return {mode['name']: mode for mode in plan['modes']}


def test_scope_rule_survives_different_labels_identities_prices_and_domains():
    rows = card_rows()
    game = rows[0]['content']['game']
    game.update(baseCostMultipliers=[1, 9], defaultBaseCostMultiplier=9)
    for i, (name, price, cap) in enumerate((
            ('BF4Cards', 1200, 80000), ('BF8Cards', 1800, 125000),
            ('BF12Cards', 2600, 200000)), 1):
        game['costConfiguration'][i].update(name=name, cost=price, uuid='other-cost-'+str(i))
        game['costConfiguration'][i]['parameters']['startingMode'] = 'other-stage-'+str(i)
        game['activeBetOptions'][i] = name
        rows[i+1]['scope']['featureType'] = name
        rows[i+1]['content']['game'] = dict(baseCostMultipliers=[2, 7],
            defaultBaseCostMultiplier=7, minBet=price*2, maxBet=cap)
    before = deepcopy(rows)
    plan = scoped_plan(rows)
    assert plan['unresolved'] == []
    assert [(m['name'], m['cost']*m['multiplier']) for m in plan['modes']] == [
        ('default', 10), ('BF4Cards', 8400), ('BF8Cards', 12600), ('BF12Cards', 18200)]
    assert rows == before


def test_operation_domains_and_limits_are_recorded_without_cross_mode_leakage():
    rows = card_rows()
    rows[2]['content']['game'].update(baseCostMultipliers=[3, 6],
        defaultBaseCostMultiplier=6, minBet=6000, maxBet=6000)
    modes = by_name(scoped_plan(rows))
    assert modes['BF3Cards']['multiplier'] == 6
    assert modes['BF6Cards']['multiplier'] == 50
    assert modes['default']['multiplier'] == 1
    assert modes['BF3Cards']['configuration_context'] == {
        'betType': 'default', 'featureType': 'BF3Cards'}
    assert modes['BF3Cards']['stake_domain'] == dict(
        factors=[3, 6], default_factor=6, min_bet=6000, max_bet=6000)


def test_base_uses_a_legal_factor_after_its_specific_minimum_override():
    rows = card_rows()
    rows.append(dict(scope=dict(betType='default', featureType='default'),
                     content=dict(game=dict(minBet=100, maxBet=400))))
    modes = by_name(scoped_plan(rows))
    assert modes['default']['multiplier'] == 10
    assert modes['BF9Cards']['multiplier'] == 50


@pytest.mark.parametrize('override', [
    dict(activeBetOptions=['default']), dict(featureBetEnabled=False),
])
def test_explicitly_disabled_operation_is_not_scheduled(override):
    rows = card_rows()
    rows[2]['content']['game'].update(override)
    plan = scoped_plan(rows)
    assert 'BF3Cards' not in by_name(plan)
    assert 'BF3Cards' in plan['disabled_modes']
    assert by_name(plan)['BF6Cards']['kind'] == 'PURCHASE'
    assert plan['unresolved'] == []


@pytest.mark.parametrize('mutation', ['uuid', 'name', 'cost', 'parameters', 'duplicate'])
def test_scope_cannot_replace_a_bound_cost_identity_or_economic_declaration(mutation):
    rows = card_rows()
    costs = deepcopy(rows[0]['content']['game']['costConfiguration'])
    if mutation == 'uuid':
        costs[1]['uuid'] = 'different-identity'
    elif mutation == 'name':
        costs[1]['name'] = 'different-name'
    elif mutation == 'cost':
        costs[1]['cost'] = 1100
    elif mutation == 'parameters':
        costs[1]['parameters']['startingMode'] = 'different-economic-mode'
    else:
        costs.append(deepcopy(costs[1]))
    rows[2]['content']['game']['costConfiguration'] = costs
    plan = scoped_plan(rows)
    assert by_name(plan)['BF3Cards']['kind'] == 'UNKNOWN_FEATURE'
    assert any(issue.startswith('MODE_SCOPE_') for issue in plan['unresolved'])
    assert by_name(plan)['BF6Cards']['kind'] == 'PURCHASE'


def test_replaced_cost_list_can_narrow_to_the_identical_selected_operation():
    rows = card_rows()
    chosen = deepcopy(rows[0]['content']['game']['costConfiguration'][1])
    rows[2]['content']['game'].update(costConfiguration=[chosen],
                                     activeBetOptions=['BF3Cards'])
    plan = scoped_plan(rows)
    assert by_name(plan)['BF3Cards']['multiplier'] == 50
    assert plan['unresolved'] == []


@pytest.mark.parametrize('override', [
    dict(baseCostMultipliers=[]), dict(baseCostMultipliers=[True, 50]),
    dict(baseCostMultipliers=[0, 50]), dict(baseCostMultipliers=[-1, 50]),
    dict(defaultBaseCostMultiplier=True), dict(defaultBaseCostMultiplier=7),
    dict(maxBet=None), dict(maxBet=True), dict(maxBet='500000'),
    dict(minBet=-1), dict(minBet=50001, maxBet=50000),
    dict(minBet=20000, maxBet=40000), dict(maxBet=12000),
    dict(activeBetOptions=None), dict(activeBetOptions=['default', 'Undeclared']),
    dict(featureBetEnabled='false'),
])
def test_malformed_or_contradictory_operation_domain_remains_unexecutable(override):
    rows = card_rows()
    rows[2]['content']['game'].update(override)
    plan = scoped_plan(rows)
    assert by_name(plan)['BF3Cards']['kind'] == 'UNKNOWN_FEATURE'
    assert any(issue.startswith('MODE_SCOPE_') for issue in plan['unresolved'])
    assert by_name(plan)['BF6Cards']['multiplier'] == 50


def test_top_level_limits_are_resolved_and_intersect_the_game_limits():
    rows = card_rows()
    rows[2]['content']['limits'] = dict(minBet=50000, maxBet=50000)
    mode = by_name(scoped_plan(rows))['BF3Cards']
    assert mode['multiplier'] == 50
    assert mode['stake_domain']['min_bet'] == mode['stake_domain']['max_bet'] == 50000
    rows[2]['content']['limits']['maxBet'] = True
    assert by_name(scoped_plan(rows))['BF3Cards']['kind'] == 'UNKNOWN_FEATURE'


def test_later_matching_broad_override_keeps_server_order():
    rows = card_rows()
    rows.append(dict(scope={}, content=dict(game=dict(
        baseCostMultipliers=[2], defaultBaseCostMultiplier=2))))
    plan = scoped_plan(rows)
    assert [(m['name'], m['multiplier']) for m in plan['modes']] == [
        ('default', 2), ('BF3Cards', 2), ('BF6Cards', 2), ('BF9Cards', 2)]


def test_scope_prices_do_not_authorize_a_purchase_without_client_binding():
    plan = scoped_plan(card_rows(), source=SOURCE.replace('BuyFeatureController', 'OtherController'))
    assert all(m['kind'] != 'PURCHASE' for m in plan['modes'])
    assert plan['unresolved']


def test_invalid_purchase_scope_is_blocked_before_the_adapter_sends_it(tmp_path):
    rows = card_rows()
    rows[2]['content']['game']['maxBet'] = True
    result, emitted, _ = run_adapter(tmp_path, rows=rows)
    assert emitted == [('default', 10), ('BF6Cards', 75000),
                       ('BF9Cards', 100000), ('default', 10)]
    assert result.status == 'PARCIAL'
    assert 'MODE_SCOPE_' in result.error


def test_client_bound_named_purchase_resolves_its_bet_type_and_distinct_selector():
    game = dict(costConfiguration=[
        dict(name='default', uuid='base-other', cost=10),
        dict(name='DeclaredOption', uuid='purchase-other', cost=500)],
        activeBetOptions=['default', 'DeclaredOption'],
        namedScopes={'DeclaredOption': {'betType': 'bonus', 'featureType': 'server-option'}},
        baseCostMultipliers=[1, 9], defaultBaseCostMultiplier=9, minBet=10, maxBet=90)
    rows = [dict(scope={}, content=dict(game=game)),
            dict(scope=dict(betType='bonus', featureType='server-option'),
                 content=dict(game=dict(baseCostMultipliers=[4, 8],
                     defaultBaseCostMultiplier=8, minBet=2000, maxBet=5000)))]
    source = SOURCE.replace('BuyFeatureController', 'OtherController') + (
        'baseCostName:"DeclaredOption",betParams:{betType:Kinds.BONUS}')
    mode = by_name(scoped_plan(rows, source=source))['DeclaredOption']
    assert mode['kind'] == 'PURCHASE'
    assert mode['multiplier'] == 8
    assert mode['cost']*mode['multiplier'] == 4000
    assert mode['configuration_context'] == {'betType': 'bonus', 'featureType': 'server-option'}


def test_feature_boost_ante_uses_its_scope_without_becoming_a_purchase():
    costs = [dict(name=name, uuid='boost-'+name, cost=cost,
                  parameters=dict(startingMode=phase, startingPlays='1', winline='20'))
             for name, cost, phase in (('default-20', 20, 'base'),
                                       ('feature-20', 30, 'boost'))]
    rows = [dict(scope={}, content=dict(game=dict(costConfiguration=costs,
        baseCostMultipliers=[1, 5], defaultBaseCostMultiplier=5,
        featureBetEnabled=True, extraBetEnabled=False, minBet=20, maxBet=100))),
        dict(scope=dict(betType='default', featureType='feature-20'),
             content=dict(game=dict(baseCostMultipliers=[2, 3],
                 defaultBaseCostMultiplier=3, minBet=60, maxBet=90)))]
    plan = scoped_plan(rows)
    assert [(m['kind'], m['cost']*m['multiplier']) for m in plan['modes']] == [
        ('SPIN', 20), ('ANTE_BET', 60)]
    assert plan['unresolved'] == []
    rows[1]['content']['game']['featureBetEnabled'] = False
    disabled = scoped_plan(rows)
    assert [m['kind'] for m in disabled['modes']] == ['SPIN']
    assert disabled['disabled_modes'] == ['feature-20']
