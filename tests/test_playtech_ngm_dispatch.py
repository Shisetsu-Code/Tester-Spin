
"""Independent receipt-level guarantees for Playtech NGM local demo runtime."""
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from tester_spin.providers.playtech.ngm_dispatch import DispatchJournal
from tester_spin.providers.playtech.ngm_runtime import NGMDemoSession
from tester_spin.providers.playtech.ngm_execution import NGMRoundLedger
from tester_spin.providers.playtech.ngm_capture import local_capture_gaps

GAME_FRAME = 'https://cachedownload.playtechone.com/ngmdistributed/fixture/1/index.html'


def emit(runtime, kind, value, *, frame_instance='frame-A'):
    row={'type':kind,'frame':GAME_FRAME,'frame_instance':frame_instance,'data':{'value':value}}
    runtime._console(SimpleNamespace(text='__TESTER_NGM__'+json.dumps(row)))


def test_nested_auxiliary_dispatch_cannot_steal_a_spin_receipt():
    journal=DispatchJournal()
    spin=journal.request(kind='spin',frame='frame-A',event_index=1,step=0,request_class='SpinRequest')
    aux=journal.request(kind='aux',frame='frame-A',event_index=2,request_class='LogUserPreferencesRequest')
    assert journal.response(frame='frame-A',event_index=3)['dispatch_id']==aux['dispatch_id']
    assert journal.response(frame='frame-A',event_index=4)['dispatch_id']==spin['dispatch_id']
    assert journal.verify_round(from_pair=0,expected_spins=1)[0]['step']==0


def test_two_same_url_iframes_cannot_cross_correlate():
    journal=DispatchJournal()
    journal.request(kind='spin',frame='frame-A',event_index=1,step=0)
    with pytest.raises(ValueError,match='NGM_RESPONSE_WRONG_FRAME'):
        journal.response(frame='frame-B',event_index=2)
    assert len(journal.stack)==1
    journal.response(frame='frame-A',event_index=3)


def test_missing_response_blocks_completed_round_and_next_wager():
    journal=DispatchJournal()
    journal.request(kind='spin',frame='doc',event_index=1,step=0)
    with pytest.raises(ValueError,match='NGM_DISPATCH_UNCLOSED'):
        journal.verify_round(from_pair=0,expected_spins=1)
    assert journal.result()['open_dispatches']==1


def test_runtime_records_matching_dispatch_ids_in_request_and_response(tmp_path):
    runtime=NGMDemoSession('fixture',tmp_path,10,Event())
    runtime.ledger=NGMRoundLedger(1000)
    runtime.ledger.accept('message',dict(classifier='GameRoundStartNotification'))
    runtime.ledger.accept('message',dict(classifier='ISetGameBalanceRequest',amount=980))
    runtime.source_hashes=['synthetic']
    runtime.capture_directory=tmp_path
    emit(runtime,'offline.request',
         dict(spin=dict(bet=20,numCoins=1,spinType='regular'),requestClass='SpinRequest'))
    emit(runtime,'offline.response',{})
    req=json.loads((tmp_path/'step-0-request.json').read_text())
    rep=json.loads((tmp_path/'step-0-response.json').read_text())
    assert req['dispatch_id']==rep['dispatch_id']
    assert req['event_index']<rep['event_index']
    assert runtime.ledger.spins==runtime.ledger.responses==1
    assert runtime.dispatch_journal.verify_round(from_pair=0,expected_spins=1)


def test_runtime_rejects_response_from_another_live_document(tmp_path):
    runtime=NGMDemoSession('fixture',tmp_path,10,Event())
    runtime.ledger=NGMRoundLedger(1000)
    runtime.ledger.accept('message',dict(classifier='GameRoundStartNotification'))
    runtime.ledger.accept('message',dict(classifier='ISetGameBalanceRequest',amount=980))
    emit(runtime,'offline.request',
         dict(spin=dict(bet=20,numCoins=1,spinType='regular'),requestClass='SpinRequest'))
    emit(runtime,'offline.response',{},frame_instance='frame-B')
    assert 'NGM_RESPONSE_WRONG_FRAME' in runtime.errors
    assert runtime.ledger.responses==0
    assert len(runtime.dispatch_journal.stack)==1


def _round_events():
    return [
       dict(kind='message',value=dict(classifier='GameRoundStartNotification')),
       dict(kind='message',value=dict(classifier='ISetGameBalanceRequest',amount=980)),
       dict(kind='spin',value=dict(bet=20,numCoins=1,spinType='regular')),
       dict(kind='response',value={}),
       dict(kind='payout',value=dict(calculatedWin=40)),
       dict(kind='message',value=dict(classifier='ISetGameBalanceRequest',amount=1020)),
       dict(kind='message',value=dict(classifier='GameRoundEndNotification')),
       dict(kind='message',value=dict(classifier='NextGameRoundAllowed')),
    ]


def test_capture_verifier_requires_new_dispatch_journal_provenance(tmp_path):
    events=_round_events()
    ledger=NGMRoundLedger(1000)
    for e in events:ledger.accept(e['kind'],e['value'])
    assert ledger.verified
    summary=dict(ledger.summary(),source_sha256=['digest'])
    (tmp_path/'wire-events.json').write_text(json.dumps(dict(
        schema='tester-spin/ngm-ledger/v2',execution_scope='official-local-demo',
        server_execution=False,balance_before=1000,events=events)))
    (tmp_path/'summary.json').write_text(json.dumps(summary))
    pair=dict(dispatch_id='dispatch-000001',kind='spin',frame='frame-A',
              request_class='SpinRequest',request_event=10,response_event=12,step=0)
    (tmp_path/'dispatch-journal.json').write_text(json.dumps(dict(
        schema='tester-spin/ngm-dispatch-journal/v1',pairs=[pair],
        open_dispatches=0)))
    for direction,index,event_idx in [('request',2,10),('response',3,12)]:
        row=dict(type='offline.'+direction,
                 data=dict(value=dict(spin=events[index]['value'])
                           if direction=='request' else events[index]['value']))
        (tmp_path/f'step-0-{direction}.json').write_text(json.dumps(dict(
            dispatch_id='dispatch-000001',event_index=event_idx,
            execution_scope='official-local-demo',server_execution=False,
            source_sha256=['digest'],observation=row)))
    read=lambda path:json.loads(Path(path).read_text())
    assert local_capture_gaps(tmp_path,1,read)==[]
    bad=json.loads((tmp_path/'step-0-response.json').read_text())
    bad['dispatch_id']='dispatch-forged'
    (tmp_path/'step-0-response.json').write_text(json.dumps(bad))
    assert local_capture_gaps(tmp_path,1,read)==['NGM_DISPATCH_PAIR_PROVENANCE_MISMATCH']
    (tmp_path/'dispatch-journal.json').unlink()
    assert local_capture_gaps(tmp_path,1,read)==['NGM_LOCAL_EVIDENCE_MISSING_OR_INVALID']


def test_dispatch_journal_has_bounded_memory_and_no_stray_responses():
    journal=DispatchJournal(max_depth=1)
    journal.request(kind='spin',frame='doc',event_index=1,step=0)
    with pytest.raises(ValueError,match='NGM_DISPATCH_LIMIT'):
        journal.request(kind='aux',frame='doc',event_index=2)
    with pytest.raises(ValueError,match='NGM_DISPATCH_RESPONSE_ORDER_INVALID'):
        journal.response(frame='doc',event_index=1)
    journal.response(frame='doc',event_index=3)
    with pytest.raises(ValueError,match='NGM_RESPONSE_WITHOUT_DISPATCH'):
        journal.response(frame='doc',event_index=4)
