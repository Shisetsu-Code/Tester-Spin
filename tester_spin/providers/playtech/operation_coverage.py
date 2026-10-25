"""Exact operation inventory versus attempted and verified GPAS operations.

One item per *currently active* server cost row and live client contract.
A mode is not verified by appearing in a payload, having a UUID, or sharing
a protocol envelope with another mode.
"""
from collections import Counter

EXECUTABLE = frozenset(('SPIN', 'ANTE_BET', 'PURCHASE'))


def operation_coverage(plan, attempts=()):
    if not isinstance(plan, dict) or not isinstance(plan.get('modes'), list):
        raise ValueError('GPAS_OPERATION_PLAN_INVALID')
    modes=plan['modes']
    if any(not isinstance(m,dict) or not m.get('id') or
           not isinstance(m.get('kind'),str) for m in modes):
        raise ValueError('GPAS_OPERATION_MODE_INVALID')
    if len({m['id'] for m in modes}) != len(modes):
        raise ValueError('GPAS_OPERATION_IDS_AMBIGUOUS')
    observed={}
    for a in attempts:
        identity=getattr(a,'mode_id',None)
        if identity is None:
            raise ValueError('GPAS_OPERATION_ATTEMPT_UNBOUND')
        observed.setdefault(identity,[]).append(a)
    rows=[]
    for mode in modes:
        identity=mode['id']
        hits=observed.get(identity,[])
        # A purchase with several offered picks is not complete until
        # every server-advertised option is executed in a closed round.
        choices=mode.get('choice_domains',[])
        choice_complete=bool(not choices or all(
            isinstance(domain,dict) and
            set(domain.get('options',[]))<=set(domain.get('covered',[]))
            for domain in choices))
        valid=mode['kind'] in EXECUTABLE and any(
            getattr(a,'ok',False) is True and getattr(a,'terminal',False) is True
            for a in hits) and choice_complete
        rows.append(dict(id=identity,name=mode.get('name'),kind=mode['kind'],
                         discovered=True,executable=mode['kind'] in EXECUTABLE,
                         attempts=len(hits),verified=valid,
                         choice_coverage_complete=choice_complete,
                         failed_attempts=sum(not getattr(a,'ok',False) for a in hits)))
    expected=Counter(x['kind'] for x in rows if x['executable'])
    verified=Counter(x['kind'] for x in rows if x['verified'])
    return dict(schema='tester-spin/gpas-operation-coverage/v1',
                expected_by_kind={k:expected[k] for k in ('SPIN','ANTE_BET','PURCHASE')},
                verified_by_kind={k:verified[k] for k in ('SPIN','ANTE_BET','PURCHASE')},
                declared_unknown=[x['id'] for x in rows if not x['executable']],
                disabled_not_offered=list(plan.get('disabled_modes',[])),
                missing=[x['id'] for x in rows if x['executable'] and not x['verified']],
                modes=rows,
                all_declared_operations_verified=bool(
                    not plan.get('unresolved') and
                    all(x['verified'] for x in rows if x['executable']) and
                    any(x['kind']=='SPIN' for x in rows)))
