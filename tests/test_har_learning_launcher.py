import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from tester_spin.har_learning import kick_worker,isolate_capture


class LearningLauncherTests(unittest.TestCase):
    def test_disabled_or_missing_configuration_never_starts_process(self):
        with tempfile.TemporaryDirectory() as td, patch("tester_spin.har_learning.subprocess.Popen") as launch:
            self.assertFalse(kick_worker(Path(td)/"tester-spin.sqlite3"))
            launch.assert_not_called()

    def test_configured_worker_is_nonblocking_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/"Aislador";(source/"aislador").mkdir(parents=True);(source/"aislador/__main__.py").write_text("")
            (root/"har-learning.json").write_text(json.dumps({"enabled":True,"aislador_root":str(source),"python":"python.exe","after_id":50}))
            process=Mock();process.poll.return_value=None
            with patch("tester_spin.har_learning.subprocess.Popen",return_value=process) as launch:
                self.assertTrue(kick_worker(root/"tester-spin.sqlite3"))
                self.assertTrue(kick_worker(root/"tester-spin.sqlite3"))
                self.assertEqual(launch.call_count,1)
                command=launch.call_args.args[0]
                self.assertIn("follow-failures",command)
                self.assertIn("50",command)
                self.assertFalse(launch.call_args.kwargs.get("shell",False))

    def test_manual_har_is_filtered_without_browser_or_fuzzer(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/"Aislador";(source/"aislador").mkdir(parents=True);(source/"aislador/__main__.py").write_text("")
            (root/"har-learning.json").write_text(json.dumps({"enabled":True,"aislador_root":str(source),"python":"python.exe"}))
            har=root/"capture.har";har.write_text('{"log":{"entries":[{"request":{"url":"https://example.invalid/"}}]}}')
            completed=Mock(returncode=0,stdout='[{"output":"result"}]',stderr='')
            with patch("tester_spin.har_learning.subprocess.run",return_value=completed) as run:
                r=isolate_capture(har,root)
                self.assertEqual(r[0]["output"],"result")
                self.assertIn("extract",run.call_args.args[0])
                self.assertNotIn("capture",run.call_args.args[0])


def test_storage_only_requests_capture_for_error_or_partial(tmp_path):
    from tester_spin.storage import Storage
    from tester_spin.models import Game,GameTestResult
    storage=Storage(tmp_path/"tester-spin.sqlite3")
    game=Game("playtech","fixture","Fixture","https://www.playtechone.com/fixture",symbol="gpas_fixture")
    storage.upsert_games([game])
    with patch("tester_spin.har_learning.kick_worker") as kick:
        for status in ("OK","ERROR","PARCIAL","CANCELADO"):
            storage.record_result(GameTestResult("playtech","fixture","Fixture",game.url,1,0,0,status,symbol=game.symbol))
    assert kick.call_count==2
    assert storage.get_game("playtech","fixture").last_status=="CANCELADO"


def test_last_failure_during_worker_shutdown_is_not_lost(tmp_path):
    import sqlite3
    from contextlib import closing
    from tester_spin.har_learning import _reap
    db=tmp_path/"tester-spin.sqlite3"
    with closing(sqlite3.connect(db)) as con:
        con.execute("CREATE TABLE test_results(id,status)");con.execute("INSERT INTO test_results VALUES(11,'PARCIAL')");con.commit()
    out=tmp_path/"har-learning";out.mkdir();(out/"failures.private.json").write_text('{"cursor":10}')
    process=Mock();process.wait.return_value=0
    with patch("tester_spin.har_learning.kick_worker") as kick:_reap(process,db,tmp_path)
    kick.assert_called_once_with(db)


def test_manual_empty_har_is_rejected_before_optional_learner(tmp_path):
    har=tmp_path/'capture.har';har.write_text('{"log":{"entries":[]}}')
    with patch('tester_spin.har_learning.subprocess.run') as run:
        import pytest
        with pytest.raises(ValueError,match='HAR_EMPTY_CAPTURE.*recarg'):
            isolate_capture(har,tmp_path)
        run.assert_not_called()


def test_ngm_manual_capture_shows_diagnosis_even_without_aislador(tmp_path):
    import pytest
    har=tmp_path/'capture.har'
    har.write_text(json.dumps({'log':{'entries':[{'request':{'url':'https://cachedownload.playtechone.com/ngmdistributed/ngm-desktop/igv/example/1/resources/config.json'},'response':{'status':200,'content':{'text':'{}'}}}]}}))
    with pytest.raises(ValueError,match='NGM_CLIENT_SOURCE_MISSING') as error:
        isolate_capture(har,tmp_path)
    assert 'ngm-events.jsonl' in str(error.value)


def test_manual_ngm_import_attaches_diagnostics_without_mutating_capture(tmp_path):
    from test_playtech_ngm_contracts import har as fixture
    source=tmp_path/'Aislador';(source/'aislador').mkdir(parents=True);(source/'aislador/__main__.py').write_text('')
    (tmp_path/'har-learning.json').write_text(json.dumps({'enabled':True,'aislador_root':str(source)}))
    capture=tmp_path/'capture.har';original=json.dumps(fixture());capture.write_text(original)
    completed=Mock(returncode=0,stdout='[{"output":"result"}]',stderr='')
    with patch('tester_spin.har_learning.subprocess.run',return_value=completed):
        report=isolate_capture(capture,tmp_path)
    assert report[0]['capture_diagnostics']['round_evidence']=='REQUIRES_RUNTIME_TRACE'
    assert report[0]['capture_diagnostics']['entry_count']==2
    assert capture.read_text()==original
