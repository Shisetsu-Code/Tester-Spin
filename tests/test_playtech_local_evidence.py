"""Exercise genuine runtime observation callbacks without a browser or wagers."""
import hashlib
import json
import threading
from pathlib import Path
from types import SimpleNamespace
import pytest
from tester_spin.models import Game
from tester_spin.providers.playtech.adapter import PlaytechProvider
from tester_spin.providers.playtech.ngm_contracts import analyze_har
from tester_spin.providers.playtech.ngm_runtime import NGMDemoSession
from tester_spin.run_diagnostics import write_run_diagnostics
from test_playtech_ngm_inventory import complete_har


class ObservedSession(NGMDemoSession):
    def __enter__(self):
        self.document=complete_har()
        report=analyze_har(self.document,'example')
        self.demo_verified=True
        self.source_hashes=[report['source_sha256']]
        self.manifest=report['manifest']
        self.contract={'fields':{'bet':'cost'}}
        self.balance=1000
        self.passive_roles={'LogUserPreferencesRequest':'aux'}
        return self

    def __exit__(self,*args):
        (self.directory/'session.har').write_text(json.dumps(self.document),encoding='utf-8')

    def wait(self,predicate,reason):
        assert not self.errors
        assert self.ledger.verified

    def emit(self,kind,value):
        row={'type':kind,'frame':'https://cachedownload.playtechone.com/ngmdistributed/example/1/index.html','data':value}
        self._console(SimpleNamespace(text='__TESTER_NGM__'+json.dumps(row)))

    def play(self,*args):
        self.emit('message',{'classifier':'GameRoundStartNotification'})
        self.emit('message',{'classifier':'ISetGameBalanceRequest','amount':self.balance-20})
        for index,spin_type in enumerate(('regular','free')):
            self.emit('offline.request',{'value':{'spin':{'bet':20,'numCoins':1,'spinType':spin_type},'requestClass':'SpinRequest','raw':{'phase':spin_type}}})
            # A nested auxiliary response must not become the spin response.
            self.emit('offline.request',{'value':{'spin':None,'requestClass':'LogUserPreferencesRequest','raw':{'setting':True}}})
            self.emit('offline.response',{'value':{'auxiliary':True}})
            self.emit('offline.response',{'value':{'result':index}})
            self.emit('offline.payout',{'value':{'calculatedWin':0}})
        self.emit('message',{'classifier':'GameRoundEndNotification'})
        self.emit('message',{'classifier':'NextGameRoundAllowed'})

    def _action_frame(self):return SimpleNamespace(evaluate=self.play)


def observed_result(tmp_path):
    provider=PlaytechProvider(tmp_path);provider.ngm_session_factory=ObservedSession
    game=Game('playtech','game-example','Example','https://www.playtechone.com/games/example',symbol='example')
    result=provider.test_game(game,spins=1,timeout_s=10,stop_event=threading.Event(),progress=lambda _:None)
    assert result.status=='OK'
    return provider,result


def test_actual_local_pairs_survive_finalizer_catalog_tree_and_diagnostics(tmp_path):
    provider,result=observed_result(tmp_path)
    result=provider.finalize_test_result(result,progress=lambda _:None)
    assert result.status=='OK'
    report=write_run_diagnostics(result)
    assert report['modes'][0]['status']=='VALIDATED'
    attempt=Path(result.attempts[0].artifact_dir)
    response=json.loads((attempt/'step-0-response.json').read_text())
    assert response['observation']['data']['value']=={'result':0}
    assert response['execution_scope']=='official-local-demo'
    assert response['server_execution'] is False
    assert len(list(attempt.glob('step-*-request.json')))==2
    assert (attempt/'summary.json').exists()


@pytest.mark.parametrize('damage',['pair','start','end','trace'])
def test_missing_local_pair_or_lifecycle_never_validates(tmp_path,damage):
    provider,result=observed_result(tmp_path)
    attempt=Path(result.attempts[0].artifact_dir)
    if damage=='pair':
        (attempt/'step-1-response.json').unlink()
    elif damage=='trace':
        (attempt/'wire-events.json').unlink()
    else:
        path=attempt/'wire-events.json'
        value=json.loads(path.read_text())
        classifier='GameRoundStartNotification' if damage=='start' else 'GameRoundEndNotification'
        value['events']=[event for event in value['events'] if event['value'].get('classifier')!=classifier]
        path.write_text(json.dumps(value))
    result=provider.finalize_test_result(result,progress=lambda _:None)
    report=write_run_diagnostics(result)
    assert report['modes'][0]['status']=='INCOMPLETE'
    assert any(gap['code']=='TRAJECTORY_SEQUENCE_GAP' for gap in report['evidence_gaps'])
