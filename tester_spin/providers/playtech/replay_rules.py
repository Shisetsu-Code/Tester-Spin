"""Evidence-first rules for prioritizing incomplete Playtech verifications.

This module never sends inputs, resumes captured accounts, or promotes a game
from PARCIAL to OK. It converts *sanitized* replay evidence into explicit,
provider-family-wide next steps for a new demo verification run. A fuzzer replay
and a fresh Tester-Spin runtime trace have different evidentiary authority.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re

AUDIT_SCHEMA = 'tester-spin/playtech-fuzzer-evidence/v1'
RULE_SCHEMA = 'tester-spin/playtech-replay-rules/v1'
_SAFE_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,119}\Z')
_MAX_ROUTES = 1024

# Every rule is a bounded next *verification* action, not a captured command.
RULES = {
    'EXCLUDE_NON_PLAYTECH': (0, 'Excluir del adaptador Playtech', 'provider-mismatch'),
    'WAIT_FOR_DEMO_READY': (2, 'Esperar bootstrap y estado jugable demostrados antes de tomar una nueva captura; no repetir entradas anteriores', 'readiness'),
    'REFRESH_VISUAL_TARGET': (2, 'Recapturar interfaz y geometría del iframe; verificar estado actual antes de volver a decidir', 'visual-state'),
    'CAPTURE_NGM_GAME_EVENTS': (3, 'Instrumentar el cliente NGM/iframe de una demo nueva y correlacionar SpinRequest, respuesta, premio y cierre; la negociación urlList no es una ronda', 'ngm-capture'),
    'CAPTURE_GPAS_GAME_COMMAND': (3, 'Instrumentar el socket GPAS de una demo nueva y registrar GameCommand con correlationId, request y respuesta', 'gpas-capture'),
    'RECONCILE_UNCERTAIN_GAME_COMMAND': (5, 'Resolver el resultado de los comandos emitidos sin respuesta usando evidencia del servidor; nunca repetir la apuesta incierta', 'unpaired-wire'),
    'RESUME_OPEN_FREE_GAME': (5, 'En la misma sesión viva, resolver FreeGame con el contrato vigente y comprobar cierre/retorno; si la sesión expiró, iniciar una demo nueva sin repetir la apuesta antigua', 'free-game'),
    'RECONCILE_SERVER_COST': (5, 'Revisar betCost/stakeAmount/gameData.stake y saldo autoritativo antes de autorizar más apuestas', 'economic-integrity'),
    'VERIFY_DECLARED_MODES': (4, 'Descubrir compras y modificadores desde el cliente/configuración vigente; ejecutar ramas distintas en sesiones demo verificadas, con retorno a base', 'mode-coverage'),
    'INSPECT_UNKNOWN_PROTOCOL': (1, 'Conservar PARCIAL hasta demostrar el protocolo; no asumir que pertenece a GPAS o NGM', 'unknown-capture'),
}


def _count(row: dict, key: str) -> int:
    value = row.get(key, 0)
    if type(value) is not int or not 0 <= value <= 1_000_000:
        raise ValueError('INVALID_CAPTURE_COUNT:'+key)
    return value


def route_rule(route: dict) -> dict:
    """Classify one offline replay, preserving the evidence/closure boundary."""
    if not isinstance(route, dict):
        raise ValueError('INVALID_ROUTE')
    family = route.get('family')
    if family not in ('GPAS', 'NGM', 'UNKNOWN'):
        raise ValueError('INVALID_GAME_FAMILY')
    game = route.get('game')
    if not isinstance(game, str) or not _SAFE_NAME.fullmatch(game):
        raise ValueError('INVALID_GAME_NAME')
    route_id = route.get('route_id')
    if route_id is not None and (type(route_id) is not int or not 0 <= route_id <= 1_000_000):
        raise ValueError('INVALID_ROUTE_ID')
    commands = _count(route, 'game_commands_paired')
    sent = _count(route, 'game_commands_sent')
    received = _count(route, 'game_commands_received')
    terminal = _count(route, 'rounds_terminal')
    open_rounds = _count(route, 'rounds_nonterminal')
    _count(route, 'ui_actions_sent')
    reason = route.get('partial_reason')
    if reason not in (None, 'GAME_NOT_READY', 'VISUAL_STATE_MISMATCH', 'OTHER'):
        raise ValueError('UNKNOWN_REPLAY_FAILURE')
    if sent < commands or received < commands or commands < terminal + open_rounds:
        raise ValueError('INCONSISTENT_WIRE_COUNTS')

    rounds = route.get('rounds', [])
    if not isinstance(rounds, list) or len(rounds) > 1000:
        raise ValueError('INVALID_ROUND_EVIDENCE')
    if len(rounds) != commands:
        raise ValueError('MISSING_GAME_COMMAND_DETAILS')
    # Missing fields cannot become a price/settlement assertion.
    bad_cost = any(isinstance(r, dict) and r.get('cost_consistent') is False for r in rounds)
    unknown_cost = any(not isinstance(r, dict) or r.get('cost_consistent') is not True for r in rounds)
    free_game = any(isinstance(r, dict) and r.get('next_round') == 'FreeGame'
                    and r.get('round_closed') is False for r in rounds)
    unknown_open = any(isinstance(r, dict) and not r.get('terminal_observed')
                       and r.get('next_round') != 'FreeGame' for r in rounds)

    if family == 'UNKNOWN':
        name = 'EXCLUDE_NON_PLAYTECH' if not game.startswith('gpas_') else 'INSPECT_UNKNOWN_PROTOCOL'
    elif sent != commands or received != commands:
        name = 'RECONCILE_UNCERTAIN_GAME_COMMAND'
    elif bad_cost:
        name = 'RECONCILE_SERVER_COST'
    elif open_rounds or free_game or unknown_open:
        name = 'RESUME_OPEN_FREE_GAME' if family == 'GPAS' and free_game and not unknown_open else 'RECONCILE_UNCERTAIN_GAME_COMMAND'
    elif reason == 'GAME_NOT_READY' and not sent:
        name = 'WAIT_FOR_DEMO_READY'
    elif reason == 'VISUAL_STATE_MISMATCH' and not sent:
        name = 'REFRESH_VISUAL_TARGET'
    elif family == 'NGM' and not commands:
        name = 'CAPTURE_NGM_GAME_EVENTS'
    elif family == 'GPAS' and not commands:
        name = 'CAPTURE_GPAS_GAME_COMMAND'
    elif commands and terminal == commands:
        name = 'VERIFY_DECLARED_MODES'
    else:
        name = 'INSPECT_UNKNOWN_PROTOCOL'

    priority, instruction, group = RULES[name]
    return {
        'game': game,
        'route_id': route_id,
        'family': family,
        'rule': name,
        'group': group,
        'priority': priority,
        'instruction': instruction,
        'captured_commands': commands,
        'terminal_rounds': terminal,
        'open_rounds': open_rounds,
        'costs_validated_in_capture': commands > 0 and not unknown_cost and not bad_cost,
        'safe_to_auto_retry_a_wager': False,
        'result_status': 'PARCIAL',
        'new_demo_evidence_required': True,
        'captured_replay_is_gameplay_proof': False,
    }


def plan_for_audit(audit: dict) -> dict:
    if not isinstance(audit, dict) or audit.get('schema') != AUDIT_SCHEMA:
        raise ValueError('UNSUPPORTED_AUDIT_SCHEMA')
    routes = audit.get('routes')
    if not isinstance(routes, list) or len(routes) > _MAX_ROUTES:
        raise ValueError('INVALID_ROUTE_SET')
    decisions = [route_rule(r) for r in routes]
    decisions.sort(key=lambda r: (-r['priority'], r['group'], r['game'], r['route_id'] if r['route_id'] is not None else -1))
    groups = Counter(d['rule'] for d in decisions)
    examples = {rule: sorted({r['game'] for r in decisions if r['rule'] == rule})[:5]
                for rule in groups}
    return {
        'schema': RULE_SCHEMA,
        'routes': len(decisions),
        'groups': [dict(rule=rule, count=count, examples=examples[rule],
                        priority=RULES[rule][0], instruction=RULES[rule][1])
                   for rule, count in sorted(groups.items(), key=lambda x: (-RULES[x[0]][0], x[0]))],
        'worklist': decisions,
        'games_promoted_to_ok': 0,
        'limits': ['Only captured evidence is classified',
                   'Missing commands may be missing capture, not a game failure',
                   'NGM offline runtime traces can independently prove rounds; fuzzer websocket absence cannot negate them',
                   'A historical session cannot be resumed by sending old requests or coordinates'],
    }


def runtime_actions(variant: str, issues: list[str]) -> list[dict]:
    """Bind common failure classes to a short, non-executing next-step plan."""
    if variant not in ('gpas', 'ngm') or not isinstance(issues, list):
        raise ValueError('INVALID_RUNTIME_TRIAGE')
    rules: set[str] = set()
    for issue in issues:
        if not isinstance(issue, str):
            raise ValueError('INVALID_RUNTIME_ISSUE')
        if variant == 'ngm':
            if 'BOOTSTRAP' in issue or 'SPIN_ACTION_NOT_BOUND' in issue or 'NOT_READY_FOR_SPIN' in issue:
                rules.add('WAIT_FOR_DEMO_READY')
            if any(x in issue for x in ('HAR_MISSING', 'HAR_EMPTY', 'SOURCE_MISMATCH', 'MANIFEST_MISMATCH', 'INSTRUMENTATION')):
                rules.add('CAPTURE_NGM_GAME_EVENTS')
            if any(x in issue for x in ('ROUND_NOT_CLOSED', 'CONTINUATION', 'FREE_SPINS', 'PAYOUT')):
                rules.add('RECONCILE_UNCERTAIN_GAME_COMMAND')
            if any(x in issue for x in ('INVENTORY_UNKNOWN', 'FEATURE_', 'CONTROL_', 'SELECTOR_', 'PLAN_', 'SERIALIZER_')):
                rules.add('VERIFY_DECLARED_MODES')
        else:
            if 'BOOTSTRAP' in issue or 'SESSION' in issue:
                rules.add('WAIT_FOR_DEMO_READY')
            if any(x in issue for x in ('CONTINUATION', 'ROUND_STEP_LIMIT', 'PICK_COMMAND', 'PICK_DOMAIN')):
                rules.add('RESUME_OPEN_FREE_GAME')
            if any(x in issue for x in ('CHOICE_BRANCHES_PENDING', 'UNBOUND_STAKE', 'FEATURE', 'MODE_')):
                rules.add('VERIFY_DECLARED_MODES')
            if 'COMMAND_RESPONSE_MISSING' in issue:
                rules.add('RECONCILE_UNCERTAIN_GAME_COMMAND')
        if any(x in issue for x in ('BALANCE', 'BET_COST_MISMATCH', 'CHARGE', 'MONEY', 'STAKE_UUID')):
            rules.add('RECONCILE_SERVER_COST')
    if not rules and issues:
        rules.add('INSPECT_UNKNOWN_PROTOCOL')
    return [dict(rule=name, priority=RULES[name][0], instruction=RULES[name][1],
                 status='PARCIAL', safe_to_auto_retry_a_wager=False)
            for name in sorted(rules, key=lambda x: (-RULES[x][0], x))]


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Plan bounded Playtech verification from a sanitized fuzzer audit')
    parser.add_argument('sanitized_audit', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    source = args.sanitized_audit
    if source.stat().st_size > 8*1024*1024:
        parser.error('AUDIT_TOO_LARGE')
    report = plan_for_audit(json.loads(source.read_text(encoding='utf-8')))
    output = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.out:
        if args.out.resolve() == source.resolve():
            parser.error('Output must differ from input')
        args.out.write_text(output, encoding='utf-8')
    else:
        print(output)


if __name__ == '__main__':
    main()
