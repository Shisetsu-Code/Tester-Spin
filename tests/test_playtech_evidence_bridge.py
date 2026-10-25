"""User-supplied Playtech evidence cannot masquerade as settled gameplay."""
import json
import pytest
from tester_spin.providers.playtech.evidence_bridge import summarize_capture

def op(kind,*,ended=True):
    return dict(kind=kind,protocolComplete=ended,
        endpoint='wss://private.example/ws?client=DO_NOT_PRINT',session='DO_NOT_PRINT',
        requests=[dict(correlationId='SECRET_CORRELATION',url='wss://secret')],
        responses=[dict(correlationId='SECRET_CORRELATION',
            nextRound='BET_END_STATE_IDENTIFIER' if ended else 'ChooseFG',
            remainingPlays=0 if ended else 1)])

def bundle():
    records=[
      dict(id='gpas_checked_pop',status='recorded',authority='model-reported',
           url='https://private.example/?token=DO_NOT_PRINT',
           attempts=[dict(modelReport={'notes':'DO_NOT_PRINT'},
                          operations=[op('buyFeature3')])]),
      dict(id='gpas_open_pop',status='needs_review',
           attempts=[dict(operations=[op('stakeCostUuid:SECRET_UUID',ended=False)])]),
      dict(id='ashadv',status='recorded',authority='model-reported',
           attempts=[dict(modelReport={'notes':'DO_NOT_PRINT'},operations=[])]),
    ]
    return (dict(games=records,total=3,excludedPrevious15=True),
      dict(protocolController=dict(completedRuns=[
        dict(gameId='gpas_checked_pop',terminal='BET_END_STATE_IDENTIFIER',remainingPlays=0)])),
      dict(games=[dict(id='gpas_open_pop',status='revision_manual')]))


def test_bridge_separates_visual_report_from_terminal_wire_and_choice():
    result=summarize_capture(*bundle())
    assert result['scope']==dict(games=3,gpas=2,ngm=1,
        operation_records=2,terminal_wire_records=1,unresolved_wire_records=1,
        controller_summary_runs=1,manual_review_games=1)
    checks={x['game_code']:x for x in result['rows']}
    assert checks['gpas_checked_pop']['terminal_wire_operations']==1
    assert checks['gpas_checked_pop']['game_verdict']=='NOT_ESTABLISHED'
    assert not checks['gpas_checked_pop']['independent_balance_verified']
    assert checks['gpas_open_pop']['next_primitive']=='PLAYER_CHOICE_SERIALIZER_UNBOUND'
    assert checks['gpas_open_pop']['observed_mode_labels']==['UNKNOWN_OR_UUID_SELECTOR']
    assert checks['ashadv']['next_primitive']=='NGM_CLIENT_RUNTIME_EVIDENCE_REQUIRED'
    assert result['game_verdicts_changed']==0


def test_bridge_strips_session_urls_secrets_and_model_report_content():
    result=summarize_capture(*bundle())
    serialized=json.dumps(result)
    for token in ('DO_NOT_PRINT','SECRET_UUID','SECRET_CORRELATION',
                  'wss://','https://private','modelReport','session='):
        assert token not in serialized
    assert 'buyFeature3' in serialized


def test_uncorrelated_or_unclosed_wager_never_becomes_wire_terminal():
    c,s,m=bundle()
    attempt=c['games'][0]['attempts'][0]
    attempt['operations'][0]['responses'][0]['correlationId']='DIFFERENT'
    assert summarize_capture(c,s,m)['scope']['terminal_wire_records']==0
    attempt['operations'][0]['responses'][0]['correlationId']='SECRET_CORRELATION'
    attempt['operations'][0]['protocolComplete']=False
    assert summarize_capture(c,s,m)['scope']['terminal_wire_records']==0


def test_invalid_scope_and_unknown_manual_ids_fail_closed():
    c,s,m=bundle()
    c['excludedPrevious15']=False
    with pytest.raises(ValueError,match='BUNDLE_SCOPE_INVALID'):
        summarize_capture(c,s,m)
    c['excludedPrevious15']=True
    m['games'][0]['id']='not-in-catalog'
    with pytest.raises(ValueError,match='BUNDLE_MANUAL_UNKNOWN_GAME'):
        summarize_capture(c,s,m)


def test_duplicate_games_cannot_be_inferred_as_distinct():
    c,s,m=bundle()
    c['games'].append(c['games'][0].copy())
    c['total']=len(c['games'])
    with pytest.raises(ValueError,match='BUNDLE_GAME_IDS_INVALID'):
        summarize_capture(c,s,m)
