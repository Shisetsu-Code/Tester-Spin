import json
import threading

from tester_spin.models import Game
from tester_spin.independent.worker import _worker, result_from_payload


class BlockedProvider:
    display_name = "Blocked fixture"

    def effective_test_concurrency(self, requested):
        return 1

    def test_start_block_reason(self, *, timeout_s):
        return "SERVER_RETRY_AFTER: KA HTTP 404; retry_at=2000000000"

    def test_start_block_metadata(self):
        return {"server_retry_after": {"retry_at": 2000000000, "http_status": 404}}

    def prepare_test_artifacts(self, *args, **kwargs):
        raise AssertionError("blocked provider must not prepare HTTP artifacts")

    def test_game(self, *args, **kwargs):
        raise AssertionError("blocked provider must not execute")


def run_worker(game, tmp_path, stop, monkeypatch):
    import tester_spin.providers.registry as registry
    monkeypatch.setattr(registry, "create_provider", lambda *args: BlockedProvider())
    gate = threading.Event(); gate.set()
    path = tmp_path / (game.slug + ".result.json")
    _worker(game, tmp_path, 2, 1, stop, path, tmp_path / (game.slug + ".log"), False, gate)
    assert path.is_file(), "blocked worker must produce an explicit result"
    return result_from_payload(json.loads(path.read_text(encoding="utf-8")))


def test_real_worker_entry_saves_blocked_result_without_cancelling_shared_run(tmp_path, monkeypatch):
    game = Game("ka_gaming", "blocked", "Blocked", "https://gamesdemo.kaga88.com/")
    stop = threading.Event()
    result = run_worker(game, tmp_path, stop, monkeypatch)
    assert result.status == "ERROR"
    assert "SERVER_RETRY_AFTER" in result.error
    assert result.structural_map["server_retry_after"]["http_status"] == 404
    assert not stop.is_set()


def test_real_worker_blocked_result_stops_batch_after_first_record(tmp_path, monkeypatch):
    from tester_spin.independent.batches import run_batches
    games = [Game("ka_gaming", slug, slug, "https://gamesdemo.kaga88.com/") for slug in ("first", "second")]
    stop = threading.Event()
    recorded = []
    report = run_batches(games, execute=lambda game: run_worker(game, tmp_path, stop, monkeypatch),
        record=recorded.append, profiles=[], games_per_ip=None, stop_event=stop)
    assert report["reason"] == "RATE_LIMIT"
    assert report["attempted"] == 1
    assert len(recorded) == 1
    assert recorded[0].status == "ERROR"
    assert "SERVER_RETRY_AFTER" in recorded[0].error



def test_user_cancellation_prevents_provider_preflight(tmp_path, monkeypatch):
    import tester_spin.providers.registry as registry
    def forbidden(*args):
        raise AssertionError("cancelled worker must not create a provider")
    monkeypatch.setattr(registry, "create_provider", forbidden)
    game = Game("ka_gaming", "cancelled", "Cancelled", "https://gamesdemo.kaga88.com/")
    gate = threading.Event(); gate.set()
    stop = threading.Event(); stop.set()
    _worker(game, tmp_path, 2, 1, stop, tmp_path / "unused.json", tmp_path / "unused.log", False, gate)
    assert stop.is_set()
