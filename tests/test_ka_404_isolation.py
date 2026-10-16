import json
import threading

import pytest

from tester_spin.models import Game
from tester_spin.providers.ka_gaming.runtime import refresh_signing_profile, run_rmp_game


class Response:
    def __init__(self, status, payload):
        self.status_code = status
        self.payload = payload
        self.text = json.dumps(payload)
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class DemoHTTP:
    headers = {}

    def __init__(self):
        self.started = []

    def post(self, url, **kwargs):
        payload = json.loads(kwargs["data"])
        if url.endswith("/startGame"):
            self.started.append(payload["gn"])
            if len(self.started) == 1:
                return Response(404, {"message": "Not found"})
            return Response(200, {"e": False, "ec": 0, "un": "fixture-user", "si": "fixture-session",
                "sgr": {"lsd": STATE}})
        return Response(200, {"e": False, "ec": 0, "md": STATE})


STATE = {"sel": 5, "cps": 1, "atb": 0, "dn": .01, "fs": False, "rf": 0, "acb": 0}


def game(symbol):
    return Game("ka_gaming", symbol.lower(), symbol,
        "https://gamesdemo.kaga88.com/?g=" + symbol + "&p=demo", symbol=symbol)


def execute(symbol, http, tmp_path, stop):
    return run_rmp_game(game(symbol), http=http, root=tmp_path,
        profile=("2080", "test-version", "test-literal"), modes=[{"id": "SPIN", "kind": "SPIN"}],
        spins=1, timeout_s=1, stop_event=stop, progress=lambda _: None)


def test_session_404_preserves_game_error_and_attempts_next_game(tmp_path):
    stop = threading.Event()
    http = DemoHTTP()
    failed = execute("First", http, tmp_path, stop)
    assert failed.status == "ERROR"
    assert "HTTP 404" in failed.error
    assert failed.successful_spins == 0
    assert not stop.is_set()
    following = execute("Second", http, tmp_path, stop)
    assert http.started == ["First", "Second"]
    assert following.status == "OK"


def test_user_cancellation_still_prevents_next_session(tmp_path):
    stop = threading.Event()
    stop.set()
    http = DemoHTTP()
    result = execute("Cancelled", http, tmp_path, stop)
    assert http.started == []
    assert result.successful_spins == 0
    assert result.status != "OK"
    assert stop.is_set()


def test_game_launcher_404_does_not_cancel_shared_batch(tmp_path):
    class MissingLauncher:
        def get(self, url, **kwargs):
            return Response(404, {})

    stop = threading.Event()
    with pytest.raises(RuntimeError, match="HTTP 404"):
        refresh_signing_profile(game("Missing"), http=MissingLauncher(), root=tmp_path,
            timeout_s=1, stop_event=stop, progress=lambda _: None)
    assert not stop.is_set()
