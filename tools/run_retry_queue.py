"""Run a provider recovery queue with a hard per-game wall-clock limit.

The GUI scheduler is intentionally used inside an isolated child process so its
normal artifact/finalization pipeline is preserved.  The parent process keeps
the queue moving when a provider browser or transport stalls indefinitely.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import re
import sys
import threading
import time
from pathlib import Path

# Workers are spawned under Windows with the active console code page.  Provider
# diagnostics deliberately contain protocol symbols, so force UTF-8 before a
# child inherits the environment and turns a successful run into a logging error.
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def provider_for(key: str, data_root: Path):
    from tester_spin.providers.registry import create_provider
    return create_provider(key,data_root)


def _run_one(project_root: str, provider_key: str, game, timeout_s: float, spins: int = 1, shared_stop=None, gate=None) -> None:
    # The parent must own this process before provider/browser code can run.
    if gate is not None:gate.wait()
    if shared_stop is not None and shared_stop.is_set():return
    os.chdir(project_root)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from tester_spin.scheduler import run_game_tests
    from tester_spin.storage import Storage

    data_root = Path(project_root) / "data"
    storage = Storage(data_root / "tester-spin.sqlite3")
    provider = provider_for(provider_key, data_root)
    stop=shared_stop if shared_stop is not None else threading.Event()
    def record(result):
        storage.record_result(result)
        if re.search(r"HTTP(?: Error)?\s+429\b",result.error or "",re.I):stop.set()
    run_game_tests(
        provider,
        [game],
        concurrency=1,
        spins_per_game=max(1, int(spins)),
        delay_between_starts_s=0,
        timeout_s=timeout_s,
        stop_event=stop,
        progress=lambda message: print(f"[{game.name}] {message}", flush=True),
        on_result=record,
    )


def _run_isolated(context, root, provider_key, game, timeout, spins, wall_timeout, shared_stop):
    """Return only after every owned process exits; unsafe cleanup is fatal."""
    from tester_spin.independent.processes import ProcessTree, UnsafeProcessTree

    gate=context.Event();tree=ProcessTree();process=None;started=False
    try:
        process=context.Process(target=_run_one,args=(str(root),provider_key,game,timeout,spins,shared_stop,gate))
        process.start();started=True
        tree.bind(process.pid)
        gate.set()
        deadline=time.monotonic()+max(1.0,wall_timeout);reason=None
        while process.is_alive():
            if shared_stop.is_set():reason='STOPPED';break
            remaining=deadline-time.monotonic()
            if remaining<=0:reason='TIMEOUT';break
            process.join(min(.2,remaining))
        tree.stop_and_wait() # Also closes detached browser/driver descendants.
        process.join(5)
        if process.is_alive():raise UnsafeProcessTree('El árbol del juego no cerró; no se inicia otro juego')
        return reason,process.exitcode
    finally:
        if started and not tree.bound:
            # The gate is still closed, so no provider descendants can exist.
            if process.is_alive():process.terminate();process.join(5)
            if process.is_alive():process.kill();process.join(5)
            if process.is_alive():raise UnsafeProcessTree('El proceso bloqueado no cerró; no se inicia otro juego')
        tree.close() # Raises rather than advancing when ownership cannot be released safely.
        if started and not process.is_alive():process.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--spins", type=int, default=1, help="muestras por modo y rama conocida")
    parser.add_argument("--timeout", type=float, default=35.0, help="provider request timeout")
    parser.add_argument("--wall-timeout", type=float, default=60.0, help="hard timeout for an entire game")
    parser.add_argument("--statuses", nargs="+", default=["ERROR", "PARCIAL", "SIN_DEMO"])
    parser.add_argument("--game", help="slug exacto para reintentar un ÃƒÂºnico juego ya almacenado")
    args = parser.parse_args()

    # Provider discovery launches Python helpers.  On Windows the inherited
    # console can otherwise be cp1252, which turns harmless protocol arrows
    # in diagnostics into a bootstrap failure before the game is contacted.
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    root = Path.cwd().resolve()
    if not (root / "tester_spin").is_dir():
        raise SystemExit("Ejecutar desde la raÃƒÂ­z de Tester-Spin.")
    sys.path.insert(0, str(root))
    from tester_spin.models import GameTestResult
    from tester_spin.storage import Storage

    data_root = root / "data"
    storage = Storage(data_root / "tester-spin.sqlite3")
    provider = provider_for(args.provider, data_root)
    allowed = {status.upper() for status in args.statuses}
    games = [game for game in storage.list_games(provider.key) if game.last_status.upper() in allowed]
    if args.game:
        games = [game for game in games if game.slug == args.game]
        if not games:
            raise SystemExit(f"No hay un juego pendiente con slug={args.game!r} para {provider.key}.")
    if args.limit:
        games = games[: args.limit]
    print(f"QUEUE provider={provider.key} games={len(games)} statuses={sorted(allowed)}", flush=True)

    context = mp.get_context("spawn")
    shared_stop=context.Event()
    for index, game in enumerate(games, start=1):
        if shared_stop.is_set():
            print("STOP proveedor: seÃ±al compartida de detenciÃ³n; no se abre otra sesiÃ³n",flush=True)
            break
        print(f"START {index}/{len(games)} {game.name}", flush=True)
        reason,exitcode=_run_isolated(context,root,provider.key,game,args.timeout,args.spins,args.wall_timeout,shared_stop)
        if reason=='TIMEOUT':
            storage.record_result(
                GameTestResult(
                    provider=game.provider,
                    slug=game.slug,
                    game_name=game.name,
                    game_url=game.url,
                    symbol=game.symbol,
                    requested_spins=max(1,args.spins),
                    successful_spins=0,
                    failed_spins=max(1,args.spins),
                    status="ERROR",
                    error=f"RUNNER_WALL_TIMEOUT: excediÃƒÂ³ {args.wall_timeout:.0f}s; pendiente para revisiÃƒÂ³n puntual.",
                )
            )
            print(f"TIMEOUT {game.name}", flush=True)
        else:
            print(f"END {game.name} exit={exitcode}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
