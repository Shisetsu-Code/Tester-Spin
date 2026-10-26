"""Resolve stake declarations for an already bound GPAS operation.

The mode's semantic classification and selector must come from its client
contract. Scoped prices never create a purchase or a new executable mode.
"""
from .protocol import money, resolve_configuration


def _stake_limits(configuration, game):
    limits = configuration.get('limits', {})
    if not isinstance(limits, dict):
        raise ValueError('MODE_SCOPE_LIMITS_INVALID')
    minimum, maximum = 0, None
    for values in (game, limits):
        if 'minBet' in values:
            low = values['minBet']
            if not money(low):
                raise ValueError('MODE_SCOPE_MIN_BET_INVALID')
            minimum = max(minimum, low)
        if 'maxBet' in values:
            high = values['maxBet']
            if not money(high) or not high:
                raise ValueError('MODE_SCOPE_MAX_BET_INVALID')
            maximum = high if maximum is None else min(maximum, high)
    if maximum is not None and minimum > maximum:
        raise ValueError('MODE_SCOPE_LIMITS_CONTRADICTORY')
    return minimum, maximum


def validate_stake_domain(configuration):
    """Validate economic declarations without classifying or executing a mode.

    Shared by current-session discovery and historical wire evaluation. Explicit
    nulls, booleans and malformed domains are not equivalent to absent limits.
    """
    if not isinstance(configuration, dict):
        raise ValueError('MODE_SCOPE_CONFIGURATION_INVALID')
    game = configuration.get('game')
    if not isinstance(game, dict):
        raise ValueError('MODE_SCOPE_GAME_MISSING')
    factors = game.get('baseCostMultipliers', game.get('coinSizes'))
    if not isinstance(factors, list) or not factors or not all(money(n) and n > 0 for n in factors):
        raise ValueError('MODE_SCOPE_MULTIPLIER_DOMAIN_INVALID')
    default = game.get('defaultBaseCostMultiplier')
    if 'defaultBaseCostMultiplier' in game and (
            not money(default) or not default or default not in factors):
        raise ValueError('MODE_SCOPE_DEFAULT_FACTOR_INVALID')
    minimum, maximum = _stake_limits(configuration, game)
    return dict(factors=list(factors), default_factor=default,
                min_bet=minimum, max_bet=maximum)


def resolve_operation_stake(configuration_rows, mode, declared_costs, *, enabled_flag=None):
    """Return stake metadata, or None when this operation is explicitly disabled.

Matching rows retain the server's merge order, including array replacement.
An overridden economic identity needs a new client binding rather than reuse
of the base table's classification. Errors block this mode before dispatch.
"""
    context = {'betType': mode['bet_type'], 'featureType': mode['selector']}
    if not all(isinstance(v, str) and v for v in context.values()):
        raise ValueError('MODE_SCOPE_CONTEXT_INVALID')
    try:
        configuration = resolve_configuration(configuration_rows, context)
    except (TypeError, ValueError) as exc:
        raise ValueError('MODE_SCOPE_CONFIGURATION_INVALID') from exc
    game = configuration.get('game')
    if not isinstance(game, dict):
        raise ValueError('MODE_SCOPE_GAME_MISSING')
    if enabled_flag and enabled_flag in game:
        if type(game[enabled_flag]) is not bool:
            raise ValueError('MODE_SCOPE_ENABLED_FLAG_INVALID')
        if game[enabled_flag] is False:
            return None
    active = game.get('activeBetOptions')
    if 'activeBetOptions' in game and (
            not isinstance(active, list) or
            not all(isinstance(name, str) and name for name in active) or
            len(set(active)) != len(active)):
        raise ValueError('MODE_SCOPE_ACTIVE_OPTIONS_INVALID')
    declared_names = {row['name'] for row in declared_costs}
    if active is not None and any(name not in declared_names and name != 'default' for name in active):
        raise ValueError('MODE_SCOPE_ACTIVE_OPTION_UNBOUND')
    alias = (mode['kind'] == 'SPIN' and declared_costs and
             declared_costs[0]['uuid'] == mode['id'])
    if active is not None and mode['name'] not in active and not (alias and 'default' in active):
        return None

    costs = game.get('costConfiguration')
    if not isinstance(costs, list) or not costs:
        raise ValueError('MODE_SCOPE_COSTS_MISSING')
    names, identities = set(), set()
    declared = {row['uuid']: row for row in declared_costs}
    selected = None
    for row in costs:
        if not isinstance(row, dict) or not money(row.get('cost')) or not row['cost']:
            raise ValueError('MODE_SCOPE_COST_INVALID')
        name, identity = row.get('name'), row.get('uuid')
        if (not isinstance(name, str) or not name or not isinstance(identity, str) or
                not identity or name in names or identity in identities):
            raise ValueError('MODE_SCOPE_COST_IDENTITY_INVALID')
        names.add(name)
        identities.add(identity)
        if identity == mode['id'] and name == mode['name']:
            selected = row
        # A new active declaration cannot hide behind a pre-existing mode's
        # otherwise valid context and make the inventory look complete.
        if active is None or name in active or (row is costs[0] and 'default' in active):
            if identity not in declared or row != declared[identity]:
                raise ValueError('MODE_SCOPE_COST_CHANGED')
    if selected is None or selected != mode['declaration']:
        raise ValueError('MODE_SCOPE_COST_IDENTITY_MISMATCH')
    if active is not None and any(name not in names and name != 'default' for name in active):
        raise ValueError('MODE_SCOPE_ACTIVE_OPTION_UNBOUND')

    domain = validate_stake_domain(configuration)
    factors, default = domain['factors'], domain['default_factor']
    minimum, maximum = domain['min_bet'], domain['max_bet']
    eligible = [factor for factor in factors if minimum <= selected['cost']*factor
                and (maximum is None or selected['cost']*factor <= maximum)]
    if not eligible:
        raise ValueError('MODE_SCOPE_NO_LEGAL_STAKE')
    multiplier = min(eligible)
    if mode['kind'] == 'PURCHASE' and default is not None:
        if default not in eligible:
            raise ValueError('MODE_SCOPE_DEFAULT_OUTSIDE_LIMITS')
        multiplier = default
    return dict(multiplier=multiplier, configuration_context=context,
                stake_domain=domain)
