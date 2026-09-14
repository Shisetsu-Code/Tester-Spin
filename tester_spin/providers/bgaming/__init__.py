from __future__ import annotations

import threading
from pathlib import Path

from tester_spin.models import Game, GameTestResult
from tester_spin.providers.base import Progress
from tester_spin.providers.bgaming.adapter import BGamingProvider as _BGamingProvider
from tester_spin.providers.bgaming.complexity import persist_result_complexity
from tester_spin.providers.bgaming.har_capture import append_har_debug
from tester_spin.providers.bgaming.har_select import inspect_har, select_best_har
from tester_spin.providers.bgaming.hyperhive_har import (
    clear_thread_har_path,
    set_thread_har_path,
)
from tester_spin.providers.bgaming.hyperhive_har_bridge import install_har_bridge
from tester_spin.providers.bgaming.hyperhive_har_script_bridge import install_har_script_bridge
from tester_spin.providers.bgaming.hyperhive_wire import install_observed_wire_adapter
from tester_spin.providers.bgaming.hyperhive_transport import install_hyperhive_transport_adapter
from tester_spin.providers.bgaming.runner_diagnostics import diagnose_progress_event


install_observed_wire_adapter()
install_hyperhive_transport_adapter()
install_har_bridge()
install_har_script_bridge()


class BGamingProvider(_BGamingProvider):
    """BGaming provider with cheap-first execution and explicit complexity triage."""

    def har_artifact_dir(self, game: Game) -> Path | None:
        game_dir = self.game_dir(game)
        existing = select_best_har(game_dir)
        if existing is not None:
            return existing.parent
        analysis_dir = game_dir / "analysis"
        if analysis_dir.is_dir():
            return analysis_dir
        return None

    def test_game(
        self,
        game: Game,
        *,
        spins: int,
        timeout_s: float,
        stop_event: threading.Event,
        progress: Progress,
    ) -> GameTestResult:
        game_dir = self.game_dir(game)
        append_har_debug(
            game_dir,
            "runner_start",
            requested_spins=spins,
            timeout_s=timeout_s,
            game_url=game.url,
            symbol=game.symbol,
        )

        selected_har = select_best_har(game_dir)
        set_thread_har_path(selected_har)
        if selected_har is not None:
            quality = inspect_har(selected_har)
            append_har_debug(
                game_dir,
                "runner_har_context",
                path=str(selected_har),
                quality=(quality.grade if quality is not None else "UNKNOWN"),
                plays=(quality.plays if quality is not None else 0),
                purchases=(quality.purchases if quality is not None else 0),
            )

        def logged_progress(message: str) -> None:
            append_har_debug(game_dir, "runner_progress", message=str(message))
            progress(message)
            diagnostic = diagnose_progress_event(game_dir, message)
            if diagnostic is None:
                return
            diagnostic_message = str(diagnostic.get("message") or "").strip()
            append_har_debug(
                game_dir,
                "runner_error_context",
                **{key: value for key, value in diagnostic.items() if key != "message"},
            )
            if diagnostic_message:
                progress(f"[{game.name}] DIAGNÓSTICO: {diagnostic_message}")

        try:
            try:
                result = super().test_game(
                    game,
                    spins=spins,
                    timeout_s=timeout_s,
                    stop_event=stop_event,
                    progress=logged_progress,
                )
            except Exception as exc:
                append_har_debug(
                    game_dir,
                    "runner_exception",
                    error=f"{type(exc).__name__}: {exc}",
                )
                raise
        finally:
            clear_thread_har_path()

        complexity = persist_result_complexity(game_dir, result)
        classification = str(complexity.get("classification") or "INDETERMINADO")
        reasons = complexity.get("reasons") or []
        if complexity.get("requires_review"):
            reason_text = ", ".join(
                f"{row.get('kind')}={row.get('value')}"
                for row in reasons[:6]
                if isinstance(row, dict)
            )
            progress(
                f"[{game.name}] CLASIFICACIÓN: {classification}; "
                f"revisión manual recomendada"
                + (f"; {reason_text}" if reason_text else "")
                + "."
            )
        else:
            progress(f"[{game.name}] CLASIFICACIÓN: {classification}.")

        append_har_debug(
            game_dir,
            "runner_result",
            status=result.status,
            complexity=classification,
            requires_review=bool(complexity.get("requires_review")),
            reasons=reasons,
            requested_spins=result.requested_spins,
            successful_spins=result.successful_spins,
            failed_spins=result.failed_spins,
            elapsed_ms=result.elapsed_ms,
            error=result.error,
            run_dir=result.run_dir,
            discovered_modes=[
                {
                    "id": mode.get("id"),
                    "kind": mode.get("kind"),
                    "executable": mode.get("executable"),
                    "discovery_state": mode.get("discovery_state"),
                }
                for mode in result.discovered_modes[:50]
                if isinstance(mode, dict)
            ],
        )
        return result

    def prepare_test_artifacts(
        self,
        game: Game,
        *,
        timeout_s: float,
        stop_event: threading.Event,
        progress: Progress,
    ) -> None:
        """Cheap-first preparation.

        Normal catalogue tests must not open Chromium merely to discover whether a
        game is simple. Existing HAR evidence is reused when present; browser-based
        capture is deferred to explicit analysis/resolution of games classified as
        requiring review.
        """
        game_dir = self.game_dir(game)
        existing = select_best_har(game_dir)
        if existing is None:
            append_har_debug(game_dir, "prepare_cheap_first_no_har")
            progress(
                f"[{game.name}] preparación barata: sin HAR útil; Chromium diferido; "
                "no se recaptura Chromium en la prueba normal."
            )
            return

        quality = inspect_har(existing)
        try:
            relative = existing.relative_to(game_dir)
        except ValueError:
            relative = existing
        append_har_debug(
            game_dir,
            "prepare_cheap_first_reuse_har",
            path=str(relative),
            quality=(quality.grade if quality is not None else "UNKNOWN"),
            operations=(quality.operations if quality is not None else 0),
            plays=(quality.plays if quality is not None else 0),
            purchases=(quality.purchases if quality is not None else 0),
        )
        progress(
            f"[{game.name}] HAR existente reutilizado: {relative}; "
            f"calidad={quality.grade if quality is not None else 'UNKNOWN'}; "
            "Chromium diferido; no se sobrescribe ni se recaptura Chromium en la prueba normal."
        )


__all__ = ["BGamingProvider"]
