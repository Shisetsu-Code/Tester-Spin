import threading
import pytest
from tester_spin.independent.batches import run_batches
from tester_spin.models import Game, GameTestResult


def games():
    return [Game("ka_gaming", slug, slug, "https://gamesdemo.kaga88.com/") for slug in ("first", "second")]


def blocked(game):
    return GameTestResult(game.provider, game.slug, game.name, game.url, 1, 0, 1, "ERROR",
        error="SERVER_RETRY_AFTER: HTTP 404", structural_map={"server_retry_after": {"retry_at": 2000000000, "http_status": 404}})


def test_known_pause_is_recorded_before_tunnel_worker_or_quota():
    calls = []; recorded = []
    def forbidden(*args):
        calls.append(args)
        raise AssertionError("must not activate network or execute")
    report = run_batches(games(), execute=forbidden, record=recorded.append, profiles=["first", "second"],
        games_per_ip=1, stop_event=threading.Event(), tunnel_factory=forbidden, block_check=blocked)
    assert calls == []
    assert report["reason"] == "RATE_LIMIT"
    assert report["attempted"] == 1 and report["pending"] == 1
    assert report["ip_counts"] == {}
    assert len(recorded) == 1 and recorded[0].status == "ERROR"
    assert "SERVER_RETRY_AFTER" in recorded[0].error
    assert recorded[0].structural_map["server_retry_after"]["http_status"] == 404


def test_pause_appearing_between_games_is_checked_before_next_worker():
    started = []; recorded = []
    def execute(game):
        started.append(game.slug)
        return GameTestResult(game.provider, game.slug, game.name, game.url, 1, 1, 0, "OK")
    report = run_batches(games(), execute=execute, record=recorded.append, profiles=[], games_per_ip=None,
        stop_event=threading.Event(), block_check=lambda game: blocked(game) if started else None)
    assert started == ["first"]
    assert report["reason"] == "RATE_LIMIT"
    assert [r.status for r in recorded] == ["OK", "ERROR"]


def test_user_cancel_has_priority_over_parent_preflight():
    stop = threading.Event(); stop.set()
    calls = []
    report = run_batches(games(), execute=lambda _: calls.append("execute"), record=lambda _: calls.append("record"),
        profiles=["first"], games_per_ip=1, stop_event=stop,
        tunnel_factory=lambda _: calls.append("tunnel"), block_check=lambda _: calls.append("block"))
    assert calls == []
    assert report["reason"] == "CANCELLED" and report["attempted"] == 0



@pytest.mark.parametrize("refresh", [False, True])
def test_cli_wires_parent_pause_before_network_without_database(tmp_path, monkeypatch, refresh):
    import tester_spin.cli as cli
    import tester_spin.storage as storage
    import tester_spin.vpn.wireguard as wireguard
    import tester_spin.independent.worker as worker
    import tester_spin.independent.batches as batches
    recorded = []; calls = []
    class MemoryStorage:
        def __init__(self, path): pass
        def list_games(self, provider): return games()
        def latest_results(self, provider=None): return []
        def record_result(self, result): recorded.append(result)
    class PausedProvider:
        execution_supported = True
        def test_start_block_reason(self, *, timeout_s): return "SERVER_RETRY_AFTER: HTTP 404"
        def test_start_block_metadata(self): return {"server_retry_after": {"retry_at": 2000000000, "http_status": 404}}
    def forbidden(*args, **kwargs):
        calls.append("network_or_worker")
        raise AssertionError("known cooldown precedes network")
    monkeypatch.setattr(storage, "Storage", MemoryStorage)
    monkeypatch.setattr(cli, "create_provider", lambda *args: PausedProvider())
    monkeypatch.setattr(cli, "profiles_for", lambda args: ["fixture"])
    monkeypatch.setattr(wireguard, "WireGuardTunnel", forbidden)
    monkeypatch.setattr(batches, "WireGuardTunnel", forbidden)
    monkeypatch.setattr(worker, "execute_game", forbidden)
    status = cli.main(["run", "ka_gaming", "--data-root", str(tmp_path), "--games-per-ip", "1"] + (["--refresh-catalog"] if refresh else []))
    assert status == 3
    assert calls == []
    assert len(recorded) == 1 and "SERVER_RETRY_AFTER" in recorded[0].error
    assert recorded[0].structural_map["server_retry_after"]["http_status"] == 404
