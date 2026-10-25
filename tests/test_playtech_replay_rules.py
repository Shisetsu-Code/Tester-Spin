"""Provider-wide triage: replay != settlement != verified coverage."""
from copy import deepcopy

import pytest

from tester_spin.providers.playtech.replay_rules import (
    plan_for_audit, route_rule, runtime_actions, RULE_SCHEMA,
)


def record(**changes):
    row = dict(game='gpas_example_pop', route_id=1, family='GPAS',
               diagnostic='NO_GAME_COMMANDS_CAPTURED', partial_reason=None,
               ui_actions_sent=1, game_commands_sent=0,
               game_commands_received=0, game_commands_paired=0,
               rounds_terminal=0, rounds_nonterminal=0, rounds=[])
    row.update(changes)
    return row


def terminal():
    return dict(wire_command_id=40021, round_closed=True,
                next_round='BET_END_STATE_IDENTIFIER', terminal_observed=True,
                cost_consistent=True, stake_wire=500, cost_wire=500)


def incomplete():
    return dict(wire_command_id=40021, round_closed=False,
                next_round='FreeGame', terminal_observed=False,
                cost_consistent=True)


def wire(*rounds):
    return dict(game_commands_sent=len(rounds), game_commands_received=len(rounds),
                game_commands_paired=len(rounds), rounds_terminal=sum(x['terminal_observed'] for x in rounds),
                rounds_nonterminal=sum(not x['terminal_observed'] for x in rounds), rounds=list(rounds))


def test_ngm_directory_never_claims_a_round_or_faulty_engine():
    row = record(game='ashadv', family='NGM', diagnostic='URL_DIRECTORY_ONLY_NO_CAPTURED_GAME_COMMANDS',
                 ui_actions_sent=4)
    rule = route_rule(row)
    assert rule['rule'] == 'CAPTURE_NGM_GAME_EVENTS'
    assert rule['result_status'] == 'PARCIAL'
    assert not rule['captured_replay_is_gameplay_proof']
    assert not rule['safe_to_auto_retry_a_wager']


def test_active_free_game_gets_continuation_not_another_spin():
    result = route_rule(record(game='gpas_squeen_pop', **wire(terminal(), incomplete()),
                               partial_reason='VISUAL_STATE_MISMATCH'))
    assert result['rule'] == 'RESUME_OPEN_FREE_GAME'
    assert result['open_rounds'] == 1
    assert result['new_demo_evidence_required']
    assert not result['safe_to_auto_retry_a_wager']


def test_closed_wire_commands_are_not_purchase_coverage():
    result = route_rule(record(game='gpas_wcupcc_pop', **wire(terminal(),terminal())))
    assert result['rule'] == 'VERIFY_DECLARED_MODES'
    assert result['costs_validated_in_capture']
    assert result['result_status'] == 'PARCIAL'


def test_readiness_and_visual_gate_without_wire():
    assert route_rule(record(partial_reason='GAME_NOT_READY'))['rule'] == 'WAIT_FOR_DEMO_READY'
    assert route_rule(record(partial_reason='VISUAL_STATE_MISMATCH'))['rule'] == 'REFRESH_VISUAL_TARGET'


def test_pending_command_or_conflicting_cost_never_auto_retried():
    unpaired = record(game_commands_sent=1)
    assert route_rule(unpaired)['rule'] == 'RECONCILE_UNCERTAIN_GAME_COMMAND'
    conflict = deepcopy(terminal())
    conflict['cost_consistent'] = False
    assert route_rule(record(**wire(conflict)))['rule'] == 'RECONCILE_SERVER_COST'
    assert not route_rule(record(**wire(conflict)))['safe_to_auto_retry_a_wager']


def test_off_provider_and_malformed_data_fail_closed():
    assert route_rule(record(game='OtherGame',family='UNKNOWN'))['rule'] == 'EXCLUDE_NON_PLAYTECH'
    with pytest.raises(ValueError, match='INCONSISTENT_WIRE_COUNTS'):
        route_rule(record(rounds_terminal=1))
    with pytest.raises(ValueError, match='INVALID_CAPTURE_COUNT'):
        route_rule(record(game_commands_sent=True))
    with pytest.raises(ValueError, match='INVALID_GAME_NAME'):
        route_rule(record(game='../../secrets.json'))
    with pytest.raises(ValueError, match='UNSUPPORTED_AUDIT_SCHEMA'):
        plan_for_audit({'schema':'other','routes':[]})


def test_missing_paired_command_details_cannot_prove_prices():
    with pytest.raises(ValueError, match='MISSING_GAME_COMMAND_DETAILS'):
        route_rule(record(game_commands_sent=1, game_commands_received=1, game_commands_paired=1,
                          rounds_terminal=1))


def test_aggregate_preserves_partial_and_groups_reusable_fixes():
    rows = [record(game='a',family='NGM'),record(game='b',family='NGM'),
            record(game='gpas_squeen_pop',**wire(incomplete())),record(**wire(terminal()))]
    result=plan_for_audit(dict(schema='tester-spin/playtech-fuzzer-evidence/v1',routes=rows))
    assert result['schema'] == RULE_SCHEMA
    assert result['games_promoted_to_ok'] == 0
    assert result['routes'] == 4
    assert result['worklist'][0]['rule'] == 'RESUME_OPEN_FREE_GAME'
    assert next(g['count'] for g in result['groups'] if g['rule']=='CAPTURE_NGM_GAME_EVENTS') == 2


def test_runtime_triage_never_overrides_real_test_verdict():
    rules=runtime_actions('gpas', ['CONTINUATION_STATE_UNKNOWN','BALANCE_NOT_RECONCILED'])
    assert {x['rule'] for x in rules} == {'RESUME_OPEN_FREE_GAME','RECONCILE_SERVER_COST'}
    assert all(x['status']=='PARCIAL' and not x['safe_to_auto_retry_a_wager'] for x in rules)
    assert runtime_actions('ngm', ['NGM_HAR_MISSING','NGM_FEATURE_INVENTORY_UNKNOWN'])
    assert runtime_actions('ngm', []) == []


def test_batch_111_reuses_family_primitives_without_inventing_success():
    base = [record(game='ngm_'+str(i),family='NGM') for i in range(80)]
    base += [record(game='gpas_'+str(i)) for i in range(14)]
    base += [record(game='ngm_review_'+str(i),family='NGM',
                    partial_reason='VISUAL_STATE_MISMATCH') for i in range(6)]
    base += [record(game='gpas_ready_'+str(i),partial_reason='GAME_NOT_READY') for i in range(3)]
    base += [record(game='gpas_checked_'+str(i), **wire(terminal())) for i in range(5)]
    base += [record(game='gpas_squeen_pop',**wire(incomplete()))]
    base += [record(game='other_'+str(i), family='UNKNOWN') for i in range(2)]
    output = plan_for_audit({'schema':'tester-spin/playtech-fuzzer-evidence/v1','routes':base})
    assert output['routes'] == 111
    assert output['games_promoted_to_ok'] == 0
    assert {x['rule']:x['count'] for x in output['groups']} == {
        'CAPTURE_NGM_GAME_EVENTS':80, 'CAPTURE_GPAS_GAME_COMMAND':14,
        'REFRESH_VISUAL_TARGET':6, 'WAIT_FOR_DEMO_READY':3,
        'VERIFY_DECLARED_MODES':5, 'RESUME_OPEN_FREE_GAME':1,
        'EXCLUDE_NON_PLAYTECH':2,
    }
