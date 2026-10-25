"""Import captured Playtech evidence without importing sessions or verdicts.

Raw model reports, socket URLs, private traces and user-local paths NEVER reach
the returned structure. Wire closure is *not* financial settlement or a Tester-
Spin OK. Only a new runtime execution can establish that verdict.
"""
from __future__ import annotations

from collections import Counter
import re

_ID=re.compile(r'(?:gpas_)?[A-Za-z][A-Za-z0-9_]{0,79}\Z')
_MODE=re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,55}\Z')
_END='BET_END_STATE_IDENTIFIER'
_AUTH={'model-reported','direct-observation','scope-reconciliation','captured-protocol'}


def _labels(value):
    if not isinstance(value,str) or not _MODE.fullmatch(value):
        return 'UNKNOWN_OR_UUID_SELECTOR'
    if value.casefold().startswith('stakecostuuid'):
        return 'UNKNOWN_OR_UUID_SELECTOR'
    return value


def _correlated_terminal(op):
    """Use correlations only transiently; never return or print those IDs."""
    if not isinstance(op,dict):
        return False
    requests=op.get('requests') or []
    responses=op.get('responses') or []
    if (not isinstance(requests,list) or not isinstance(responses,list)
        or not requests or len(requests)!=len(responses)
        or len(requests)>1000 or not all(isinstance(x,dict) for x in requests+responses)):
        return False
    sent=[x.get('correlationId') for x in requests]
    received=[x.get('correlationId') for x in responses]
    if (not all(isinstance(x,str) and x and len(x)<130 for x in sent+received)
        or len(sent)!=len(set(sent)) or set(sent)!=set(received)):
        return False
    last=responses[-1]
    return (op.get('protocolComplete') is True
            and last.get('nextRound')==_END
            and type(last.get('remainingPlays')) is int
            and last['remainingPlays']==0)


def summarize_capture(catalog,final,manual):
    """Produce a safe investigation worklist, never a playable request."""
    if not all(isinstance(o,dict) for o in (catalog,final,manual)):
        raise ValueError('BUNDLE_ROOT_INVALID')
    games=catalog.get('games')
    if (not isinstance(games,list) or len(games)>1000
        or catalog.get('total')!=len(games)
        or catalog.get('excludedPrevious15') is not True):
        raise ValueError('BUNDLE_SCOPE_INVALID')
    ids=[g.get('id') for g in games if isinstance(g,dict)]
    if len(ids)!=len(games) or len(set(ids))!=len(ids) or any(not isinstance(s,str) or not _ID.fullmatch(s) for s in ids):
        raise ValueError('BUNDLE_GAME_IDS_INVALID')
    review=manual.get('games',[])
    if not isinstance(review,list) or any(not isinstance(x,dict) for x in review):
        raise ValueError('BUNDLE_MANUAL_LIST_INVALID')
    review_ids={x.get('id') for x in review}
    if not review_ids.issubset(set(ids)):
        raise ValueError('BUNDLE_MANUAL_UNKNOWN_GAME')
    completed=final.get('protocolController',{}).get('completedRuns',[])
    if not isinstance(completed,list):
        raise ValueError('BUNDLE_PROTOCOL_RUNS_INVALID')
    controller={x.get('gameId') for x in completed if isinstance(x,dict) and
                x.get('terminal')==_END and x.get('remainingPlays')==0}
    if not controller.issubset(set(ids)):
        raise ValueError('BUNDLE_PROTOCOL_RUN_UNKNOWN_GAME')
    rows=[]
    for game in games:
        code=game['id']
        candidates=Counter()
        terminal=0;unclosed=0;paired=0
        attempts=game.get('attempts',[])
        if not isinstance(attempts,list) or len(attempts)>1000:
            raise ValueError('BUNDLE_ATTEMPTS_INVALID')
        for attempt in attempts:
            if not isinstance(attempt,dict):
                raise ValueError('BUNDLE_ATTEMPT_INVALID')
            for op in attempt.get('operations') or []:
                if not isinstance(op,dict):
                    continue
                label=_labels(op.get('kind'))
                candidates[label]+=1
                if _correlated_terminal(op):
                    terminal+=1;paired+=1
                else:
                    unclosed+=1
                    # A matched but unclosed response is still recorded,
                    # without implying a successful bonus.
                    req=op.get('requests') or []
                    rep=op.get('responses') or []
                    if req and rep and {x.get('correlationId') for x in req if isinstance(x,dict)}=={
                        x.get('correlationId') for x in rep if isinstance(x,dict)}:
                        paired+=1
        family='GPAS' if code.startswith('gpas_') else 'NGM'
        if code in review_ids:
            next_step='PLAYER_CHOICE_SERIALIZER_UNBOUND'
        elif family=='NGM':
            next_step='NGM_CLIENT_RUNTIME_EVIDENCE_REQUIRED'
        elif unclosed:
            next_step='RECONCILE_UNCLOSED_GPAs_COMMAND'
        elif terminal:
            next_step='RUN_NEW_DEMO_LEDGER_AND_MODE_COVERAGE'
        else:
            next_step='CAPTURE_GPAs_GAME_COMMANDS'
        rows.append(dict(game_code=code,family=family,
            authority=game.get('authority') if game.get('authority') in _AUTH else 'UNKNOWN',
            source_status='recorded' if game.get('status')=='recorded' else 'requires-review',
            recorded_attempts=len(attempts),wire_operations=sum(candidates.values()),
            correlated_operations=paired,terminal_wire_operations=terminal,
            nonterminal_wire_operations=unclosed,
            observed_mode_labels=sorted(candidates),
            external_controller_terminal_summary=code in controller,
            next_primitive=next_step,
            independent_balance_verified=False,game_verdict='NOT_ESTABLISHED'))
    rows.sort(key=lambda x:x['game_code'])
    return dict(schema='tester-spin/playtech-capture-evidence-bridge/v1',
                scope=dict(games=len(rows),
                  gpas=sum(x['family']=='GPAS' for x in rows),
                  ngm=sum(x['family']=='NGM' for x in rows),
                  operation_records=sum(x['wire_operations'] for x in rows),
                  terminal_wire_records=sum(x['terminal_wire_operations'] for x in rows),
                  unresolved_wire_records=sum(x['nonterminal_wire_operations'] for x in rows),
                  controller_summary_runs=len(controller),
                  manual_review_games=len(review_ids)),
                rows=rows,game_verdicts_changed=0,
                caveats=[
                    'Evidence closure does not reconcile financial balance or feature coverage.',
                    'Model-reported visual completion is not proof of gameplay commands.',
                    'Never reuse a historical wager, client token or session URL.',
                ])
