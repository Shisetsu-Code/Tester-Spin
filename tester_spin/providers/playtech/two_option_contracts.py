"""Fail-closed GPAS two-option contracts observed in live HardFire demo wires.

These are provider-family schemas, NOT game IDs or HAR replays. Names alone,
configuration alone, or a successful offline capture cannot certify a mode.
The live adapter still sends a NEW demo operation and verifies server UUID,
charge, balance, continuation and return to base.
"""
from __future__ import annotations
import re


def _available(rows, game, source, contract):
    if (not isinstance(rows, list) or len(rows)!=2 or
        not isinstance(game,dict) or not isinstance(contract,dict) or
        contract.get('dialect')!='modern' or
        not all(s in source for s in ('GLU.game.playMoney','stakeCostUuid','featureType'))):
        return False
    names=[r.get('name') for r in rows if isinstance(r,dict)]
    if len(names)!=2 or len(set(names))!=2:
        return False
    active=game.get('activeBetOptions')
    if active is not None and (not isinstance(active,list) or set(active)!=set(names)):
        return False
    scopes=game.get('namedScopes',{})
    if not isinstance(scopes,dict):
        return False
    for row in rows:
        params=row.get('parameters')
        if (not isinstance(params,dict) or params.get('startingPlays') not in ('1',1) or
            not isinstance(params.get('startingMode'),str) or not params['startingMode'] or
            type(row.get('cost')) is not int or row['cost']<=0 or
            not isinstance(row.get('uuid'),str) or not row['uuid']):
            return False
    return rows[0]['uuid']!=rows[1]['uuid']


def _scopes_agree(rows, game, selectors):
    scopes=game.get('namedScopes',{})
    for row in rows:
        scope=scopes.get(row['name'],{})
        if not isinstance(scope,dict):
            return False
        if scope and (scope.get('betType','default')!='default' or
                      scope.get('featureType',selectors[row['name']])!=selectors[row['name']]):
            return False
    return True


def infer_two_option_modes(costs, game, contract, source):
    """Map all modes or none; no partial guess and no title-specific tables."""
    if not _available(costs,game,source,contract):
        return {}
    rows=list(costs)
    by={x['name']:x for x in rows}
    # Same-winline variant: Classic is an alternative paid base (not antebet).
    classic=next((r for r in rows if r['name'].casefold()=='classic'),None)
    if classic is not None:
        base=next((r for r in rows if r is not classic),None)
        p=base['parameters']; q=classic['parameters']
        if (re.fullmatch(r'[1-9][0-9]{0,3}',base['name']) and
            p.get('startingMode')=='Standard' and
            re.fullmatch(r'[1-9][0-9]{0,4}',str(p.get('winline',''))) and
            p.get('winline')==q.get('winline') and
            p['startingMode']!=q.get('startingMode') and
            base['cost']==classic['cost'] and
            game.get('extraBetEnabled') is not True and
            game.get('featureBetEnabled') is not True):
            selectors={base['name']:'default',classic['name']:'classic'}
            if _scopes_agree(rows,game,selectors):
                return {n:{'kind':'SPIN','selector':v} for n,v in selectors.items()}
        return {}
    # Feature-boost ante: default-N and feature-N share winline N, but have
    # different cost/startingMode. A 50% extra stake is asserted by *current*
    # server config and a fresh runtime, not inferred from an archive.
    base=next((r for r in rows if re.fullmatch(r'default-[1-9][0-9]{0,3}',r['name'])),None)
    if base is not None:
        n=base['name'].split('-')[1]
        feature=by.get('feature-'+n)
        if feature is None:return {}
        p=base['parameters'];q=feature['parameters']
        if (str(p.get('winline'))==n and q.get('winline')==p.get('winline') and
            p.get('startingMode')!=q.get('startingMode') and
            feature['cost']*2==base['cost']*3 and
            game.get('featureBetEnabled') is True and
            game.get('extraBetEnabled') is not True):
            selectors={base['name']:'default',feature['name']:feature['name']}
            if _scopes_agree(rows,game,selectors):
                return {base['name']:{'kind':'SPIN','selector':'default'},
                        feature['name']:{'kind':'ANTE_BET','selector':feature['name']}}
        return {}
    # Numeric base + explicitly enabled BuyBonus. Unlike an unbound string
    # label, both cost rows agree on line count and playable session version.
    bonus=by.get('BuyBonus')
    if bonus is not None:
        base=next((r for r in rows if r is not bonus),None)
        p=base['parameters'];q=bonus['parameters']
        if (re.fullmatch(r'[1-9][0-9]{0,3}',base['name']) and
            p.get('winline')==q.get('winline') and
            isinstance(p.get('winline'),str) and p.get('winline').isdigit() and
            p.get('startingMode')!=q.get('startingMode') and
            bonus['cost']>=base['cost']*10 and
            game.get('featureBetEnabled') is True and
            game.get('extraBetEnabled') is not True):
            selectors={base['name']:'default','BuyBonus':'buy-bonus'}
            if _scopes_agree(rows,game,selectors):
                return {base['name']:{'kind':'SPIN','selector':'default'},
                        'BuyBonus':{'kind':'PURCHASE','selector':'buy-bonus'}}
    return {}
