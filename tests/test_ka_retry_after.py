import threading

from test_ka_404_isolation import DemoHTTP, execute


def test_explicit_retry_after_stops_new_sessions_without_cancelling_result(tmp_path):
    class PausedDemo(DemoHTTP):
        def post(self, url, **kwargs):
            response = super().post(url, **kwargs)
            if response.status_code == 404:
                response.headers = {"Retry-After": "600"}
            return response

    stop = threading.Event()
    http = PausedDemo()
    result = execute("First", http, tmp_path, stop)
    assert result.status == "ERROR"
    assert "SERVER_RETRY_AFTER" in result.error
    assert result.structural_map["server_retry_after"]["http_status"] == 404
    assert not stop.is_set()
    following = execute("Second", http, tmp_path, stop)
    assert following.status == "ERROR"
    assert "SERVER_RETRY_AFTER" in following.error
    assert http.started == ["First"]


def test_independent_batch_records_retry_after_error_before_stopping():
    from tester_spin.independent.batches import run_batches
    from tester_spin.models import Game, GameTestResult
    games = [Game("ka_gaming", name, name, "https://gamesdemo.kaga88.com/") for name in ("first", "second")]
    recorded = []
    def execute(game):
        return GameTestResult(game.provider, game.slug, game.name, game.url, 1, 0, 1, "ERROR",
            error="SERVER_RETRY_AFTER: HTTP 404")
    stop = threading.Event()
    report = run_batches(games, execute=execute, record=recorded.append, profiles=[],
        games_per_ip=None, stop_event=stop)
    assert report["attempted"] == 1
    assert report["reason"] == "RATE_LIMIT"
    assert len(recorded) == 1 and recorded[0].status == "ERROR"
    assert "SERVER_RETRY_AFTER" in recorded[0].error



def test_cooldown_persists_for_new_guard_and_expires(tmp_path):
    from tester_spin.providers.ka_gaming.cooldown import ServerCooldown, ServerRetryAfter
    import pytest
    now = [1000.0]
    guard = ServerCooldown(tmp_path, clock=lambda: now[0])
    guard.observe(404, {"retry-after": "20"}, "https://rmpdemo.kaga88.com/kaga/rmp/startGame")
    fresh = ServerCooldown(tmp_path, clock=lambda: now[0])
    with pytest.raises(ServerRetryAfter): fresh.check(threading.Event())
    assert fresh.remaining_s() == 20
    now[0] = 1020
    fresh.check(threading.Event())
    assert fresh.remaining_s() == 0


def test_retry_after_http_date_and_longer_persisted_deadline(tmp_path):
    from tester_spin.providers.ka_gaming.cooldown import ServerCooldown
    guard = ServerCooldown(tmp_path, clock=lambda: 1445412400.0)
    guard.observe(503, {"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}, "https://example.invalid/path?token=secret")
    assert guard.remaining_s() == 80
    guard.observe(404, {"Retry-After": "20"}, "https://example.invalid/path")
    assert guard.remaining_s() == 80
    assert "secret" not in (tmp_path / "server-cooldown.json").read_text(encoding="utf-8")


def test_invalid_or_absent_retry_after_does_not_invent_a_pause(tmp_path):
    from tester_spin.providers.ka_gaming.cooldown import ServerCooldown
    guard = ServerCooldown(tmp_path, clock=lambda: 1000.0)
    for value in (None, "", "garbage", "nan", "inf", "-1", "1e999", "Wed, 21 Oct 2015 07:28:00"):
        guard.observe(404, {"Retry-After": value}, "https://example.invalid/")
        assert guard.remaining_s() == 0
    assert not (tmp_path / "server-cooldown.json").exists()


def test_cancellation_has_priority_over_persisted_pause(tmp_path):
    from tester_spin.providers.ka_gaming.cooldown import ServerCooldown
    import pytest
    guard = ServerCooldown(tmp_path, clock=lambda: 1000.0)
    guard.observe(404, {"Retry-After": "20"}, "https://example.invalid/")
    stop = threading.Event(); stop.set()
    with pytest.raises(InterruptedError): guard.check(stop)


def test_provider_hook_and_refresh_prevent_any_http_during_pause(tmp_path):
    from tester_spin.providers.ka_gaming.adapter import KAGamingProvider
    from tester_spin.providers.ka_gaming.cooldown import ServerCooldown
    from test_ka_404_isolation import game
    from unittest.mock import MagicMock
    provider = KAGamingProvider(tmp_path)
    ServerCooldown(provider.provider_root).observe(404, {"Retry-After": "600"}, "https://rmpdemo.kaga88.com/")
    assert "SERVER_RETRY_AFTER" in provider.test_start_block_reason(timeout_s=1)
    provider.http = MagicMock()
    result = provider.test_game(game("Paused"), spins=1, timeout_s=1, stop_event=threading.Event(), progress=lambda _: None)
    assert result.status == "ERROR" and "SERVER_RETRY_AFTER" in result.error
    assert result.structural_map["server_retry_after"]["http_status"] == 404
    assert not provider.http.get.called and not provider.http.post.called



def test_retry_after_on_session_close_is_preserved_in_final_result(tmp_path):
    class ClosingPause(DemoHTTP):
        def __init__(self):
            super().__init__()
            self.started = ["previous"]
        def post(self, url, **kwargs):
            response = super().post(url, **kwargs)
            if url.endswith("/endSession"):
                response.status_code = 503
                response.headers = {"Retry-After": "600"}
            return response
    result = execute("Closing", ClosingPause(), tmp_path, threading.Event())
    assert "SERVER_RETRY_AFTER" in result.error
    assert result.status != "OK"
    assert result.structural_map["server_retry_after"]["http_status"] == 503
