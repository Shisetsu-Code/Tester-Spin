"""Source- and server-bound GPAS mode families observed in fresh demo config.

Mode classification alone never verifies execution. Each option must still
be sent in a new demo and pass the independent financial/terminal ledger.
"""
from __future__ import annotations

import re


def _parameters(row):
    params = row.get('parameters') if isinstance(row,dict) else None
    return params if isinstance(params,dict) else {}


def _base_plays(row):
    params=_parameters(row)
    return (params.get('startingPlays') in (1,'1') and
            params.get('evalPayout')=='LEFT_TO_RIGHT' and
            isinstance(params.get('startingMode'),str) and bool(params['startingMode']))


def _active_costs(costs, game):
    active=game.get('activeBetOptions')
    return [row for row in costs if isinstance(row,dict) and
            (active is None or row.get('name') in active)]


def _safe_legacy_flags(game):
    return game.get('featureBetEnabled') is not True and game.get('extraBetEnabled') is not True


def base_price_families(costs, game, contract, source):
    """Return base selectors only when the whole *active* family is unambiguous.

    Two observed wire variants:
      * monetary-labeled cost presets with identical base startingMode and
        explicitly scoped featureTypes (DOLLAR-10 .. DOLLAR-1000)
    Prices alone are insufficient: every row needs its own base-wager schema.
    """
    if not isinstance(costs,list) or not isinstance(game,dict) or not isinstance(contract,dict):
        return set()
    if contract.get('dialect')!='modern' or not _safe_legacy_flags(game):
        return set()
    entries=_active_costs(costs,game)
    if len(entries)<2 or len(entries)>40 or any(not _base_plays(r) for r in entries):
        return set()
    labels=[r.get('name') for r in entries]
    values=[r.get('cost') for r in entries]
    if (len(set(labels))!=len(labels) or
        any(type(x) is not str or not x or len(x)>80 for x in labels) or
        any(type(x) is not int or x<=0 for x in values)):
        return set()
    params=[_parameters(r) for r in entries]
    # Server-declared selectors, not a regex match on a title or a cost alone.
    named=game.get('namedScopes')
    if not isinstance(named,dict):
        named={}
    if all(re.fullmatch(r'DOLLAR-[1-9][0-9]{0,5}',n) and int(n.split('-')[1])==v
           and named.get(n)=={'betType':'default','featureType':n}
           for n,v in zip(labels,values)):
        if (len({p.get('startingMode') for p in params})==1 and
            len({p.get('winline') for p in params})==1 and
            all(p.get('winline') is not None for p in params)):
            return set(labels)
    # Numeric names/cost ratios without a declared server selector are NOT
    # sufficient. Live GPAS demos returned EngineError and, on another tier,
    # STAKE_UUID_MISMATCH even with featureType='default'. Fail closed.
    return set()


def is_disabled_extra_base(row, costs, game, contract):
    """An explicit inactive extra fallback can be the only playable base."""
    if (not isinstance(row,dict) or row.get('name')!='extra_disabled' or
        contract.get('dialect')!='modern' or game.get('extraBetEnabled') is not False or
        game.get('activeBetOptions')!=['extra_disabled']):
        return False
    first=next((x for x in costs if isinstance(x,dict) and x.get('name')=='default'),None)
    p,base=_parameters(row),_parameters(first)
    return bool(first and _base_plays(row) and _base_plays(first) and
                type(row.get('cost')) is int and row['cost']==first.get('cost') and
                p.get('winline')==base.get('winline') and p.get('evalPayout')==base.get('evalPayout'))


def uniquely_declared_standard(row, costs, contract, source):
    """Recognize a solitary server Standard base, not adjacent HR/extra modes."""
    p=_parameters(row)
    if (contract.get('dialect')!='modern' or not _base_plays(row) or
        p.get('startingMode')!='Standard' or
        not ('stakeCostUuid' in source and 'featureType' in source and 'GLU.game.playMoney' in source)):
        return False
    return sum(_parameters(x).get('startingMode')=='Standard' for x in costs)==1


def mixed_standard_line_selectors(costs, game, contract, source):
    """Bind a complete line ladder with one Standard base and several variants.

    The live GPAS client must expose wager/selector/line bindings. Every cost
    row must be an integer line tier, with a shared lines-per-unit ratio and
    a unique server startingMode. Distinct row UUIDs, rather than names, are
    still the settlement authority. No other declared economic modes may hide
    in this family. Unbound patterns (e.g. proportional labels with constant
    winline) remain UNKNOWN.
    """
    if (not isinstance(costs,list) or not isinstance(game,dict) or
        not isinstance(contract,dict) or contract.get('dialect')!='modern'
        or not _safe_legacy_flags(game) or not 3<=len(costs)<=30):
        return {}
    if not all(token in source for token in
               ('GLU.game.playMoney','stakeCostUuid','featureType','winline')):
        return {}
    active=game.get('activeBetOptions')
    if active is not None and (
            not isinstance(active,list) or set(active)!={r.get('name') for r in costs if isinstance(r,dict)}):
        return {}
    ratios=set();standards=[];identities=set();mapping={}
    for row in costs:
        if not isinstance(row,dict) or not _base_plays(row):
            return {}
        name,cost=row.get('name'),row.get('cost')
        p=_parameters(row)
        start=p.get('startingMode')
        winline=p.get('winline')
        uuid=row.get('uuid')
        if (type(name) is not str or not re.fullmatch(r'[1-9][0-9]{0,3}',name)
            or type(cost) is not int or cost<=0 or cost!=int(name)
            or not isinstance(winline,str) or not re.fullmatch(r'[1-9][0-9]{0,4}',winline)
            or not isinstance(uuid,str) or not uuid or uuid in identities):
            return {}
        identities.add(uuid)
        q,remain=divmod(int(winline),cost)
        if remain or not 1<=q<=50:
            return {}
        ratios.add(q)
        standards.append(name) if start=='Standard' else None
        mapping[name]=('default' if start=='Standard' else 'lines-'+winline)
    if len(ratios)!=1 or len(standards)!=1:
        return {}
    return mapping


def named_standard_line_selectors(costs, game, contract, source):
    """Bind all-Standard line wagers with one explicitly named base row.

    A genuine line domain can have numeric options named by their winline and
    one named base option (e.g. BasePP). The whole server cost table, selectors
    and cost/winline ratio must agree; this rule never promotes unknown buys.
    """
    if (not isinstance(costs,list) or not isinstance(game,dict) or
        not isinstance(contract,dict) or contract.get('dialect')!='modern'
        or not _safe_legacy_flags(game) or not 3<=len(costs)<=40):
        return {}
    if not all(key in source for key in
               ('GLU.game.playMoney','stakeCostUuid','winline','stakeCostName')):
        return {}
    active=game.get('activeBetOptions')
    if active is not None and (
            not isinstance(active,list) or set(active)!={r.get('name') for r in costs if isinstance(r,dict)}):
        return {}
    special=[];ratio=set();mapping={};uuids=set();levels=[]
    for row in costs:
        if not isinstance(row,dict) or not _base_plays(row):
            return {}
        p=_parameters(row)
        if p.get('startingMode')!='Standard':
            return {}
        name,cost,winline,uuid=row.get('name'),row.get('cost'),p.get('winline'),row.get('uuid')
        if (type(name) is not str or type(cost) is not int or cost<=0
            or not isinstance(winline,str) or not re.fullmatch(r'[1-9][0-9]{0,4}',winline)
            or not isinstance(uuid,str) or not uuid or uuid in uuids):
            return {}
        uuids.add(uuid)
        value=int(winline)
        factor,remainder=divmod(value,cost)
        if remainder or not 1<=factor<=100:
            return {}
        ratio.add(factor);levels.append(value)
        if re.fullmatch(r'[1-9][0-9]{0,4}',name):
            if int(name)!=value:return {}
        elif re.fullmatch(r'(?i:base(?:pp)?)',name):
            special.append((name,value))
        else:
            return {}
        mapping[name]='lines-'+str(value)
    if (len(special)!=1 or len(ratio)!=1 or len(set(levels))!=len(levels)
        or special[0][1]!=max(levels)):
        return {}
    return mapping


def card_buy_family(costs, game, contract, source):
    """A bounded, client-backed BF*Cards purchase family from live GPAS.

    Do not infer purchases from names or historical captures alone. Require
    the full *current* active-options list, a live BuyFeature client binder,
    individually named/UUID-backed feature options, and distinct server
    starting modes. Any incomplete/contradictory declaration fails closed.
    """
    if (not isinstance(costs,list) or not 2 <= len(costs) <= 12
        or not isinstance(game,dict) or not isinstance(contract,dict)
        or contract.get('dialect') != 'modern'
        or game.get('featureBetEnabled') is not True
        or not all(key in source for key in ('BuyFeatureController','featureType',
                                             'stakeCostUuid','GLU.game.playMoney'))):
        return set()
    active=game.get('activeBetOptions')
    if (not isinstance(active,list) or len(active)!=len(costs)
        or set(active)!={r.get('name') for r in costs if isinstance(r,dict)}):
        return set()
    bases=[r for r in costs if isinstance(r,dict) and r.get('name')=='default']
    if len(bases)!=1:
        return set()
    base=bases[0]
    if not _base_plays(base) or type(base.get('cost')) is not int or base['cost']<=0:
        return set()
    base_winline=_parameters(base).get('winline')
    if not isinstance(base_winline,str) or not base_winline:
        return set()
    seen_uuid={base.get('uuid')}
    seen_modes={_parameters(base).get('startingMode')}
    if not all(isinstance(x,str) and x for x in seen_uuid|seen_modes):
        return set()
    features=set()
    for row in costs:
        if row is base:
            continue
        if not isinstance(row,dict):
            return set()
        name=row.get('name')
        if not isinstance(name,str) or not re.fullmatch(r'BF[1-9][0-9]{0,2}Cards',name):
            return set()
        params=_parameters(row)
        uuid,mode=row.get('uuid'),params.get('startingMode')
        if (not _base_plays(row)
            or params.get('winline')!=base_winline
            or type(row.get('cost')) is not int or row['cost']<=base['cost']
            or not isinstance(uuid,str) or not uuid or uuid in seen_uuid
            or not isinstance(mode,str) or not mode or mode in seen_modes):
            return set()
        seen_uuid.add(uuid);seen_modes.add(mode);features.add(name)
    return features
