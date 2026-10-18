"""Reduced synthetic captures: no downloaded client code or session credentials."""
import json
import pytest
from tester_spin.providers.playtech.ngm_contracts import analyze_har


def lobby_capture(format='_webSocketFrames'):
    payloads = [('received', '1::'), ('sent', '3:::'+json.dumps({'ID':35844,'urlTypeList':['mobile_support']})),
                ('received', '3:::'+json.dumps({'ID':35845,'data':{'urlList':[]}})), ('sent', '0::')]
    frames = [dict(direction=direction, opcode=1, payloadData=payload) for direction,payload in payloads]
    if format == '_webSocketMessages':
        frames = [dict(type='send' if f['direction']=='sent' else 'receive', opcode=1, data=f['payloadData']) for f in frames]
    return {'log':{'entries':[{'request':{'url':'wss://oapi.playtechhorizon.com/socket.io/1/websocket/fixture'},
                              'response':{'status':101}, format:frames}]}}


def test_empty_capture_has_specific_recapture_diagnostic():
    report=analyze_har({'log':{'entries':[]}},'example')
    assert 'HAR_EMPTY_CAPTURE' in report['capture_diagnostics']['issues']
    assert report['capture_diagnostics']['entry_count']==0
    assert any('recarg' in text.lower() for text in report['capture_diagnostics']['next_steps'])
    assert report['certifies_game_ok'] is False
    assert not report['execution_plan']['complete']


@pytest.mark.parametrize('format',['_webSocketFrames','_webSocketMessages'])
def test_socket_lobby_frames_do_not_become_spin_evidence(format):
    report=analyze_har(lobby_capture(format),'example')
    capture=report['capture_diagnostics']
    assert capture['websocket_frame_count']==4
    assert capture['websocket_control_count']==2
    assert capture['websocket_navigation_count']==2
    assert capture['websocket_unclassified_count']==0
    assert 'HAR_ONLY_LOBBY_WEBSOCKET_TRAFFIC' in capture['issues']
    assert capture['round_evidence']=='REQUIRES_RUNTIME_TRACE'
    assert report['request_count']==0
    assert report['certifies_game_ok'] is False
    assert 'fixture' not in json.dumps(capture)


def test_unknown_frame_is_retained_as_unknown_and_never_certifies_round():
    document=lobby_capture()
    document['log']['entries'][0]['_webSocketFrames'].append({'direction':'sent','opcode':1,'payloadData':'3:::{"ID":999,"token":"private-value","spin":true}'})
    capture=analyze_har(document,'example')['capture_diagnostics']
    assert capture['websocket_unclassified_count']==1
    assert 'HAR_ONLY_LOBBY_WEBSOCKET_TRAFFIC' not in capture['issues']
    assert 'private-value' not in json.dumps(capture)


@pytest.mark.parametrize('document',[{},[],{'log':None},{'log':{'entries':None}},{'log':{'entries':[None]}}])
def test_malformed_capture_has_stable_error_not_an_attribute_traceback(document):
    with pytest.raises(ValueError,match='HAR_INVALID_STRUCTURE'):
        analyze_har(document,'example')


def test_static_contract_and_observed_rounds_remain_separate():
    from test_playtech_ngm_contracts import har
    report=analyze_har(har(),'example')
    assert report['request_count']==3
    assert report['capture_diagnostics']['round_evidence']=='REQUIRES_RUNTIME_TRACE'
    assert not report['certifies_game_ok']
    assert report['capture_diagnostics']['websocket_frame_count']==0
    assert 'NGM_CLIENT_SOURCE_MISSING' not in report['unresolved']


def test_cli_prints_actionable_capture_summary(tmp_path,monkeypatch,capsys):
    from tester_spin.providers.playtech.ngm_contracts import main
    source=tmp_path/'empty.har';source.write_text('{"log":{"entries":[]}}')
    monkeypatch.setattr('sys.argv',['ngm_contracts',str(source),'--code','example','--out',str(tmp_path/'report.json')])
    main()
    output=json.loads(capsys.readouterr().out)
    assert output['capture_diagnostics']['issues']==['HAR_EMPTY_CAPTURE']
    assert output['capture_diagnostics']['next_steps']
