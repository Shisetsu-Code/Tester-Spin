"""Provenance and coverage checks for the user's 32 HardFire HAR captures.

No raw HTTP/WS traffic, session keys, tokens, cookies or headers in repo.
Every game changing PARCIAL->OK has an independent fresh demo CI witness.
"""
import json
from pathlib import Path

FIX=Path(__file__).parent/'fixtures/playtech_hardfire_20261025_sanitized.json'


def records():
    return json.loads(FIX.read_text(encoding='utf-8'))


def test_original_archive_counts_and_private_source_boundary():
    d=records()
    assert d['schema']=='tester-spin/hardfire-capture-audit/v1'
    assert len(d['artifact_source_sha256'])==64
    assert d['har_total']==32 and d['har_empty']==8 and d['har_nonempty']==24
    assert len(d['gpas'])==d['attributed_gpas_games']==8
    assert len(d['ngm'])==d['ngm_manifest_games']==7
    assert len({r['code'] for r in d['gpas']+d['ngm']})==15
    assert d['attributed_gamecommands']==32
    assert d['paired_gamecommands']==31
    # Some sockets were captured too late for a trustworthy game association.
    assert d['unattributed_wager_requests']==17


def test_gpas_captured_commands_do_not_count_as_successful_game_validation():
    d=records()
    assert sum(r['captured_commands'] for r in d['gpas'])==32
    assert sum(r['paired'] for r in d['gpas'])==31
    assert all(r['paired']>=r['terminal'] for r in d['gpas'])
    by={r['code']:r for r in d['gpas']}
    assert by['gpas_pigeonfs_pop']['captured_auto_continuations']==6
    assert by['gpas_pigeonfs_pop']['captured_bonus']=='FreeGame'
    assert by['gpas_diamdhrbf_pop']['captured_bonus']=='Respin'
    assert by['gpas_ghgranny_pop']['captured_modes']==['default','extra','ultra']
    assert by['gpas_icave_pop']['captured_modes']==['feature-20']
    assert by['gpas_twolf_pop']['captured_modes']==['20','Classic']


def test_five_fixed_gpas_have_new_demo_proof_and_unknown_variants_stay_partial():
    by={r['code']:r for r in records()['gpas']}
    improved=[r for r in by.values() if r['fresh_before']=='PARCIAL'
              and r['fresh_after']=='OK']
    assert len(improved)==5
    assert set(r['code'] for r in improved)=={
        'gpas_ghgranny_pop','gpas_icave_pop','gpas_pigeonfs_pop',
        'gpas_twolf_pop','gpas_diamdhrbf_pop'}
    assert by['gpas_krfforest_pop']['fresh_after']=='PARCIAL'
    assert by['gpas_krsqueen_pop']['fresh_after']=='PARCIAL'
    assert sum(r['fresh_after']=='OK' for r in by.values())==6


def test_ngm_jmm_does_not_certify_missing_client_code_or_feature_inventory():
    ngm=records()['ngm']
    assert len(ngm)==7
    assert all(g['manifest_jmm'] and not g['client_cache_js'] for g in ngm)
    assert all(g['fresh_state']=='PARCIAL' for g in ngm)


def test_allowlisted_fixture_has_no_raw_credential_or_session_fields():
    d=records()
    forbidden={'token','cookie','authorization','password','session_id',
        'request_headers','response_headers','payloadData','raw_url',
        'websocket_frames','username','bearer','secret'}
    def walk(value):
        if isinstance(value,dict):
            for k,v in value.items():
                assert k not in forbidden
                walk(v)
        elif isinstance(value,list):
            for item in value:walk(item)
    walk(d)
